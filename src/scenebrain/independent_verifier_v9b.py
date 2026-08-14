from __future__ import annotations

import json,os,time
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
from typing import Literal

from pydantic import BaseModel,ConfigDict,Field

from .hashing import fingerprint,sha256_file
from .shot_models import ShotRange,ShotRequest

VERSION='independent-candidate-verifier/9b.0'
PROMPT='independent-literal-candidate/9b.0'
MODELS={'gemini-3.1-flash-lite':{'temperature':.1,'max_output_tokens':900,'thinking_budget':None},'gemini-2.5-flash':{'temperature':.1,'max_output_tokens':4096,'thinking_budget':512},'gemini-3.6-flash':{'temperature':.1,'max_output_tokens':1800,'thinking_budget':512}}

class VisibleFacts(BaseModel):
    model_config=ConfigDict(extra='forbid')
    request_id:str;query:str;required_visible_facts:list[str];not_sufficient:list[str];category:str
class IndependentDecision(BaseModel):
    model_config=ConfigDict(extra='forbid')
    request_id:str;candidate_id:str;classification:Literal['LITERAL_MATCH','PARTIAL_MATCH','NO_MATCH'];visible_facts_supported:list[str]=Field(default_factory=list);visible_facts_missing:list[str]=Field(default_factory=list);evidence_frame_ids:list[str]=Field(default_factory=list);evidence_shot_ids:list[str]=Field(default_factory=list);evidence_statement:str

def facts(row:dict)->VisibleFacts:
    query=row['query'];required=list(row.get('required_visual_facts') or [query]);lower=query.lower();insufficient=['static presence without the requested action']
    if any(x in lower for x in ('enter','leave','walk','approach','arrive')):insufficient.append('person merely standing at destination without visible movement/transition')
    if any(x in lower for x in ('eat','hand','put','pick','pour','cut','mop','hold')):insufficient.append('object merely visible without the requested interaction')
    if 'react' in lower:insufficient.append('trigger visible without requested reaction subject visibly reacting')
    return VisibleFacts(request_id=row['request_id'],query=query,required_visible_facts=required,not_sufficient=insufficient,category=row['category'])

def _upload(client,path):
    f=client.files.upload(file=path)
    for _ in range(40):
        state=getattr(f.state,'name',str(f.state))
        if state=='ACTIVE':return f
        if state=='FAILED':raise RuntimeError('file processing failed')
        time.sleep(.5);f=client.files.get(name=f.name)
    raise TimeoutError('file processing timeout')

def verify_one(root:Path,req:ShotRequest,c:ShotRange,video:dict,visible:VisibleFacts,model:str):
    if model not in MODELS:raise ValueError('unversioned model config')
    allowed=[f'S{x:04d}' for x in range(int(c.start_shot[1:]),int(c.end_shot[1:])+1)];vf=video['sha256'];schema=IndependentDecision;fp=fingerprint(VERSION,model,PROMPT,req.model_dump_json(),c.model_dump_json(),visible.model_dump_json(),vf,json.dumps(MODELS[model],sort_keys=True),json.dumps(schema.model_json_schema(),sort_keys=True));cache=root/'runtime/sprint9b/cache'/model/f'{fp}.json';cache.parent.mkdir(parents=True,exist_ok=True)
    if cache.exists():
        env=json.loads(cache.read_text());raw=env['response']
        if env['seal']!=fingerprint(json.dumps(raw,sort_keys=True),fp):raise ValueError('tampered independent cache')
        return {**env,'cache_hit':True}
    if not os.environ.get('GEMINI_API_KEY'):return {'status':'ABSTAIN','reason':'credential unavailable','cache_hit':False}
    from google import genai
    from google.genai import types
    client=genai.Client(api_key=os.environ['GEMINI_API_KEY']);uploaded=None
    try:
        uploaded=_upload(client,Path(video['path']));prompt=f'''Prompt {PROMPT}. Independently judge ONLY this one bounded candidate microvideo. You cannot see other candidates, rank, expected answer, or ground truth. Visible-fact contract: {visible.model_dump_json()}. Candidate ID: {c.candidate_id}. Allowed physical shot IDs: {allowed}. LITERAL_MATCH only if the video itself visibly proves every required fact and the requested temporal action. PARTIAL_MATCH for plausible/static/before-after evidence. Otherwise NO_MATCH. Evidence frame IDs may be empty because the video is authoritative; never invent frame IDs, timestamps, candidate IDs, or shot IDs.'''
        cfg=MODELS[model];kwargs={'temperature':cfg['temperature'],'max_output_tokens':cfg['max_output_tokens'],'response_mime_type':'application/json','response_json_schema':schema.model_json_schema()}
        if cfg['thinking_budget'] is not None:kwargs['thinking_config']=types.ThinkingConfig(thinking_budget=cfg['thinking_budget'])
        response=client.models.generate_content(model=model,contents=[prompt,uploaded],config=types.GenerateContentConfig(**kwargs));parsed=schema.model_validate_json(response.text)
        if parsed.request_id!=visible.request_id or parsed.candidate_id!=c.candidate_id or any(x not in allowed for x in parsed.evidence_shot_ids):raise ValueError('invented id/shot')
        u=response.usage_metadata;usage={'input_tokens':getattr(u,'prompt_token_count',0),'output_tokens':getattr(u,'candidates_token_count',0),'total_tokens':getattr(u,'total_token_count',0)};cost=usage['input_tokens']/1e6*.10+usage['output_tokens']/1e6*.40;raw=parsed.model_dump();env={'status':'SUCCESS','response':raw,'usage':usage,'estimated_cost_usd':cost,'seal':fingerprint(json.dumps(raw,sort_keys=True),fp)};tmp=cache.with_suffix('.building');tmp.write_text(json.dumps(env,indent=2));tmp.replace(cache);return {**env,'cache_hit':False}
    except Exception as exc:return {'status':'ABSTAIN','reason':type(exc).__name__,'cache_hit':False}
    finally:
        if uploaded:
            try:client.files.delete(name=uploaded.name)
            except Exception:pass

def verify_all(root,req,candidates,videos,visible,model,workers=8):
    out=[None]*len(candidates)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures={pool.submit(verify_one,root,req,c,v,visible,model):i for i,(c,v) in enumerate(zip(candidates,videos))}
        for f in as_completed(futures):out[futures[f]]=f.result()
    return out
