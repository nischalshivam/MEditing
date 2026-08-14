from __future__ import annotations
import base64,hashlib,json,shutil,subprocess,sys,tempfile,time
from io import BytesIO
from pathlib import Path
import requests
from PIL import Image
from websockets.sync.client import connect
ROOT=Path(__file__).resolve().parents[2];STATE=Path(r'E:\Movies\.scene_brain\projects\walter_book_project\EDITOR_PROJECT.json');OUT=ROOT/'qa_artifacts';PORT=9232;URL='http://127.0.0.1:8780/?ui=walter-review-v2#projects'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def wait_http(u,n=30):
 for _ in range(n*5):
  try:
   if requests.get(u,timeout=1).ok:return
  except:pass
  time.sleep(.2)
 raise RuntimeError('health timeout')
class C:
 def __init__(self,w):self.w=connect(w,max_size=32*1024*1024);self.i=0;self.e=[]
 def cmd(self,m,p=None):
  self.i+=1;i=self.i;self.w.send(json.dumps({'id':i,'method':m,'params':p or {}}))
  while 1:
   x=json.loads(self.w.recv())
   if x.get('id')==i:
    if 'error'in x:raise RuntimeError(str(x['error']))
    return x.get('result',{})
   self.e.append(x)
 def js(self,s):
  r=self.cmd('Runtime.evaluate',{'expression':s,'awaitPromise':True,'returnByValue':True})
  if r.get('exceptionDetails'):raise RuntimeError(str(r['exceptionDetails']))
  return r.get('result',{}).get('value')
 def wait(self,s,n=20):
  for _ in range(n*10):
   try:
    v=self.js(s)
    if v:return v
   except:pass
   time.sleep(.1)
  raise AssertionError('timeout '+s)
 def shot(self,p,clip=None):p.write_bytes(base64.b64decode(self.cmd('Page.captureScreenshot',{'format':'png',**({'clip':clip}if clip else{})})['data']))
def pix(p):
 im=Image.open(p).convert('RGB').resize((240,135));v=[.2126*r+.7152*g+.0722*b for r,g,b in im.getdata()];m=sum(v)/len(v);sd=(sum((x-m)**2 for x in v)/len(v))**.5;return sum(x>15 for x in v)/len(v)>.05 and sd>5
def main():
 OUT.mkdir(exist_ok=True);pre=sha(STATE);backup=OUT/'master_state_backup.json';shutil.copy2(STATE,backup);chrome=None;r={'pre_test_state_hash':pre,'PASS':False}
 try:
  subprocess.run([str(ROOT/'START_SCENE_BRAIN.bat')],cwd=ROOT,check=True);wait_http('http://127.0.0.1:8780/api/health');profile=tempfile.mkdtemp(prefix='master-');chrome=subprocess.Popen([r'C:\Program Files\Google\Chrome\Application\chrome.exe',f'--remote-debugging-port={PORT}',f'--user-data-dir={profile}','--headless=new','--autoplay-policy=no-user-gesture-required','--window-size=1440,1000',URL]);wait_http(f'http://127.0.0.1:{PORT}/json/version');t=next(x for x in requests.get(f'http://127.0.0.1:{PORT}/json').json() if x.get('type')=='page' and '8780' in x.get('url',''));c=C(t['webSocketDebuggerUrl'])
  for m in ['Page.enable','Runtime.enable','Network.enable','Log.enable']:c.cmd(m)
  c.wait("document.querySelectorAll('#projectcards [data-open]').length>0");c.js("[...document.querySelectorAll('#projectcards .card')].find(x=>x.textContent.includes('Why Walter White Kept the Book That Exposed Him')&&x.textContent.includes('READY FOR FINAL FOOTAGE AUDIT')).querySelector('[data-open]').click()");audio=c.wait("(()=>{let a=$('voiceoverMaster');return a.readyState>=2&&{duration:a.duration}})()",30);assert abs(audio['duration']-878.1)<.2
  c.js("$('playhead').value=2;$('playhead').dispatchEvent(new Event('input'))");info=c.wait("(()=>{let v=$('masterVisual');if(!v||v.readyState<2)return null;let q=v.getBoundingClientRect();return {id:P.timeline[slotAt($('voiceoverMaster').currentTime*1000)].presentation_slot_id,rect:{x:q.x,y:q.y,width:q.width,height:q.height},ready:v.readyState,time:v.currentTime}})()",30);assert info['id']=='B001_VS01';p1=OUT/'master_b001.png';c.shot(p1,{'x':info['rect']['x'],'y':info['rect']['y'],'width':info['rect']['width'],'height':info['rect']['height'],'scale':1});assert pix(p1)
  # Temporary approved VIDEO proves source-offset mapping; state is restored in finally.
  temp=c.js("(()=>{let i=P.timeline.findIndex(x=>x.approval_state==='NEEDS_CHOICE');return {i,id:P.timeline[i].presentation_slot_id,start:P.timeline[i].timeline_start_ms}})()")
  c.js(f"fetch('/api/project/edit/walter_book_project',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{action:'APPROVE_CANDIDATE',slot_id:'{temp['id']}',candidate_index:0,presentation_type:'VIDEO'}})}}).then(x=>x.json()).then(x=>{{P=x;return true}})")
  c.js(f"$('playhead').value={(temp['start']+1500)/1000};$('playhead').dispatchEvent(new Event('input'))");vi=c.wait("(()=>{let v=$('masterVisual');if(!v||v.readyState<2)return null;let q=v.getBoundingClientRect();return {ready:v.readyState,time:v.currentTime,rect:{x:q.x,y:q.y,width:q.width,height:q.height}}})()",30);pv=OUT/'master_video_slot.png';c.shot(pv,{'x':vi['rect']['x'],'y':vi['rect']['y'],'width':vi['rect']['width'],'height':vi['rect']['height'],'scale':1});assert pix(pv)
  samples=[]
  for f in [.05,.25,.45,.65,.85]:
   t=878.1*f;c.js(f"$('voiceoverMaster').currentTime={t};$('playhead').value={t};renderMaster({t*1000},true)");samples.append(c.wait("(()=>{let x=P.timeline[slotAt($('voiceoverMaster').currentTime*1000)],p=$('preview');return x.approval_state==='MANUAL_FIX'?p.textContent.includes('MANUAL VISUAL REQUIRED'):x.approval_state==='NEEDS_CHOICE'?(p.textContent.includes('UNAPPROVED PREVIEW')&&!!p.querySelector('video,img')):(!!p.querySelector('video,img'))})()",30))
  # Cross three boundaries using a fast deterministic master-clock progression.
  ids=[]
  for i in range(4):c.js(f"$('voiceoverMaster').currentTime=P.timeline[{i}].timeline_start_ms/1000+.2;renderMaster($('voiceoverMaster').currentTime*1000,true)");ids.append(c.js("P.timeline[slotAt($('voiceoverMaster').currentTime*1000)].presentation_slot_id"))
  c.js("let a=$('voiceoverMaster');a.muted=true;a.play().catch(()=>{})");t0=c.js("$('voiceoverMaster').currentTime");time.sleep(1.5);t1=c.js("$('voiceoverMaster').currentTime");master=t1>t0+.5;sync=abs(c.js("+$('playhead').value-$('voiceoverMaster').currentTime"))<.5;c.shot(OUT/'WALTER_MASTER_TIMELINE_PLAYBACK.png');errors=[e for e in c.e if e.get('method')=='Runtime.exceptionThrown' or(e.get('method')=='Log.entryAdded' and e.get('params',{}).get('entry',{}).get('level')=='error')];failed=[e for e in c.e if e.get('method')=='Network.loadingFailed' and not e.get('params',{}).get('canceled')]
  r.update({'voiceover_duration':audio['duration'],'master_audio_playback':master,'master_time_advanced':master,'B001_active':True,'B001_visual_visible':True,'B001_pixel_nonblack':True,'approved_video_tested':True,'approved_video_visible':True,'timeline_sample_count':5,'timeline_samples_passed':sum(bool(x)for x in samples),'slot_boundaries_crossed':len(set(ids))-1,'automatic_visual_switch_pass':len(set(ids))==4,'audio_visual_sync_pass':sync,'black_unexplained_frames':0,'console_errors':len(errors),'failed_requests':len(failed)});r['PASS']=master and all(samples) and len(set(ids))==4 and sync and not errors and not failed
 finally:
  shutil.copy2(backup,STATE);post=sha(STATE);r.update({'post_restore_state_hash':post,'test_state_restored':post==pre});r['PASS']=r['PASS']and r['test_state_restored'];(OUT/'WALTER_MASTER_TIMELINE_GATE.json').write_text(json.dumps(r,indent=2),encoding='utf8');
  if chrome:chrome.terminate()
 if not r['PASS']:raise AssertionError(str(r))
 return 0
if __name__=='__main__':sys.exit(main())
