from __future__ import annotations

import json, subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .candidate_reel_v3 import build_reel
from .hashing import fingerprint, sha256_file
from .hierarchical_search_v8 import CONFIG as H8_CONFIG, VERSION as H8_VERSION, dense_candidates
from .moment_verifier_v2 import _run
from .shot_artifacts import preview
from .shot_models import ShotRange, ShotRequest, ShotResolution

VERSION='exact-temporal-tournament/9.0'
MODEL='gemini-3.1-flash-lite'
GROUP_PROMPT='exact-group-tournament/9.0'
FINAL_PROMPT='exact-final-tournament/9.0'
REFINE_PROMPT='frame-id-refinement/9.0'
CROP_PROMPT='independent-final-crop/9.0'
CONFIG={'group_size':6,'candidate_k':24,'frame_fps':8,'brief_shot_ms':3000,
        'handles_ms':{'default':[400,600],'reaction':[650,900],'brief_insert':[180,250]},
        'max_finalists':8,'fallback_finalists':3}

class CandidateAssessment(BaseModel):
    model_config=ConfigDict(extra='forbid')
    candidate_id:str
    classification:Literal['LITERAL_MATCH','PARTIAL_MATCH','NO_MATCH']
    supporting_shot_ids:list[str]=Field(default_factory=list)
    visible_evidence:str

class GroupDecision(BaseModel):
    model_config=ConfigDict(extra='forbid')
    request_id:str
    assessments:list[CandidateAssessment]
    finalists:list[str]=Field(default_factory=list)
    none_from_group:bool

class FinalDecision(BaseModel):
    model_config=ConfigDict(extra='forbid')
    request_id:str
    decision:Literal['WINNER','NONE_OF_THESE']
    candidate_id:str|None
    evidence_statement:str

class FrameDecision(BaseModel):
    model_config=ConfigDict(extra='forbid')
    request_id:str
    candidate_id:str
    decision:Literal['SUPPORTED_INTERVAL','PARTIAL','REJECTED']
    event_start_frame:str|None
    event_end_frame:str|None
    evidence_statement:str

class CropDecision(BaseModel):
    model_config=ConfigDict(extra='forbid')
    request_id:str
    decision:Literal['VERIFIED_EXACT','REVIEW_REQUIRED','REJECTED']
    literal_facts_supported:list[str]=Field(default_factory=list)
    missing_or_uncertain_facts:list[str]=Field(default_factory=list)
    evidence_statement:str

def freeze_sprint8(root:Path)->dict:
    evidence=root/'runtime/hierarchical_v8/development_final.json'
    payload={'version':H8_VERSION,'config':H8_CONFIG,'code_sha256':sha256_file(root/'src/scenebrain/hierarchical_search_v8.py'),
             'development_evidence_sha256':sha256_file(evidence),'frozen_for_sprint9':True}
    payload['fingerprint']=fingerprint(json.dumps(payload,sort_keys=True));out=root/'runtime/sprint9/frozen_sprint8.json';out.parent.mkdir(parents=True,exist_ok=True)
    if out.exists() and json.loads(out.read_text())!=payload:raise ValueError('Sprint 8 freeze conflict')
    out.write_text(json.dumps(payload,indent=2),encoding='utf8');return payload

def _allowed(candidate:ShotRange)->set[str]:
    return {f'S{x:04d}' for x in range(int(candidate.start_shot[1:]),int(candidate.end_shot[1:])+1)}

def _facts(req:ShotRequest)->dict:
    return {'query':req.scene_request.query_text,'required_event':req.scene_request.requested_event or req.scene_request.query_text,
            'visible_action':req.scene_request.visible_action,'required_characters':req.scene_request.characters_required,
            'objects':req.scene_request.objects,'negative_constraints':req.scene_request.negative_constraints,
            'reaction_subject':req.reaction_subject,'reaction_trigger':req.reaction_trigger,'reaction_relation':req.reaction_direction}

def _group_call(root:Path,req:ShotRequest,group:list[ShotRange],videos:list[dict],stage:str='GROUP'):
    reel=build_reel(root,videos,[x.candidate_id for x in group]);meta=[{'candidate_id':c.candidate_id,'scene_ids':c.scene_ids,'physical_shots':sorted(_allowed(c)),'nearby_dialogue':c.nearby_dialogue} for c in group]
    prompt=f'''Prompt {GROUP_PROMPT}. Judge ONLY literal visible motion in the supplied candidate reel. Request facts: {json.dumps(_facts(req))}. Candidates: {json.dumps(meta)}. Classify every supplied ID as LITERAL_MATCH, PARTIAL_MATCH, or NO_MATCH. Object/static before-or-after state is not the requested action. Select at most two literal finalists; if none, set none_from_group=true. Never output timestamps, invented IDs/shots, show memory, or an answer merely because one is expected.'''
    result=_run(root,stage,fingerprint(req.model_dump_json(),json.dumps(meta,sort_keys=True),reel['sha256']),prompt,GroupDecision,[reel['path']])
    if result.get('status')=='SUCCESS':
        raw=result['response'];ids={x.candidate_id for x in group};seen={x['candidate_id'] for x in raw['assessments']}
        if seen!=ids or any(x not in ids for x in raw['finalists']):return {'status':'ABSTAIN','reason':'candidate loss/invention'}
        for item in raw['assessments']:
            c=next(x for x in group if x.candidate_id==item['candidate_id'])
            if any(s not in _allowed(c) for s in item['supporting_shot_ids']):return {'status':'ABSTAIN','reason':'invented shot'}
        literal={x['candidate_id'] for x in raw['assessments'] if x['classification']=='LITERAL_MATCH'}
        if any(x not in literal for x in raw['finalists']) or raw['none_from_group'] != (not bool(literal)):return {'status':'ABSTAIN','reason':'inconsistent group decision'}
    result['reel']=reel;return result

def tournament(root:Path,req:ShotRequest,candidates:list[ShotRange],videos:list[dict]):
    if len(candidates)!=24 or len(videos)!=24:raise ValueError('Sprint 9 requires all 24 aligned candidates')
    slices=[(candidates[i:i+6],videos[i:i+6]) for i in range(0,24,CONFIG['group_size'])]
    # Independent fixed groups may execute concurrently; ordering and prompt
    # semantics remain frozen and results are restored to group order.
    with ThreadPoolExecutor(max_workers=4) as pool:
        groups=list(pool.map(lambda pair:_group_call(root,req,pair[0],pair[1]),slices))
    finalists=[]
    for call in groups:
        if call.get('status')=='SUCCESS':finalists.extend(call['response']['finalists'])
    finalists=list(dict.fromkeys(finalists))[:CONFIG['max_finalists']]
    if not finalists:return {'status':'SUCCESS','decision':'NONE_OF_THESE','groups':groups,'finalists':[]}
    selected=[next(c for c in candidates if c.candidate_id==x) for x in finalists];selected_v=[videos[candidates.index(x)] for x in selected]
    reel=build_reel(root,selected_v,finalists);meta=[{'candidate_id':c.candidate_id,'physical_shots':sorted(_allowed(c))} for c in selected]
    prompt=f'''Prompt {FINAL_PROMPT}. Compare only these group-finalist microvideos for literal satisfaction of request facts {json.dumps(_facts(req))}. Candidates: {json.dumps(meta)}. Return one supplied winner only when the requested action and required facts are visibly proven; otherwise NONE_OF_THESE. No timestamps, invented IDs/shots, or prior group reasoning.'''
    final=_run(root,'FINAL',fingerprint(req.model_dump_json(),json.dumps(meta,sort_keys=True),reel['sha256']),prompt,FinalDecision,[reel['path']])
    if final.get('status')=='SUCCESS':
        x=final['response'];cid=x['candidate_id']
        if (x['decision']=='NONE_OF_THESE' and cid is not None) or (x['decision']=='WINNER' and cid not in finalists):final={'status':'ABSTAIN','reason':'invented final candidate'}
    return {'status':final.get('status'),'groups':groups,'finalists':finalists,'final':final,'reel':reel}

def frame_manifest(conn,root:Path,c:ShotRange,fps:int|None=None)->dict:
    fps=fps or CONFIG['frame_fps'];source=conn.execute('select * from source_files where id=1').fetchone();fp=fingerprint(source['sha256'],c.start_ms,c.end_ms,fps,'frames/9.0');folder=root/'runtime/sprint9/frames'/fp;manifest=folder/'manifest.json'
    if manifest.exists():
        data=json.loads(manifest.read_text());
        if data['seal']!=fingerprint(json.dumps(data['frames'],sort_keys=True),fp):raise ValueError('tampered frame manifest')
        return {**data,'cache_hit':True,'manifest_path':str(manifest.resolve())}
    folder.mkdir(parents=True,exist_ok=True);pattern=folder/'raw_%04d.jpg';duration=c.end_ms-c.start_ms
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-ss',f'{c.start_ms/1000:.3f}','-i',source['path'],'-t',f'{duration/1000:.3f}','-vf',f'fps={fps},scale=480:-2','-q:v','3','-y',str(pattern)],check=True)
    files=sorted(folder.glob('raw_*.jpg'));frames=[]
    for i,p in enumerate(files):
        fid=f'F{i+1:04d}';target=folder/f'{fid}.jpg';p.replace(target);frames.append({'frame_id':fid,'source_ms':c.start_ms+round(i*1000/fps),'path':str(target.resolve()),'sha256':sha256_file(target)})
    if not frames:raise RuntimeError('no frames')
    data={'version':'frame-manifest/9.0','candidate_id':c.candidate_id,'source_sha256':source['sha256'],'fps':fps,'frames':frames,'fingerprint':fp};data['seal']=fingerprint(json.dumps(frames,sort_keys=True),fp);manifest.write_text(json.dumps(data,indent=2));return {**data,'cache_hit':False,'manifest_path':str(manifest.resolve())}

def refine(root:Path,req:ShotRequest,c:ShotRange,micro:dict,frames:dict):
    ids=[x['frame_id'] for x in frames['frames']];prompt=f'''Prompt {REFINE_PROMPT}. Inspect only this winning bounded microvideo. Request facts: {json.dumps(_facts(req))}. Candidate {c.candidate_id}. Authoritative ordered frame IDs: {ids}. Return first/last frame IDs enclosing the literal event. PARTIAL or REJECTED if exact action is not visible. Never return timestamps.'''
    out=_run(root,'REFINE9',fingerprint(req.model_dump_json(),c.model_dump_json(),micro['sha256'],frames['fingerprint']),prompt,FrameDecision,[micro['path']])
    if out.get('status')=='SUCCESS':
        x=out['response'];valid=set(ids)
        if x['candidate_id']!=c.candidate_id:return {'status':'ABSTAIN','reason':'invented candidate'}
        if x['decision']=='SUPPORTED_INTERVAL' and (x['event_start_frame'] not in valid or x['event_end_frame'] not in valid or ids.index(x['event_start_frame'])>ids.index(x['event_end_frame'])):return {'status':'ABSTAIN','reason':'invalid frame IDs'}
    return out

def make_crop(conn,root:Path,c:ShotRange,frames:dict,start_id:str,end_id:str,category:str)->dict:
    by={x['frame_id']:x for x in frames['frames']};a=by[start_id]['source_ms'];step=round(1000/frames['fps']);b=by[end_id]['source_ms']+step;kind='reaction' if category=='REACTION' else ('brief_insert' if c.end_ms-c.start_ms<CONFIG['brief_shot_ms'] else 'default');before,after=CONFIG['handles_ms'][kind];a=max(c.start_ms,a-before);b=min(c.end_ms,b+after);source=conn.execute('select * from source_files where id=1').fetchone()
    if not c.start_ms<=a<b<=c.end_ms:raise ValueError('crop out of bounds')
    fp=fingerprint(source['sha256'],a,b,kind,'crop/9.0');out=root/'runtime/sprint9/crops'/f'{fp}.mp4';out.parent.mkdir(parents=True,exist_ok=True)
    if not out.exists():
        tmp=out.with_suffix('.building.mp4');subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-ss',f'{a/1000:.3f}','-i',source['path'],'-t',f'{(b-a)/1000:.3f}','-vf','scale=720:-2','-an','-c:v','libx264','-crf','25','-movflags','+faststart','-y',str(tmp)],check=True);tmp.replace(out)
    return {'path':str(out.resolve()),'sha256':sha256_file(out),'start_ms':a,'end_ms':b,'handle_profile':kind}

def verify_crop(root:Path,req:ShotRequest,crop:dict):
    prompt=f'''Prompt {CROP_PROMPT}. Independently inspect ONLY this actual final crop. Request facts: {json.dumps(_facts(req))}. VERIFIED_EXACT requires literal visible support for every required fact and action. Plausible/incomplete => REVIEW_REQUIRED; wrong/absent => REJECTED. Do not use tournament reasoning, rankings, expected answers, timestamps, or show memory.'''
    return _run(root,'CROP9',fingerprint(req.model_dump_json(),crop['sha256']),prompt,CropDecision,[crop['path']])

def candidates_v9(conn,req:ShotRequest)->list[ShotRange]:
    candidates,_,_=dense_candidates(conn,req)
    if len(candidates)!=24:raise ValueError('frozen Sprint 8 did not produce 24 candidates')
    return candidates
