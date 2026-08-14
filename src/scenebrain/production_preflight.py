from __future__ import annotations
import json,sqlite3,uuid,hashlib,re
from datetime import datetime,timezone
from pathlib import Path
from .portable_library import db,episode,quick
from .hashing import sha256_file,fingerprint

JOB=['QUEUED','RUNNING','COMPLETE','FAILED','CANCELLED','NOT_REQUIRED']
def now():return datetime.now(timezone.utc).isoformat()
def migrate_schema(c):
 c.executescript('''CREATE TABLE IF NOT EXISTS transcript_jobs(job_id TEXT PRIMARY KEY,source_id TEXT NOT NULL,status TEXT NOT NULL,config_json TEXT NOT NULL,source_fingerprint TEXT NOT NULL,output_path TEXT,error TEXT,created TEXT NOT NULL,updated TEXT NOT NULL);CREATE TABLE IF NOT EXISTS rich_jobs(job_id TEXT PRIMARY KEY,source_id TEXT NOT NULL,status TEXT NOT NULL,version TEXT NOT NULL,source_fingerprint TEXT NOT NULL,output_path TEXT,error TEXT,created TEXT NOT NULL,updated TEXT NOT NULL);CREATE TABLE IF NOT EXISTS permanent_indexes(source_id TEXT,index_type TEXT,version TEXT,path TEXT,receipt_sha256 TEXT,strong_source_sha256 TEXT,status TEXT,PRIMARY KEY(source_id,index_type,version));CREATE TABLE IF NOT EXISTS project_preflights(project_id TEXT PRIMARY KEY,script_sha256 TEXT NOT NULL,voiceover_sha256 TEXT,scope_json TEXT NOT NULL,receipt_path TEXT NOT NULL,ready INTEGER NOT NULL,library_pin_json TEXT NOT NULL,created TEXT NOT NULL);''');c.commit()
def register_legacy(media_root:Path,project_root:Path):
 c=db(media_root/'.scene_brain/catalog.db');migrate_schema(c);row=c.execute("select s.* from sources s join titles t on t.title_id=s.title_id where t.display_name='Breaking Bad' and s.relative_path like '%Season 4 Episode 1.%'").fetchone();atlas=project_root/'runtime/scene_atlas/S04E01_SCENE_CARDS.json';receipt={'version':'legacy-index-migration/1.0','items':[],'created':now()}
 if row and atlas.exists():
  src=media_root/row['relative_path'];strong=sha256_file(src);cards=json.loads(atlas.read_text());status='FULL_RICH_ATLAS' if len(cards)==13 and all('scene_id' in x and 'start_shot' in x and 'end_shot' in x and 'start_ms' in x and 'end_ms' in x and 'main_event' in x for x in cards) else 'PARTIAL_INDEX';target=media_root/'.scene_brain/libraries'/row['source_id']/'legacy_s04e01_scene_atlas';target.mkdir(parents=True,exist_ok=True);copy=target/atlas.name;copy.write_bytes(atlas.read_bytes());item={'source_id':row['source_id'],'episode':'S04E01','index_type':status,'path':str(copy.relative_to(media_root)), 'source_strong_sha256':strong,'atlas_sha256':sha256_file(copy),'historical_source':str(atlas),'historical_unchanged':sha256_file(atlas)==sha256_file(copy)};receipt['items'].append(item);c.execute('insert or replace into permanent_indexes values(?,?,?,?,?,?,?)',(row['source_id'],status,'legacy-v2-s04e01',item['path'],item['atlas_sha256'],strong,'VALID'))
  if status=='FULL_RICH_ATLAS':c.execute("update sources set strong_sha256=?,maturity='RICH_ATLAS_READY' where source_id=?",(strong,row['source_id']))
 # Repair-scoped structures are registered truthfully as partial only.
 for p in (project_root/'runtime/sprint13_repair/atlases').glob('*/ATLAS_V2.json'):
  x=json.loads(p.read_text());ep=x['episode'];s,e,_=episode(ep);srcrow=None
  for z in c.execute("select s.* from sources s join titles t on t.title_id=s.title_id where t.display_name='Breaking Bad'"):
   ss,ee,_=episode(Path(z['relative_path']).stem)
   if (ss,ee)==(s,e):srcrow=z;break
  if srcrow:receipt['items'].append({'source_id':srcrow['source_id'],'episode':ep,'index_type':'PARTIAL_INDEX','path':str(p),'reason':'repair-scoped cue atlas is not full V2'})
 rp=media_root/'.scene_brain/receipts/LEGACY_INDEX_MIGRATION_RECEIPT.json';rp.write_text(json.dumps(receipt,indent=2),encoding='utf8');c.commit();c.close();return receipt
def enqueue_transcripts(catalog:Path,title:str,source_ids:list[str]|None=None,config=None):
 c=db(catalog);migrate_schema(c);q="select s.* from sources s join titles t on t.title_id=s.title_id where t.display_name=? and s.present=1 and s.subtitle_status='TRANSCRIPT_REQUIRED'";rows=list(c.execute(q,(title,)));rows=[x for x in rows if not source_ids or x['source_id'] in source_ids];created=[]
 for x in rows:
  existing=c.execute("select * from transcript_jobs where source_id=? and status='COMPLETE'",(x['source_id'],)).fetchone()
  if existing:continue
  jid='tx_'+uuid.uuid4().hex[:16];cfg=config or {'model':'base.en','device':'cpu','compute_type':'int8','word_timestamps':True};c.execute('insert into transcript_jobs values(?,?,?,?,?,?,?,?,?)',(jid,x['source_id'],'QUEUED',json.dumps(cfg),x['quick_fingerprint'],None,None,now(),now()));created.append(jid)
 c.commit();c.close();return created
def set_job_status(catalog:Path,job_id,status,error=None):
 if status not in JOB:raise ValueError(status)
 c=db(catalog);migrate_schema(c);c.execute('update transcript_jobs set status=?,error=?,updated=? where job_id=?',(status,error,now(),job_id));c.commit();c.close()
def validate_transcript(words:list[dict],duration_ms:int):
 if not words:return {'healthy':False,'reason':'EMPTY'}
 if any(words[i]['start_ms']>words[i+1]['start_ms'] for i in range(len(words)-1)):return {'healthy':False,'reason':'NON_MONOTONIC'}
 if words[-1]['end_ms']>duration_ms+1000:return {'healthy':False,'reason':'OUT_OF_BOUNDS'}
 toks=[str(x.get('token','')).lower() for x in words];top=max(Counter(toks).values())/len(toks) if toks else 1
 return {'healthy':len(words)>=5 and top<.35,'reason':None if len(words)>=5 and top<.35 else 'IMPLAUSIBLE_DENSITY','word_count':len(words)}
def search_title_dialogue(catalog:Path,title:str,queries:list[str],limit=20):
 c=db(catalog);out=[]
 for q in queries:
  tokens=re.findall(r"[A-Za-z0-9]+",q)[:8];phrase='"'+' '.join(tokens)+'"';terms=tokens[0] if len(tokens)==1 else phrase
  if not terms:continue
  rows=list(c.execute('''select s.source_id,s.relative_path,sf.text,bm25(subtitle_fts) score from subtitle_fts sf join sources s on s.source_id=sf.source_id join titles t on t.title_id=s.title_id where t.display_name=? and subtitle_fts match ? order by score limit ?''',(title,terms,limit)))
  if not rows:rows=list(c.execute('''select s.source_id,s.relative_path,sf.text,bm25(subtitle_fts) score from subtitle_fts sf join sources s on s.source_id=sf.source_id join titles t on t.title_id=s.title_id where t.display_name=? and subtitle_fts match ? order by score limit ?''',(title,' AND '.join(tokens),limit)))
  for r in rows:
   text=r['text'];low=text.lower();positions=[low.find(x.lower()) for x in tokens if low.find(x.lower())>=0];at=min(positions) if positions else 0;snippet=text[max(0,at-120):min(len(text),at+300)];se,ep,_=episode(Path(r['relative_path']).stem);out.append({'title':title,'season':se,'episode':ep,'source_id':r['source_id'],'relative_path':r['relative_path'],'match_score':r['score'],'query':q,'evidence_text':snippet,'matched_terms':[x for x in tokens if x.lower() in low]})
 c.close();return sorted(out,key=lambda x:x['match_score'])[:limit]
def title_status(c,title):
 r=c.execute('''select count(*) cataloged,sum(s.maturity in ('SEARCHABLE','RICH_ATLAS_READY')) searchable,sum(s.maturity='RICH_ATLAS_READY') rich,sum(s.subtitle_status='TRANSCRIPT_REQUIRED') transcript_required from sources s join titles t on t.title_id=s.title_id where t.display_name=? and s.present=1''',(title,)).fetchone();return dict(r) if r else {'cataloged':0,'searchable':0,'rich':0,'transcript_required':0}
def preflight_project(catalog:Path,project_id:str,script:Path,scope:list[str],grounded_sources:list[dict]|None=None,voiceover:Path|None=None):
 c=db(catalog);migrate_schema(c);grounded_sources=grounded_sources or [];statuses={t:title_status(c,t) for t in scope};requirements=[];ambiguous=[];bootstrap=[]
 for title in scope:
  gs=[x for x in grounded_sources if x['title']==title]
  if gs:
   for g in gs:
    src=None
    for x in c.execute('select s.* from sources s join titles t on t.title_id=s.title_id where t.display_name=? and s.present=1',(title,)):
     se,ep,_=episode(Path(x['relative_path']).stem)
     if (se,ep)==(g.get('season'),g.get('episode')) or (g.get('movie') and title==g.get('movie')):src=x;break
    requirements.append({**g,'routing_state':'VERIFIED_LOCAL' if src else 'UNRESOLVED','routing_mode':'GROUNDED_SOURCE_MODE','source_id':src['source_id'] if src else None,'maturity':src['maturity'] if src else 'MEDIA_MISSING','local_evidence':g.get('local_evidence',[])})
  else:
   st=statuses[title]
   if st['searchable']==0:bootstrap.append({'title':title,'status':'SEARCHABILITY_BOOTSTRAP_REQUIRED',**st})
   else:ambiguous.append({'title':title,'state':'UNRESOLVED','reason':'script clue routing not yet executed','routing_mode':'DISCOVERY_MODE','partial_searchability_gaps':st['cataloged']-st['searchable']})
 ready=bool(requirements) and not bootstrap and not ambiguous and all(x['maturity']=='RICH_ATLAS_READY' for x in requirements)
 receipt={'version':'project-preflight/1.0','project_id':project_id,'script_sha256':sha256_file(script),'voiceover_sha256':sha256_file(voiceover) if voiceover else None,'scope':scope,'title_status':statuses,'required_sources':requirements,'searchability_bootstrap':bootstrap,'ambiguous_sources':ambiguous,'ready_for_retrieval':ready,'gate_reason':None if ready else 'PREREQUISITES_UNSATISFIED','library_pin':{'catalog_path':str(catalog),'volume_id':json.loads((catalog.parent/'volume_manifest.json').read_text())['scene_brain_volume_id']},'created':now()}
 rp=catalog.parent/'projects'/project_id/'PROJECT_PREFLIGHT_RECEIPT.json';rp.parent.mkdir(parents=True,exist_ok=True);rp.write_text(json.dumps(receipt,indent=2),encoding='utf8');c.execute('insert or replace into project_preflights values(?,?,?,?,?,?,?,?)',(project_id,receipt['script_sha256'],receipt['voiceover_sha256'],json.dumps(scope),str(rp.relative_to(catalog.parent)),int(ready),json.dumps(receipt['library_pin']),now()));c.commit();c.close();return receipt
from collections import Counter

def enqueue_rich(catalog:Path,source_ids:list[str],version='rich-atlas-v2'):
 c=db(catalog);migrate_schema(c);created=[]
 for sid in source_ids:
  x=c.execute('select * from sources where source_id=? and present=1',(sid,)).fetchone()
  if not x:continue
  jid='rich_'+uuid.uuid4().hex[:16];c.execute('insert into rich_jobs values(?,?,?,?,?,?,?,?,?)',(jid,sid,'QUEUED',version,x['quick_fingerprint'],None,None,now(),now()));created.append(jid)
 c.commit();c.close();return created
def promote_rich_atomic(catalog:Path,job_id:str,receipt:Path):
 c=db(catalog);migrate_schema(c);j=c.execute('select * from rich_jobs where job_id=?',(job_id,)).fetchone()
 if not j or j['status']!='RUNNING' or not receipt.is_file():c.close();raise ValueError('validated RUNNING job receipt required')
 x=c.execute('select * from sources where source_id=?',(j['source_id'],)).fetchone();payload=json.loads(receipt.read_text())
 if payload.get('source_fingerprint')!=x['quick_fingerprint'] or payload.get('status')!='VALIDATED':c.close();raise ValueError('rich receipt invalid')
 with c:c.execute("update rich_jobs set status='COMPLETE',output_path=?,updated=? where job_id=?",(str(receipt),now(),job_id));c.execute("update sources set maturity='RICH_ATLAS_READY' where source_id=?",(j['source_id'],))
 c.close()
