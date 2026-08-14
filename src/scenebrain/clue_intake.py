"""Independent, fail-closed Clue V4 intake validation."""
from __future__ import annotations
import re, unicodedata

EVIDENCE_CLASSES={"EXACT_DIALOGUE","EXACT_EVENT","EVENT_CONTEXT","EDITORIAL_CONTEXT","CHARACTER_CONTEXT"}

def _norm(text:str,punctuation:bool=True)->str:
 text=unicodedata.normalize("NFKC",str(text or "").lstrip("\ufeff")).replace("’","'").replace("“",'"').replace("”",'"')
 if not punctuation:text=re.sub(r"[^\w']+"," ",text,flags=re.UNICODE)
 return re.sub(r"\s+"," ",text).strip()

def validate_clue(clean_script:str,clue:dict,selected_titles:list[str])->dict:
 errors=[];warnings=[];beats=clue.get("beats") if isinstance(clue,dict) else None
 if clue.get("schema_version")!="production-clue-script/4.0":errors.append({"code":"SCHEMA_VERSION","message":"Expected production-clue-script/4.0"})
 if not isinstance(beats,list) or not beats:errors.append({"code":"BEATS_REQUIRED","message":"Clue beats are required"});beats=[]
 ids=[str(b.get("beat_id",'')) for b in beats]
 if len(ids)!=len(set(ids)) or any(not x for x in ids):errors.append({"code":"BEAT_ID_ORDER","message":"Beat IDs must be non-empty and unique"})
 events={str(x.get("canonical_event_id")) for x in clue.get("canonical_events",[]) if isinstance(x,dict)}
 for i,b in enumerate(beats):
  if b.get("evidence_class") not in EVIDENCE_CLASSES:errors.append({"code":"EVIDENCE_CLASS","beat_id":ids[i],"message":"Unsupported evidence class"})
  refs=b.get("canonical_event_ids",[]) or ([b["canonical_event_id"]] if b.get("canonical_event_id") else [])
  if any(str(x) not in events for x in refs):errors.append({"code":"CANONICAL_EVENT_REFERENCE","beat_id":ids[i],"message":"Unknown canonical event reference"})
  pref=b.get("source_title_preference")
  if pref and pref not in selected_titles:errors.append({"code":"SOURCE_SCOPE","beat_id":ids[i],"message":f"Title preference outside selected scope: {pref}"})
  if any(k in b for k in ("timestamp","start_ms","end_ms","source_time")):errors.append({"code":"TIMESTAMP_AUTHORITY","beat_id":ids[i],"message":"Clue beats may not contain source timestamps"})
 narration=" ".join(str(b.get("narration",'')) for b in beats)
 exact=_norm(clean_script)==_norm(narration)
 words=_norm(clean_script,False)==_norm(narration,False)
 comparison="EXACT_MATCH" if exact else "PUNCTUATION_ONLY_DIFFERENCE" if words else "WORD_SEQUENCE_MISMATCH"
 if comparison=="WORD_SEQUENCE_MISMATCH":
  a=_norm(clean_script,False).split();b=_norm(narration,False).split();i=next((i for i,(x,y) in enumerate(zip(a,b)) if x!=y),min(len(a),len(b)))
  errors.append({"code":"NARRATION_MISMATCH","beat_id":next((ids[j] for j,beat in enumerate(beats) if i < len(_norm(' '.join(str(x.get('narration','')) for x in beats[:j+1]),False).split())),None),"message":"Clean Script and Clue word sequences differ","clean_context":" ".join(a[max(0,i-5):i+6]),"clue_context":" ".join(b[max(0,i-5):i+6])})
 elif comparison=="PUNCTUATION_ONLY_DIFFERENCE":warnings.append({"code":"PUNCTUATION_ONLY","message":"Words match; punctuation differs"})
 return {"valid":not errors,"comparison":comparison,"errors":errors,"warnings":warnings,"beat_count":len(beats),"selected_titles":selected_titles}
