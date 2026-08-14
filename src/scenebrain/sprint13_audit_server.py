from __future__ import annotations
import json,sys
from datetime import datetime,timezone
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from .hashing import fingerprint,sha256_file

ROOT=Path(__file__).resolve().parents[2];RUNTIME=ROOT/'runtime/sprint12_real_script';PLAN=RUNTIME/'VISUAL_PLAN_REAL_SCRIPT.json';AUDIT=RUNTIME/'audit'

def freeze(payload:dict):
 plan=json.loads(PLAN.read_text(encoding='utf8'));expected='s12:'+plan['plan_fingerprint']
 if payload.get('local_storage_key')!=expected:raise ValueError('wrong localStorage key')
 decisions=payload.get('decisions');
 if not isinstance(decisions,dict) or len(decisions)!=59:raise ValueError(f'exactly 59 decisions required, got {len(decisions) if isinstance(decisions,dict) else "invalid"}')
 slots={s['slot_id']:(b,s) for b in plan['beats'] for s in b['visual_slots']};rows=[]
 if set(decisions)!=set(slots):raise ValueError('decision slot coverage mismatch')
 for sid in sorted(slots):
  b,s=slots[sid];d=decisions[sid];kind=d.get('decision');aid=d.get('asset_id');opts=([s['chosen_asset']] if s['chosen_asset'] else [])+s['alternatives'];chosen=next((x for x in opts if x['asset_id']==aid),None)
  if kind!='NONE_GOOD' and not chosen:raise ValueError(f'{sid}: selected asset not presented')
  rows.append({'beat_id':b['beat_id'],'slot_id':sid,'narration':b['exact_narration'],'evidence_class':b['evidence_class'],'original_color':s['color'],'decision':'NONE_GOOD' if kind=='NONE_GOOD' else 'PROJECT_SLOT_APPROVAL','raw_decision':kind,'chosen_asset_id':chosen['asset_id'] if chosen else None,'chosen_media_type':chosen['media_type'] if chosen else None,'chosen_source':chosen['source_path'] if chosen else None,'chosen_episode':chosen['episode_code'] if chosen else None,'chosen_source_range_or_frame':({'source_in_ms':chosen['source_in_ms'],'source_out_ms':chosen['source_out_ms'],'frame_time_ms':chosen['frame_time_ms']} if chosen else None),'all_presented_options':opts,'review_timestamp':d.get('at')})
 AUDIT.mkdir(parents=True,exist_ok=True);audit={'version':'sprint12-human-audit/1.0','project_fingerprint':plan['plan_fingerprint'],'local_storage_key':expected,'frozen_at':datetime.now(timezone.utc).isoformat(),'decisions':rows};ap=AUDIT/'SPRINT12_HUMAN_AUDIT.json';ap.write_text(json.dumps(audit,indent=2),encoding='utf8');receipt={'version':'human-audit-receipt/1.0','audit_sha256':sha256_file(ap),'plan_sha256':sha256_file(PLAN),'decision_count':59,'accepted_count':sum(x['decision']=='PROJECT_SLOT_APPROVAL' for x in rows),'none_good_count':sum(x['decision']=='NONE_GOOD' for x in rows)};receipt['fingerprint']=fingerprint(json.dumps(receipt,sort_keys=True));(AUDIT/'SPRINT12_HUMAN_AUDIT_RECEIPT.json').write_text(json.dumps(receipt,indent=2),encoding='utf8')
 baseline={'version':'sprint12-human-baseline/1.0','total':59,'accepted_slot_count':receipt['accepted_count'],'none_good_count':receipt['none_good_count'],'orange_unresolved_count':sum(x['original_color']=='ORANGE_UNRESOLVED' for x in rows),'accepted_rate':receipt['accepted_count']/59,'media_bearing_accepted_rate':sum(x['chosen_asset_id'] is not None for x in rows)/59,'breakdown':{}}
 for field in ['original_color','chosen_episode','evidence_class','chosen_media_type']:
  vals={}
  for x in rows:vals[str(x.get(field))]=vals.get(str(x.get(field)),0)+1
  baseline['breakdown'][field]=vals
 (AUDIT/'SPRINT12_HUMAN_BASELINE.json').write_text(json.dumps(baseline,indent=2),encoding='utf8');return receipt

class Handler(SimpleHTTPRequestHandler):
 def do_POST(self):
  if self.path!='/freeze-review':self.send_error(404);return
  try:
   n=int(self.headers.get('Content-Length','0'));result=freeze(json.loads(self.rfile.read(n)));body=json.dumps({'ok':True,'receipt':result}).encode();self.send_response(200)
  except Exception as e:body=json.dumps({'ok':False,'error':str(e)}).encode();self.send_response(400)
  self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)

def main():
 import os;os.chdir(RUNTIME);ThreadingHTTPServer(('127.0.0.1',8772),Handler).serve_forever()
if __name__=='__main__':main()
