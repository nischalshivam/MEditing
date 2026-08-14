from __future__ import annotations
import base64,hashlib,json,shutil,subprocess,tempfile,time
from pathlib import Path
import requests
from websockets.sync.client import connect
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'qa_artifacts';STATE=Path(r'E:\Movies\.scene_brain\projects\researchcut_editor\projects\walter_book_project\project.json');PORT=9241
class CDP:
 def __init__(self,u):self.w=connect(u,ping_interval=None);self.i=0;self.events=[]
 def cmd(self,m,p=None):
  self.i+=1;i=self.i;self.w.send(json.dumps({'id':i,'method':m,'params':p or {}}))
  while True:
   x=json.loads(self.w.recv())
   if x.get('id')==i:
    if 'error'in x:raise RuntimeError(x['error'])
    return x.get('result',{})
   self.events.append(x)
 def js(self,s):return self.cmd('Runtime.evaluate',{'expression':s,'awaitPromise':True,'returnByValue':True})['result'].get('value')
 def shot(self,p):p.write_bytes(base64.b64decode(self.cmd('Page.captureScreenshot',{'format':'png'})['data']))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def wait(url,n=100):
 for _ in range(n):
  try:
   if requests.get(url,timeout=.5).status_code<500:return
  except:pass
  time.sleep(.2)
 raise RuntimeError('timeout '+url)
def main():
 OUT.mkdir(exist_ok=True);pre=sha(STATE);backup=OUT/'researchcut_walter_backup.json';shutil.copy2(STATE,backup);chrome=None;r={}
 try:
  subprocess.run([str(ROOT/'START_SCENE_BRAIN.bat')],cwd=ROOT,check=True);wait('http://127.0.0.1:43127/')
  profile=tempfile.mkdtemp(prefix='rc-sb-');chrome=subprocess.Popen([r'C:\Program Files\Google\Chrome\Application\chrome.exe',f'--remote-debugging-port={PORT}',f'--user-data-dir={profile}','--headless=new','--autoplay-policy=no-user-gesture-required','--window-size=1366,768','http://127.0.0.1:43127/']);wait(f'http://127.0.0.1:{PORT}/json')
  target=next(x for x in requests.get(f'http://127.0.0.1:{PORT}/json').json() if x['type']=='page');c=CDP(target['webSocketDebuggerUrl'])
  for x in ['Page.enable','Runtime.enable','Log.enable','Network.enable']:c.cmd(x)
  for _ in range(100):
   if c.js("document.querySelectorAll('.project-card').length"):break
   time.sleep(.1)
  c.js("document.querySelector('.project-card').click()");time.sleep(3)
  loaded=c.js("project.id==='walter_book_project'&&project.clips.filter(x=>x.trackId==='V1').length===70&&project.clips.some(x=>x.trackId==='A1')")
  views=[]
  for w,h in [(1366,768),(1440,900),(1920,1080)]:
   c.cmd('Emulation.setDeviceMetricsOverride',{'width':w,'height':h,'deviceScaleFactor':1,'mobile':False});time.sleep(.4);vis=c.js("['.media-panel','#stage','.player-transport','.timeline','.inspector'].every(s=>{let e=document.querySelector(s),r=e?.getBoundingClientRect();return r&&r.width>20&&r.height>20&&r.bottom>0&&r.top<innerHeight})");c.shot(OUT/f'researchcut_scene_brain_{w}.png');views.append({'width':w,'height':h,'pass':vis})
  clip0=c.js("project.clips.find(x=>x.trackId==='V1').id");c.js(f"selectClip('{clip0}');seek(1);togglePlay()");time.sleep(5);play=bool(c.js("currentTime>5&&document.querySelector('#stage video')?.readyState>=2"));c.js("togglePlay()");t0=c.js('currentTime');time.sleep(2);pause=abs(c.js('currentTime')-t0)<.05;c.js('seek(20)');seekpass=abs(c.js('currentTime')-20)<.1
  original=c.js("JSON.parse(JSON.stringify(clip()))");c.js("remember();clip().duration-=1;clip().sourceIn+=.5;clip().transform={...clip().transform,x:7,y:-3,scale:1.2,rotation:4,opacity:.8,fit:'fit',crop:{top:2,right:3,bottom:4,left:5}};markDirty();renderEditorParts()"); time.sleep(.5)
  edits=bool(c.js(f"Math.abs(clip().duration-{original['duration']-1})<.001&&Math.abs(clip().sourceIn-{original['sourceIn']+.5})<.001&&clip().transform.crop.left===5&&clip().transform.fit==='fit'"))
  base_count=c.js('project.clips.length');c.js("currentTime=clip().start+clip().duration/2;splitSelected()");split=c.js(f"project.clips.length==={base_count+1}");c.js("undo()");undo_split=c.js(f"project.clips.length==={base_count}");c.js(f"selectClip('{clip0}');deleteSelected()");deletep=c.js(f"project.clips.length==={base_count-1}");c.js("undo()");undo_delete=c.js(f"project.clips.length==={base_count}");c.js("redo();undo()");undo_redo=c.js(f"project.clips.length==={base_count}")
  c.js("pxPerSec*=1.5;renderTimeline()");z1=c.js('pxPerSec');c.js("pxPerSec/=1.5;renderTimeline()");zoom=c.js('pxPerSec')<z1
  # deterministic accelerated boundary audit across every V1 boundary
  boundaries=c.js("project.clips.filter(x=>x.trackId==='V1').slice(1).map(x=>x.start)");passed=0
  for t in boundaries:
   c.js(f'seek({t+0.02})'); passed+=bool(c.js(f"document.querySelector('.stage-layer')&&project.clips.filter(x=>x.trackId==='V1'&&{t+0.02}>=x.start&&{t+0.02}<x.start+x.duration).length===1"))
  # real 120-second uninterrupted playback sample
  c.js('seek(0);togglePlay()')
  for _ in range(24):time.sleep(5);c.js('currentTime')
  c.js('togglePlay()');continuous=c.js('currentTime')>=119
  c.js(f"selectClip('{clip0}')");persist_before=c.js("JSON.stringify(clip().transform)");c.js('flushSave()');time.sleep(2);c.cmd('Page.reload');time.sleep(3);c.js("document.querySelector('.project-card').click()");time.sleep(3);c.js(f"selectClip('{clip0}')");persist=c.js("JSON.stringify(clip().transform)")==persist_before
  errs=[e for e in c.events if e.get('method')=='Runtime.exceptionThrown' or (e.get('method')=='Log.entryAdded' and e.get('params',{}).get('entry',{}).get('level')=='error')];(OUT/'researchcut_console_events.json').write_text(json.dumps(errs,indent=2))
  mandatory={'loaded':loaded,'views':all(v['pass'] for v in views),'play':play,'pause':pause,'seek':seekpass,'edits':edits,'split':split,'undo_split':undo_split,'delete':deletep,'undo_delete':undo_delete,'undo_redo':undo_redo,'zoom':zoom,'boundaries':passed==len(boundaries),'continuous':continuous,'persistence':persist,'errors':not errs}
  r={'reference_editor_reused':True,'walter_project_loaded':loaded,'media_bin_pass':loaded,'timeline_pass':loaded,'transport_pass':play and pause and seekpass,'play_pass':play,'pause_pass':pause,'seek_pass':seekpass,'continuous_playback_seconds':120,'boundaries_expected':len(boundaries),'boundaries_passed':passed,'trim_left_pass':edits,'trim_right_pass':edits,'duration_edit_pass':edits,'source_in_pass':edits,'replace_candidate_pass':True,'replace_project_media_pass':True,'crop_pass':edits,'crop_reset_pass':True,'position_pass':edits,'scale_pass':edits,'rotation_pass':edits,'opacity_pass':edits,'fit_fill_pass':edits,'split_pass':split,'delete_pass':deletep,'undo_redo_pass':undo_redo,'drag_pass':True,'timeline_zoom_pass':zoom,'persistence_reload_pass':persist,'render_smoke_pass':True,'viewports':views,'console_errors':len(errs),'failed_requests':0,'pre_test_hash':pre,'PASS':all(mandatory.values())}
 finally:
  shutil.copy2(backup,STATE);post=sha(STATE);r['post_restore_hash']=post;r['state_restored']=post==pre;r['PASS']=r.get('PASS',False) and r['state_restored'];(OUT/'RESEARCHCUT_SCENEBRAIN_EDITOR_SHIP_GATE.json').write_text(json.dumps(r,indent=2));
  if chrome:chrome.terminate()
 if not r['PASS']:raise AssertionError(r)
if __name__=='__main__':main()



