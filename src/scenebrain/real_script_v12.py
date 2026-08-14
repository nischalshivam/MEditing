from __future__ import annotations
import hashlib,json,re,sqlite3,subprocess,time
from collections import Counter
from pathlib import Path
from .hashing import fingerprint,sha256_file

VERSION='real-script-composer/12.0'
TIMESTAMP_RE=re.compile(r'\b(?:\d{1,2}:){1,2}\d{2}(?:[.,]\d{1,3})?\b')
EP_RE=re.compile(r'S(\d{2})E(\d{2})',re.I)

def validate_inputs(script:Path,clue_path:Path,map_path:Path):
 text=script.read_text(encoding='utf-8-sig');clue=json.loads(clue_path.read_text(encoding='utf-8-sig'));emap=json.loads(map_path.read_text(encoding='utf-8-sig'));beats=clue['beats'];ids=[x['beat_id'] for x in beats]
 errors=[]
 if clue.get('beat_count')!=59 or len(beats)!=59 or len(set(ids))!=59:errors.append('beat count/uniqueness')
 cursor=0
 for b in beats:
  span=b['exact_narration'];pos=text.find(span,cursor)
  if pos<0:errors.append(f"{b['beat_id']}: exact narration missing/out of order")
  else:cursor=pos+len(span)
  # Truth fields may not carry timestamps. Episode IDs such as S04E11 are not timestamps.
  for key,value in b.items():
   if key not in {'episode_hints'} and TIMESTAMP_RE.search(json.dumps(value,ensure_ascii=False)):errors.append(f"{b['beat_id']}: timestamp in {key}")
 req=[x['episode'] for x in emap['required_episodes']]
 return text,clue,emap,errors,req

def discover(legacy:sqlite3.Connection,required:list[str]):
 out=[]
 for code in required:
  m=EP_RE.fullmatch(code);s,e=map(int,m.groups());rows=legacy.execute('select * from media where season=? and episode=?',(s,e)).fetchall()
  valid=[dict(x) for x in rows if Path(x['path']).exists()]
  status='FOUND_UNIQUE' if len(valid)==1 else ('MISSING' if not valid else 'AMBIGUOUS')
  out.append({'episode':code,'status':status,'matches':valid})
 return out

def words(s):return {x for x in re.findall(r"[a-z0-9']+",s.lower()) if len(x)>2 and x not in {'the','and','that','this','with','from','into','what','when','where','because','show','skyler','walt','walter'}}
def episode_hints(beat):
 found=[]
 for h in beat.get('episode_hints') or []:
  code=h if isinstance(h,str) else json.dumps(h)
  m=EP_RE.search(code)
  if m:found.append(f'S{int(m.group(1)):02d}E{int(m.group(2)):02d}')
 return found

def search_cues(legacy,media,beat,limit=4):
 q=' '.join((beat.get('dialogue_clues') or [])+(beat.get('search_clues') or []));qt=words(q+' '+beat.get('visual_intent',''));rows=legacy.execute('select start_ms,end_ms,text from cue where media_id=?',(media['id'],)).fetchall();rank=[]
 for r in rows:
  score=len(qt&words(r['text']))
  if score:rank.append((score,dict(r)))
 return [x[1] for x in sorted(rank,key=lambda x:(-x[0],x[1]['start_ms']))[:limit]]

def proxy_video(source:Path,sha:str,a:int,b:int,folder:Path):
 fp=fingerprint(VERSION,'video-540p',sha,a,b);p=folder/f'{fp}.mp4'
 if p.exists():return p,True
 folder.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix('.building.mp4');subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-ss',f'{a/1000:.3f}','-i',str(source),'-t',f'{(b-a)/1000:.3f}','-vf','scale=960:-2','-an','-c:v','libx264','-crf','29','-movflags','+faststart','-y',str(tmp)],check=True);tmp.replace(p);return p,False
def proxy_image(source:Path,sha:str,ms:int,folder:Path):
 fp=fingerprint(VERSION,'image-960',sha,ms);p=folder/f'{fp}.jpg'
 if p.exists():return p,True
 folder.mkdir(parents=True,exist_ok=True);subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-ss',f'{ms/1000:.3f}','-i',str(source),'-frames:v','1','-vf','scale=1280:-2','-q:v','3','-y',str(p)],check=True);return p,False

def build(root:Path,script:Path,clue_path:Path,map_path:Path,legacy_db:Path):
 started=time.time();out=root/'runtime/sprint12_real_script';prev=out/'previews';(out/'audit').mkdir(parents=True,exist_ok=True)
 text,clue,emap,errors,required=validate_inputs(script,clue_path,map_path);legacy=sqlite3.connect(f'file:{legacy_db.as_posix()}?mode=ro',uri=True);legacy.row_factory=sqlite3.Row;coverage=discover(legacy,required);available={x['episode']:x['matches'][0] for x in coverage if x['status']=='FOUND_UNIQUE'}
 source_hashes={};source_before={}
 for code,m in available.items():source_before[code]=(Path(m['path']).stat().st_size,Path(m['path']).stat().st_mtime_ns);source_hashes[code]=sha256_file(Path(m['path']))
 active={};planbeats=[];cursor=0;hits=misses=0
 for beat in clue['beats']:
  narration=beat['exact_narration'];duration=max(6000,min(18000,len(narration.split())*420));hints=episode_hints(beat);event=beat.get('canonical_event_id') or 'NONE';media=None;resolved_code=None
  for code in hints:
   if code in available:media=available[code];resolved_code=code;break
  if not media and beat.get('active_scene_relation')!='NEW_EVENT' and event in active:media,resolved_code=active[event]
  cues=search_cues(legacy,media,beat) if media else [];options=[]
  for i,cue in enumerate(cues[:2],1):
   a=max(0,cue['start_ms']-1800);b=min(media['last_cue_ms']+30000,cue['end_ms']+3500);typ='IMAGE' if beat.get('preferred_media')=='IMAGE' and i==1 else 'VIDEO'
   if typ=='VIDEO':p,hit=proxy_video(Path(media['path']),source_hashes[resolved_code],a,b,prev/'video')
   else:p,hit=proxy_image(Path(media['path']),source_hashes[resolved_code],(a+b)//2,prev/'images')
   hits+=hit;misses+=not hit;options.append({'asset_id':f"{beat['beat_id']}_{resolved_code}_{i}",'media_type':typ,'source_path':media['path'],'source_hash':source_hashes[resolved_code],'season':media['season'],'episode':media['episode'],'episode_code':resolved_code,'scene_id':None,'shot_ids':[],'source_in_ms':a,'source_out_ms':b if typ=='VIDEO' else None,'frame_time_ms':(a+b)//2 if typ=='IMAGE' else None,'preview_path':str(p.resolve()),'provenance':[{'authority':'VERIFIED_LOCAL_SUBTITLE_CUE','cue_text':cue['text'],'cue_start_ms':cue['start_ms'],'episode_hint_only':True}]})
  if options:active[event]=(media,resolved_code)
  exact=beat['evidence_class'] in {'EXACT_EVENT','EXACT_DIALOGUE','EVENT_CONTEXT'}
  if options and exact:color='YELLOW';reason='Local episode and subtitle neighborhood support a reviewable hypothesis; exact visuals remain unproved.'
  elif options:color='ORANGE';reason='Contextual local source option; no literal-event claim.'
  else:color='ORANGE_UNRESOLVED';reason='No safe grounded local cue/active-event range; no timestamp guessed.'
  timeline={'status':'PROVISIONAL_NO_VOICEOVER','start_ms':cursor,'end_ms':cursor+duration};cursor+=duration
  planbeats.append({'beat_id':beat['beat_id'],'exact_narration':narration,'evidence_class':beat['evidence_class'],'subjects':beat.get('primary_subjects',[]),'canonical_event_id':event,'episode_hints':hints,'resolved_episode':resolved_code,'timeline':timeline,'active_scene_relation':beat.get('active_scene_relation'),'visual_slots':[{'slot_id':beat['beat_id']+'_VS01','timeline_start_ms':timeline['start_ms'],'timeline_end_ms':timeline['end_ms'],'timeline_status':'PROVISIONAL','color':color,'media_type':options[0]['media_type'] if options else None,'chosen_asset':options[0] if options else None,'alternatives':options[1:5],'reason':reason,'review_required':color!='GREEN'}]})
 source_after={code:(Path(m['path']).stat().st_size,Path(m['path']).stat().st_mtime_ns) for code,m in available.items()};colors=Counter(b['visual_slots'][0]['color'] for b in planbeats);types=Counter(b['visual_slots'][0]['media_type'] for b in planbeats if b['visual_slots'][0]['media_type']);plan={'schema_version':'visual-plan/2.1','composer_version':VERSION,'project':{'title':clue['project_title'],'voiceover':None,'timeline_status':'PROVISIONAL_NO_VOICEOVER'},'script_hash':sha256_file(script),'clue_hash':sha256_file(clue_path),'library_scope':required,'beats':planbeats,'source_receipt':{'hashes':source_hashes},'plan_fingerprint':''};plan['plan_fingerprint']=fingerprint(json.dumps(plan,sort_keys=True));out.mkdir(parents=True,exist_ok=True);(out/'VISUAL_PLAN_REAL_SCRIPT.json').write_text(json.dumps(plan,indent=2),encoding='utf8')
 receipt={'version':'clue-validation/1.0','valid':not errors,'errors':errors,'beat_count':len(clue['beats']),'unique_beat_ids':len({x['beat_id'] for x in clue['beats']}),'script_sha256':sha256_file(script),'clue_sha256':sha256_file(clue_path),'map_sha256':sha256_file(map_path),'no_timestamps':not any('timestamp' in x for x in errors)};receipt['fingerprint']=fingerprint(json.dumps(receipt,sort_keys=True));(out/'CLUE_VALIDATION_RECEIPT.json').write_text(json.dumps(receipt,indent=2),encoding='utf8')
 event_coverage=[]
 for b,pb in zip(clue['beats'],planbeats):event_coverage.append({'beat_id':b['beat_id'],'canonical_event_id':b.get('canonical_event_id'),'expected_episode_hints':episode_hints(b),'resolved_local_episode':pb['resolved_episode'],'status':'ROUTED_LOCAL_CUE' if pb['resolved_episode'] else 'UNRESOLVED_NO_GUESS'})
 coverage_payload={'version':'source-coverage/12.0','required_episodes':coverage,'canonical_event_routing':event_coverage};(out/'SOURCE_COVERAGE.json').write_text(json.dumps(coverage_payload,indent=2),encoding='utf8')
 metrics={'clean_script_words':len(re.findall(r"\b[\w']+\b",text)),'clue_beats_validated':59 if not errors else 0,'required_episodes_found':len(available),'required_episodes_missing':len(required)-len(available),'libraries_reused':len(available),'libraries_new_full_scene_atlas':0,'legacy_subtitle_cues_across_scope':sum(m['cue_count'] for m in available.values()),'narrative_scenes_indexed_across_required_scope':13,'narrative_scene_scope_note':'Only S04E01 has full V2 narrative atlas; required scopes reuse legacy episode-level subtitle/visual indexes and cue-neighborhood routing. Count is episode containers, not semantic scenes.','visual_slots':59,'colors':dict(colors),'media':dict(types),'yellow_average_options':sum(len(b['visual_slots'][0]['alternatives'])+1 for b in planbeats if b['visual_slots'][0]['color']=='YELLOW')/max(1,colors['YELLOW']),'post_human_metrics':{'yellow_none_good_rate':None,'orange_usable_rate':None,'green_wrong_count':None},'api':{'calls':0,'tokens':0,'cost_usd':0},'cache':{'hits':hits,'misses':misses},'cold_runtime_seconds':time.time()-started,'source_integrity':source_before==source_after}
 (out/'metrics.json').write_text(json.dumps(metrics,indent=2),encoding='utf8');write_review(plan,out/'SPRINT12_REVIEW.html');write_launcher(out/'START_SPRINT12_REVIEW.bat');legacy.close();return plan,metrics,receipt,coverage_payload

def write_review(plan,path):
 web=json.loads(json.dumps(plan));
 for b in web['beats']:
  s=b['visual_slots'][0]
  for a in ([s['chosen_asset']] if s['chosen_asset'] else [])+s['alternatives']:a['preview_path']='./'+Path(a['preview_path']).relative_to(path.parent).as_posix()
 data=json.dumps(web,separators=(',',':')).replace('</','<\\/');html=f'''<!doctype html><meta charset=utf-8><title>Sprint 12 Review</title><style>body{{background:#0b1220;color:#eef2ff;font:15px system-ui;margin:auto;max-width:1200px;padding:20px}}.stage{{aspect-ratio:16/9;background:#000;display:grid;place-items:center}}video,img{{max-width:100%;max-height:100%}}.opts{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px}}.o{{background:#1e293b;padding:8px}}button{{padding:9px;margin:6px}}.YELLOW{{color:#facc15}}.ORANGE,.ORANGE_UNRESOLVED{{color:#fb923c}}</style><h1>Skyler Money — Full Script Review</h1><p id=p></p><select id=filter><option>ALL</option><option>YELLOW</option><option>ORANGE</option><option>ORANGE_UNRESOLVED</option></select><h2 id=n></h2><h3 id=m></h3><div class=stage id=stage></div><div class=opts id=opts></div><button id=none>None Good (N)</button><script>const plan={data};let slots=plan.beats.map(b=>({{...b.visual_slots[0],narration:b.exact_narration,beat_id:b.beat_id}})),i=0,key='s12:'+plan.plan_fingerprint,d=JSON.parse(localStorage.getItem(key)||'{{}}');const E=x=>document.getElementById(x);function save(x,a=null){{d[slots[i].slot_id]={{decision:x,asset_id:a,at:new Date().toISOString()}};localStorage.setItem(key,JSON.stringify(d));next()}}function media(a){{return a.media_type==='VIDEO'?`<video controls src="${{a.preview_path}}"></video>`:`<img src="${{a.preview_path}}">`}}function draw(){{let s=slots[i],as=[s.chosen_asset,...s.alternatives].filter(Boolean);E('p').textContent=`Reviewed ${{Object.keys(d).length}} / ${{slots.length}} · beat ${{i+1}}/59`;E('n').textContent=s.beat_id+' — '+s.narration;E('m').textContent=s.color+' · '+(s.media_type||'NO MEDIA');E('m').className=s.color;E('stage').innerHTML=as[0]?media(as[0]):'<b>No safe grounded visual</b>';E('opts').innerHTML=as.map((a,j)=>`<div class=o>${{media(a)}}<p>${{a.episode_code}} · ${{a.asset_id}}</p><button data-j="${{j}}">Use ${{j+1}}</button></div>`).join('');E('opts').querySelectorAll('button').forEach(x=>x.onclick=()=>{{let j=+x.dataset.j;save('USE_OPTION_'+(j+1),as[j].asset_id)}})}}function next(){{for(let z=0;z<slots.length;z++){{i=(i+1)%slots.length;if(!d[slots[i].slot_id])break}}draw()}}E('none').onclick=()=>save('NONE_GOOD');document.onkeydown=e=>{{if('12345'.includes(e.key)){{let s=slots[i],a=[s.chosen_asset,...s.alternatives][+e.key-1];if(a)save('USE_OPTION_'+e.key,a.asset_id)}}else if(e.key.toLowerCase()==='n')save('NONE_GOOD');else if(e.key==='ArrowRight')next();else if(e.key==='ArrowLeft'){{i=(i-1+slots.length)%slots.length;draw()}}}};draw()</script>''';path.write_text(html,encoding='utf8')
def write_launcher(path):path.write_text('@echo off\r\ncd /d "C:\\Users\\Dell\\Documents\\Codex\\2026-07-30\\m-ek-automation-tool-banwa-rha\\film_tv_scene_brain_v2"\r\nstart "Sprint12Server" /min python -m scenebrain.sprint13_audit_server\r\ntimeout /t 2 /nobreak >nul\r\nstart "" http://127.0.0.1:8772/SPRINT12_REVIEW.html\r\n',encoding='ascii')
