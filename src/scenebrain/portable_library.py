from __future__ import annotations
import json,os,re,sqlite3,subprocess,time,uuid,hashlib
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
from pathlib import Path

MEDIA={'.mp4','.mkv','.avi','.mov','.m4v','.webm'};SUBS={'.srt','.vtt','.ass','.ssa'}
EP=[re.compile(r'(?i)S(\d{1,2})E(\d{1,3})(?:[-_. ]?E?(\d{1,3}))?'),re.compile(r'(?i)Season[ ._-]*(\d+).*Episode[ ._-]*(\d+)(?:.*(?:-|to).*?(\d+))?')]
CANON={'better call saul':'Better Call Saul','breaking bad':'Breaking Bad','game of thrones':'Game of Thrones','joker 2019':'Joker (2019)','the big bang theory':'The Big Bang Theory','young sheldon':'Young Sheldon'}
def now():return datetime.now(timezone.utc).isoformat()
def quick(p:Path):
 h=hashlib.sha256();size=p.stat().st_size
 with p.open('rb') as f:h.update(f.read(1024*1024));f.seek(max(0,size-1024*1024));h.update(f.read(1024*1024))
 h.update(str(size).encode());return h.hexdigest()
def episode(name):
 for r in EP:
  if m:=r.search(name):return int(m[1]),int(m[2]),int(m[3]) if m[3] else None
 return None,None,None
def probe(p:Path):
 x=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration,format_name:stream=index,codec_type,codec_name,width,height,avg_frame_rate:stream_tags=language,title','-of','json',str(p)],text=True,errors='replace'))
 v=next((s for s in x['streams'] if s.get('codec_type')=='video'),{});fps=v.get('avg_frame_rate','0/1');subs=[s for s in x['streams'] if s.get('codec_type')=='subtitle'];audio=[s for s in x['streams'] if s.get('codec_type')=='audio']
 return {'duration_ms':round(float(x.get('format',{}).get('duration') or 0)*1000),'container':x.get('format',{}).get('format_name'),'width':v.get('width'),'height':v.get('height'),'fps':fps,'video_codec':v.get('codec_name'),'audio_streams':audio,'subtitle_streams':subs}
def db(path):
 c=sqlite3.connect(path);c.row_factory=sqlite3.Row;c.executescript('''PRAGMA journal_mode=WAL;CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);CREATE TABLE IF NOT EXISTS titles(title_id TEXT PRIMARY KEY,display_name TEXT NOT NULL,kind TEXT NOT NULL,year INTEGER,relative_root TEXT NOT NULL UNIQUE);CREATE TABLE IF NOT EXISTS sources(source_id TEXT PRIMARY KEY,title_id TEXT NOT NULL,relative_path TEXT NOT NULL UNIQUE,size INTEGER NOT NULL,mtime_ns INTEGER NOT NULL,quick_fingerprint TEXT NOT NULL,strong_sha256 TEXT,duration_ms INTEGER,width INTEGER,height INTEGER,fps TEXT,container TEXT,video_codec TEXT,audio_json TEXT,subtitle_json TEXT,subtitle_status TEXT NOT NULL,maturity TEXT NOT NULL,present INTEGER NOT NULL DEFAULT 1,last_seen TEXT NOT NULL);CREATE TABLE IF NOT EXISTS subtitles(id INTEGER PRIMARY KEY,source_id TEXT NOT NULL,origin TEXT NOT NULL,relative_path TEXT,stream_index INTEGER,language TEXT,text TEXT NOT NULL);CREATE VIRTUAL TABLE IF NOT EXISTS subtitle_fts USING fts5(source_id UNINDEXED,text);CREATE TABLE IF NOT EXISTS franchises(franchise_id TEXT PRIMARY KEY,display_name TEXT NOT NULL);CREATE TABLE IF NOT EXISTS franchise_titles(franchise_id TEXT,title_id TEXT,PRIMARY KEY(franchise_id,title_id));CREATE TABLE IF NOT EXISTS scans(scan_id TEXT PRIMARY KEY,started TEXT,finished TEXT,receipt_path TEXT);CREATE TABLE IF NOT EXISTS migrations(id TEXT PRIMARY KEY,kind TEXT,payload_json TEXT,created TEXT);''');return c
def parse_sub(p:Path):
 try:s=p.read_text(encoding='utf-8-sig',errors='replace')
 except:return ''
 s=re.sub(r'(?m)^\d+\s*$|\d\d:\d\d:\d\d[,.]\d+\s+-->.*$|<[^>]+>|\{[^}]+\}',' ',s);return re.sub(r'\s+',' ',s).strip()
def scan(media_root:Path,workers=8):
 started=time.time();state=media_root/'.scene_brain';[ (state/x).mkdir(parents=True,exist_ok=True) for x in ['libraries','memory','projects','receipts','logs'] ];manifest_path=state/'volume_manifest.json'
 serial=os.environ.get('SCENEBRAIN_VOLUME_SERIAL','FAD16543');label=os.environ.get('SCENEBRAIN_VOLUME_LABEL','SSD')
 if manifest_path.exists():manifest=json.loads(manifest_path.read_text())
 else:manifest={'schema_version':'scene-brain-volume/1.0','scene_brain_volume_id':str(uuid.uuid4()),'volume_label':label,'filesystem':'NTFS','filesystem_serial':serial,'media_root_relative_path':'Movies','created_at':now()}
 manifest['last_seen_at']=now();manifest['last_resolved_media_root']=str(media_root);manifest_path.write_text(json.dumps(manifest,indent=2),encoding='utf8')
 c=db(state/'catalog.db');prior={r['relative_path']:dict(r) for r in c.execute('select * from sources')};files=sorted(p for p in media_root.rglob('*') if p.is_file() and '.scene_brain' not in p.parts and p.suffix.lower() in MEDIA)
 title_dirs={p.relative_to(media_root).parts[0] for p in files};titles={}
 for folder in sorted(title_dirs):
  display=CANON.get(folder.lower(),folder);kind='MOVIE' if folder.lower().startswith('joker') else 'SERIES';year=2019 if kind=='MOVIE' else None;tid='ttl_'+hashlib.sha256(display.lower().encode()).hexdigest()[:16];titles[folder]=(tid,display,kind,year);c.execute('insert or replace into titles values(?,?,?,?,?)',(tid,display,kind,year,folder))
 def work(p):
  rel=p.relative_to(media_root).as_posix();st=p.stat();old=prior.get(rel)
  if old and old['size']==st.st_size and old['mtime_ns']==st.st_mtime_ns:return rel,None,'unchanged'
  try:return rel,probe(p),'changed' if old else 'new'
  except Exception as e:return rel,{'error':str(e)[:500]},'error'
 results=[]
 with ThreadPoolExecutor(max_workers=workers) as ex:
  fut={ex.submit(work,p):p for p in files}
  for f in as_completed(fut):results.append((fut[f],*f.result()))
 counts={'new':0,'changed':0,'unchanged':0,'error':0,'missing':0,'moved':0}
 c.execute('update sources set present=0')
 for p,rel,info,status in results:
  counts[status]+=1;folder=Path(rel).parts[0];tid,display,kind,year=titles[folder];season,ep,epto=episode(p.stem);st=p.stat();q=quick(p) if status!='unchanged' else prior[rel]['quick_fingerprint'];sid='src_'+hashlib.sha256((manifest['scene_brain_volume_id']+'|'+rel).encode()).hexdigest()[:20]
  old=prior.get(rel);season,ep,_=episode(p.stem);side=[x for x in p.parent.iterdir() if x.suffix.lower() in SUBS and episode(x.stem)[:2]==(season,ep)];embedded=(info or {}).get('subtitle_streams',[]) if info else json.loads(prior[rel]['subtitle_json']);substatus='SIDECAR_AVAILABLE' if side else ('EMBEDDED_AVAILABLE' if embedded else 'TRANSCRIPT_REQUIRED');derived_searchable=bool(old and old.get('maturity')=='SEARCHABLE') or (state/'libraries/embedded_subtitles'/(sid+'.srt')).exists();maturity='SEARCHABLE' if side or derived_searchable else ('CATALOGED' if embedded else 'TRANSCRIPT_REQUIRED')
  d=info or prior[rel];c.execute('''insert into sources(source_id,title_id,relative_path,size,mtime_ns,quick_fingerprint,strong_sha256,duration_ms,width,height,fps,container,video_codec,audio_json,subtitle_json,subtitle_status,maturity,present,last_seen) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?) ON CONFLICT(relative_path) DO UPDATE SET size=excluded.size,mtime_ns=excluded.mtime_ns,quick_fingerprint=excluded.quick_fingerprint,duration_ms=excluded.duration_ms,width=excluded.width,height=excluded.height,fps=excluded.fps,container=excluded.container,video_codec=excluded.video_codec,audio_json=excluded.audio_json,subtitle_json=excluded.subtitle_json,subtitle_status=excluded.subtitle_status,maturity=CASE WHEN sources.maturity='RICH_ATLAS_READY' THEN sources.maturity ELSE excluded.maturity END,present=1,last_seen=excluded.last_seen''',(sid,tid,rel,st.st_size,st.st_mtime_ns,q,None,d.get('duration_ms',0),d.get('width'),d.get('height'),d.get('fps'),d.get('container'),d.get('video_codec'),json.dumps(d.get('audio_streams',[])),json.dumps(embedded),substatus,maturity,now()))
  if status!='unchanged' and side:
   c.execute('delete from subtitles where source_id=?',(sid,));c.execute('delete from subtitle_fts where source_id=?',(sid,))
   for sp in side:
    text=parse_sub(sp)
    if text:c.execute('insert into subtitles(source_id,origin,relative_path,text) values(?,?,?,?)',(sid,'SIDECAR',sp.relative_to(media_root).as_posix(),text));c.execute('insert into subtitle_fts(source_id,text) values(?,?)',(sid,text))
 missing=[r for rel,r in prior.items() if rel not in {x[1] for x in results}];counts['missing']=len(missing)
 # Moved detection by quick fingerprint among new/missing.
 newrows=[(rel,quick(p)) for p,rel,_,st in results if st=='new']
 for old in missing:
  if any(q==old['quick_fingerprint'] for _,q in newrows):counts['moved']+=1
 c.execute("insert or ignore into franchises values('breaking_bad_universe','Breaking Bad Universe')");c.execute("insert or ignore into franchises values('sheldon_universe','Sheldon Universe')")
 for fr,names in [('breaking_bad_universe',['Breaking Bad','Better Call Saul']),('sheldon_universe',['The Big Bang Theory','Young Sheldon'])]:
  for name in names:
   row=c.execute('select title_id from titles where display_name=?',(name,)).fetchone()
   if row:c.execute('insert or ignore into franchise_titles values(?,?)',(fr,row[0]))
 scanid='scan_'+uuid.uuid4().hex[:16];summary=[]
 for r in c.execute('''select t.title_id,t.display_name,t.kind,t.relative_root,count(s.source_id) detected,sum(s.subtitle_status='SIDECAR_AVAILABLE') sidecar,sum(s.subtitle_status='EMBEDDED_AVAILABLE') embedded,sum(s.subtitle_status='TRANSCRIPT_REQUIRED') transcript_required,sum(s.maturity='SEARCHABLE') searchable,sum(s.maturity='RICH_ATLAS_READY') rich,sum(s.maturity='ERROR') errors from titles t left join sources s on s.title_id=t.title_id and s.present=1 group by t.title_id order by t.display_name'''):summary.append(dict(r))
 receipt={'version':'library-scan-receipt/1.0','scan_id':scanid,'volume_identity':{k:manifest[k] for k in ['scene_brain_volume_id','volume_label','filesystem','filesystem_serial','media_root_relative_path']},'resolved_media_root':str(media_root),'titles':summary,'titles_detected':len(summary),'media_files_detected':len(files),'movies':sum(x['kind']=='MOVIE' for x in summary),'series':sum(x['kind']=='SERIES' for x in summary),'subtitle_coverage':{'sidecar':sum(x['sidecar'] for x in summary),'embedded':sum(x['embedded'] for x in summary),'transcript_required':sum(x['transcript_required'] for x in summary)},'searchable':sum(x['searchable'] for x in summary),'rich':sum(x['rich'] for x in summary),'incremental':counts,'errors':counts['error'],'scan_timestamp':now(),'runtime_seconds':time.time()-started,'mass_whisper_calls':0}
 rp=state/'receipts'/f'{scanid}.json';rp.write_text(json.dumps(receipt,indent=2),encoding='utf8');(state/'receipts/LIBRARY_SCAN_RECEIPT.json').write_text(json.dumps(receipt,indent=2),encoding='utf8');c.execute('insert into scans values(?,?,?,?)',(scanid,manifest['last_seen_at'],now(),rp.relative_to(state).as_posix()));c.commit();c.close();return receipt
def preflight(catalog:Path,requirements:list[dict]):
 c=db(catalog);rows=[]
 for req in requirements:
  title=c.execute('select * from titles where display_name=?',(req['title'],)).fetchone();src=None
  if title:
   if title['kind']=='MOVIE':src=c.execute('select * from sources where title_id=? and present=1',(title['title_id'],)).fetchone()
   else:
    # Parsing is performed dynamically from portable relative paths.
    for x in c.execute('select * from sources where title_id=? and present=1',(title['title_id'],)):
     s,e,_=episode(Path(x['relative_path']).stem)
     if s==req.get('season') and e==req.get('episode'):src=x;break
  status='MEDIA_MISSING' if not src else src['maturity'];rows.append({**req,'status':status,'cataloged':bool(src),'searchable':bool(src and src['maturity'] in ('SEARCHABLE','RICH_ATLAS_READY')),'rich':bool(src and src['maturity']=='RICH_ATLAS_READY'),'transcript_required':bool(src and src['subtitle_status']=='TRANSCRIPT_REQUIRED')})
 c.close();return {'requirements':rows,'ready_for_retrieval':all(x['rich'] and not x['transcript_required'] for x in rows),'new_rich_builds_required':sum(x['cataloged'] and not x['rich'] for x in rows),'transcripts_required':sum(x['transcript_required'] for x in rows),'missing_media':sum(x['status']=='MEDIA_MISSING' for x in rows)}

def extract_embedded(media_root:Path,workers=6):
 state=media_root/'.scene_brain';c=db(state/'catalog.db');rows=[dict(x) for x in c.execute("select * from sources where subtitle_status='EMBEDDED_AVAILABLE' and maturity!='SEARCHABLE' and present=1")];derived=state/'libraries/embedded_subtitles';derived.mkdir(parents=True,exist_ok=True)
 def one(x):
  src=media_root/Path(x['relative_path']);target=derived/(x['source_id']+'.srt');streams=json.loads(x['subtitle_json']);idx=streams[0]['index']
  p=subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-i',str(src),'-map',f'0:{idx}','-c:s','srt','-y',str(target)],capture_output=True,text=True)
  return x,target,parse_sub(target) if p.returncode==0 and target.exists() else '',p.stderr[-300:] if p.returncode else None
 results=[]
 with ThreadPoolExecutor(max_workers=workers) as ex:
  for z in ex.map(one,rows):results.append(z)
 ok=0;errors=[]
 for x,target,text,error in results:
  if text:
   c.execute('insert into subtitles(source_id,origin,relative_path,stream_index,text) values(?,?,?,?,?)',(x['source_id'],'EMBEDDED_DERIVED',target.relative_to(media_root).as_posix(),json.loads(x['subtitle_json'])[0]['index'],text));c.execute('insert into subtitle_fts(source_id,text) values(?,?)',(x['source_id'],text));c.execute("update sources set maturity='SEARCHABLE' where source_id=?",(x['source_id'],));ok+=1
  else:errors.append({'source_id':x['source_id'],'error':error})
 c.commit();c.close();return {'attempted':len(rows),'searchable':ok,'errors':errors}

def resolve_volume(manifest_path:Path,candidate_roots:list[Path]):
 manifest=json.loads(manifest_path.read_text())
 for root in candidate_roots:
  p=root/'.scene_brain/volume_manifest.json'
  if p.exists() and json.loads(p.read_text()).get('scene_brain_volume_id')==manifest['scene_brain_volume_id']:return root
 return None
