from __future__ import annotations
import json,statistics,subprocess
from collections import Counter
from pathlib import Path
from .hashing import sha256_file,fingerprint

FROZEN_SHA='08428494d51f7d6f9e75208dd6e2c8ca2007e2641d28ee4d975008392dc1d4e5'
EXACT={'EXACT_EVENT','EXACT_DIALOGUE'}
def write(p,o):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(o,indent=2,ensure_ascii=False),encoding='utf8')
def range_key(a):return (a.get('source_hash'),a.get('source_in_ms'),a.get('source_out_ms'))

def build(root:Path):
 frozen=root/'runtime/final_project/FINAL_LOCKED_VISUAL_PLAN.json'
 if sha256_file(frozen)!=FROZEN_SHA:raise ValueError('frozen retrieval changed')
 final=json.loads(frozen.read_text());old=json.loads((root/'runtime/sprint14_voiceover/TIMELINE_PLAN.json').read_text());align=json.loads((root/'runtime/sprint14_voiceover/BEAT_ALIGNMENT.json').read_text())['beats'];out=root/'runtime/sprint14b_polish';(out/'images').mkdir(parents=True,exist_ok=True)
 locked={x['beat_id']:x for x in final['slots']};pool=list(final['slots']);manual={'B002','B022'};used_recent=[];slots=[];callbacks=0
 def borrow(beat,now):
  base=locked[beat];subjects=set(base['chosen_asset'].get('subjects') or [])
  candidates=[]
  for x in pool:
   a=x['chosen_asset'];age=now-next((t for k,t,_ in reversed(used_recent) if k==range_key(a)),-999999)
   score=(4 if x['chosen_episode']==base['chosen_episode'] else 0)+(2 if x['evidence_class']==base['evidence_class'] else 0)+(3 if age>120000 else -5)
   if range_key(a)!=range_key(base['chosen_asset']):candidates.append((score,x))
  return max(candidates,key=lambda z:(z[0],z[1]['slot_id']))[1] if candidates else base
 for i,b in enumerate(align):
  start=0 if i==0 else b['voice_start_ms'];end=align[i+1]['voice_start_ms'] if i+1<len(align) else 887300;dur=end-start
  if b['beat_id'] in manual:
   slots.append({'presentation_slot_id':b['beat_id']+'_V2P01','beat_id':b['beat_id'],'timeline_start_ms':start,'timeline_end_ms':end,'exact_narration':b['exact_narration'],'presentation_type':'MANUAL_PLACEHOLDER','approval_state':'MANUAL_FIX','locked_asset_id':None,'source_path':None,'source_hash':None,'source_in_ms':None,'source_out_ms':None,'frame_time_ms':None,'derived_asset_path':None,'reuse_provenance':None,'callback_status':None,'repetition_score':0});continue
  own=locked[b['beat_id']];parts=3 if dur>=15500 else 2;cuts=[start+round(dur*j/parts) for j in range(parts+1)]
  for j in range(parts):
   chosen=own;borrowed=False
   if j==parts-1 and own['evidence_class'] not in EXACT:
    chosen=borrow(b['beat_id'],cuts[j]);borrowed=chosen['slot_id']!=own['slot_id']
   if own['evidence_class'] not in EXACT and any(k==range_key(chosen['chosen_asset']) and cuts[j]-t<120000 for k,t,beat in used_recent if beat!=b['beat_id']):
    chosen=borrow(b['beat_id'],cuts[j]);borrowed=chosen['slot_id']!=own['slot_id']
   a=chosen['chosen_asset'];natural=max(0,(a.get('source_out_ms') or 0)-(a.get('source_in_ms') or 0));pdur=cuts[j+1]-cuts[j]
   typ='VIDEO' if a['media_type']=='VIDEO' and j%2==0 else 'IMAGE'
   if typ=='VIDEO' and natural<pdur:typ='IMAGE'
   frame=a.get('frame_time_ms') or ((a.get('source_in_ms') or 0)+(a.get('source_out_ms') or 0))//2;derived=None
   if typ=='IMAGE':
    derived=out/'images'/f"{a['asset_id']}_{frame}.jpg"
    if not derived.exists():subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-ss',f'{frame/1000:.3f}','-i',a['source_path'],'-frames:v','1','-vf','scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2','-q:v','2','-y',str(derived)],check=True)
   key=range_key(a);prior=next(((t,beat) for k,t,beat in reversed(used_recent) if k==key and beat!=b['beat_id']),None);recent=prior[0] if prior else None
   callback=bool(recent is not None and (own['evidence_class'] in EXACT or cuts[j]-recent>=120000) and chosen['chosen_episode']==own['chosen_episode']);callbacks+=callback
   repeat=1 if recent is not None and cuts[j]-recent<120000 and not callback else 0
   slots.append({'presentation_slot_id':f"{b['beat_id']}_V2P{j+1:02d}",'beat_id':b['beat_id'],'timeline_start_ms':cuts[j],'timeline_end_ms':cuts[j+1],'exact_narration':b['exact_narration'],'presentation_type':typ,'approval_state':'APPROVED','source_lock_slot_id':chosen['slot_id'],'locked_asset_id':a['asset_id'],'source_path':a['source_path'],'source_hash':a['source_hash'],'source_in_ms':a.get('source_in_ms'),'source_out_ms':a.get('source_out_ms'),'frame_time_ms':frame if typ=='IMAGE' else None,'derived_asset_path':str(derived.resolve()) if derived else None,'reuse_provenance':'SOURCE_REUSED_FROM_LOCKED_PROJECT_ASSET' if borrowed else 'OWN_LOCKED_PROJECT_ASSET','callback_status':'INTENTIONAL_CALLBACK' if callback else None,'repetition_score':repeat});used_recent.append((key,cuts[j],b['beat_id']))
 timeline={'version':'timeline-plan/2.0','voiceover_path':old['voiceover_path'],'voiceover_sha256':old['voiceover_sha256'],'duration_ms':887300,'frozen_retrieval_plan_sha256':FROZEN_SHA,'presentation_slots':slots,'manual_slots':['B002_VS01','B022_VS01']};timeline['fingerprint']=fingerprint(json.dumps(timeline,sort_keys=True));write(out/'TIMELINE_PLAN_V2.json',timeline)
 exact=Counter((x['beat_id'],x['source_hash'],x['source_in_ms'],x['source_out_ms'],x['presentation_type']) for x in slots if x['approval_state']=='APPROVED');still=Counter((x['beat_id'],x['source_hash'],x['frame_time_ms']) for x in slots if x['presentation_type']=='IMAGE');audit={'version':'final-repetition-manager-v2','exact_range_repeats':[{'key':list(k),'count':v} for k,v in exact.items() if v>1],'same_still_repeats':[{'key':list(k),'count':v} for k,v in still.items() if v>1],'accidental_repeat_slots':[x['presentation_slot_id'] for x in slots if x['repetition_score']>0],'intentional_callback_slots':[x['presentation_slot_id'] for x in slots if x['callback_status']],'policy':'Exact/event owns source; contextual borrowing only from locked project assets; 120s recency window.'};write(out/'REPETITION_AUDIT.json',audit);return timeline,audit
