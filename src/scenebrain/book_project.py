from __future__ import annotations
import json,re,shutil,uuid
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
from .clue_v3 import validate
from .hashing import sha256_file
from .portable_library import db,episode
from .production_preflight import search_title_dialogue,title_status,migrate_schema

def now():return datetime.now(timezone.utc).isoformat()
def run(media:Path,root:Path,clean:Path,clue:Path):
 out=root/'runtime/new_project_book_test';out.mkdir(parents=True,exist_ok=True)
 checked,errors=validate(clean,clue,['Breaking Bad'])
 if errors:raise ValueError('; '.join(errors))
 data,receipt=checked
 shutil.copy2(clean,out/'CLEAN_SCRIPT.txt');shutil.copy2(clue,out/'IMPORTED_ORIGINAL.json')
 (out/'VALIDATED_CLUE_SCRIPT.json').write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf8');(out/'CLUE_VALIDATION_RECEIPT.json').write_text(json.dumps(receipt,indent=2),encoding='utf8')
 (out/'CLEAN_SCRIPT_RECEIPT.json').write_text(json.dumps({'sha256':sha256_file(clean),'managed_copy':str(out/'CLEAN_SCRIPT.txt'),'created':now()},indent=2),encoding='utf8')
 catalog=media/'.scene_brain/catalog.db';c=db(catalog);migrate_schema(c)
 source_by_ep={}
 for r in c.execute("select s.* from sources s join titles t on t.title_id=s.title_id where t.display_name='Breaking Bad' and s.present=1"):
  se,ep,_=episode(Path(r['relative_path']).stem)
  if se and ep:source_by_ep[f'S{se:02d}E{ep:02d}']=dict(r)
 discovery=[];required=defaultdict(list);hint_counts=Counter()
 for b in data['beats']:
  hint=(b.get('episode_hint') or {}).get('value');results=search_title_dialogue(catalog,'Breaking Bad',b.get('dialogue_clues',[])+b.get('search_clues',[])[:3],15);votes=Counter(f"S{x['season']:02d}E{x['episode']:02d}" for x in results if x['season'] and x['episode']);top=votes.most_common(3)
  exact=b['evidence_class'] in {'EXACT_EVENT','EXACT_DIALOGUE','EVENT_CONTEXT'}
  deterministic=[x for x in results if len(x.get('matched_terms',[]))>=2 and ' '.join(x.get('matched_terms',[])).lower() in x.get('evidence_text','').lower()]
  dvotes=Counter(f"S{x['season']:02d}E{x['episode']:02d}" for x in deterministic if x['season'] and x['episode'])
  if not exact:state='EDITORIAL_NO_EXACT_EPISODE_REQUIRED';chosen=None
  elif dvotes:
   chosen=dvotes.most_common(1)[0][0];state='VERIFIED_LOCAL' if dvotes[chosen]>=2 else 'STRONG_LOCAL';hint_counts['accepted' if hint==chosen else 'conflict' if hint else 'unknown']+=1;required[chosen].append(b['beat_id'])
  elif hint and hint in source_by_ep:
   chosen=hint;state='AMBIGUOUS';hint_counts['unknown']+=1
  else:chosen=None;state='UNRESOLVED';hint_counts['unknown']+=1
  discovery.append({'beat_id':b['beat_id'],'canonical_event':b.get('canonical_event_id'),'episode_hint':hint,'local_search_evidence':results[:5],'resolved_episode_candidates':[x[0] for x in top],'final_episode':chosen,'routing_state':state})
 c.close();(out/'PROJECT_SOURCE_DISCOVERY.json').write_text(json.dumps(discovery,indent=2),encoding='utf8')
 req=[]
 for ep,beats in sorted(required.items()):
  s=source_by_ep[ep];req.append({'title':'Breaking Bad','episode':ep,'source_id':s['source_id'],'relative_path':s['relative_path'],'maturity':s['maturity'],'supporting_beats':beats,'media_present':bool(s['present']),'strong_hash_available':bool(s.get('strong_sha256'))})
 (out/'PROJECT_EPISODE_REQUIREMENT_MAP.json').write_text(json.dumps({'title':'Breaking Bad','required_sources':req},indent=2),encoding='utf8')
 unresolved=[x['beat_id'] for x in discovery if x['routing_state'] in {'AMBIGUOUS','UNRESOLVED'}]
 pre={'version':'book-project-preflight/1.0','clean_valid':True,'clue_valid':True,'scope_valid':True,'title_searchable':title_status(db(catalog),'Breaking Bad')['searchable']==62,'required_sources':req,'unresolved_exact_beats':unresolved,'ready_for_retrieval':not unresolved and all(x['maturity']=='RICH_ATLAS_READY' for x in req),'created':now()};(out/'PROJECT_PREFLIGHT_RECEIPT.json').write_text(json.dumps(pre,indent=2),encoding='utf8')
 metrics={'beats':len(data['beats']),'recommended_visual_slots':receipt['recommended_visual_slot_count'],'required_unique_episodes':len(req),'episode_hints':dict(hint_counts),'unresolved_exact_beats':len(unresolved),'rich_reused':sum(x['maturity']=='RICH_ATLAS_READY' for x in req),'rich_needed':sum(x['maturity']!='RICH_ATLAS_READY' for x in req),'api_cost_usd':0,'generated_at':now()};(out/'metrics.json').write_text(json.dumps(metrics,indent=2),encoding='utf8');return metrics
