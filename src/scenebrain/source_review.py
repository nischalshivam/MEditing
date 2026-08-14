from __future__ import annotations
import hashlib,json,sqlite3,subprocess
from datetime import datetime,timezone
from pathlib import Path
from .portable_library import db,episode
from .router_v4 import search_windows
from .hashing import sha256_file

PROJECT_ID='walter_book_project'
DISCOVERY_VERSION='project-source-discovery/4.0'
def now():return datetime.now(timezone.utc).isoformat()
def atomic(p,obj):p.parent.mkdir(parents=True,exist_ok=True);q=p.with_suffix('.building.json');q.write_text(json.dumps(obj,indent=2,ensure_ascii=False),encoding='utf8');q.replace(p)
def sha(p):return sha256_file(p)

def sources(media):
 c=db(media/'.scene_brain/catalog.db');out=[]
 for r in c.execute("select s.* from sources s join titles t on t.title_id=s.title_id where t.display_name='Breaking Bad'"):
  se,ep,_=episode(Path(r['relative_path']).stem);out.append({'source_id':r['source_id'],'title_id':r['title_id'],'season':se,'episode':ep,'label':f'S{se:02d}E{ep:02d}','relative_path':r['relative_path'],'absolute_path':str(media/r['relative_path']),'duration_ms':r['duration_ms'],'maturity':r['maturity']})
 c.close();return sorted(out,key=lambda x:(x['season'],x['episode']))

def ensure_project(media,root,pid=PROJECT_ID):
 p=media/'.scene_brain/projects'/pid;p.mkdir(parents=True,exist_ok=True);state=p/'EDITOR_PROJECT.json'
 if not state.exists():atomic(state,{'version':'production-editor-project/2.0','project_id':pid,'name':'Why Walter White Kept the Book That Exposed Him'+(' [QA COPY]' if pid!=PROJECT_ID else ''),'scope':['Breaking Bad'],'script_path':str(root/'runtime/new_project_book_test/CLEAN_SCRIPT.txt'),'script_sha256':'5ab589901ad5c9029d568107ac48e9512826dbd1b3cad1f137632068a314e4cc','clue_sha256':'9354ae8b68d8aaa9f7ef0b7057daa993a76e6b482c7ca72ae44049902818bede','status':'SOURCE REVIEW REQUIRED','source_review_required':8,'timeline':[],'undo':[],'redo':[],'locked_source_count':0,'manual_fix_count':0,'library_pin':'b844b9d0-31d9-488f-afd8-2da7c57ce781','created':now()})
 return p

def review_payload(media,root,pid=PROJECT_ID):
 p=ensure_project(media,root,pid);queue=json.loads((root/'runtime/bb_discovery_router_v4/SOURCE_RESOLUTION_REVIEW_QUEUE.json').read_text());clue=json.loads((root/'runtime/new_project_book_test/VALIDATED_CLUE_SCRIPT.json').read_text());beats=clue['beats'];all_sources=sources(media);bylabel={x['label']:x for x in all_sources};apath=p/'source_review/PROJECT_SOURCE_APPROVALS.json';approvals=json.loads(apath.read_text()).get('approvals',[]) if apath.exists() else [];approved={x['canonical_event_id']:x for x in approvals};items=[]
 for q in queue:
  ev=q['event_id'];linked=[b for b in beats if b.get('canonical_event_id')==ev];hint=q.get('episode_hint');labels=[]
  if q['routing_state']=='VISUAL_SOURCE_UNVERIFIED' and hint in bylabel:labels.append(hint)
  labels += [x for x in q.get('episode_options',[]) if x not in labels]
  cards=[]
  for lab in labels[:3]:
   if lab not in bylabel:continue
   src=bylabel[lab];e=[x for x in q.get('window_evidence',[]) if f"S{x['season']:02d}E{x['episode']:02d}"==lab][:2]
   reason='CLUE HINT' if lab==hint else ('EXACT DIALOGUE' if any(x.get('match_mode')=='EXACT_PHRASE' for x in e) else ('LOCAL DIALOGUE' if e else 'CONTEXT MATCH'))
   cards.append({**src,'reason':reason,'hinted':lab==hint,'evidence':e,'media_url':'/media?path='+src['absolute_path']})
  items.append({'canonical_event_id':ev,'description':q['description'],'narration_excerpt':linked[0]['exact_narration'] if linked else '', 'routing_label':'VISUAL SOURCE NEEDS CONFIRMATION' if q['routing_state']=='VISUAL_SOURCE_UNVERIFIED' else 'SOURCE AMBIGUOUS','clue_hint':hint,'candidates':cards,'linked_beats':[b['beat_id'] for b in linked],'decision':approved.get(ev)})
 items.sort(key=lambda x:(not bool(x['clue_hint']),x['canonical_event_id']))
 if not apath.exists():atomic(apath,{'version':'project-source-approvals/1.0','project_id':pid,'approvals':[],'updated_at':now()})
 return {'project_id':pid,'project_name':'Why Walter White Kept the Book That Exposed Him','auto_resolved':7,'total_events':15,'required':len(items),'completed':sum(bool(x['decision']) for x in items),'items':items,'episodes':all_sources}

def approve(media,root,payload,pid=PROJECT_ID):
 p=ensure_project(media,root,pid);review=review_payload(media,root,pid);valid={x['canonical_event_id'] for x in review['items']};ev=payload['canonical_event_id']
 if ev not in valid:raise ValueError('Unknown canonical event')
 src=None
 if payload.get('source_id'):src=next((x for x in review['episodes'] if x['source_id']==payload['source_id']),None)
 status='MANUAL_SOURCE_REQUIRED' if payload.get('manual_later') else 'PROJECT_SOURCE_APPROVAL'
 if status!='MANUAL_SOURCE_REQUIRED' and not src:raise ValueError('Choose a valid Breaking Bad episode')
 path=p/'source_review/PROJECT_SOURCE_APPROVALS.json';old=json.loads(path.read_text()) if path.exists() else {'version':'project-source-approvals/1.0','project_id':pid,'approvals':[]};old['approvals']=[x for x in old['approvals'] if x['canonical_event_id']!=ev];row={'project_id':pid,'canonical_event_id':ev,'status':status,'approval_method':payload.get('approval_method','HUMAN_ROUTER_CANDIDATE'),'timestamp':now(),'clue_sha':'9354ae8b68d8aaa9f7ef0b7057daa993a76e6b482c7ca72ae44049902818bede','discovery_version':DISCOVERY_VERSION}
 if src:row.update({k:src[k] for k in ('title_id','source_id','season','episode','label')})
 old['approvals'].append(row);old['updated_at']=now();atomic(path,old);return finalize(media,root,pid)

def finalize(media,root,pid=PROJECT_ID):
 p=ensure_project(media,root,pid);review=review_payload(media,root,pid);apath=p/'source_review/PROJECT_SOURCE_APPROVALS.json';approvals=json.loads(apath.read_text()).get('approvals',[]) if apath.exists() else []
 result={'review':review,'complete':len(approvals)==8,'approvals':approvals}
 if len(approvals)!=8:return result
 canonical=json.loads((root/'runtime/bb_discovery_router_v4/CANONICAL_EVENT_SOURCE_MAP.json').read_text());mapping=[]
 for x in canonical:
  human=next((a for a in approvals if a['canonical_event_id']==x['event_id']),None)
  if human:mapping.append({'canonical_event_id':x['event_id'],'routing':'HUMAN','status':human['status'],'episode':human.get('label'),'source_id':human.get('source_id')})
  else:mapping.append({'canonical_event_id':x['event_id'],'routing':'ROUTER_V4','status':x['routing_state'],'episode':x['episode_candidates'][0] if x['episode_candidates'] else None,'source_id':x['window_evidence'][0]['source_id'] if x['window_evidence'] else None})
 grouped={}
 for x in mapping:
  if not x['episode']:continue
  grouped.setdefault(x['episode'],{'episode':x['episode'],'canonical_events':[],'source_id':x['source_id']})['canonical_events'].append(x['canonical_event_id'])
 srcs={x['source_id']:x for x in sources(media)};requirements=[]
 for g in grouped.values():
  s=srcs.get(g['source_id']) or next((x for x in srcs.values() if x['label']==g['episode']),None);requirements.append({**g,'current_library_maturity':s['maturity'] if s else 'MEDIA_MISSING','rich_required':'NO' if s and s['maturity']=='RICH_ATLAS_READY' else 'YES'})
 final={'version':'final-project-episode-requirement-map/1.0','project_id':pid,'canonical_events':mapping,'required_unique_episodes':len(requirements),'episodes':sorted(requirements,key=lambda x:x['episode']),'rich_preview':{'already_full_rich':sum(x['current_library_maturity']=='RICH_ATLAS_READY' for x in requirements),'need_rich_preparation':sum(x['rich_required']=='YES' for x in requirements)},'ready_to_prepare_required_episodes':all(x['status']!='MANUAL_SOURCE_REQUIRED' for x in mapping)};atomic(p/'source_review/FINAL_PROJECT_EPISODE_REQUIREMENT_MAP.json',final)
 receipt={'version':'source-review-receipt/1.0','original_discovery_sha':sha(root/'runtime/bb_discovery_router_v4/PROJECT_SOURCE_DISCOVERY_V4.json'),'clue_sha':'9354ae8b68d8aaa9f7ef0b7057daa993a76e6b482c7ca72ae44049902818bede','queue_sha':sha(root/'runtime/bb_discovery_router_v4/SOURCE_RESOLUTION_REVIEW_QUEUE.json'),'approved_count':sum(x['status']=='PROJECT_SOURCE_APPROVAL' for x in approvals),'manual_unresolved_count':sum(x['status']=='MANUAL_SOURCE_REQUIRED' for x in approvals),'timestamp':now()};atomic(p/'source_review/SOURCE_REVIEW_RECEIPT.json',receipt);result['final_map']=final;return result

def search_dialogue(root,query):return search_windows(Path(r'E:\Movies\.scene_brain\libraries\breaking_bad_dialogue_windows_v4_0.db'),query,20)

def contact_sheet(media,root,source_id):
 src=next(x for x in sources(media) if x['source_id']==source_id);folder=Path.home()/'AppData/Local/SceneBrain/cache'/PROJECT_ID/'contact_sheets'/source_id;folder.mkdir(parents=True,exist_ok=True);items=[]
 for i in range(16):
  t=round(src['duration_ms']*(i+.5)/16);target=folder/f'KF_{i+1:02d}_{t}.jpg'
  if not target.exists():subprocess.run(['ffmpeg','-v','error','-ss',str(t/1000),'-i',src['absolute_path'],'-frames:v','1','-vf','scale=320:-2','-q:v','5','-y',str(target)],check=True)
  items.append({'frame_id':f'KF_{i+1:02d}','time_ms':t,'path':str(target),'url':'/media?path='+str(target)})
 return {'source_id':source_id,'frames':items,'rich_atlas_created':False}
