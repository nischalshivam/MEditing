"""Real Chrome employee journey for title onboarding and product hardening."""
from __future__ import annotations
import base64, json, shutil, sqlite3, subprocess, tempfile, time
from pathlib import Path
import requests
from websockets.sync.client import connect

ROOT=Path(__file__).resolve().parents[2]; PORT=9564; MEDIA=Path(r"E:\Movies")
MOVIE="SceneBrain QA Movie 20260814"; SERIES="SceneBrain QA Series 20260814"
class C:
 def __init__(self,u):self.w=connect(u,max_size=None,ping_interval=None);self.i=0;self.events=[]
 def cmd(self,m,p=None):
  self.i+=1;i=self.i;self.w.send(json.dumps({'id':i,'method':m,'params':p or {}}))
  while 1:
   x=json.loads(self.w.recv())
   if x.get('id')==i:return x.get('result',{})
   self.events.append(x)
 def js(self,s):return self.cmd('Runtime.evaluate',{'expression':s,'awaitPromise':True,'returnByValue':True})['result'].get('value')
def wait(u,n=150):
 for _ in range(n):
  try:
   if requests.get(u,timeout=.5).ok:return
  except:pass
  time.sleep(.2)
 raise RuntimeError(u)
def dom_file(c,selector,files):
 root=c.cmd('DOM.getDocument')['root']['nodeId'];node=c.cmd('DOM.querySelector',{'nodeId':root,'selector':selector})['nodeId'];c.cmd('DOM.setFileInputFiles',{'nodeId':node,'files':[str(x) for x in files]})
def shot(c,name):
 data=c.cmd('Page.captureScreenshot',{'format':'png','captureBeyondViewport':False})['data'];(ROOT/'qa_artifacts'/name).write_bytes(base64.b64decode(data))
def cleanup():
 for name in (MOVIE,SERIES):
  p=(MEDIA/name).resolve()
  if p.parent==MEDIA.resolve() and p.name in (MOVIE,SERIES) and p.exists():shutil.rmtree(p)
 db=MEDIA/'.scene_brain/catalog.db'
 with sqlite3.connect(db) as cx:
  ids=[r[0] for r in cx.execute('select title_id from titles where display_name in (?,?)',(MOVIE,SERIES))]
  for tid in ids:
   source_ids=[r[0] for r in cx.execute('select source_id from sources where title_id=?',(tid,))]
   for sid in source_ids:
    for table in ('subtitles','transcript_jobs','rich_jobs','permanent_indexes'):cx.execute(f'delete from {table} where source_id=?',(sid,))
   cx.execute('delete from sources where title_id=?',(tid,))
   cx.execute('delete from titles where title_id=?',(tid,))
def main():
 cleanup(); subprocess.run([str(ROOT/'START_SCENE_BRAIN.bat')],cwd=ROOT,check=True);wait('http://127.0.0.1:43127/api/health')
 tmp=Path(tempfile.mkdtemp());script=tmp/'script.txt';script.write_text('Hank Schrader reads the book while Walter White watches.',encoding='utf8')
 movie=tmp/'qa_movie.mp4';series=tmp/'series';series.mkdir();eps=[series/'SceneBrain.QA.S01E01.mp4',series/'SceneBrain.QA.S01E02.mp4']
 for p in [movie,*eps]:subprocess.run(['ffmpeg','-y','-f','lavfi','-i','color=c=blue:s=320x180:d=0.5','-c:v','libx264','-pix_fmt','yuv420p',str(p)],capture_output=True,check=True)
 port=12000+(int(time.time())%1000)
 chrome=subprocess.Popen([r'C:\Program Files\Google\Chrome\Application\chrome.exe',f'--remote-debugging-port={port}',f'--user-data-dir={tmp/"profile"}','--headless=new','--window-size=1366,768','http://127.0.0.1:43127/?product-gate'])
 result={}
 try:
  wait(f'http://127.0.0.1:{port}/json');t=next(x for x in requests.get(f'http://127.0.0.1:{port}/json').json() if x['type']=='page');c=C(t['webSocketDebuggerUrl'])
  for x in ('Page.enable','Runtime.enable','Log.enable','Network.enable'):c.cmd(x)
  for _ in range(80):
   if c.js("!!document.querySelector('#libraryHome')"):break
   time.sleep(.1)
  c.js("document.querySelector('#libraryHome').click()");time.sleep(.7);result['library_navigation']=c.js("document.querySelectorAll('.library-card').length===6");shot(c,'library_final_1366.png')
  # Movie onboarding through real controls.
  c.js("document.querySelector('#addTitle').click()");time.sleep(.2);shot(c,'add_title_final.png');c.js(f"document.querySelector('#titleName').value={json.dumps(MOVIE)}")
  dom_file(c,'#titleFiles',[movie]);c.js("document.querySelector('#previewTitle').click()");result['movie_preview']=c.js("document.querySelector('#titlePreview').textContent.includes('READY')");c.js("document.querySelector('#commitTitle').click()")
  for _ in range(180):
   time.sleep(.25)
   if c.js(f"document.body.textContent.includes({json.dumps(MOVIE)})"):break
  result['add_movie']=c.js(f"document.body.textContent.includes({json.dumps(MOVIE)})")
  # Series onboarding and episode parsing.
  c.js("document.querySelector('#addTitle').click()");time.sleep(.2);c.js(f"document.querySelector('#titleType').value='SERIES';document.querySelector('#titleType').dispatchEvent(new Event('change'));document.querySelector('#titleName').value={json.dumps(SERIES)}")
  # CDP cannot synthesize a native directory picker; feed the two files into the
  # exact same multi-file control after removing only the automation-only flag.
  c.js("document.querySelector('#titleFiles').removeAttribute('webkitdirectory')")
  dom_file(c,'#titleFiles',eps);c.js("document.querySelector('#previewTitle').click()");result['series_preview']=c.js("document.querySelectorAll('#titlePreview b').length===2&&document.querySelector('#titlePreview').textContent.includes('READY')");c.js("document.querySelector('#commitTitle').click()")
  for _ in range(180):
   time.sleep(.25)
   if c.js(f"document.body.textContent.includes({json.dumps(SERIES)})"):break
  result['add_series']=c.js(f"document.body.textContent.includes({json.dumps(SERIES)})")
  # New Project upload, analysis, preparation gate/progress.
  c.js("document.querySelector('[data-nav=new]').click()");time.sleep(.5);result['new_titles_available']=c.js(f"[...document.querySelector('#intakeTitle').options].some(x=>x.textContent==={json.dumps(MOVIE)})&&[...document.querySelector('#intakeTitle').options].some(x=>x.textContent==={json.dumps(SERIES)})");shot(c,'new_project_final_1366.png')
  result['responsive']=True
  for w,h in ((1366,768),(1440,900),(1920,1080)):
   c.cmd('Emulation.setDeviceMetricsOverride',{'width':w,'height':h,'deviceScaleFactor':1,'mobile':False});time.sleep(.1)
   result['responsive'] &= bool(c.js("document.documentElement.scrollWidth<=document.documentElement.clientWidth"))
  c.cmd('Emulation.setDeviceMetricsOverride',{'width':1366,'height':768,'deviceScaleFactor':1,'mobile':False})
  dom_file(c,'#intakeScript',[script]);c.js("document.querySelector('#analyzeProject').click()");time.sleep(.7);result['analysis']=c.js("document.querySelector('#projectAnalysis').textContent.includes('Project Analysis')&&!document.querySelector('#prepareProject').disabled");shot(c,'new_project_analysis.png');c.js("document.querySelector('#prepareProject').click()");result['progress']=c.js("document.querySelector('#intakeStatus').textContent.includes('Preparing Project')")
  # Gallery and GPU pages.
  c.js("document.querySelector('[data-nav=library]').click()");time.sleep(.5);c.js("document.querySelector('[data-title=\"ttl_eccbfe16a2d49aac\"] [data-characters]').click()");time.sleep(.6);result['character_management']=c.js("document.querySelectorAll('.character-card').length===7&&document.querySelectorAll('.reference-strip img').length===24&&[...document.images].every(x=>x.complete&&x.naturalWidth>0)");shot(c,'character_gallery_breaking_bad.png')
  c.js("document.querySelector('[data-nav=performance]').click()");time.sleep(.4);result['gpu_diagnostics']=c.js("document.body.textContent.includes('Quadro P1000')&&document.body.textContent.includes('CPU (validated)')");shot(c,'performance_gpu.png')
  # Existing editor and support button; no project mutation.
  c.js("document.querySelector('[data-nav=projects]').click()");time.sleep(.5);c.js("document.querySelector('[data-edit]').click()");time.sleep(1.5);result['editor']=c.js("!!document.querySelector('.timeline')&&!!document.querySelector('#stage')&&!!document.querySelector('#supportBtn')");shot(c,'editor_final_1366.png');c.js("document.querySelector('#supportBtn').click()");time.sleep(.3);result['support']=c.js("document.querySelector('#toast').textContent.includes('Support report')")
  errors=[e for e in c.events if e.get('method')=='Runtime.exceptionThrown'];failed=[e for e in c.events if e.get('method')=='Network.responseReceived' and e.get('params',{}).get('response',{}).get('status',200)>=400]
  result.update(console_errors=len(errors),failed_requests=len(failed));result['PASS']=all(v is True for k,v in result.items() if k not in ('console_errors','failed_requests')) and not errors and not failed
 finally:
  chrome.terminate();chrome.wait(timeout=10);cleanup();shutil.rmtree(tmp,ignore_errors=True)
 (ROOT/'qa_artifacts'/'PRODUCT_ONBOARDING_BROWSER_QA.json').write_text(json.dumps(result,indent=2),encoding='utf8')
 print(json.dumps(result,indent=2));raise SystemExit(0 if result.get('PASS') else 1)
if __name__=='__main__':main()
