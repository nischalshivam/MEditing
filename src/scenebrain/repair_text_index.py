from __future__ import annotations
import json,sqlite3,time
from pathlib import Path
from .portable_library import db,episode,parse_sub,SUBS
from .search_integrity import digest
def repair(media:Path,out:Path):
 c=db(media/'.scene_brain/catalog.db');c.execute('drop table if exists subtitles_v2');c.execute('create table subtitles_v2(id integer primary key,source_id text,origin text,relative_path text,stream_index integer,language text,text text)');c.execute('drop table if exists subtitle_fts_v2');c.execute('create virtual table subtitle_fts_v2 using fts5(source_id UNINDEXED,text)');before=c.execute("select count(*) from subtitle_fts sf join sources s on s.source_id=sf.source_id join titles t on t.title_id=s.title_id where t.display_name='Breaking Bad'").fetchone()[0];built=[]
 for s in c.execute("select s.* from sources s join titles t on t.title_id=s.title_id where t.display_name='Breaking Bad' and s.present=1"):
  source=media/s['relative_path'];se,ep,_=episode(source.stem);side=[p for p in source.parent.iterdir() if p.suffix.lower() in SUBS and episode(p.stem)[:2]==(se,ep)]
  if side:
   for p in side:
    text=parse_sub(p)
    if text:c.execute('insert into subtitles_v2(source_id,origin,relative_path,text) values(?,?,?,?)',(s['source_id'],'SIDECAR',p.relative_to(media).as_posix(),text));c.execute('insert into subtitle_fts_v2 values(?,?)',(s['source_id'],text))
  else:
   # Preserve exact source-bound embedded-derived payload only.
   for old in c.execute("select * from subtitles where source_id=? and origin='EMBEDDED_DERIVED'",(s['source_id'],)):
    c.execute('insert into subtitles_v2(source_id,origin,relative_path,stream_index,language,text) values(?,?,?,?,?,?)',(old['source_id'],old['origin'],old['relative_path'],old['stream_index'],old['language'],old['text']));c.execute('insert into subtitle_fts_v2 values(?,?)',(old['source_id'],old['text']))
  built.append(f'S{se:02d}E{ep:02d}')
 c.commit();after=c.execute('select count(*) from subtitle_fts_v2').fetchone()[0];dups=c.execute('select count(*) from (select text,count(distinct source_id) n from subtitle_fts_v2 group by text having n>1)').fetchone()[0]
 if len(set(built))!=62 or after<62 or dups:raise ValueError(f'validation failed episodes={len(set(built))} rows={after} duplicates={dups}')
 backup=out/'failed_index_backup.json';backup.write_text(json.dumps({'before_rows':before,'reason':'unsafe prefix sidecar glob attached Episode 10-16 to Episode 1','preserved_failure_discovery':'runtime/new_project_book_test/PROJECT_SOURCE_DISCOVERY.json'},indent=2),encoding='utf8')
 c.executescript('alter table subtitles rename to subtitles_failed_v1;alter table subtitles_v2 rename to subtitles;drop table subtitle_fts;alter table subtitle_fts_v2 rename to subtitle_fts;');c.execute("update sources set maturity='SEARCHABLE' where source_id in (select distinct source_id from subtitles)");c.commit();receipt={'version':'search-index-repair/1.0','status':'ATOMICALLY_PROMOTED','episodes':62,'fts_rows_before':before,'fts_rows_after':after,'cross_episode_exact_duplicates_after':dups,'root_cause':'prefix glob p.stem* treated Episode 1 as prefix of Episode 10-16','whisper_runs':0,'media_modified':0};(out/'SEARCH_INDEX_REPAIR_RECEIPT.json').write_text(json.dumps(receipt,indent=2),encoding='utf8');c.close();return receipt
