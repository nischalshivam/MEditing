from __future__ import annotations

import json,os
from pathlib import Path
from typing import Literal
from pydantic import BaseModel,ConfigDict

from .hashing import fingerprint,sha256_file
from .resolver_models import ResolverResult,SceneRetrievalRequest

PROMPT_VERSION='scene-verifier/1.0';MODEL='gemini-3.1-flash-lite'

class VerifierResponse(BaseModel):
    model_config=ConfigDict(extra='forbid')
    request_id:str
    decision:Literal['LITERAL_MATCH','CONTEXTUAL_MATCH','NONE_OF_THESE']
    candidate_scene_id:str|None
    evidence_shots:list[str]
    reasoning:str

def _prompt(req,candidates):
    return f'''Verify a local film-scene retrieval result using ONLY supplied candidates and evidence.
Request JSON: {json.dumps(req.model_dump(),ensure_ascii=False)}
Candidate JSON: {json.dumps(candidates,ensure_ascii=False)}
Attached images are candidate contact sheets in the same order; tiles contain authoritative shot IDs.
Choose LITERAL_MATCH only for directly evidenced requested visible action/event. CONTEXTUAL_MATCH is relevant context but not literal proof. Otherwise NONE_OF_THESE.
candidate_scene_id must be one supplied ID or null for NONE_OF_THESE. Evidence shots must be visible supplied shot IDs. Never output timestamps, another scene, or show-memory facts. Do not choose merely because candidates exist.'''

def verify_topk(conn,root:Path,req:SceneRetrievalRequest,local:ResolverResult,cost_ceiling:float=2.0)->dict:
    if not os.environ.get('GEMINI_API_KEY'):return {'status':'ABSTAIN','reason':'credential unavailable','used':False}
    candidates=[];parts=[];allowed_scenes=set();allowed_shots={}
    from google import genai
    from google.genai import types
    for c in local.candidates[:3]:
        allowed_scenes.add(c.scene_id);scene=conn.execute('select id from scenes where scene_uid=?',(c.scene_id,)).fetchone();shots={f'S{r[0]:04d}' for r in conn.execute('select s.ordinal from scene_shots ss join shots s on s.id=ss.shot_id where ss.scene_id=?',(scene[0],))};allowed_shots[c.scene_id]=shots
        image=root/'runtime/scene_atlas/inspection'/c.scene_id/'contact_sheet.jpg';parts.append(types.Part.from_bytes(data=image.read_bytes(),mime_type='image/jpeg'))
        candidates.append({'scene_id':c.scene_id,'atlas_status':c.atlas_status,'matched_fragments':c.matched_fragments,'matched_dialogue':c.matched_dialogue,'evidence_shots':c.evidence_shot_ids,'contact_sheet_sha256':sha256_file(image)})
    reqfp=fingerprint(json.dumps(req.model_dump(),sort_keys=True));fp=fingerprint(reqfp,json.dumps(candidates,sort_keys=True),MODEL,PROMPT_VERSION)
    cache=root/'runtime/resolver/verifier_cache'/f'{fp}.json';cache.parent.mkdir(parents=True,exist_ok=True)
    if cache.exists():
        env=json.loads(cache.read_text(encoding='utf8'));raw=env['response']
        if env.get('seal')!=fingerprint(json.dumps(raw,sort_keys=True),fp):raise ValueError('tampered verifier cache')
        parsed=VerifierResponse.model_validate(raw);return {'status':'SUCCESS','used':True,'cache_hit':True,'response':parsed.model_dump(),'usage':env['usage'],'estimated_cost_usd':env['estimated_cost_usd']}
    spent=conn.execute('select coalesce(sum(estimated_cost_usd),0) from resolver_verifier_runs').fetchone()[0]
    if spent>=cost_ceiling:return {'status':'ABSTAIN','reason':'cost ceiling reached','used':False}
    try:
        client=genai.Client(api_key=os.environ['GEMINI_API_KEY']);response=client.models.generate_content(model=MODEL,contents=[_prompt(req,candidates),*parts],config=types.GenerateContentConfig(temperature=.1,max_output_tokens=1200,response_mime_type='application/json',response_json_schema=VerifierResponse.model_json_schema()));raw=json.loads(response.text);parsed=VerifierResponse.model_validate(raw)
        if parsed.decision=='NONE_OF_THESE':
            if parsed.candidate_scene_id is not None or parsed.evidence_shots:raise ValueError('NONE must have null scene and no evidence shots')
        else:
            if parsed.candidate_scene_id not in allowed_scenes:raise ValueError('invented candidate scene')
            if any(x not in allowed_shots[parsed.candidate_scene_id] for x in parsed.evidence_shots):raise ValueError('invented or cross-scene evidence shot')
        u=response.usage_metadata;usage={'input_tokens':getattr(u,'prompt_token_count',None),'output_tokens':getattr(u,'candidates_token_count',None),'total_tokens':getattr(u,'total_token_count',None)};cost=(usage['input_tokens'] or 0)/1e6*.10+(usage['output_tokens'] or 0)/1e6*.40;out=parsed.model_dump();env={'response':out,'usage':usage,'estimated_cost_usd':cost};env['seal']=fingerprint(json.dumps(out,sort_keys=True),fp);tmp=cache.with_suffix('.building');tmp.write_text(json.dumps(env,indent=2),encoding='utf8');tmp.replace(cache)
        with conn:conn.execute('insert into resolver_verifier_runs(resolver_version,request_fingerprint,provider,model,prompt_version,input_fingerprint,output_fingerprint,decision,selected_scene_uid,cache_hit,input_tokens,output_tokens,total_tokens,estimated_cost_usd) values(?,?,?,?,?,?,?,?,?,0,?,?,?,?)',('scene-resolver/1.0',reqfp,'google-gemini',MODEL,PROMPT_VERSION,fp,fingerprint(json.dumps(out,sort_keys=True)),parsed.decision,parsed.candidate_scene_id,usage['input_tokens'],usage['output_tokens'],usage['total_tokens'],cost))
        return {'status':'SUCCESS','used':True,'cache_hit':False,'response':out,'usage':usage,'estimated_cost_usd':cost}
    except Exception as exc:
        with conn:conn.execute('insert or ignore into resolver_verifier_runs(resolver_version,request_fingerprint,provider,model,prompt_version,input_fingerprint,decision,cache_hit,sanitized_error) values(?,?,?,?,?,? ,"ABSTAIN",0,?)',('scene-resolver/1.0',reqfp,'google-gemini',MODEL,PROMPT_VERSION,fp,type(exc).__name__))
        return {'status':'ABSTAIN','reason':type(exc).__name__,'used':True,'cache_hit':False}

def apply_verifier(local:ResolverResult,verification:dict,req:SceneRetrievalRequest)->ResolverResult:
    if verification.get('status')!='SUCCESS':local.verifier=verification;return local
    v=verification['response'];local.verifier=verification
    if v['decision']=='LITERAL_MATCH':local.decision='VERIFIED';local.primary_scene=v['candidate_scene_id'];local.decision_reason='Gemini top-K verifier found literal support in supplied local evidence'
    elif v['decision']=='CONTEXTUAL_MATCH' and req.exactness_policy!='LITERAL':local.decision='CONTEXTUAL';local.primary_scene=v['candidate_scene_id'];local.decision_reason='Gemini top-K verifier found contextual support only'
    else:local.decision='ABSTAIN';local.primary_scene=None;local.decision_reason='Gemini top-K verifier returned NONE_OF_THESE or insufficient literal support'
    return local
