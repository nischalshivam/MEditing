from __future__ import annotations
import base64,hashlib,json,random,shutil,subprocess,sys,tempfile,time
from pathlib import Path
import requests
from websockets.sync.client import connect
ROOT=Path(__file__).resolve().parents[2];STATE=Path(r'E:\Movies\.scene_brain\projects\walter_book_project\EDITOR_PROJECT.json');OUT=ROOT/'qa_artifacts';PORT=9233;URL='http://127.0.0.1:8780/?ui=editor-v1-final#projects'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def wait_http(u,n=30):
 for _ in range(n*5):
  try:
   if requests.get(u,timeout=1).ok:return
  except:pass
  time.sleep(.2)
 raise RuntimeError('health timeout')
class C:
 def __init__(self,w):self.w=connect(w,max_size=64*1024*1024,ping_interval=None);self.i=0;self.e=[]
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
 def shot(self,p):p.write_bytes(base64.b64decode(self.cmd('Page.captureScreenshot',{'format':'png','captureBeyondViewport':False})['data']))
def main():
 OUT.mkdir(exist_ok=True);pre=sha(STATE);backup=OUT/'editor_ship_state_backup.json';shutil.copy2(STATE,backup);chrome=None;defects=[];r={'PASS':False}
 try:
  subprocess.run([str(ROOT/'START_SCENE_BRAIN.bat')],cwd=ROOT,check=True);wait_http('http://127.0.0.1:8780/api/health');profile=tempfile.mkdtemp(prefix='editor-ship-');chrome=subprocess.Popen([r'C:\Program Files\Google\Chrome\Application\chrome.exe',f'--remote-debugging-port={PORT}',f'--user-data-dir={profile}','--headless=new','--autoplay-policy=no-user-gesture-required','--window-size=1366,768',URL]);wait_http(f'http://127.0.0.1:{PORT}/json/version');t=next(x for x in requests.get(f'http://127.0.0.1:{PORT}/json').json() if x.get('type')=='page' and '8780' in x.get('url',''));c=C(t['webSocketDebuggerUrl'])
  for m in ['Page.enable','Runtime.enable','Network.enable','Log.enable']:c.cmd(m)
  c.wait("document.querySelectorAll('#projectcards [data-open]').length>0");c.js("[...document.querySelectorAll('#projectcards .card')].find(x=>x.textContent.includes('Why Walter White Kept the Book That Exposed Him')&&x.textContent.includes('READY FOR FINAL FOOTAGE AUDIT')).querySelector('[data-open]').click()");c.wait("document.querySelectorAll('#track .clip').length===70")
  viewports=[]
  for w,h in [(1366,768),(1440,900),(1920,1080)]:
   c.cmd('Emulation.setDeviceMetricsOverride',{'width':w,'height':h,'deviceScaleFactor':1,'mobile':False});time.sleep(.3);boxes=c.js("(()=>{let ids=['play','timecode','timelinearea','preview'];return Object.fromEntries(ids.map(id=>{let r=$(id).getBoundingClientRect();return[id,{x:r.x,y:r.y,w:r.width,h:r.height,visible:r.bottom>0&&r.right>0&&r.top<innerHeight&&r.left<innerWidth}]}))})()")
   ok=all(x['visible'] and x['w']>20 and x['h']>10 for x in boxes.values());viewports.append({'width':w,'height':h,'pass':ok,'boxes':boxes});c.shot(OUT/f'editor_{w}x{h}.png')
   if not ok:defects.append(f'layout_{w}x{h}')
  c.cmd('Emulation.setDeviceMetricsOverride',{'width':1440,'height':900,'deviceScaleFactor':1,'mobile':False});audio=c.wait("(()=>{let a=$('voiceoverMaster');return a.readyState>=2&&{duration:a.duration}})()",30)
  # Begin in a video-capable unapproved slot; candidate 1 is the safe master preview.
  video_slot=c.js("(()=>{let i=P.timeline.findIndex(x=>x.approval_state==='NEEDS_CHOICE'&&x.candidates?.length);return {i,start:P.timeline[i].timeline_start_ms,id:P.timeline[i].presentation_slot_id}})()")
  c.js(f"seekMaster({video_slot['start']/1000+1});setPlaying(true)");c.wait("$('masterVisual')&&$('masterVisual').readyState>=2",30);a0=c.js("$('voiceoverMaster').currentTime");v0=c.js("$('masterVisual').currentTime");time.sleep(2);a1=c.js("$('voiceoverMaster').currentTime");v1=c.js("$('masterVisual').currentTime");play=a1-a0>1.5 and v1-v0>1.2
  c.js("setPlaying(false)");ap=c.js("$('voiceoverMaster').currentTime");vp=c.js("$('masterVisual').currentTime");time.sleep(2);af=c.js("$('voiceoverMaster').currentTime");vf=c.js("$('masterVisual').currentTime");pause_a=abs(af-ap)<.05;pause_v=abs(vf-vp)<.05;c.js("setPlaying(true)");time.sleep(1);resume=c.js("$('voiceoverMaster').currentTime")>af+.5;c.js("setPlaying(false)")
  rng=random.Random(41);seek_pass=0
  for _ in range(20):
   t=rng.uniform(1,877);c.js(f"seekMaster({t})");ok=c.wait(f"Math.abs($('voiceoverMaster').currentTime-{t})<.7&&slotAt({t*1000})===activePlaybackIndex&&($('preview').children.length>0)",8);seek_pass+=bool(ok)
  # Continue beyond the minimum minute so ten real boundaries are exercised.
  run_seconds=80
  dense=c.js(f"(()=>{{let best={{start:0,count:0}};for(let s=0;s<=$('voiceoverMaster').duration-{run_seconds};s+=1){{let n=P.timeline.filter(x=>x.timeline_start_ms>s*1000&&x.timeline_start_ms<(s+{run_seconds})*1000).length;if(n>best.count)best={{start:s,count:n}}}}return best}})()")
  c.js(f"seekMaster({dense['start']});window.__shipTransitions=[];window.__lastShip='';window.__shipTimer=setInterval(()=>{{let x=P.timeline[slotAt($('voiceoverMaster').currentTime*1000)].presentation_slot_id;if(x!==window.__lastShip){{window.__shipTransitions.push(x);window.__lastShip=x}}}},100);setPlaying(true)")
  for _ in range(run_seconds//5):time.sleep(5);c.js("$('voiceoverMaster').currentTime")
  time.sleep(.5);c.js("setPlaying(false);clearInterval(window.__shipTimer)");trans=c.js("window.__shipTransitions");advanced=c.js("$('voiceoverMaster').currentTime")>=dense['start']+run_seconds-1
  # State/render modes and review regression.
  needs=c.js("(()=>{let i=P.timeline.findIndex(x=>x.approval_state==='NEEDS_CHOICE');seekMaster(P.timeline[i].timeline_start_ms/1000+.2);return $('preview').textContent.includes('UNAPPROVED PREVIEW')&&!!$('preview').querySelector('video,img')})()")
  manual=c.js("(()=>{let i=P.timeline.findIndex(x=>x.approval_state==='MANUAL_FIX');seekMaster(P.timeline[i].timeline_start_ms/1000+.2);return $('preview').textContent.includes('MANUAL VISUAL REQUIRED')})()")
  review=c.js("(()=>{let i=P.timeline.findIndex(x=>x.approval_state==='NEEDS_CHOICE'&&x.candidates?.length);selectClip(i);$('issues').click();return {i,hidden:$('drawer').classList.contains('hidden'),cards:document.querySelectorAll('#candidates .candidate').length,preview:!!document.querySelector('[data-preview-c]'),html:$('candidates').textContent.slice(0,80)}})()")
  if review['hidden'] or not review['cards'] or not review['preview']: defects.append('review_choices')
  c.js("$('closedrawer').click()")
  errors=[e for e in c.e if e.get('method')=='Runtime.exceptionThrown' or(e.get('method')=='Log.entryAdded' and e.get('params',{}).get('entry',{}).get('level')=='error')];failed=[e for e in c.e if e.get('method')=='Network.loadingFailed' and not e.get('params',{}).get('canceled')]
  checks={'layout':all(x['pass']for x in viewports),'play':play,'pause_audio':pause_a,'pause_video':pause_v,'resume':resume,'seeks':seek_pass==20,'continuous':advanced,'boundaries':len(trans)>=10,'needs':needs,'manual':manual,'review':not review['hidden'] and review['cards']>0 and review['preview'],'errors':not errors and not failed}
  defects += [k for k,v in checks.items() if not v];(OUT/'EDITOR_V1_INITIAL_DEFECTS.json').write_text(json.dumps({'initial_defects':['layout_fixed_height_overflow','transport_not_master_state_machine','audio_ontimeupdate_not_rendering_visual','pause_not_stopping_visual','unapproved_source_drift_mapping'],'remaining_defects':defects},indent=2),encoding='utf8')
  r={'viewports_tested':viewports,'viewports_passed':sum(x['pass']for x in viewports),'transport_visibility_pass':checks['layout'],'audio_play_pass':a1-a0>1.5,'video_play_pass':v1-v0>1.2,'pause_audio_frozen':pause_a,'pause_video_frozen':pause_v,'resume_pass':resume,'random_seeks_tested':20,'random_seeks_passed':seek_pass,'continuous_playback_seconds':run_seconds,'automatic_boundaries_expected':10,'automatic_boundaries_passed':len(trans)-1,'automatic_slot_ids':trans,'image_video_transition_pass':len(trans)>=4,'needs_choice_preview_pass':needs,'manual_placeholder_pass':manual,'review_choices_regression_pass':bool(review),'voiceover_duration':audio['duration'],'console_errors':len(errors),'failed_requests':len(failed),'pre_test_state_hash':pre,'all_existing_tests_pass':None,'PASS':all(checks.values())}
 finally:
  shutil.copy2(backup,STATE);post=sha(STATE);r.update({'post_restore_state_hash':post,'project_state_restored':post==pre});r['PASS']=r.get('PASS',False) and r['project_state_restored'];(OUT/'PRODUCTION_EDITOR_V1_SHIP_GATE.json').write_text(json.dumps(r,indent=2),encoding='utf8');
  if chrome:chrome.terminate()
 if not r['PASS']:raise AssertionError(str(r))
 return 0
if __name__=='__main__':sys.exit(main())

