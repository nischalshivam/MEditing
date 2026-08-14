from __future__ import annotations

import json,os
from pathlib import Path
from typing import Literal
from pydantic import BaseModel,ConfigDict

from .hashing import fingerprint,sha256_file
from .shot_models import ShotRange,ShotRequest

MODEL='gemini-3.1-flash-lite';CANDIDATE_PROMPT='shot-candidate-verifier/1.0';CROP_PROMPT='final-crop-verifier/1.0'

class CandidateVerdict(BaseModel):
    model_config=ConfigDict(extra='forbid')
    request_id:str
    decision:Literal['LITERAL_MATCH','PARTIAL_MATCH','NONE_OF_THESE']
    candidate_id:str|None
    supporting_shot_ids:list[str]
    evidence_statement:str

class CropVerdict(BaseModel):
    model_config=ConfigDict(extra='forbid')
    request_id:str
    candidate_id:str
    decision:Literal['VERIFIED_CROP','REVIEW_REQUIRED','REJECTED']
    supporting_shot_ids:list[str]
    literal_action_visible:bool
    correct_object:bool|None
    required_character_visible:bool|None
    temporal_relation_supported:bool
    usability_flags:list[Literal['TOO_SHORT','TOO_LONG','STARTS_MID_MOTION','ENDS_BEFORE_REACTION','DISTRACTING_TRANSITION','BETTER_NEIGHBOR_AVAILABLE','USABLE']]
    evidence_statement:str

def _call(conn,root:Path,stage:str,reqfp:str,prompt_version:str,schema,parts:list,allowed_cost:float=3.0):
    if not os.environ.get('GEMINI_API_KEY'):return {'status':'ABSTAIN','reason':'credential unavailable','used':False}
    from google import genai
    from google.genai import types
    hashes=[fingerprint(x.text) if getattr(x,'text',None) else fingerprint(getattr(x,'inline_data',None).data if getattr(x,'inline_data',None) else str(x)) for x in parts]
    fp=fingerprint(stage,reqfp,MODEL,prompt_version,json.dumps(hashes),json.dumps(schema.model_json_schema(),sort_keys=True))
    cache=root/'runtime/shot_resolver/verifier_cache'/f'{fp}.json';cache.parent.mkdir(parents=True,exist_ok=True)
    if cache.exists():
        env=json.loads(cache.read_text(encoding='utf8'));raw=env['response']
        if env.get('seal')!=fingerprint(json.dumps(raw,sort_keys=True),fp):raise ValueError('tampered shot verifier cache')
        parsed=schema.model_validate(raw);return {'status':'SUCCESS','used':True,'cache_hit':True,'response':parsed.model_dump(),'usage':env['usage'],'estimated_cost_usd':env['cost']}
    spent=conn.execute('select coalesce(sum(estimated_cost_usd),0) from shot_verifier_runs').fetchone()[0]
    if spent>=allowed_cost:return {'status':'ABSTAIN','reason':'cost ceiling reached','used':False}
    try:
        client=genai.Client(api_key=os.environ['GEMINI_API_KEY'])
        response=client.models.generate_content(model=MODEL,contents=parts,config=types.GenerateContentConfig(temperature=.1,max_output_tokens=1400,response_mime_type='application/json',response_json_schema=schema.model_json_schema()))
        parsed=schema.model_validate_json(response.text);u=response.usage_metadata;usage={'input_tokens':getattr(u,'prompt_token_count',0),'output_tokens':getattr(u,'candidates_token_count',0),'total_tokens':getattr(u,'total_token_count',0)};cost=(usage['input_tokens'] or 0)/1e6*.10+(usage['output_tokens'] or 0)/1e6*.40
        raw=parsed.model_dump();env={'response':raw,'usage':usage,'cost':cost,'seal':fingerprint(json.dumps(raw,sort_keys=True),fp)};tmp=cache.with_suffix('.building');tmp.write_text(json.dumps(env,indent=2),encoding='utf8');tmp.replace(cache)
        with conn:conn.execute('insert into shot_verifier_runs(stage,request_fingerprint,provider,model,prompt_version,input_fingerprint,output_fingerprint,decision,cache_hit,input_tokens,output_tokens,total_tokens,estimated_cost_usd) values(?,?,?,?,?,?,?,?,0,?,?,?,?)',(stage,reqfp,'google-gemini',MODEL,prompt_version,fp,fingerprint(json.dumps(raw,sort_keys=True)),raw['decision'],usage['input_tokens'],usage['output_tokens'],usage['total_tokens'],cost))
        return {'status':'SUCCESS','used':True,'cache_hit':False,'response':raw,'usage':usage,'estimated_cost_usd':cost}
    except Exception as exc:
        with conn:conn.execute('insert or ignore into shot_verifier_runs(stage,request_fingerprint,provider,model,prompt_version,input_fingerprint,decision,cache_hit,sanitized_error) values(?,?,?,?,?,? ,"ABSTAIN",0,?)',(stage,reqfp,'google-gemini',MODEL,prompt_version,fp,type(exc).__name__))
        return {'status':'ABSTAIN','used':True,'cache_hit':False,'reason':type(exc).__name__}

def verify_candidates(conn,root:Path,req:ShotRequest,candidates:list[ShotRange],artifacts:list[dict])->dict:
    from google.genai import types
    meta=[];parts=[];allowed={}
    for c,a in zip(candidates,artifacts):
        ids=[f'S{x:04d}' for x in range(int(c.start_shot[1:]),int(c.end_shot[1:])+1)];allowed[c.candidate_id]=set(ids)
        meta.append({'candidate_id':c.candidate_id,'physical_shots':ids,'scene_ids':c.scene_ids,'provenance':c.provenance,'nearby_dialogue':c.nearby_dialogue,'boundary_sensitive':c.boundary_sensitive})
        # Dense sequential frames are the temporal evidence transport. The cached MP4 remains
        # the human-review artifact; avoiding inline video keeps requests within API limits.
        parts.append(types.Part.from_bytes(data=Path(a['sheet']['path']).read_bytes(),mime_type='image/jpeg'))
    prompt=f'''Use only supplied local candidate videos/labelled dense frames. Request: {req.scene_request.model_dump_json()} Candidates: {json.dumps(meta)}. Determine whether the requested visible action/event literally occurs, not merely the object or before/after state. Return only a supplied candidate_id and its physical shot IDs, or NONE_OF_THESE. PARTIAL_MATCH never proves exactness. Never output timestamps or use show memory.'''
    reqfp=fingerprint(req.model_dump_json(),json.dumps(meta,sort_keys=True));out=_call(conn,root,'CANDIDATE',reqfp,CANDIDATE_PROMPT,CandidateVerdict,[types.Part.from_text(text=prompt),*parts])
    if out.get('status')=='SUCCESS':
        v=out['response'];cid=v['candidate_id']
        if v['decision']=='NONE_OF_THESE':
            if cid is not None or v['supporting_shot_ids']:return {'status':'ABSTAIN','used':True,'cache_hit':out.get('cache_hit',False),'reason':'invalid NONE evidence'}
        elif cid not in allowed or any(x not in allowed[cid] for x in v['supporting_shot_ids']):return {'status':'ABSTAIN','used':True,'cache_hit':out.get('cache_hit',False),'reason':'invented candidate/shot'}
    return out

def verify_crop(conn,root:Path,req:ShotRequest,candidate:ShotRange,crop:dict,dense:dict)->dict:
    from google.genai import types
    ids=[f'S{x:04d}' for x in range(int(candidate.start_shot[1:]),int(candidate.end_shot[1:])+1)]
    prompt=f'''Independently verify this ACTUAL proposed crop using local visual evidence only. Request: {req.scene_request.model_dump_json()}. Candidate ID: {candidate.candidate_id}. Authoritative shot IDs: {ids}. Check literal requested action (not object presence), temporal relation, and editorial usability. Character face/identity visibility is mandatory ONLY for names explicitly listed in characters_required or reaction_subject; a named actor in natural query wording may be supported by the surrounding supplied candidate provenance even if an insert shows only their hand. For exact dialogue, verify supplied occurrence and requested speaker/reaction requirement. VERIFIED_CROP only if literal and usable. Never output timestamps or substitute another candidate.'''
    reqfp=fingerprint(req.model_dump_json(),candidate.model_dump_json(),crop['sha256'],dense['sha256']);out=_call(conn,root,'FINAL_CROP',reqfp,CROP_PROMPT,CropVerdict,[types.Part.from_text(text=prompt),types.Part.from_bytes(data=Path(dense['path']).read_bytes(),mime_type='image/jpeg')])
    if out.get('status')=='SUCCESS':
        v=out['response']
        if v['candidate_id']!=candidate.candidate_id or any(x not in ids for x in v['supporting_shot_ids']):return {'status':'ABSTAIN','used':True,'cache_hit':out.get('cache_hit',False),'reason':'invented crop candidate/shot'}
    return out
