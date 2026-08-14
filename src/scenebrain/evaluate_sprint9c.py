from __future__ import annotations
import json,time
from collections import Counter,defaultdict
from pathlib import Path
from .db import connect
from .exact_tournament_v9 import candidates_v9
from .frame_verifier_v9c import OracleLabel,extract_frames,verify
from .hashing import fingerprint,sha256_file
from .independent_verifier_v9b import facts
from .resolver import resolve_local
from .resolver_models import SceneRetrievalRequest
from .shot_artifacts import preview
from .shot_models import ShotRequest

def validate_and_freeze(root:Path):
 p=root/'runtime/sprint9c/SPRINT9C_HUMAN_ORACLE.jsonl';manifest=json.loads((root/'runtime/sprint9c/oracle_manifest.json').read_text());rows=[OracleLabel.model_validate_json(x) for x in p.read_text().splitlines() if x.strip()];expected={(x['request_id'],x['candidate_id']):(x['source_fingerprint'],x['candidate_fingerprint']) for x in manifest['items']};seen=set();errors=[]
 for x in rows:
  key=(x.request_id,x.candidate_id)
  if key in seen:errors.append(f'duplicate {key}')
  seen.add(key)
  if key not in expected:errors.append(f'unknown {key}')
  elif expected[key]!=(x.source_fingerprint,x.candidate_fingerprint):errors.append(f'fingerprint mismatch {key}')
 if len(rows)!=192 or seen!=set(expected):errors.append(f'coverage mismatch rows={len(rows)} unique={len(seen)} expected=192')
 if errors:raise ValueError('\n'.join(errors))
 payload={'version':'human-candidate-oracle/1.0','rows':192,'requests':len({x.request_id for x in rows}),'labels':dict(Counter(x.human_label for x in rows)),'oracle_sha256':sha256_file(p),'manifest_sha256':sha256_file(root/'runtime/sprint9c/oracle_manifest.json'),'fingerprint':fingerprint(p.read_bytes(),(root/'runtime/sprint9c/oracle_manifest.json').read_bytes())};out=root/'runtime/sprint9c/HUMAN_ORACLE_RECEIPT.json';out.write_text(json.dumps(payload,indent=2));return payload,rows

def metrics(records,oracle):
 cm={a:{b:0 for b in ('LITERAL_MATCH','PARTIAL_MATCH','NO_MATCH','ERROR')} for a in ('LITERAL','PARTIAL','NO_MATCH')};cats=defaultdict(list)
 for rec in records:
  truth=oracle[(rec['request_id'],rec['candidate_id'])];pred=rec['prediction'];cm[truth][pred]+=1;cats[rec['category']].append((truth,pred))
 tp=cm['LITERAL']['LITERAL_MATCH'];fn=cm['LITERAL']['PARTIAL_MATCH']+cm['LITERAL']['NO_MATCH']+cm['LITERAL']['ERROR'];fp=cm['PARTIAL']['LITERAL_MATCH']+cm['NO_MATCH']['LITERAL_MATCH'];precision=tp/max(1,tp+fp);recall=tp/max(1,tp+fn);f1=2*precision*recall/max(1e-12,precision+recall)
 def one(xs):
  t=sum(a=='LITERAL' and b=='LITERAL_MATCH' for a,b in xs);fnp=sum(a=='LITERAL' and b!='LITERAL_MATCH' for a,b in xs);fpp=sum(a!='LITERAL' and b=='LITERAL_MATCH' for a,b in xs);p=t/max(1,t+fpp);r=t/max(1,t+fnp);return {'n':len(xs),'literal':sum(a=='LITERAL' for a,b in xs),'recall':r,'precision':p,'f1':2*p*r/max(1e-12,p+r),'fp':fpp,'fn':fnp}
 return {'literal_recall':recall,'literal_precision':precision,'literal_f1':f1,'false_positives':fp,'false_negatives':fn,'confusion_matrix':cm,'by_category':{k:one(v) for k,v in cats.items()}}

def old_records(root,labels):
 p=json.loads((root/'runtime/sprint9b/gemini-3.1-flash-lite_dev_v2.json').read_text());wanted={x.request_id for x in labels};out=[]
 for request in p['results']:
  if request['request_id'] not in wanted:continue
  for c,j in zip(request['candidate_ranges'],request['judgments']):out.append({'request_id':request['request_id'],'candidate_id':c['candidate_id'],'category':request['category'],'prediction':j['response']['classification'] if j.get('status')=='SUCCESS' else 'ERROR','cache_hit':j.get('cache_hit',False)})
 return out

def frame_run(root,labels):
 rows={x['request_id']:x for x in map(json.loads,(root/'benchmark/sprint9/SPRINT9_EXACT_DEV_V2.jsonl').read_text().splitlines())};wanted={x.request_id for x in labels};conn=connect(root/'runtime/scene_brain.db');records=[];calls=[];started=time.time()
 for rid in sorted(wanted):
  row=rows[rid];q=SceneRetrievalRequest(request_id=rid,query_text=row['query'],evidence_class=row['evidence_class']);req=ShotRequest(scene_request=q,sprint3_result=resolve_local(conn,q,top_k=3));cs=candidates_v9(conn,req);visible=facts(row)
  for c in cs:
   manifest=extract_frames(conn,root,c);result=verify(root,visible,c,manifest);calls.append(result);records.append({'request_id':rid,'candidate_id':c.candidate_id,'category':row['category'],'prediction':result['response']['classification'] if result.get('status')=='SUCCESS' else 'ERROR','cache_hit':result.get('cache_hit',False)});print(rid,c.candidate_id,records[-1]['prediction'],flush=True)
 usage={'attempted':len(calls),'successful':sum(x.get('status')=='SUCCESS' for x in calls),'errors':sum(x.get('status')!='SUCCESS' for x in calls),'cache_hits':sum(bool(x.get('cache_hit')) for x in calls),'input_tokens':sum((x.get('usage') or {}).get('input_tokens') or 0 for x in calls),'output_tokens':sum((x.get('usage') or {}).get('output_tokens') or 0 for x in calls),'latency_seconds':time.time()-started,'attempts':sum(x.get('attempts',1) for x in calls)};return records,usage

def run(root:Path):
 receipt,labels=validate_and_freeze(root);oracle={(x.request_id,x.candidate_id):x.human_label for x in labels};old=old_records(root,labels);new,usage=frame_run(root,labels);payload={'version':'sprint9c-evaluation/1.0','oracle_receipt':receipt,'old_video':metrics(old,oracle),'ordered_frames':metrics(new,oracle),'ordered_frame_usage':usage,'old_records':old,'ordered_frame_records':new};out=root/'runtime/sprint9c/SPRINT9C_EVALUATION.json';out.write_text(json.dumps(payload,indent=2));return payload
