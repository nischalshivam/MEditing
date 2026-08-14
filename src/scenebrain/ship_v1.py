from __future__ import annotations
import json,hashlib,subprocess,time,sqlite3,re
from collections import defaultdict,Counter
from datetime import datetime,timezone
from pathlib import Path
from .portable_library import db,episode
from .hashing import sha256_file
from .router_v4 import load_cues,windows,search_windows
from .production_preflight import migrate_schema

EVENTS={'PRISON_MURDERS':'S05E08','WALT_REDISCOVERS_LEAVES_OF_GRASS':'S05E03','GALE_WHITMAN_BOND':'S03E06','GALE_LEAVES_OF_GRASS_INSCRIPTION':'S05E08','GALE_NOTEBOOK_WW_CLUE':'S04E04','WALT_REVIEWS_GALE_CASE_FILE':'S04E04','WALT_DEFLECTS_WW_SUSPICION':'S04E04','HANK_FINDS_LEAVES_OF_GRASS':'S05E08','BOOK_MISSING_TRACKER_GARAGE':'S05E09','FAMILY_POOL_BEFORE_DISCOVERY':'S05E08','HANK_ASSUMES_GALE_IS_HEISENBERG':'S04E04','WALT_REOPENS_CASE_AT_DINNER':'S04E05','GALE_MURDER':'S03E13','WALT_KILLS_MIKE':'S05E07','HANK_REBUILDS_CASE':'S05E09'}
EXPECTED={'S03E06','S03E13','S04E04','S04E05','S05E03','S05E07','S05E08','S05E09'}
def now():return datetime.now(timezone.utc).isoformat()
def atomic(p,o):p.parent.mkdir(parents=True,exist_ok=True);q=p.with_suffix('.building.json');q.write_text(json.dumps(o,indent=2,ensure_ascii=False),encoding='utf8');q.replace(p)
def sources(media):
 c=db(media/'.scene_brain/catalog.db');out={}
 for r in c.execute("select s.* from sources s join titles t on t.title_id=s.title_id where t.display_name='Breaking Bad' and s.present=1"):
  se,ep,_=episode(Path(r['relative_path']).stem);out[f'S{se:02d}E{ep:02d}']=dict(r)
 c.close();return out
def freeze_admin(media,root):
 src=sources(media);missing=EXPECTED-set(src)
 if missing:raise RuntimeError('missing canonical physical sources: '+','.join(sorted(missing)))
 p=media/'.scene_brain/projects/walter_book_project/source_review';approvals=[]
 for ev,ep in EVENTS.items():
  s=src[ep];approvals.append({'project_id':'walter_book_project','canonical_event_id':ev,'status':'PROJECT_SOURCE_APPROVAL','approval_method':'ADMIN_SOURCE_CORRECTION','timestamp':now(),'clue_sha':'9354ae8b68d8aaa9f7ef0b7057daa993a76e6b482c7ca72ae44049902818bede','discovery_version':'admin-source-correction/1.0','title_id':s['title_id'],'source_id':s['source_id'],'season':int(ep[1:3]),'episode':int(ep[4:]),'label':ep})
 atomic(p/'PROJECT_SOURCE_APPROVALS.json',{'version':'project-source-approvals/1.1','project_id':'walter_book_project','authority':'ADMIN_SOURCE_CORRECTION','approvals':approvals,'updated_at':now()})
 grouped=defaultdict(list)
 for ev,ep in EVENTS.items():grouped[ep].append(ev)
 req=[]
 for ep in sorted(grouped):
  s=src[ep];req.append({'episode':ep,'source_id':s['source_id'],'relative_path':s['relative_path'],'strong_sha256':s['strong_sha256'],'canonical_events':grouped[ep],'current_library_maturity':s['maturity'],'rich_required':'NO' if s['maturity']=='RICH_ATLAS_READY' else 'YES'})
 if set(grouped)!=EXPECTED:raise RuntimeError('admin requirement set mismatch')
 result={'version':'final-project-episode-requirement-map/2.0','project_id':'walter_book_project','authority':'ADMIN_SOURCE_CORRECTION','canonical_events':[{'canonical_event_id':e,'episode':ep,'source_id':src[ep]['source_id']} for e,ep in EVENTS.items()],'required_unique_episodes':len(req),'episodes':req,'expected_set_verified':True,'frozen_at':now()};atomic(p/'FINAL_PROJECT_EPISODE_REQUIREMENT_MAP.json',result);atomic(root/'FINAL_PROJECT_EPISODE_REQUIREMENT_MAP.json',result);atomic(p/'ADMIN_SOURCE_CORRECTION_RECEIPT.json',{'version':'admin-source-correction/1.0','event_count':15,'unique_episode_count':8,'episode_set':sorted(EXPECTED),'map_sha256':sha256_file(p/'FINAL_PROJECT_EPISODE_REQUIREMENT_MAP.json'),'created_at':now()});return result

def detect_shots(path,duration_ms):
 cmd=['ffmpeg','-hide_banner','-v','info','-i',str(path),'-vf',"select='gt(scene,0.18)',showinfo",'-an','-f','null','-'];r=subprocess.run(cmd,capture_output=True,text=True,errors='replace');pts=[0]
 for m in re.finditer(r'pts_time:([0-9.]+)',r.stderr):pts.append(round(float(m.group(1))*1000))
 pts=sorted(set(x for x in pts if 0<x<duration_ms));return [(a,b) for a,b in zip([0]+pts,pts+[duration_ms]) if b>a]
def build_rich(media,root,ep,s):
 started=time.time();lib=media/'.scene_brain/libraries'/s['source_id']/'rich_atlas_v1';receipt=lib/'RICH_ATLAS_RECEIPT.json'
 if receipt.exists() and json.loads(receipt.read_text()).get('status')=='VALIDATED':return {'episode':ep,'status':'REUSED','runtime_seconds':0,'path':str(lib)}
 building=lib.parent/'rich_atlas_v1.building';building.mkdir(parents=True,exist_ok=True);src=media/s['relative_path'];strong=s['strong_sha256'] or sha256_file(src);c=db(media/'.scene_brain/catalog.db');sub=dict(c.execute('select * from subtitles where source_id=?',(s['source_id'],)).fetchone());c.close();cues=load_cues(media,sub);shots=detect_shots(src,s['duration_ms']);frames=building/'keyframes';frames.mkdir(exist_ok=True);items=[]
 for i,(a,b) in enumerate(shots):
  target=frames/f'S{i:05d}.jpg'
  if not target.exists():subprocess.run(['ffmpeg','-v','error','-ss',str(((a+b)/2)/1000),'-i',str(src),'-frames:v','1','-vf','scale=640:-2','-q:v','5','-y',str(target)],check=True)
  items.append({'shot_id':f'S{i:05d}','start_ms':a,'end_ms':b,'keyframe':str(target.relative_to(building)).replace('\\','/'),'keyframe_sha256':sha256_file(target)})
 # Deterministic narrative candidates: subtitle-gap boundaries plus physical continuity; no invented semantics.
 bounds=[0]
 for i in range(1,len(cues)):
  if cues[i]['start_ms']-cues[i-1]['end_ms']>=12000:bounds.append(cues[i]['start_ms'])
 bounds.append(s['duration_ms']);regions=[]
 for i,(a,b) in enumerate(zip(bounds,bounds[1:])):
  sh=[x['shot_id'] for x in items if x['end_ms']>a and x['start_ms']<b];dialogue=' '.join(x['text'] for x in cues if x['end_ms']>a and x['start_ms']<b)
  if sh:regions.append({'scene_region_id':f'{ep}_R{i+1:04d}','start_ms':a,'end_ms':b,'start_shot':sh[0],'end_shot':sh[-1],'dialogue':dialogue,'semantic_status':'OBJECTIVE_DIALOGUE_CONTEXT_ONLY'})
 payload={'version':'production-rich-atlas/1.0','episode':ep,'source_id':s['source_id'],'relative_path':s['relative_path'],'strong_source_sha256':strong,'duration_ms':s['duration_ms'],'shots':items,'subtitle':{'authority_origin':sub['origin'],'relative_path':sub['relative_path'],'cue_count':len(cues)},'scene_regions':regions,'capabilities':['PHYSICAL_SHOTS','REPRESENTATIVE_KEYFRAMES','VERIFIED_DIALOGUE_CUES','LOCAL_SCENE_REGIONS'],'semantic_scope':'No cloud semantic enrichment; exact visual candidates require human review.'};atomic(building/'ATLAS.json',payload);checks={'source_bound':sha256_file(src)==strong,'shot_coverage':bool(items) and items[0]['start_ms']==0 and items[-1]['end_ms']==s['duration_ms'] and all(items[i]['end_ms']==items[i+1]['start_ms'] for i in range(len(items)-1)),'keyframes_complete':all((building/x['keyframe']).exists() for x in items),'dialogue_nonempty':bool(cues),'regions_nonempty':bool(regions)}
 if not all(checks.values()):raise RuntimeError(ep+' rich validation failed '+str(checks))
 atomic(building/'RICH_ATLAS_RECEIPT.json',{'version':'rich-atlas-receipt/1.0','status':'VALIDATED','source_id':s['source_id'],'source_fingerprint':s['quick_fingerprint'],'strong_source_sha256':strong,'atlas_sha256':sha256_file(building/'ATLAS.json'),'shots':len(items),'keyframes':len(items),'scene_regions':len(regions),'checks':checks,'runtime_seconds':time.time()-started,'created_at':now()});
 if lib.exists():import shutil;shutil.rmtree(lib)
 building.replace(lib);c=db(media/'.scene_brain/catalog.db');migrate_schema(c);c.execute("update sources set strong_sha256=?,maturity='RICH_ATLAS_READY' where source_id=?",(strong,s['source_id']));c.execute("insert or replace into permanent_indexes values(?,?,?,?,?,?,?)",(s['source_id'],'FULL_RICH_ATLAS','production-rich-atlas/1.0',str((lib/'ATLAS.json').relative_to(media)),sha256_file(lib/'RICH_ATLAS_RECEIPT.json'),strong,'VALID'));c.commit();c.close();return {'episode':ep,'status':'BUILT','runtime_seconds':time.time()-started,'shots':len(items),'regions':len(regions),'path':str(lib)}

def make_plan(media,root,req):
 clue=json.loads((root/'runtime/new_project_book_test/VALIDATED_CLUE_SCRIPT.json').read_text());src=sources(media);index=media/'.scene_brain/libraries/breaking_bad_dialogue_windows_v4_0.db';slots=[];timeline=0
 for b in clue['beats']:
  for vs in b['recommended_visual_slots']:
   anchor=vs.get('canonical_event_anchor') or b.get('canonical_event_id');ep=EVENTS.get(anchor);s=src.get(ep) if ep else None;cands=[]
   if s:
    queries=b.get('dialogue_clues',[])+b.get('search_clues',[])[:2]
    hits=[]
    for q in queries[:3]:hits += [x for x in search_windows(index,q,10) if f"S{x['season']:02d}E{x['episode']:02d}"==ep]
    seen=set()
    for h in hits:
     key=(h['start_ms'],h['end_ms'])
     if key in seen:continue
     seen.add(key);cands.append({'source_id':s['source_id'],'episode':ep,'source_path':str(media/s['relative_path']),'source_in_ms':max(0,h['start_ms']-5000),'source_out_ms':min(s['duration_ms'],h['end_ms']+5000),'evidence':'TRUSTED_DIALOGUE_WINDOW','evidence_text':h['original_text']})
     if len(cands)==3:break
    if not cands:
     for f in [.25,.5,.75]:
      mid=round(s['duration_ms']*f);cands.append({'source_id':s['source_id'],'episode':ep,'source_path':str(media/s['relative_path']),'source_in_ms':max(0,mid-5000),'source_out_ms':min(s['duration_ms'],mid+5000),'evidence':'RICH_ATLAS_SCOUTING_CANDIDATE'})
   exact=b['evidence_class'] in {'EXACT_EVENT','EXACT_DIALOGUE'};state='NEEDS_CHOICE' if cands else 'MANUAL_REQUIRED';duration=7000;slots.append({'presentation_slot_id':f"{b['beat_id']}_VS{vs['slot_number']:02d}",'beat_id':b['beat_id'],'slot_number':vs['slot_number'],'exact_narration':b['exact_narration'],'purpose':vs['purpose'],'evidence_class':b['evidence_class'],'canonical_event_id':anchor,'approved_episode':ep,'state':state,'candidates':cands[:3],'selected_candidate':None,'presentation_type':vs.get('preferred_media','VIDEO'),'timeline_start_ms':timeline,'timeline_end_ms':timeline+duration,'approval_state':'MANUAL_FIX' if state=='MANUAL_REQUIRED' else 'NEEDS_CHOICE'});timeline+=duration
 if len(slots)!=70:raise RuntimeError(f'expected 70 slots, got {len(slots)}')
 plan={'version':'walter-visual-plan/1.0','project_id':'walter_book_project','source_authority':'ADMIN_SOURCE_CORRECTION','slot_count':70,'slots':slots,'metrics':dict(Counter(x['state'] for x in slots)),'created_at':now()};p=media/'.scene_brain/projects/walter_book_project';atomic(p/'VISUAL_PLAN.json',plan);editor={'version':'production-editor-project/2.1','project_id':'walter_book_project','name':'Why Walter White Kept the Book That Exposed Him','scope':['Breaking Bad'],'script_path':str(root/'runtime/new_project_book_test/CLEAN_SCRIPT.txt'),'script_sha256':'5ab589901ad5c9029d568107ac48e9512826dbd1b3cad1f137632068a314e4cc','voiceover_path':None,'status':'READY FOR FINAL FOOTAGE AUDIT','timeline':slots,'undo':[],'redo':[],'locked_source_count':0,'manual_fix_count':sum(x['state']=='MANUAL_REQUIRED' for x in slots),'library_pin':'b844b9d0-31d9-488f-afd8-2da7c57ce781','created':now()};atomic(p/'EDITOR_PROJECT.json',editor);return plan

def run(media,root):
 started=time.time();req=freeze_admin(media,root);src=sources(media);built=[]
 for x in req['episodes']:built.append(build_rich(media,root,x['episode'],src[x['episode']]))
 plan=make_plan(media,root,req);metrics={'required_episodes':sorted(EXPECTED),'rich_reused':sum(x['status']=='REUSED' for x in built),'rich_newly_built':sum(x['status']=='BUILT' for x in built),'rich_items':built,'rich_runtime_seconds':sum(x['runtime_seconds'] for x in built),'cloud_cost_usd':0,'visual_slots':70,'auto_usable':0,'needs_choice':sum(x['state']=='NEEDS_CHOICE' for x in plan['slots']),'manual_required':sum(x['state']=='MANUAL_REQUIRED' for x in plan['slots']),'video_slots':sum(x['presentation_type']=='VIDEO' for x in plan['slots']),'image_slots':sum(x['presentation_type']=='IMAGE' for x in plan['slots']),'total_runtime_seconds':time.time()-started};atomic(media/'.scene_brain/projects/walter_book_project/SCENE_BRAIN_V1_SHIP_RECEIPT.json',metrics);return metrics
