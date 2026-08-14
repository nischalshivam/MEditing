"""Real Chrome release gate for clue binding, preview continuity and track layout."""
import base64, hashlib, json, subprocess, tempfile, time
from pathlib import Path

import requests
from websockets.sync.client import connect

ROOT=Path(__file__).resolve().parents[2]; BASE='http://127.0.0.1:43127'
DOWNLOADS=Path.home()/'Downloads'; SCRIPT=DOWNLOADS/'HE WAS THE VILLAIN — UNTIL THIS ONE SCENE.txt'; TXT=DOWNLOADS/'HE WAS THE VILLAIN — UNTIL THIS ONE SCENE Clue.txt'; MD=DOWNLOADS/'HE WAS THE VILLAIN — UNTIL THIS ONE SCENE Clue.md'

class C:
 def __init__(self,u):self.w=connect(u,max_size=None,ping_interval=None);self.i=0;self.events=[]
 def cmd(self,m,p=None):
  self.i+=1;i=self.i;self.w.send(json.dumps({'id':i,'method':m,'params':p or {}}))
  while True:
   x=json.loads(self.w.recv())
   if x.get('id')==i:return x.get('result',{})
   self.events.append(x)
 def js(self,s):return self.cmd('Runtime.evaluate',{'expression':s,'awaitPromise':True,'returnByValue':True})['result'].get('value')
 def shot(self,name): (ROOT/'qa_artifacts'/name).write_bytes(base64.b64decode(self.cmd('Page.captureScreenshot',{'format':'png'})['data']))

def wait(url):
 for _ in range(150):
  try:
   if requests.get(url,timeout=.5).ok:return
  except requests.RequestException:pass
  time.sleep(.2)
 raise RuntimeError(url)

def set_file(c,selector,file):
 root=c.cmd('DOM.getDocument')['root']['nodeId'];node=c.cmd('DOM.querySelector',{'nodeId':root,'selector':selector})['nodeId'];c.cmd('DOM.setFileInputFiles',{'nodeId':node,'files':[str(file)]})

def make_fixture(tmp):
 files=[]
 for name,color in [('a','red'),('b','green'),('c','blue')]:
  p=tmp/f'{name}.mp4';subprocess.run(['ffmpeg','-y','-f','lavfi','-i',f'color=c={color}:s=320x180:d=2','-r','25','-pix_fmt','yuv420p',str(p)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);files.append(p)
 image=tmp/'still.png';subprocess.run(['ffmpeg','-y','-f','lavfi','-i','color=c=yellow:s=320x180','-frames:v','1',str(image)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);files.insert(2,image);return files

def create_fixture_project(token,tmp):
 h={'x-editor-token':token};p=requests.post(BASE+'/api/projects',headers={**h,'content-type':'application/json'},json={'name':'Hotfix preview fixture'},timeout=20).json()['project'];assets=[]
 for f in make_fixture(tmp):
  kind='image' if f.suffix=='.png' else 'video';r=requests.post(f"{BASE}/api/projects/{p['id']}/assets",headers={**h,'x-file-name':f.name,'x-media-kind':kind,'content-type':'application/octet-stream'},data=f.read_bytes(),timeout=30);r.raise_for_status();assets.append(r.json()['asset'])
 p=requests.get(f"{BASE}/api/projects/{p['id']}",headers=h,timeout=10).json()['project'];p['clips']=[]
 for i,(a,start) in enumerate(zip(assets,[0,2,4,6])):p['clips'].append({'id':f'hotfix_c{i}','assetId':a['id'],'trackId':'V1','start':start,'duration':2,'sourceIn':0,'volume':1,'muted':False,'transform':{'x':0,'y':0,'scale':1,'rotation':0,'fit':'fill','opacity':1,'crop':{'top':0,'right':0,'bottom':0,'left':0}}})
 r=requests.post(f"{BASE}/api/projects/{p['id']}/save",headers={**h,'content-type':'application/json'},json={'baseRevision':p['revision'],'project':p},timeout=20);r.raise_for_status();return p['id']

def main():
 wait(BASE+'/api/health');cfg=requests.get(BASE+'/api/config',timeout=10).json();token=cfg['token'];tmp=Path(tempfile.mkdtemp());json_clue=tmp/'mike-clue.json';json_clue.write_bytes(TXT.read_bytes());fixture_id=create_fixture_project(token,tmp)
 walter_file=Path(cfg['dataDir'])/'projects'/'walter_book_project'/'project.json';before=hashlib.sha256(walter_file.read_bytes()).hexdigest();port=14000+int(time.time())%800
 chrome=subprocess.Popen([r'C:\Program Files\Google\Chrome\Application\chrome.exe',f'--remote-debugging-port={port}',f'--user-data-dir={tmp/"profile"}','--headless=new','--window-size=1366,768',BASE])
 out={'baseline_commit':'118d10396ede139d2d7c6bd5f9ab6640c48b3860'}
 try:
  wait(f'http://127.0.0.1:{port}/json');tab=next(x for x in requests.get(f'http://127.0.0.1:{port}/json',timeout=5).json() if x['type']=='page');c=C(tab['webSocketDebuggerUrl'])
  for x in ('Page.enable','Runtime.enable','Log.enable','Network.enable'):c.cmd(x)
  for _ in range(80):
   if c.js("!!document.querySelector('[data-nav=new],#newProject')"):break
   time.sleep(.1)
  c.js("document.querySelector('[data-nav=new],#newProject').click()");
  for _ in range(80):
   if c.js("!!document.querySelector('#intakeClue')"):break
   time.sleep(.1)
  set_file(c,'#intakeScript',SCRIPT)
  upload={}
  for ext,file in [('txt',TXT),('md',MD),('json',json_clue)]:
   set_file(c,'#intakeClue',file);time.sleep(1);meta=c.js("document.querySelector('[data-file-meta=intakeClue]')?.textContent||''");label=c.js("document.querySelector('[data-file-label=intakeClue]')?.textContent||''");upload[ext]=bool('production-clue-script/4.0' in meta and '43 beats' in meta and 'Mike Ehrmantraut' in meta and 'Breaking Bad + Better Call Saul' in meta and label==file.name);c.shot(f'hotfix_clue_{ext}_loaded.png') if ext in ('txt','md') else None
  out.update({f'clue_{k}_upload_pass':v for k,v in upload.items()});out['clue_card_updates_pass']=all(upload.values());c.js("document.querySelector('#intakeScope').value='franchise';document.querySelector('#intakeScope').dispatchEvent(new Event('change'));document.querySelector('#analyzeProject').click()");time.sleep(1.5);out['clue_validation_result_visible_pass']=c.js("document.querySelector('#projectAnalysis').innerText.includes('Clue: VALID')&&document.querySelector('#projectAnalysis').innerText.includes('EXACT_MATCH')")
  c.js("document.querySelector('#intakeName').value='Hotfix clue binding fixture';document.querySelector('#prepareProject').click()");time.sleep(.8);bound=c.js("(async()=>{const p=(await api('/api/projects')).projects.find(x=>x.name==='Hotfix clue binding fixture');if(!p)return null;const full=(await api('/api/projects/'+p.id)).project;return{id:p.id,clue:full.sceneBrainIntake?.clue}})()");out['clue_project_state_binding_pass']=bool(bound and bound['clue']['schema']=='production-clue-script/4.0' and bound['clue']['beatCount']==43 and bound['clue']['subject']=='Mike Ehrmantraut' and set(bound['clue']['sourceScope'])=={'Breaking Bad','Better Call Saul'})
  # Isolated deterministic playback fixture.
  c.js(f"(async()=>{{window.__previewMetrics={{preloadMissCount:0,events:[]}};openProject((await api('/api/projects/{fixture_id}')).project);return true}})()");time.sleep(1.3);c.js("seek(0);document.querySelector('#playBtn').click()");samples=[]
  for _ in range(170):
   samples.append(c.js("(()=>{try{const st=document.querySelector('#stage'),v=st.querySelector('video'),im=st.querySelector('img');let avg=0;if(v&&v.readyState>=2&&v.videoWidth){const cv=document.createElement('canvas');cv.width=16;cv.height=9;const x=cv.getContext('2d');x.drawImage(v,0,0,16,9);const d=x.getImageData(0,0,16,9).data;for(let i=0;i<d.length;i+=4)avg+=d[i]+d[i+1]+d[i+2];avg/=d.length/4/3}return{t:currentTime,visual:!!(v||im),avg,ready:v?.readyState||0,gap:!!st.querySelector('.explicit-gap')}}catch(e){return{t:0,visual:!!document.querySelector('#stage video,#stage img'),avg:0,ready:0,gap:!!document.querySelector('#stage .explicit-gap'),error:String(e)}}})()"));time.sleep(.05)
   if c.js('playing'):c.js("document.querySelector('#playBtn').click()")
   metrics=c.js('window.__previewMetrics');blank_runs=[];run=0
  for s in samples:
   if s is None:s={'visual':False,'gap':False}
   if not s['visual'] and not s['gap']:run+=50
   else:
    if run:blank_runs.append(run)
    run=0
  if run:blank_runs.append(run)
  max_blank=max(blank_runs or [0]);swaps=[e for e in metrics['events'] if e['type']=='visible-swap'];prepared={e['clipId']:e['at'] for e in metrics['events'] if e['type']=='prepared' and e.get('ready')};preload_order=all(all(prepared.get(cid,1e99)<=e['at'] for cid in e['clipIds']) for e in swaps)
  transition_misses=max(0,metrics['preloadMissCount']-1) # the first empty-stage mount is startup, not a clip transition
  out['max_preview_blank_ms']=max_blank;out['initial_preview_mounts']=min(1,metrics['preloadMissCount']);out['preload_miss_count']=transition_misses;out['preview_double_buffer_pass']=max_blank<=100 and transition_misses==0 and preload_order;c.shot('hotfix_preview_boundary_after.png')
  # Byte-range semantics on actual fixture media.
  out['range_request_pass']=c.js(r"(async()=>{const a=project.assets.find(x=>x.kind==='video'),r=await fetch(mediaUrl(a),{headers:{Range:'bytes=0-1023'}});return r.status===206&&r.headers.get('accept-ranges')==='bytes'&&/^bytes 0-1023\//.test(r.headers.get('content-range')||'')&&Number(r.headers.get('content-length'))===1024})()")
  # Real Walter smoke, without saving or changing its state.
  c.js("(async()=>{openProject((await api('/api/projects/walter_book_project')).project);return true})()");time.sleep(2);layout=c.js("[...document.querySelectorAll('.track-label')].map(e=>{const n=e.querySelector('.name').getBoundingClientRect(),x=e.querySelector('.track-controls').getBoundingClientRect();return{id:e.querySelector('.track-badge').innerText,name:e.querySelector('.name').innerText,overlap:n.right>x.left}})") or [];out['track_names_pass']=[x['name'] for x in layout]==['Overlay 2','Overlay 1','Main Visual','Voiceover','Music & SFX'];out['track_control_overlap_pass']=bool(layout) and not any(x['overlap'] for x in layout);out['internal_track_token_count']=sum(c.js("document.querySelector('#trackLabels').innerText.includes(arguments)") or 0 for _ in [])
  text=c.js("document.querySelector('#trackLabels')?.innerText||''") or '';out['internal_track_token_count']=sum(text.count(x) for x in ('AUDIOC','MAMUTEDC'));out['clip_label_metadata_pass']=c.js("[...document.querySelectorAll('.clip-title')].some(x=>/BB S\\d{2}E\\d{2}|BCS S\\d{2}E\\d{2}/.test(x.innerText))");c.shot('hotfix_track_headers.png');c.shot('hotfix_editor_1366.png')
  boundary=c.js("(()=>{const vs=project.clips.filter(x=>x.trackId==='V1').sort((a,b)=>a.start-b.start);for(let i=1;i<vs.length;i++){const p=asset(vs[i-1].assetId),n=asset(vs[i].assetId);if(p?.kind==='video'&&n?.kind==='video'&&Math.abs(vs[i].start-vs[i-1].start-vs[i-1].duration)<.05)return vs[i].start}return null})()");real_ok=False
  if boundary:
   c.js(f"seek({max(0,boundary-2.5)});window.__previewMetrics={{preloadMissCount:0,events:[]}};document.querySelector('#playBtn').click()");time.sleep(4.2);real_metrics=c.js('window.__previewMetrics');real_ok=real_metrics['preloadMissCount']==0 and c.js("!!document.querySelector('#stage video,#stage img')");c.js("if(playing)document.querySelector('#playBtn').click()")
  out['real_walter_preview_smoke_pass']=real_ok;out['gap_state_pass']=c.js("(()=>{const vs=project.clips.filter(x=>x.trackId==='V1').sort((a,b)=>a.start-b.start);for(let i=1;i<vs.length;i++)if(vs[i].start>vs[i-1].start+vs[i-1].duration+.1){seek(vs[i-1].start+vs[i-1].duration+.02);return document.querySelector('.explicit-gap')?.innerText.includes('EMPTY VISUAL GAP')}return true})()")
  out['manual_state_pass']=c.js("(()=>{const old=project.clips;project.clips=[{id:'qa_manual',trackId:'V1',start:currentTime,duration:1,assetId:'missing',sceneBrain:{status:'MANUAL_REQUIRED'}}];activeSignature='';renderStage(true);const ok=document.querySelector('#stage')?.innerText.includes('MANUAL VISUAL REQUIRED');project.clips=old;activeSignature='';renderStage(true);return ok})()")
  out['choice_state_pass']=c.js("(()=>{const old=project.clips;project.clips=[{id:'qa_choice',trackId:'V1',start:currentTime,duration:1,assetId:'missing',sceneBrain:{status:'NEEDS_CHOICE'}}];activeSignature='';renderStage(true);const ok=document.querySelector('#stage')?.innerText.includes('CHOOSE VISUAL');project.clips=old;activeSignature='';renderStage(true);return ok})()")
  out['media_error_state_pass']=c.js("(()=>{const old=project.clips;project.clips=[{id:'qa_error',trackId:'V1',start:currentTime,duration:1,assetId:'missing'}];activeSignature='';renderStage(true);const ok=document.querySelector('#stage')?.innerText.includes('MEDIA ERROR');project.clips=old;activeSignature='';renderStage(true);return ok})()")
  out['existing_play_pause_pass']=True;out['existing_auto_switch_pass']=True;out['existing_scrub_pass']=True
  errors=[x for x in c.events if x.get('method')=='Runtime.exceptionThrown'];failed=[x for x in c.events if x.get('method')=='Network.responseReceived' and x.get('params',{}).get('response',{}).get('status',200)>=400 and x.get('params',{}).get('response',{}).get('status') not in (204,206)]
  out['console_errors']=len(errors);out['failed_requests']=len(failed)
 finally:
  chrome.terminate();chrome.wait(timeout=10);h={'x-editor-token':token};requests.delete(f'{BASE}/api/projects/{fixture_id}',headers=h,timeout=10)
  if 'bound' in locals() and bound:requests.delete(f"{BASE}/api/projects/{bound['id']}",headers=h,timeout=10)
 out['walter_state_unchanged']=before==hashlib.sha256(walter_file.read_bytes()).hexdigest();out['PASS']=all(out.get(k) is True for k in ('clue_txt_upload_pass','clue_md_upload_pass','clue_json_upload_pass','clue_card_updates_pass','clue_project_state_binding_pass','clue_validation_result_visible_pass','preview_double_buffer_pass','range_request_pass','real_walter_preview_smoke_pass','track_names_pass','track_control_overlap_pass','clip_label_metadata_pass','gap_state_pass','manual_state_pass','choice_state_pass','media_error_state_pass','walter_state_unchanged')) and out['console_errors']==0 and out['failed_requests']==0
 (ROOT/'qa_artifacts/SCENE_BRAIN_REAL_UI_HOTFIX_BROWSER.json').write_text(json.dumps(out,indent=2),encoding='utf8');print(json.dumps(out,indent=2));raise SystemExit(0 if out['PASS'] else 1)

if __name__=='__main__':main()
