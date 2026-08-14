from __future__ import annotations
import hashlib,json,re,sqlite3,time
from collections import defaultdict
from pathlib import Path
from .portable_library import db,episode

def normalized(text):return re.sub(r'\s+',' ',re.sub(r'[^a-z0-9 ]',' ',text.lower())).strip()
def digest(text):return hashlib.sha256(normalized(text).encode()).hexdigest()
def audit(media:Path,out:Path,title='Breaking Bad'):
 started=time.time();out.mkdir(parents=True,exist_ok=True);c=db(media/'.scene_brain/catalog.db');rows=[];payloads=defaultdict(list);fts_mismatch=[]
 sources=list(c.execute('select s.* from sources s join titles t on t.title_id=s.title_id where t.display_name=? and s.present=1 order by s.relative_path',(title,)))
 for s in sources:
  se,ep,_=episode(Path(s['relative_path']).stem);subs=list(c.execute('select * from subtitles where source_id=? order by id',(s['source_id'],)));fts=list(c.execute('select rowid,* from subtitle_fts where source_id=?',(s['source_id'],)));assets=[]
  for x in subs:
   text=x['text'];h=digest(text);payloads[h].append((se,ep,s['source_id'],x['id'],x['relative_path']));p=media/x['relative_path'] if x['relative_path'] else None
   assets.append({'subtitle_id':x['id'],'origin':x['origin'],'relative_path':x['relative_path'],'path_exists':bool(p and p.exists()),'subtitle_hash':h,'cue_count':len(re.findall(r'\b\d{2}:\d{2}:\d{2}[,.]\d{3}\b',p.read_text(errors='replace') if p and p.exists() else ''))//2,'normalized_word_count':len(normalized(text).split()),'first_hash':hashlib.sha256(' '.join(normalized(text).split()[:100]).encode()).hexdigest(),'middle_hash':hashlib.sha256(' '.join(normalized(text).split()[max(0,len(normalized(text).split())//2-50):len(normalized(text).split())//2+50]).encode()).hexdigest(),'last_hash':hashlib.sha256(' '.join(normalized(text).split()[-100:]).encode()).hexdigest()})
  subtexts=defaultdict(int)
  for x in subs:subtexts[digest(x['text'])]+=1
  for x in fts:
   if digest(x['text']) not in subtexts:fts_mismatch.append({'fts_rowid':x['rowid'],'source_id':s['source_id'],'reason':'NO_MATCHING_SUBTITLE_PAYLOAD'})
  rows.append({'episode':f'S{se:02d}E{ep:02d}','source_id':s['source_id'],'relative_media_path':s['relative_path'],'duration_ms':s['duration_ms'],'subtitle_status':s['subtitle_status'],'maturity':s['maturity'],'subtitle_assets':assets,'subtitle_asset_count':len(assets),'fts_row_count':len(fts),'duplicate_rows_within_source':len(assets)-len(set(x['subtitle_hash'] for x in assets))})
 duplicates=[]
 for h,items in payloads.items():
  eps={(x[0],x[1]) for x in items}
  if len(eps)>1:duplicates.append({'transcript_hash':h,'bindings':[{'episode':f'S{x[0]:02d}E{x[1]:02d}','source_id':x[2],'subtitle_id':x[3],'subtitle_path':x[4]} for x in items],'similarity':1.0})
 (out/'BREAKING_BAD_TRANSCRIPT_SOURCE_MAP.json').write_text(json.dumps(rows,indent=2),encoding='utf8');(out/'CROSS_EPISODE_TRANSCRIPT_DUPLICATES.json').write_text(json.dumps(duplicates,indent=2),encoding='utf8')
 audit={'source_count':len(sources),'subtitle_rows':sum(x['subtitle_asset_count'] for x in rows),'fts_rows':sum(x['fts_row_count'] for x in rows),'fts_payload_mismatches':fts_mismatch,'sources_with_multiple_rows':sum(x['subtitle_asset_count']>1 for x in rows),'within_source_duplicate_rows':sum(x['duplicate_rows_within_source'] for x in rows),'cross_episode_identical_payloads':len(duplicates)};(out/'FTS_INTEGRITY_AUDIT.json').write_text(json.dumps(audit,indent=2),encoding='utf8')
 metrics={**audit,'source_verified':sum(x['subtitle_asset_count']>0 and x['fts_row_count']>0 and not any(not a['path_exists'] for a in x['subtitle_assets']) for x in rows),'searchable_ready':0,'whisper_runs':0,'source_files_modified':0,'runtime_seconds':time.time()-started};(out/'metrics.json').write_text(json.dumps(metrics,indent=2),encoding='utf8');c.close();return metrics
