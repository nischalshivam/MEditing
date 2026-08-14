from __future__ import annotations
import json,re
from datetime import datetime,timezone
from pathlib import Path
from .hashing import sha256_file

SCHEMA='production-clue-script/3.0'
EVIDENCE={'EXACT_DIALOGUE','EXACT_EVENT','EVENT_CONTEXT','EDITORIAL_CONTEXT','CHARACTER_CONTEXT'}
MEDIA={'VIDEO','IMAGE','EITHER','VIDEO_OR_IMAGE'}
def norm(s):return re.sub(r'\s+',' ',s.replace('\ufeff','')).strip()
def words(s):return re.findall(r"[\w’'-]+",norm(s).lower())
def validate(clean_path:Path,clue_path:Path,scope:list[str]):
 errors=[]
 try:data=json.loads(clue_path.read_text(encoding='utf-8-sig'))
 except json.JSONDecodeError as e:return None,[f'INVALID JSON FORMAT: line {e.lineno}, column {e.colno}: {e.msg}']
 if data.get('schema_version')!=SCHEMA:errors.append(f'schema_version must be {SCHEMA}')
 beats=data.get('beats');
 if not isinstance(beats,list) or not beats:errors.append('beats must be a non-empty list');beats=[]
 ids=[x.get('beat_id') for x in beats]
 if len(ids)!=len(set(ids)):errors.append('duplicate beat IDs')
 events=data.get('canonical_event_registry',[]);event_ids={x.get('canonical_event_id') or x.get('event_id') for x in events}
 narration=[]
 for i,b in enumerate(beats):
  n=b.get('exact_narration');
  if not isinstance(n,str) or not n.strip():errors.append(f'{ids[i]} missing exact_narration');continue
  narration.append(n)
  if b.get('evidence_class') not in EVIDENCE:errors.append(f'{ids[i]} invalid evidence_class')
  ce=b.get('canonical_event_id')
  if ce and ce not in event_ids:errors.append(f'{ids[i]} unknown canonical_event_id {ce}')
  for ref in b.get('context_anchor_event_ids',[]):
   if ref not in event_ids:errors.append(f'{ids[i]} unknown context anchor {ref}')
  for h in b.get('source_title_hints',[]):
   if h.get('title') not in scope:errors.append(f"{ids[i]} title {h.get('title')} outside selected scope")
  slots=b.get('recommended_visual_slots')
  if not isinstance(slots,list) or not slots:errors.append(f'{ids[i]} has no recommended_visual_slots')
  else:
   nums=[x.get('slot_number') for x in slots]
   if nums!=list(range(1,len(slots)+1)):errors.append(f'{ids[i]} visual slot numbering invalid')
   for s in slots:
    if s.get('preferred_media') not in MEDIA:errors.append(f'{ids[i]} invalid slot media')
 clean=norm(clean_path.read_text(encoding='utf-8-sig'));joined=norm(' '.join(narration))
 pos=0
 for b,n in zip(beats,narration):
  at=clean.find(norm(n),pos)
  if at<0:errors.append(f"{b['beat_id']} narration missing/out of order")
  else:pos=at+len(norm(n))
 if words(clean)!=words(joined):
  cw,bw=words(clean),words(joined);errors.append(f'complete narration coverage failed: clean={len(cw)} words, clues={len(bw)} words')
 receipt={'version':'clue-validation-receipt/3.0','clean_script_sha256':sha256_file(clean_path),'clue_sha256':sha256_file(clue_path),'schema_version':data.get('schema_version'),'beat_count':len(beats),'canonical_event_count':len(event_ids),'recommended_visual_slot_count':sum(len(x.get('recommended_visual_slots',[])) for x in beats),'coverage':'PASS' if not errors else 'FAIL','source_scope':scope,'validated_at':datetime.now(timezone.utc).isoformat()}
 return (data,receipt),errors
