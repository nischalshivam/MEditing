from __future__ import annotations
import json,time
from pathlib import Path
from .db import connect
from .exact_tournament_v9 import candidates_v9
from .hashing import sha256_file
from .independent_verifier_v9b import facts,verify_all
from .resolver import resolve_local
from .resolver_models import SceneRetrievalRequest
from .shot_artifacts import preview
from .shot_models import ShotRequest

def overlap(c,intervals):return any(c.start_ms<x['end_ms'] and c.end_ms>x['start_ms'] for x in intervals)
def run(root:Path,model:str):
 rows=[json.loads(x) for x in (root/'benchmark/sprint9/SPRINT9_EXACT_DEV_V2.jsonl').read_text().splitlines()];conn=connect(root/'runtime/scene_brain.db');results=[];t=time.time()
 for n,row in enumerate(rows,1):
  q=SceneRetrievalRequest(request_id=row['request_id'],query_text=row['query'],evidence_class=row['evidence_class']);s=resolve_local(conn,q,top_k=3);req=ShotRequest(scene_request=q,sprint3_result=s);cs=candidates_v9(conn,req);videos=[preview(conn,root,c,width=480) for c in cs];judgments=verify_all(root,req,cs,videos,facts(row),model);oracle=[overlap(c,row['acceptable_source_intervals']) if row['expected']=='EXACT' else False for c in cs];pred=[j.get('status')=='SUCCESS' and j['response']['classification']=='LITERAL_MATCH' for j in judgments];results.append({'request_id':row['request_id'],'category':row['category'],'expected':row['expected'],'oracle':oracle,'predicted_literal':pred,'judgments':judgments,'candidate_ranges':[c.model_dump() for c in cs]});print(model,n,row['request_id'],sum(pred),flush=True)
 pos=[x for x in results if x['expected']=='EXACT'];tp=sum(p and o for x in results for p,o in zip(x['predicted_literal'],x['oracle']));fp=sum(p and not o for x in results for p,o in zip(x['predicted_literal'],x['oracle']));fn=sum(not p and o for x in results for p,o in zip(x['predicted_literal'],x['oracle']));allcalls=[j for x in results for j in x['judgments']];metrics={'requests':len(rows),'literal_candidate_recall':sum(any(p and o for p,o in zip(x['predicted_literal'],x['oracle'])) for x in pos)/len(pos),'literal_classification_precision':tp/max(1,tp+fp),'false_negative_rate':fn/max(1,tp+fn),'false_positive_rate':fp/max(1,tp+fp),'tp':tp,'fp':fp,'fn':fn,'calls':len(allcalls),'cache_hits':sum(bool(x.get('cache_hit')) for x in allcalls),'input_tokens':sum((x.get('usage') or {}).get('input_tokens') or 0 for x in allcalls),'output_tokens':sum((x.get('usage') or {}).get('output_tokens') or 0 for x in allcalls),'cost_usd':sum(x.get('estimated_cost_usd') or 0 for x in allcalls),'latency_seconds':time.time()-t}
 out={'version':'sprint9b-eval/1.0','model':model,'dataset_sha256':sha256_file(root/'benchmark/sprint9/SPRINT9_EXACT_DEV_V2.jsonl'),'metrics':metrics,'results':results};p=root/'runtime/sprint9b'/f'{model}_dev_v2.json';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(out,indent=2));print(json.dumps(metrics,indent=2));return out
