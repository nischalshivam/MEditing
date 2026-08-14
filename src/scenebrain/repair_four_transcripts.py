from __future__ import annotations
import json,time,sqlite3,re
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
from .hashing import sha256_file
from .portable_library import db,episode
from .search_integrity import digest,normalized
BAD={(2,2):(1,2),(5,4):(1,4),(5,6):(1,6),(5,7):(1,7)}
def run(media:Path,out:Path,targets=None):
 from faster_whisper import WhisperModel
 out.mkdir(parents=True,exist_ok=True);canonical=media/'.scene_brain/libraries/repaired_transcripts_v2';canonical.mkdir(parents=True,exist_ok=True);c=db(media/'.scene_brain/catalog.db');affected=[];rejected=[]
 for r in c.execute("select s.* from sources s join titles t on t.title_id=s.title_id where t.display_name='Breaking Bad'"):
  se,ep,_=episode(Path(r['relative_path']).stem)
  wanted=targets or BAD
  if (se,ep) in wanted:
   old=c.execute("select * from subtitles where source_id=? and origin='SIDECAR'",(r['source_id'],)).fetchone();affected.append(dict(r));rejected.append({'episode':f'S{se:02d}E{ep:02d}','source_id':r['source_id'],'bad_sidecar_path':old['relative_path'],'bad_subtitle_hash':digest(old['text']),'mirrored_episode':(f'S{BAD[(se,ep)][0]:02d}E{BAD[(se,ep)][1]:02d}' if (se,ep) in BAD else None),'reason':'audio alignment failed against physical episode','status':'SIDECAR_REJECTED_AUDIO_MISMATCH'})
 (out/'REJECTED_SIDECARS.json').write_text(json.dumps(rejected,indent=2),encoding='utf8');c.close();model_path=str(Path.home()/'.cache/huggingface/hub/models--Systran--faster-whisper-base.en/snapshots'/next((Path.home()/'.cache/huggingface/hub/models--Systran--faster-whisper-base.en/snapshots').iterdir()).name)
 def one(x):
  started=time.time();src=media/x['relative_path'];strong=sha256_file(src);m=WhisperModel(model_path,device='cpu',compute_type='int8');segments,info=m.transcribe(str(src),language='en',beam_size=5,vad_filter=True);rows=[]
  for s in segments:
   txt=s.text.strip()
   if txt:rows.append({'start_ms':round(s.start*1000),'end_ms':round(s.end*1000),'text':txt})
  se,ep,_=episode(src.stem);target=canonical/f'{x["source_id"]}_S{se:02d}E{ep:02d}.json';payload={'version':'managed-transcript/2.0','volume_id':json.loads((media/'.scene_brain/volume_manifest.json').read_text())['scene_brain_volume_id'],'title':'Breaking Bad','season':se,'episode':ep,'source_id':x['source_id'],'strong_media_sha256':strong,'config':{'model':'faster-whisper-base.en','device':'cpu','compute_type':'int8','beam_size':5,'vad_filter':True,'language':'en'},'duration_ms':x['duration_ms'],'segments':rows};target.write_text(json.dumps(payload,indent=2),encoding='utf8');text=' '.join(z['text'] for z in rows);runtime=time.time()-started;health={'episode':f'S{se:02d}E{ep:02d}','source_id':x['source_id'],'segments':len(rows),'words':len(normalized(text).split()),'monotonic':all(rows[i]['start_ms']<=rows[i+1]['start_ms'] for i in range(len(rows)-1)),'in_bounds':bool(rows and rows[-1]['end_ms']<=x['duration_ms']+1000),'non_empty':bool(text),'runtime_seconds':runtime,'audio_duration_seconds':x['duration_ms']/1000,'real_time_factor':runtime/(x['duration_ms']/1000),'transcript_hash':digest(text),'path':str(target.relative_to(media))};return payload,text,health
 results=[]
 with ThreadPoolExecutor(max_workers=2) as ex:
  fs=[ex.submit(one,x) for x in affected]
  for f in as_completed(fs):results.append(f.result())
 (out/'TRANSCRIPT_HEALTH.json').write_text(json.dumps([x[2] for x in results],indent=2),encoding='utf8');receipt={'version':'transcript-replacement/2.0','embedded_used':0,'whisper_generated':4,'items':[{'episode':x[2]['episode'],'source_id':x[2]['source_id'],'strong_media_sha256':x[0]['strong_media_sha256'],'transcript_hash':x[2]['transcript_hash'],'path':x[2]['path'],'config':x[0]['config']} for x in results]};(out/'TRANSCRIPT_REPLACEMENT_RECEIPT.json').write_text(json.dumps(receipt,indent=2),encoding='utf8');return results
