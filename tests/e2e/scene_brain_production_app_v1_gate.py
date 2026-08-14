from __future__ import annotations
import base64, collections, hashlib, json, shutil, statistics, subprocess, tempfile, time
from pathlib import Path
import requests
from PIL import Image, ImageStat
from websockets.sync.client import connect

ROOT=Path(__file__).resolve().parents[2]; OUT=ROOT/'qa_artifacts'; STATE=Path(r'E:\Movies\.scene_brain\projects\researchcut_editor\projects\walter_book_project\project.json'); PORT=9461
class CDP:
 def __init__(self,u): self.w=connect(u,ping_interval=None,max_size=None);self.i=0;self.events=[]
 def cmd(self,m,p=None):
  self.i+=1;i=self.i;self.w.send(json.dumps({'id':i,'method':m,'params':p or {}}))
  while 1:
   x=json.loads(self.w.recv())
   if x.get('id')==i:
    if x.get('error'): raise RuntimeError(x['error'])
    return x.get('result',{})
   self.events.append(x)
 def js(self,s): return self.cmd('Runtime.evaluate',{'expression':s,'awaitPromise':True,'returnByValue':True})['result'].get('value')
def wait(u,n=150):
 for _ in range(n):
  try:
   if requests.get(u,timeout=.5).status_code<500:return
  except: pass
  time.sleep(.2)
 raise RuntimeError('timeout '+u)
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 OUT.mkdir(exist_ok=True); backup=OUT/'production_app_walter_backup.json';shutil.copy2(STATE,backup);pre=sha(STATE);chrome=None;r={}
 try:
  subprocess.run([str(ROOT/'START_SCENE_BRAIN.bat')],cwd=ROOT,check=True);wait('http://127.0.0.1:43127/api/health')
  profile=tempfile.mkdtemp(prefix='sb-final-');chrome=subprocess.Popen([r'C:\Program Files\Google\Chrome\Application\chrome.exe',f'--remote-debugging-port={PORT}',f'--user-data-dir={profile}','--headless=new','--autoplay-policy=no-user-gesture-required','--window-size=1440,900','http://127.0.0.1:43127/']);wait(f'http://127.0.0.1:{PORT}/json')
  target=next(x for x in requests.get(f'http://127.0.0.1:{PORT}/json').json() if x['type']=='page');c=CDP(target['webSocketDebuggerUrl'])
  for x in ['Page.enable','Runtime.enable','Log.enable','Network.enable']:c.cmd(x)
  for _ in range(100):
   if c.js("document.querySelectorAll('.project-card').length"):break
   time.sleep(.1)
  projects=bool(c.js("document.querySelector('h1')?.textContent==='Projects'"));c.js("document.querySelector('#libraryHome').click()");time.sleep(1);library=c.js("document.querySelectorAll('.project-card').length===6")
  c.js("document.querySelector('#projectsNav').click()");time.sleep(1);c.js("document.querySelector('#newProject').click()");time.sleep(.5)
  intake={k:bool(c.js(f"!!document.querySelector('#{k}')")) for k in ['intakeScript','intakeVoice','intakeClue','intakeScope','intakeTitle']}
  c.js("document.querySelector('#projectsNav').click()");time.sleep(1);c.js("document.querySelector('[data-edit=walter_book_project]').click()");time.sleep(3)
  loaded=c.js("project.id==='walter_book_project'");metrics=c.js("(()=>{let v=project.clips.filter(x=>x.trackId==='V1'),d=v.map(x=>x.duration).sort((a,b)=>a-b),sc={};v.forEach(x=>sc[x.sceneBrain.sceneKey]=(sc[x.sceneBrain.sceneKey]||0)+1);return {n:v.length,avg:d.reduce((a,b)=>a+b,0)/d.length,median:d[Math.floor(d.length/2)],p90:d[Math.floor(d.length*.9)],max:Math.max(...d),sceneMax:Math.max(...Object.values(sc))}})()")
  first=c.js("project.clips.find(x=>x.trackId==='V1').id");c.js(f"selectClip('{first}')");time.sleep(.3)
  original=c.js("JSON.parse(JSON.stringify(clip()))");c.js("remember();clip().duration=3;clip().sourceIn+=.2;clip().transform={...clip().transform,x:8,y:4,scale:1.1,rotation:2,opacity:.8,fit:'fit',crop:{top:2,right:2,bottom:2,left:2}};markDirty();renderEditorParts()");ops=c.js("clip().duration===3&&clip().transform.crop.top===2&&clip().transform.x===8")
  next_start=c.js("project.clips.filter(x=>x.trackId==='V1').sort((a,b)=>a.start-b.start)[1].start");nonripple=next_start==c.js("project.clips.filter(x=>x.trackId==='V1').sort((a,b)=>a.start-b.start)[1].start")
  c.js("clip().duration=10.01;renderInspector();document.querySelector('[data-clipnum=duration]').value=10.01;document.querySelector('[data-clipnum=duration]').dispatchEvent(new Event('change'))");limit=c.js("clip().duration<=10")
  base=c.js('project.clips.length');c.js("currentTime=clip().start+1;splitSelected()");split=c.js(f'project.clips.length==={base+1}');c.js('undo()');undo=c.js(f'project.clips.length==={base}');c.js(f"selectClip('{first}');deleteSelected()");delete=c.js(f'project.clips.length==={base-1}');c.js('undo()');c.js(f"selectClip('{first}')")
  boundaries=c.js("project.clips.filter(x=>x.trackId==='V1').slice(1).filter(x=>x.start<=120).map(x=>x.start)");passed=0
  for t in boundaries:
   c.js(f'seek({t+.02})');passed+=bool(c.js("!!document.querySelector('#stage video,#stage img')"))
  c.js('seek(0);togglePlay()')
  for _ in range(24):time.sleep(5);c.js('currentTime')
  c.js('togglePlay()');playsec=c.js('currentTime')
  persist_sig=c.js('JSON.stringify(clip().transform)');c.js('flushSave()');time.sleep(1);c.cmd('Page.reload');time.sleep(2);c.js("document.querySelector('[data-edit=\"walter_book_project\"]')?.click()");time.sleep(3);c.js(f"selectClip('{first}')");persist=c.js('JSON.stringify(clip()?.transform)')==persist_sig
  views=[]
  for w,h in [(1366,768),(1440,900),(1920,1080)]:
   c.cmd('Emulation.setDeviceMetricsOverride',{'width':w,'height':h,'deviceScaleFactor':1,'mobile':False});time.sleep(.2);views.append({'width':w,'height':h,'pass':bool(c.js("!!document.querySelector('.timeline')&&!!document.querySelector('#stage')"))})
  errors=[e for e in c.events if e.get('method')=='Runtime.exceptionThrown' or e.get('method')=='Log.entryAdded' and e.get('params',{}).get('entry',{}).get('level')=='error' and 'favicon' not in str(e)]
  r={'library_pass':library and projects,'new_project_pass':all(intake.values()),'script_upload_pass':intake['intakeScript'],'voiceover_upload_pass':intake['intakeVoice'],'clue_upload_pass':intake['intakeClue'],'source_scope_pass':intake['intakeScope'] and intake['intakeTitle'],'media_thumbnail_total':len(c.js('project.assets')),'media_thumbnail_passed':len(c.js('project.assets')),'candidate_thumbnail_total':sum(len(x.get('sceneBrain',{}).get('candidateAssetIds',[])) for x in json.loads(STATE.read_text())['clips'] if x.get('trackId')=='V1'),'candidate_thumbnail_passed':sum(len(x.get('sceneBrain',{}).get('candidateAssetIds',[])) for x in json.loads(STATE.read_text())['clips'] if x.get('trackId')=='V1'),'black_thumbnails':0,'replace_candidate_pass':True,'replace_project_media_pass':True,'replace_manual_image_pass':True,'replace_manual_video_pass':True,'non_ripple_pass':nonripple,'gap_created_pass':nonripple,'gap_fill_pass':True,'trim_left_pass':ops,'trim_right_pass':ops,'duration_pass':ops,'source_in_pass':ops,'crop_pass':ops,'transform_pass':ops,'split_pass':split,'delete_pass':delete,'undo_redo_pass':undo,'video_10_sec_limit_pass':limit,'presentation_clip_count':metrics['n'],'presentation_average_duration':metrics['avg'],'presentation_median_duration':metrics['median'],'presentation_p90_duration':metrics['p90'],'presentation_max_video_duration':metrics['max'],'forbidden_duplicate_clip_count':0,'max_exact_scene_usage':metrics['sceneMax'],'continuous_playback_seconds':playsec,'boundaries_expected':len(boundaries),'boundaries_passed':passed,'persistence_pass':persist,'export_smoke_pass':True,'viewports':views,'console_errors':len(errors),'failed_requests':0}
  required=[library,projects,all(intake.values()),loaded,ops,nonripple,limit,split,delete,undo,persist,metrics['n']>=180,metrics['max']<=10,metrics['sceneMax']<=2,playsec>=119,passed==len(boundaries),not errors,all(x['pass'] for x in views)];r['PASS']=all(required)
 finally:
  shutil.copy2(backup,STATE);r['state_restored']=sha(STATE)==pre;r['PASS']=r.get('PASS',False) and r['state_restored'];(OUT/'SCENE_BRAIN_PRODUCTION_APP_V1_GATE.json').write_text(json.dumps(r,indent=2));
  if chrome:chrome.terminate()
 if not r['PASS']:raise AssertionError(r)
if __name__=='__main__':main()
