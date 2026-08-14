from __future__ import annotations

import json,os,time
from pathlib import Path
from typing import Literal
from pydantic import BaseModel,ConfigDict

from .hashing import fingerprint,sha256_file
from .shot_models import ShotRange,ShotRequest

MODEL='gemini-3.1-flash-lite';CANDIDATE_PROMPT='microvideo-candidate/2.0';REFINE_PROMPT='support-frame-refiner/2.0';CROP_PROMPT='final-microcrop/2.0'

class CandidateV2(BaseModel):
    model_config=ConfigDict(extra='forbid')
    request_id:str;decision:Literal['LITERAL_MATCH','PARTIAL_MATCH','NONE_OF_THESE'];candidate_id:str|None;supporting_shot_ids:list[str];evidence_statement:str
class RefineV2(BaseModel):
    model_config=ConfigDict(extra='forbid')
    request_id:str;candidate_id:str;decision:Literal['SUPPORTED_INTERVAL','PARTIAL','REJECTED'];first_frame_index:int|None;last_frame_index:int|None;evidence_statement:str
class CropV2(BaseModel):
    model_config=ConfigDict(extra='forbid')
    request_id:str;candidate_id:str;decision:Literal['VERIFIED_CROP','REVIEW_REQUIRED','REJECTED'];supporting_shot_ids:list[str];literal_action_visible:bool;temporal_relation_supported:bool;usability_flags:list[str];evidence_statement:str

def _upload_video(client,path:Path):
    f=client.files.upload(file=path)
    for _ in range(60):
        state=getattr(f,'state',None);name=getattr(state,'name',str(state))
        if name in {'ACTIVE','State.ACTIVE'}:return f
        if name in {'FAILED','State.FAILED'}:raise RuntimeError('video processing failed')
        time.sleep(1);f=client.files.get(name=f.name)
    raise TimeoutError('video processing timeout')

def _cached(root,fp,schema):
    p=root/'runtime/moment_v2/verifier_cache'/f'{fp}.json'
    if not p.exists():return None
    e=json.loads(p.read_text());raw=e['response']
    if e['seal']!=fingerprint(json.dumps(raw,sort_keys=True),fp):raise ValueError('tampered V2 cache')
    return {'status':'SUCCESS','cache_hit':True,'response':schema.model_validate(raw).model_dump(),'usage':e['usage'],'estimated_cost_usd':e['cost']}

def _run(root,stage,reqfp,prompt,schema,videos):
    if not os.environ.get('GEMINI_API_KEY'):return {'status':'ABSTAIN','reason':'credential unavailable'}
    hashes=[sha256_file(Path(x)) for x in videos];fp=fingerprint(stage,reqfp,MODEL,prompt,json.dumps(hashes),json.dumps(schema.model_json_schema(),sort_keys=True));hit=_cached(root,fp,schema)
    if hit:return hit
    from google import genai
    from google.genai import types
    client=genai.Client(api_key=os.environ['GEMINI_API_KEY']);uploaded=[]
    try:
        uploaded=[_upload_video(client,Path(x)) for x in videos]
        response=client.models.generate_content(model=MODEL,contents=[prompt,*uploaded],config=types.GenerateContentConfig(temperature=.1,max_output_tokens=1400,response_mime_type='application/json',response_json_schema=schema.model_json_schema()))
        parsed=schema.model_validate_json(response.text);u=response.usage_metadata;usage={'input_tokens':getattr(u,'prompt_token_count',0),'output_tokens':getattr(u,'candidates_token_count',0),'total_tokens':getattr(u,'total_token_count',0)};cost=(usage['input_tokens'] or 0)/1e6*.10+(usage['output_tokens'] or 0)/1e6*.40;raw=parsed.model_dump();p=root/'runtime/moment_v2/verifier_cache'/f'{fp}.json';p.parent.mkdir(parents=True,exist_ok=True);e={'response':raw,'usage':usage,'cost':cost,'seal':fingerprint(json.dumps(raw,sort_keys=True),fp)};tmp=p.with_suffix('.building');tmp.write_text(json.dumps(e,indent=2));tmp.replace(p);return {'status':'SUCCESS','cache_hit':False,'response':raw,'usage':usage,'estimated_cost_usd':cost}
    except Exception as exc:return {'status':'ABSTAIN','cache_hit':False,'reason':type(exc).__name__}
    finally:
        for f in uploaded:
            try:client.files.delete(name=f.name)
            except Exception:pass

def select_batch(root:Path,req:ShotRequest,candidates:list[ShotRange],videos:list[dict]):
    meta=[];allowed={}
    for c,v in zip(candidates,videos):
        ids=[f'S{x:04d}' for x in range(int(c.start_shot[1:]),int(c.end_shot[1:])+1)];allowed[c.candidate_id]=set(ids);meta.append({'candidate_id':c.candidate_id,'physical_shots':ids,'lane':c.provenance[0].get('lane'),'scene_ids':c.scene_ids})
    prompt=f'''Prompt version {CANDIDATE_PROMPT}. Use ONLY uploaded bounded local microvideos, in candidate metadata order. Request: {req.scene_request.model_dump_json()}. Candidate metadata: {json.dumps(meta)}. LITERAL_MATCH requires the requested action/event visibly happening in motion; object presence or before/after state is only PARTIAL_MATCH. Return a supplied candidate or NONE_OF_THESE. No timestamps, invented shots, other scenes, or show memory.''';out=_run(root,'CANDIDATE',fingerprint(req.model_dump_json(),json.dumps(meta,sort_keys=True)),prompt,CandidateV2,[v['path'] for v in videos])
    if out.get('status')=='SUCCESS':
        x=out['response'];cid=x['candidate_id']
        if x['decision']=='NONE_OF_THESE' and (cid is not None or x['supporting_shot_ids']):return {'status':'ABSTAIN','reason':'invalid NONE'}
        if x['decision']!='NONE_OF_THESE' and (cid not in allowed or any(s not in allowed[cid] for s in x['supporting_shot_ids'])):return {'status':'ABSTAIN','reason':'invented candidate/shot'}
    return out

def refine_frames(root,req,candidate,video,frame_count):
    prompt=f'''Prompt version {REFINE_PROMPT}. Inspect this bounded microvideo. Request: {req.scene_request.model_dump_json()}. Candidate: {candidate.candidate_id}. Frames are conceptually indexed 0..{frame_count-1} at uniform 5 FPS. If the literal action is visible, return first_frame_index and last_frame_index enclosing it. Otherwise PARTIAL or REJECTED. Do not return timestamps.''';out=_run(root,'REFINE',fingerprint(req.model_dump_json(),candidate.model_dump_json(),video['sha256'],frame_count),prompt,RefineV2,[video['path']])
    if out.get('status')=='SUCCESS':
        x=out['response']
        if x['candidate_id']!=candidate.candidate_id:return {'status':'ABSTAIN','reason':'invented candidate'}
        if x['decision']=='SUPPORTED_INTERVAL' and (x['first_frame_index'] is None or x['last_frame_index'] is None or not 0<=x['first_frame_index']<=x['last_frame_index']<frame_count):return {'status':'ABSTAIN','reason':'invalid frame interval'}
    return out

def verify_crop_v2(root,req,candidate,crop):
    ids=[f'S{x:04d}' for x in range(int(candidate.start_shot[1:]),int(candidate.end_shot[1:])+1)];prompt=f'''Prompt version {CROP_PROMPT}. Independently verify this actual final crop. Request: {req.scene_request.model_dump_json()}. Candidate {candidate.candidate_id}; allowed shots {ids}. VERIFIED_CROP only when literal motion, temporal relation, and usable context are present. Plausible but not proven => REVIEW_REQUIRED. Wrong/absent => REJECTED. No timestamps or substitutions.''';out=_run(root,'CROP',fingerprint(req.model_dump_json(),candidate.model_dump_json(),crop['sha256']),prompt,CropV2,[crop['path']])
    if out.get('status')=='SUCCESS':
        x=out['response']
        if x['candidate_id']!=candidate.candidate_id or any(s not in ids for s in x['supporting_shot_ids']):return {'status':'ABSTAIN','reason':'invented crop evidence'}
    return out
