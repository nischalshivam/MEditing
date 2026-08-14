from __future__ import annotations
import base64,hashlib,json,os,shutil,subprocess,sys,tempfile,time
from pathlib import Path
import requests
from websockets.sync.client import connect

ROOT=Path(__file__).resolve().parents[2]; PROJECT=Path(r"E:\Movies\.scene_brain\projects\walter_book_project"); STATE=PROJECT/'EDITOR_PROJECT.json'; OUT=ROOT/'qa_artifacts'; URL='http://127.0.0.1:8780/?ui=walter-review-v2#projects'; PORT=9228
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def wait_http(url,seconds=30):
 for _ in range(seconds*5):
  try:
   if requests.get(url,timeout=1).ok:return
  except:pass
  time.sleep(.2)
 raise RuntimeError('production server did not become healthy')
class CDP:
 def __init__(self,ws):self.ws=connect(ws,max_size=32*1024*1024);self.i=0;self.events=[]
 def cmd(self,m,p=None):
  self.i+=1;i=self.i;self.ws.send(json.dumps({'id':i,'method':m,'params':p or {}}))
  while True:
   x=json.loads(self.ws.recv())
   if x.get('id')==i:
    if 'error'in x:raise RuntimeError(str(x['error']))
    return x.get('result',{})
   self.events.append(x)
 def js(self,s):
  r=self.cmd('Runtime.evaluate',{'expression':s,'awaitPromise':True,'returnByValue':True})
  if r.get('exceptionDetails'):raise RuntimeError(r['exceptionDetails'].get('text','JS error'))
  return r.get('result',{}).get('value')
 def wait(self,expr,seconds=15):
  for _ in range(seconds*10):
   try:
    v=self.js(expr)
    if v:return v
   except:pass
   time.sleep(.1)
  raise AssertionError('timeout: '+expr)
 def shot(self,p):p.write_bytes(base64.b64decode(self.cmd('Page.captureScreenshot',{'format':'png','captureBeyondViewport':False})['data']))
def main():
 OUT.mkdir(exist_ok=True);backup=OUT/'walter_EDITOR_PROJECT.backup.json';shutil.copy2(STATE,backup);before_hash=sha(STATE);chrome=None;result={'project':'walter_book_project','PASS':False}
 try:
  subprocess.run([str(ROOT/'START_SCENE_BRAIN.bat')],cwd=ROOT,check=True);wait_http('http://127.0.0.1:8780/api/health')
  profile=tempfile.mkdtemp(prefix='scene-brain-release-');chrome=subprocess.Popen([r'C:\Program Files\Google\Chrome\Application\chrome.exe',f'--remote-debugging-port={PORT}',f'--user-data-dir={profile}','--headless=new','--window-size=1440,1000',URL])
  wait_http(f'http://127.0.0.1:{PORT}/json/version');targets=requests.get(f'http://127.0.0.1:{PORT}/json',timeout=2).json();target=next(x for x in targets if x.get('type')=='page' and '127.0.0.1:8780' in x.get('url',''));c=CDP(target['webSocketDebuggerUrl'])
  for m in ['Page.enable','Runtime.enable','Network.enable','Log.enable']:c.cmd(m)
  c.wait("document.querySelectorAll('#projectcards [data-open]').length>0")
  c.js("[...document.querySelectorAll('#projectcards .card')].find(x=>x.textContent.includes('Why Walter White Kept the Book That Exposed Him')&&x.textContent.includes('READY FOR FINAL FOOTAGE AUDIT')).querySelector('[data-open]').click()")
  c.wait("document.querySelectorAll('#track .clip').length===70");c.js("document.querySelector('#issues').click()")
  c.wait("!document.querySelector('#drawer').classList.contains('hidden')&&document.querySelectorAll('#candidates .candidate').length>0")
  backend=c.js("(()=>{let x=P.timeline[sel];return {slot:x.presentation_slot_id,count:x.candidates.length,needs:P.timeline.filter(z=>z.approval_state==='NEEDS_CHOICE').length,approved:P.timeline.filter(z=>z.approval_state==='APPROVED').length}})()")
  rendered=c.js("document.querySelectorAll('#candidates .candidate').length");assert rendered==backend['count'] and rendered>0
  thumb=c.wait("(()=>{let i=document.querySelector('#candidates .candidate img');return i&&i.complete&&i.naturalWidth>0&&{w:i.naturalWidth,h:i.naturalHeight}})()")
  c.js("document.querySelector('[data-preview-c=\"0\"]').click()")
  media=c.wait("(()=>{let v=document.querySelector('#player');return v&&v.readyState>=2&&v.videoWidth>0&&{src:v.currentSrc,ready:v.readyState,duration:v.duration,width:v.videoWidth,height:v.videoHeight,current:v.currentTime}})()",30)
  c.js("document.querySelector('#player').muted=true;document.querySelector('#player').play().catch(()=>{})");t0=c.js("document.querySelector('#player').currentTime");time.sleep(1.6);t1=c.js("document.querySelector('#player').currentTime");assert t1>t0+.5
  c.shot(OUT/'walter_review_candidate_visible.png')
  c.js("document.querySelector('[data-approve-c=\"0\"]').click()");after=c.wait(f"P.timeline.find(x=>x.presentation_slot_id==='{backend['slot']}').approval_state==='APPROVED'&&P.timeline.filter(x=>x.approval_state==='NEEDS_CHOICE').length==={backend['needs']-1}&&{{needs:P.timeline.filter(x=>x.approval_state==='NEEDS_CHOICE').length,approved:P.timeline.filter(x=>x.approval_state==='APPROVED').length,next:P.timeline[sel].presentation_slot_id}}")
  assert after['next']!=backend['slot'];c.cmd('Page.reload',{'ignoreCache':True});c.wait("document.querySelectorAll('#projectcards [data-open]').length>0")
  c.js("[...document.querySelectorAll('#projectcards .card')].find(x=>x.textContent.includes('Why Walter White Kept the Book That Exposed Him')&&x.textContent.includes('READY FOR FINAL FOOTAGE AUDIT')).querySelector('[data-open]').click()")
  c.wait("document.querySelectorAll('#track .clip').length===70")
  persisted=c.js(f"P.timeline.find(x=>x.presentation_slot_id==='{backend['slot']}').approval_state==='APPROVED'&&P.timeline.filter(x=>x.approval_state==='NEEDS_CHOICE').length==={after['needs']}");disk=json.loads(STATE.read_text());ssd=next(x for x in disk['timeline'] if x['presentation_slot_id']==backend['slot'])['approval_state']=='APPROVED'
  c.js("(()=>{let i=P.timeline.findIndex(x=>x.approval_state==='MANUAL_FIX');document.querySelectorAll('#track .clip')[i].click();document.querySelector('#replace').click()})()")
  manual=c.wait("document.querySelector('#candidates').textContent.includes('Manual clip required')&&!document.querySelector('#candidates').textContent.includes('Candidate 1')")
  c.js("document.querySelector('#closedrawer').click();(()=>{let i=P.timeline.findIndex(x=>x.approval_state==='NEEDS_CHOICE');document.querySelectorAll('#track .clip')[i].click();document.querySelector('#replace').click()})()")
  choice_again=c.wait("document.querySelectorAll('#candidates .candidate').length>0")
  errors=[e for e in c.events if e.get('method')=='Runtime.exceptionThrown' or (e.get('method')=='Log.entryAdded' and e.get('params',{}).get('entry',{}).get('level')=='error')];failed=[e for e in c.events if e.get('method')=='Network.loadingFailed' and not e.get('params',{}).get('canceled')]
  result.update({'timeline_slots':70,'slot_id_tested':backend['slot'],'candidate_count_backend':backend['count'],'candidate_cards_rendered':rendered,'thumbnail_loaded':True,'thumbnail_dimensions':f"{thumb['w']}x{thumb['h']}",'preview_src_present':bool(media['src']),'preview_ready_state':media['ready'],'preview_duration':media['duration'],'preview_dimensions':f"{media['width']}x{media['height']}",'playback_time_advanced':True,'approval_state_changed':True,'needs_choice_before':backend['needs'],'needs_choice_after':after['needs'],'approval_persisted_after_reload':bool(persisted),'ssd_persistence_verified':ssd,'manual_slot_verified':bool(manual and choice_again),'console_errors':len(errors),'failed_requests':len(failed),'PASS':not errors and not failed and persisted and ssd and manual and choice_again})
  if not result['PASS']:raise AssertionError(str(result))
 finally:
  (OUT/'REAL_WALTER_RELEASE_GATE.json').write_text(json.dumps(result,indent=2),encoding='utf8')
  shutil.copy2(backup,STATE)
  if sha(STATE)!=before_hash:raise RuntimeError('Walter state restore hash mismatch')
  if chrome:chrome.terminate()
 if not result['PASS']:return 1
 return 0
if __name__=='__main__':sys.exit(main())
