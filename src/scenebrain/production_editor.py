from __future__ import annotations
import base64,json,os,shutil,sqlite3,subprocess,threading,time,uuid,wave
from datetime import datetime,timezone
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse,quote
from urllib.parse import parse_qs
from .hashing import sha256_file,fingerprint
from .production_preflight import preflight_project,title_status
from .portable_library import db,scan
from .source_review import review_payload,approve,finalize,contact_sheet,search_dialogue,ensure_project,PROJECT_ID

ROOT=Path(__file__).resolve().parents[2];VOLUME_ID='b844b9d0-31d9-488f-afd8-2da7c57ce781';PORT=8780
def find_volume():
 for letter in 'DEFGHIJKLMNOPQRSTUVWXYZ':
  root=Path(f'{letter}:\\Movies');m=root/'.scene_brain/volume_manifest.json'
  if m.exists() and json.loads(m.read_text()).get('scene_brain_volume_id')==VOLUME_ID:return root
 return None
def project_dir(root,name):return root/'.scene_brain/projects'/name
def atomic(path,obj):path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.building.json');tmp.write_text(json.dumps(obj,indent=2,ensure_ascii=False),encoding='utf8');tmp.replace(path)
def import_skyler(media):
 dst=project_dir(media,'skyler_money_production_copy');state=dst/'EDITOR_PROJECT.json'
 preview=ROOT/'runtime/sprint14b_polish/SPRINT14B_POLISHED_DRAFT_720P.mp4'
 if state.exists():
  p=json.loads(state.read_text())
  if p.get('preview_path')!=str(preview):p['preview_path']=str(preview);atomic(state,p)
  return p
 src=ROOT/'runtime/sprint14b_polish/TIMELINE_PLAN_V2.json';timeline=json.loads(src.read_text());final=json.loads((ROOT/'runtime/final_project/FINAL_LOCKED_VISUAL_PLAN.json').read_text());p={'version':'production-editor-project/1.0','project_id':'skyler_money_production_copy','name':"Skyler Saw Walt's Biggest Money Problem Before He Did (Production Copy)",'scope':['Breaking Bad'],'script_path':str(Path.home()/"Downloads/Skyler/Skyler Saw Walt's Biggest Money Problem Before He Did.txt"),'voiceover_path':timeline['voiceover_path'],'preview_path':str(preview),'script_sha256':None,'voiceover_sha256':timeline['voiceover_sha256'],'retrieval_plan_sha256':timeline['frozen_retrieval_plan_sha256'],'locked_source_count':57,'manual_fix_count':2,'timeline':timeline['presentation_slots'],'undo':[],'redo':[],'status':'EDITABLE_COPY','created':datetime.now(timezone.utc).isoformat(),'library_pin':VOLUME_ID};atomic(state,p);return p
def library(media):
 c=db(media/'.scene_brain/catalog.db');rows=[]
 for t in c.execute('select * from titles order by display_name'):
  s=title_status(c,t['display_name']);state='READY TO SEARCH' if s['searchable']==s['cataloged'] else ('PARTIALLY READY' if s['searchable'] else 'NEEDS PREPARATION');rows.append({'title':t['display_name'],'kind':t['kind'],'state':state,**s})
 c.close();return rows
def projects(media):
 ensure_project(media,ROOT)
 out=[]
 for p in (media/'.scene_brain/projects').glob('*/EDITOR_PROJECT.json'):
  try:
   x=json.loads(p.read_text());row={k:x.get(k) for k in ['project_id','name','status','locked_source_count','manual_fix_count','scope','created']};row['duration_ms']=max([z.get('timeline_end_ms',0) for z in x.get('timeline',[])],default=0);out.append(row)
  except:pass
 return out
def edit(media,pid,action):
 path=project_dir(media,pid)/'EDITOR_PROJECT.json';p=json.loads(path.read_text());before=json.loads(json.dumps(p['timeline']));kind=action['action'];sid=action.get('slot_id');idx=next((i for i,x in enumerate(p['timeline']) if x['presentation_slot_id']==sid),None)
 if kind=='UNDO' and p['undo']:p['redo'].append(p['timeline']);p['timeline']=p['undo'].pop()
 elif kind=='REDO' and p['redo']:p['undo'].append(p['timeline']);p['timeline']=p['redo'].pop()
 elif idx is not None:
  p['undo'].append(before);p['redo']=[];x=p['timeline'][idx]
  if kind=='TRIM':
   old=x['timeline_end_ms']-x['timeline_start_ms'];x['source_in_ms']=max(x.get('approved_source_in_ms',x.get('source_in_ms') or 0),int(action['source_in_ms']));x['source_out_ms']=min(x.get('approved_source_out_ms',x.get('source_out_ms') or 10**12),int(action['source_out_ms']));new=max(250,x['source_out_ms']-x['source_in_ms']);x['timeline_end_ms']=x['timeline_start_ms']+new;delta=new-old
   for z in p['timeline'][idx+1:]:z['timeline_start_ms']+=delta;z['timeline_end_ms']+=delta
  elif kind=='DURATION':
   delta=int(action['end_ms'])-x['timeline_end_ms'];x['timeline_end_ms']+=delta
   for z in p['timeline'][idx+1:]:z['timeline_start_ms']+=delta;z['timeline_end_ms']+=delta
  elif kind=='SPLIT':
   at=int(action['at_ms']);y=json.loads(json.dumps(x));x['timeline_end_ms']=at;y['timeline_start_ms']=at;y['presentation_slot_id']=x['presentation_slot_id']+'_SPLIT';p['timeline'].insert(idx+1,y)
  elif kind=='DELETE':
   duration=x['timeline_end_ms']-x['timeline_start_ms'];p['timeline'].pop(idx)
   if action.get('close_gap',True):
    for z in p['timeline'][idx:]:z['timeline_start_ms']-=duration;z['timeline_end_ms']-=duration
  elif kind=='SWITCH':x['presentation_type']=action['presentation_type']
  elif kind=='REPLACE_APPROVED':
   donor=next(z for z in p['timeline'] if z.get('locked_asset_id')==action['locked_asset_id']);keep={k:x[k] for k in ['presentation_slot_id','beat_id','timeline_start_ms','timeline_end_ms','exact_narration']};x.update(json.loads(json.dumps(donor)));x.update(keep);x['reuse_provenance']='EXPLICIT_USER_PROJECT_APPROVED_REPLACEMENT'
  elif kind=='MANUAL_MEDIA':
   src=Path(action['path']);managed=path.parent/'manual_media'/src.name;managed.parent.mkdir(exist_ok=True);shutil.copy2(src,managed);x.update({'presentation_type':'IMAGE' if src.suffix.lower() in {'.jpg','.jpeg','.png','.webp'} else 'VIDEO','source_path':str(managed),'source_hash':sha256_file(managed),'approval_state':'APPROVED','manual_provenance':str(src)})
  elif kind=='RESOLVE_UPLOAD':
   managed=save_upload(path.parent/'custom_media',action['file']);x.update({'presentation_type':'IMAGE' if managed.suffix.lower() in {'.jpg','.jpeg','.png','.webp'} else 'VIDEO','source_path':str(managed),'derived_asset_path':str(managed) if managed.suffix.lower() in {'.jpg','.jpeg','.png','.webp'} else None,'source_hash':sha256_file(managed),'approval_state':'APPROVED','manual_provenance':'PROJECT_MANAGED_UPLOAD'})
  elif kind=='APPROVE_CANDIDATE':
   candidates=x.get('candidates') or [];number=int(action['candidate_index'])
   if number<0 or number>=len(candidates):raise ValueError('Candidate does not exist')
   c=candidates[number];x.update({'presentation_type':action.get('presentation_type') or x.get('presentation_type') or 'VIDEO','source_path':c['source_path'],'source_id':c.get('source_id'),'source_in_ms':c.get('source_in_ms'),'source_out_ms':c.get('source_out_ms'),'derived_asset_path':c.get('derived_asset_path'),'frame_time_ms':c.get('frame_time_ms'),'source_hash':c.get('source_hash'),'approval_state':'APPROVED','state':'APPROVED','selected_candidate':number,'approval_provenance':'PROJECT_SLOT_APPROVAL'})
 p['manual_fix_count']=sum(x.get('approval_state')=='MANUAL_FIX' for x in p['timeline']);p['review_counts']={'approved':sum(x.get('approval_state')=='APPROVED' for x in p['timeline']),'needs_choice':sum(x.get('approval_state')=='NEEDS_CHOICE' for x in p['timeline']),'manual_required':sum(x.get('approval_state')=='MANUAL_FIX' for x in p['timeline'])};atomic(path,p);return p
def save_upload(folder,file):
 folder.mkdir(parents=True,exist_ok=True);name=Path(file['name']).name;target=folder/name;target.write_bytes(base64.b64decode(file['data']));return target
def candidate_thumbnail(media,pid,slot_id,number):
 state=json.loads((project_dir(media,pid)/'EDITOR_PROJECT.json').read_text());slot=next(x for x in state['timeline'] if x['presentation_slot_id']==slot_id);c=slot['candidates'][int(number)];target=project_dir(media,pid)/'candidate_thumbnails'/f'{slot_id}_{number}.jpg';target.parent.mkdir(exist_ok=True)
 if not target.exists():
  at=((c.get('source_in_ms') or 0)+(c.get('source_out_ms') or c.get('source_in_ms') or 0))//2
  subprocess.run(['ffmpeg','-v','error','-ss',f'{at/1000:.3f}','-i',c['source_path'],'-frames:v','1','-vf','scale=480:-2','-q:v','4','-y',str(target)],check=True)
 return target
def project_from_upload(media,payload):
 pid='prj_'+uuid.uuid4().hex[:12];root=project_dir(media,pid);script=save_upload(root/'script',payload['script']);voice=save_upload(root/'voiceover',payload['voiceover']) if payload.get('voiceover') else None;text=script.read_text(encoding='utf8',errors='replace');scope=payload['scope'];clues=[{'beat_id':f'B{i:03d}','narration':p.strip(),'status':'AUTO_GENERATED'} for i,p in enumerate([x for x in text.replace('\r','').split('\n\n') if x.strip()],1)];(root/'clues').mkdir(parents=True,exist_ok=True);atomic(root/'clues/CLUE_SCRIPT.json',{'version':'production-clue-ui/1.0','script_sha256':sha256_file(script),'beats':clues});statuses={x['title']:x for x in library(media) if x['title'] in scope};ready=all(x['state']!='NEEDS PREPARATION' for x in statuses.values());p={'version':'production-editor-project/2.0','project_id':pid,'name':payload['name'],'tag':payload.get('tag'),'scope':scope,'scope_mode':payload.get('scope_mode'),'script_path':str(script),'voiceover_path':str(voice) if voice else None,'script_sha256':sha256_file(script),'voiceover_sha256':sha256_file(voice) if voice else None,'clue_status':'AUTO GENERATED','clue_count':len(clues),'title_readiness':statuses,'status':'READY FOR RETRIEVAL' if ready else 'NOT READY','timeline':[],'undo':[],'redo':[],'locked_source_count':0,'manual_fix_count':0,'library_pin':VOLUME_ID,'created':datetime.now(timezone.utc).isoformat()};atomic(root/'EDITOR_PROJECT.json',p);return p
def create_project(media,payload):
 pid='prj_'+uuid.uuid4().hex[:12];script=Path(payload['script_path']);voice=Path(payload['voiceover_path']) if payload.get('voiceover_path') else None;scope=payload['scope'];receipt=preflight_project(media/'.scene_brain/catalog.db',pid,script,scope,voiceover=voice)
 p={'version':'production-editor-project/1.0','project_id':pid,'name':payload['name'],'scope':scope,'script_path':str(script),'voiceover_path':str(voice) if voice else None,'script_sha256':sha256_file(script),'voiceover_sha256':sha256_file(voice) if voice else None,'preflight':receipt,'status':'READY FOR RETRIEVAL' if receipt['ready_for_retrieval'] else 'NOT READY','timeline':[],'undo':[],'redo':[],'locked_source_count':0,'manual_fix_count':0,'library_pin':VOLUME_ID};atomic(project_dir(media,pid)/'EDITOR_PROJECT.json',p);return p
def duplicate_project(media,pid):
 src=project_dir(media,pid)/'EDITOR_PROJECT.json';p=json.loads(src.read_text());newid=pid+'_qa_copy';p['project_id']=newid;p['name']=p['name']+' [QA COPY]';p['created']=datetime.now(timezone.utc).isoformat();p['undo']=[];p['redo']=[];atomic(project_dir(media,newid)/'EDITOR_PROJECT.json',p);return p
class H(SimpleHTTPRequestHandler):
 def end_headers(self):
  self.send_header('Cache-Control','no-store, no-cache, must-revalidate, max-age=0');self.send_header('Pragma','no-cache');self.send_header('Expires','0');super().end_headers()
 def _json(self,obj,code=200):
  b=json.dumps(obj).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def do_GET(self):
  media=find_volume()
  if self.path=='/api/health':return self._json({'status':'ok','service':'scene-brain-production-editor','volume_connected':bool(media),'volume_id':VOLUME_ID})
  if self.path=='/api/state':
   if not media:return self._json({'connected':False,'error':'MEDIA DRIVE DISCONNECTED'},503)
   import_skyler(media);return self._json({'connected':True,'volume_id':VOLUME_ID,'media_root':str(media),'library':library(media),'projects':projects(media)})
  if self.path.startswith('/api/project/'):
   p=project_dir(media,self.path.rsplit('/',1)[1])/'EDITOR_PROJECT.json';return self._json(json.loads(p.read_text()) if p.exists() else {'error':'Project not found'},200 if p.exists() else 404)
  if self.path.startswith('/api/source-review/'):
   parts=urlparse(self.path);pid=parts.path.rsplit('/',1)[1]
   try:return self._json(review_payload(media,ROOT,pid))
   except Exception as e:return self._json({'error':str(e)},400)
  if self.path.startswith('/api/contact-sheet/'):
   sid=urlparse(self.path).path.rsplit('/',1)[1]
   try:return self._json(contact_sheet(media,ROOT,sid))
   except Exception as e:return self._json({'error':str(e)},400)
  if self.path.startswith('/api/dialogue-search'):
   q=parse_qs(urlparse(self.path).query).get('q',[''])[0]
   try:return self._json({'results':search_dialogue(ROOT,q)})
   except Exception as e:return self._json({'error':str(e)},400)
  if urlparse(self.path).path=='/favicon.ico':
   self.send_response(204);self.end_headers();return
  if self.path.startswith('/api/candidate-thumbnail?'):
   q=parse_qs(urlparse(self.path).query)
   try:self.path='/media?path='+quote(str(candidate_thumbnail(media,q['project'][0],q['slot'][0],q['candidate'][0])))
   except Exception as e:return self._json({'error':str(e)},400)
  if self.path.startswith('/media?'):
   q=parse_qs(urlparse(self.path).query);p=Path(q.get('path',[''])[0])
   if not p.is_file():return self.send_error(404)
   size=p.stat().st_size;start,end=0,size-1;status=200
   if self.headers.get('Range'):
    try:
     raw=self.headers['Range'].split('=',1)[1];a,b=raw.split('-',1);start=int(a or 0);end=min(int(b) if b else start+4*1024*1024-1,size-1);status=206
    except Exception:return self.send_error(416)
   mime='image/jpeg' if p.suffix.lower() in {'.jpg','.jpeg'} else ('audio/wav' if p.suffix.lower()=='.wav' else 'video/mp4');self.send_response(status);self.send_header('Content-Type',mime);self.send_header('Accept-Ranges','bytes');self.send_header('Content-Length',str(end-start+1))
   if status==206:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
   self.end_headers()
   with p.open('rb') as f:f.seek(start);self.wfile.write(f.read(end-start+1))
   return
  if urlparse(self.path).path in {'/','/app'}:self.path='/PRODUCTION_EDITOR.html'
  return super().do_GET()
 def do_POST(self):
  media=find_volume()
  if not media:return self._json({'error':'The media drive was disconnected. Reconnect the registered Scene Brain SSD and click Retry.'},503)
  try:n=int(self.headers.get('Content-Length','0'));x=json.loads(self.rfile.read(n) or b'{}')
  except Exception as e:return self._json({'error':str(e)},400)
  try:
   if self.path=='/api/project/new':return self._json(create_project(media,x))
   if self.path=='/api/project/upload-new':return self._json(project_from_upload(media,x))
   if self.path.startswith('/api/project/duplicate/'):return self._json(duplicate_project(media,self.path.rsplit('/',1)[1]))
   if self.path.startswith('/api/project/edit/'):return self._json(edit(media,self.path.rsplit('/',1)[1],x))
   if self.path.startswith('/api/source-review/approve/'):
    return self._json(approve(media,ROOT,x,self.path.rsplit('/',1)[1]))
   if self.path=='/api/rescan':
    receipt=scan(media);return self._json({'status':'COMPLETE','message':f"{receipt['media_files_detected']} sources checked; {receipt['incremental']['unchanged']} unchanged",'receipt':receipt,'library':library(media)})
   if self.path=='/api/prepare-title':return self._json({'status':'CONFIRMATION_REQUIRED','message':'Preparation will use persistent transcript jobs; no job starts without confirmation.'})
  except Exception as e:return self._json({'error':str(e)},400)
  self._json({'error':'Not found'},404)
def main():
 media=find_volume()
 if not media:raise SystemExit('Registered Scene Brain SSD is unavailable.')
 web=ROOT/'runtime/production_editor';os.chdir(web);ThreadingHTTPServer(('127.0.0.1',PORT),H).serve_forever()
if __name__=='__main__':main()
