from __future__ import annotations

import json,time
from collections import defaultdict
from pathlib import Path

from .db import connect
from .exact_tournament_v9 import CONFIG,VERSION,candidates_v9,frame_manifest,make_crop,refine,tournament,verify_crop
from .hashing import fingerprint,sha256_file
from .resolver import resolve_local
from .resolver_models import SceneRetrievalRequest
from .shot_artifacts import preview
from .shot_models import ShotRequest

def _overlap(a,b):return a[0]<b[1] and a[1]>b[0]
def _usage(obj):
    calls=[]
    def walk(x):
        if isinstance(x,dict):
            if 'usage' in x and isinstance(x['usage'],dict):calls.append(x)
            for v in x.values():walk(v)
        elif isinstance(x,list):
            for v in x:walk(v)
    walk(obj);unique=[];seen=set()
    for x in calls:
        marker=json.dumps(x.get('usage'),sort_keys=True)+str(x.get('cache_hit'))+str(x.get('estimated_cost_usd'))
        if marker not in seen:seen.add(marker);unique.append(x)
    return {'calls':len(unique),'cache_hits':sum(bool(x.get('cache_hit')) for x in unique),'input_tokens':sum((x.get('usage') or {}).get('input_tokens') or 0 for x in unique),'output_tokens':sum((x.get('usage') or {}).get('output_tokens') or 0 for x in unique),'total_tokens':sum((x.get('usage') or {}).get('total_tokens') or 0 for x in unique),'cost_usd':sum(x.get('estimated_cost_usd') or 0 for x in unique)}

def run(root:Path,dataset:Path,label='dev'):
    conn=connect(root/'runtime/scene_brain.db');rows=[json.loads(x) for x in dataset.read_text(encoding='utf8').splitlines() if x.strip()];results=[];started=time.time();inspection=root/'runtime/sprint9/inspection'/label;inspection.mkdir(parents=True,exist_ok=True)
    for n,row in enumerate(rows,1):
        q=SceneRetrievalRequest(request_id=row['request_id'],query_text=row['query'],evidence_class=row['evidence_class'],none_allowed=True)
        s3=resolve_local(conn,q,top_k=3);req=ShotRequest(scene_request=q,sprint3_result=s3);candidates=candidates_v9(conn,req);videos=[preview(conn,root,c,width=480) for c in candidates]
        gt=[(x['start_ms'],x['end_ms']) for x in row['acceptable_source_intervals']];hits=[any(_overlap((c.start_ms,c.end_ms),g) for g in gt) for c in candidates]
        tour=tournament(root,req,candidates,videos);selected=None;crop=None;ref=None;cv=None;decision='ABSTAIN';reason='no tournament winner'
        if tour.get('status')=='SUCCESS' and tour.get('final',{}).get('status')=='SUCCESS' and tour['final']['response']['decision']=='WINNER':
            cid=tour['final']['response']['candidate_id'];selected=next(c for c in candidates if c.candidate_id==cid);micro=videos[candidates.index(selected)];frames=frame_manifest(conn,root,selected);ref=refine(root,req,selected,micro,frames)
            if ref.get('status')=='SUCCESS' and ref['response']['decision']=='SUPPORTED_INTERVAL':
                crop=make_crop(conn,root,selected,frames,ref['response']['event_start_frame'],ref['response']['event_end_frame'],row['category']);cv=verify_crop(root,req,crop)
                if cv.get('status')=='SUCCESS':decision={'VERIFIED_EXACT':'VERIFIED_EXACT','REVIEW_REQUIRED':'REVIEW_REQUIRED','REJECTED':'ABSTAIN'}[cv['response']['decision']];reason=cv['response']['evidence_statement']
            elif ref.get('status')=='SUCCESS' and ref['response']['decision']=='PARTIAL':decision='REVIEW_REQUIRED';reason=ref['response']['evidence_statement']
        selected_correct=bool(selected and any(_overlap((selected.start_ms,selected.end_ms),g) for g in gt));crop_correct=bool(crop and any(_overlap((crop['start_ms'],crop['end_ms']),g) for g in gt));expected=row['expected'];auto_correct=(decision=='VERIFIED_EXACT' and expected=='EXACT' and crop_correct)
        record={'request_id':row['request_id'],'query':row['query'],'category':row['category'],'expected':expected,'candidate_rank':next((i+1 for i,x in enumerate(hits) if x),0),'decision':decision,'selected_candidate_id':selected.candidate_id if selected else None,'selected_range_ms':[selected.start_ms,selected.end_ms] if selected else None,'selected_correct':selected_correct,'crop':crop,'crop_correct':crop_correct,'auto_correct':auto_correct,'reason':reason,'tournament':tour,'refinement':ref,'crop_verifier':cv}
        (inspection/f"{row['request_id']}.json").write_text(json.dumps(record,indent=2),encoding='utf8');results.append(record);print(f"[{n}/{len(rows)}] {row['request_id']} {decision}",flush=True)
    positives=[x for x in results if x['expected']=='EXACT'];verified=[x for x in results if x['decision']=='VERIFIED_EXACT'];none=[x for x in results if x['expected']=='NONE'];usage=_usage(results)
    metrics={'rows':len(results),'positives':len(positives),'none':len(none),'candidate_recall':{str(k):sum(0<x['candidate_rank']<=k for x in positives)/max(1,len(positives)) for k in [5,10,20,24]},'tournament_exact_selection_accuracy':sum(x['selected_correct'] for x in positives)/max(1,len(positives)),'verified_exact_precision':sum(x['auto_correct'] for x in verified)/max(1,len(verified)),'verified_exact_coverage':len(verified)/max(1,len(positives)),'wrong_auto_accept_rate':sum(not x['auto_correct'] for x in verified)/max(1,len(verified)),'review_required_rate':sum(x['decision']=='REVIEW_REQUIRED' for x in results)/len(results),'abstain_rate':sum(x['decision']=='ABSTAIN' for x in results)/len(results),'none_correct':sum(x['decision']=='ABSTAIN' for x in none),'none_count':len(none),'correct_candidate_wrong_crop':sum(x['selected_correct'] and x['crop'] and not x['crop_correct'] for x in results),'runtime_seconds':time.time()-started,**usage}
    by={}
    for cat in sorted({x['category'] for x in results}):
        xs=[x for x in results if x['category']==cat];v=[x for x in xs if x['decision']=='VERIFIED_EXACT'];by[cat]={'n':len(xs),'verified':len(v),'correct_verified':sum(x['auto_correct'] for x in v),'abstain':sum(x['decision']=='ABSTAIN' for x in xs),'review':sum(x['decision']=='REVIEW_REQUIRED' for x in xs)}
    payload={'version':VERSION,'config':CONFIG,'dataset':str(dataset.resolve()),'dataset_sha256':sha256_file(dataset),'evaluation_fingerprint':fingerprint(VERSION,sha256_file(dataset),json.dumps(CONFIG,sort_keys=True)),'metrics':metrics,'by_category':by,'results':results};out=root/'runtime/sprint9'/f'{label}_live_evaluation.json';out.write_text(json.dumps(payload,indent=2),encoding='utf8');print(json.dumps(metrics,indent=2));return payload

