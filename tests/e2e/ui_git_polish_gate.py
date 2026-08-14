"""Real Chrome gate for UI polish without mutating production projects."""
import base64,json,subprocess,tempfile,time
from pathlib import Path
import requests
from websockets.sync.client import connect
ROOT=Path(__file__).resolve().parents[2]
class C:
 def __init__(self,u):self.w=connect(u,max_size=None,ping_interval=None);self.i=0;self.events=[]
 def cmd(self,m,p=None):
  self.i+=1;i=self.i;self.w.send(json.dumps({'id':i,'method':m,'params':p or {}}))
  while 1:
   x=json.loads(self.w.recv())
   if x.get('id')==i:return x.get('result',{})
   self.events.append(x)
 def js(self,s):return self.cmd('Runtime.evaluate',{'expression':s,'awaitPromise':True,'returnByValue':True})['result'].get('value')
 def shot(self,name): (ROOT/'qa_artifacts'/name).write_bytes(base64.b64decode(self.cmd('Page.captureScreenshot',{'format':'png'})['data']))
def wait(url):
 for _ in range(150):
  try:
   if requests.get(url,timeout=.5).ok:return
  except:pass
  time.sleep(.2)
 raise RuntimeError(url)
def set_file(c,selector,file):
 root=c.cmd('DOM.getDocument')['root']['nodeId'];node=c.cmd('DOM.querySelector',{'nodeId':root,'selector':selector})['nodeId'];c.cmd('DOM.setFileInputFiles',{'nodeId':node,'files':[str(file)]})
def main():
 subprocess.run([str(ROOT/'START_SCENE_BRAIN.bat')],cwd=ROOT,check=True);wait('http://127.0.0.1:43127/api/health')
 tmp=Path(tempfile.mkdtemp());script=tmp/'script.txt';script.write_text('Mike Ehrmantraut protects his family. Walter White watches.',encoding='utf8');port=13000+int(time.time())%900
 chrome=subprocess.Popen([r'C:\Program Files\Google\Chrome\Application\chrome.exe',f'--remote-debugging-port={port}',f'--user-data-dir={tmp/"profile"}','--headless=new','--window-size=1366,768','http://127.0.0.1:43127/?ui-polish'])
 r={}
 try:
  wait(f'http://127.0.0.1:{port}/json');tab=next(x for x in requests.get(f'http://127.0.0.1:{port}/json').json() if x['type']=='page');c=C(tab['webSocketDebuggerUrl'])
  for x in ('Page.enable','Runtime.enable','Log.enable','Network.enable'):c.cmd(x)
  for _ in range(80):
   if c.js("!!document.querySelector('#newProject')"):break
   time.sleep(.1)
  c.js("document.querySelector('#libraryHome').click()");time.sleep(.5);c.shot('ui_library_final.png')
  c.js("document.querySelector('[data-nav=new]').click()");time.sleep(.6);r['guided']=c.js("document.querySelectorAll('.workflow-steps li').length===7");r['single']=c.js("document.querySelector('#intakeScope').value==='single'&&!!document.querySelector('#singleTitle')");c.shot('ui_new_project_single.png')
  c.js("document.querySelector('#intakeScope').value='franchise';document.querySelector('#intakeScope').dispatchEvent(new Event('change'))");time.sleep(.2);r['franchise']=c.js("document.querySelector('#franchiseTitles').textContent.includes('Breaking Bad')&&document.querySelector('#franchiseTitles').textContent.includes('Better Call Saul')");c.shot('ui_new_project_franchise.png')
  c.js("document.querySelector('#intakeScope').value='custom';document.querySelector('#intakeScope').dispatchEvent(new Event('change'));document.querySelector('#customAdd').click();document.querySelector('#customTitle').selectedIndex=1;document.querySelector('#customAdd').click();document.querySelector('#customTitle').selectedIndex=2;document.querySelector('#customAdd').click();document.querySelector('#customTitles [data-remove-title]').click();document.querySelector('#customTitle').selectedIndex=0;document.querySelector('#customAdd').click();document.querySelector('#customAdd').click()");r['custom']=c.js("document.querySelectorAll('#customTitles span').length===3");c.shot('ui_new_project_custom_multi.png')
  set_file(c,'#intakeScript',script);c.js("document.querySelector('#getCluePrompt').click()");time.sleep(.3);r['clue_prompt']=c.js("document.querySelector('#toast').textContent.includes('Clue V4 prompt')");c.js("document.querySelector('#copyReadyPrompt').click()");time.sleep(.3);r['copy_ready_prompt']=c.js("window.__lastReadyPrompt.includes('Mike Ehrmantraut protects his family')&&window.__lastReadyPrompt.includes('CURRENT SOURCE SCOPE')&&window.__lastReadyPrompt.includes('Breaking Bad')");c.shot('ui_clue_prompt.png')
  c.js("document.querySelector('#intakeName').value='UI polish persistence QA';document.querySelector('#analyzeProject').click()");time.sleep(.7);r['analysis']=c.js("document.querySelector('#projectAnalysis').textContent.includes('INPUT CONSISTENCY')&&!document.querySelector('#prepareProject').disabled");c.js("document.querySelector('#prepareProject').click()");time.sleep(.6);persisted=c.js("(async()=>{const p=(await api('/api/projects')).projects.find(x=>x.name==='UI polish persistence QA');if(!p)return false;const full=(await api('/api/projects/'+p.id)).project;const ok=full.sceneBrainIntake?.scopeMode==='custom'&&full.sceneBrainIntake.titleIds.length===3;await api('/api/projects/'+p.id,{method:'DELETE'});return ok})()");r['custom_persistence']=bool(persisted)
  c.js("document.querySelector('[data-nav=library]').click()");time.sleep(.4);c.js("document.querySelector('[data-title=\"ttl_eccbfe16a2d49aac\"] [data-characters]').click()");time.sleep(.5);c.js("document.querySelector('[data-manage-character]').click()");time.sleep(.5);r['character_manage']=c.js("!!document.querySelector('#addCharacterImages')&&!!document.querySelector('#importCharacterFolder')&&!!document.querySelector('#trustSelected')&&!!document.querySelector('#rejectSelected')&&document.querySelectorAll('.reference-card').length>0");c.shot('ui_character_manage_references.png');c.shot('ui_character_trust_review.png')
  c.js("document.querySelector('[data-nav=projects]').click()");time.sleep(.4);c.js("document.querySelector('[data-edit]').click()");time.sleep(1.2);const=None
  r['play_visible']=c.js("(()=>{const b=document.querySelector('#playBtn'),x=b.getBoundingClientRect();return x.width>=44&&x.height>=44&&b.getAttribute('aria-label')==='Play'})()")
  before=c.js('currentTime');c.js("document.querySelector('#playBtn').click()");time.sleep(.7);after=c.js('currentTime');r['play_sync']=bool(after>before and c.js("playing&&document.querySelector('#playBtn').getAttribute('aria-label')==='Pause'"));c.js("document.querySelector('#playBtn').click()");paused=c.js('currentTime');time.sleep(.3);r['pause_sync']=abs(c.js('currentTime')-paused)<.05
  c.js("document.querySelector('#playerSeek').value=Math.min(10,duration());document.querySelector('#playerSeek').dispatchEvent(new Event('input'))");r['scrub']=c.js("Math.abs(currentTime-Math.min(10,duration()))<.1")
  r['auto_switch']=c.js("(()=>{const vs=project.clips.filter(x=>x.trackId==='V1').sort((a,b)=>a.start-b.start);if(vs.length<3)return false;seek(vs[0].start+.01);const a=document.querySelector('.stage-layer')?.dataset.clip;seek(vs[2].start+.01);return a&&document.querySelector('.stage-layer')?.dataset.clip!==a})()")
  r['thumbnails']=c.js("[...document.querySelectorAll('.asset-thumb')].every(x=>x.querySelector('.thumb-error')?.classList.contains('hidden')!==false)");c.shot('ui_editor_transport.png')
  r['gap']=c.js("(()=>{const vs=project.clips.filter(x=>x.trackId==='V1').sort((a,b)=>a.start-b.start);for(let i=1;i<vs.length;i++)if(vs[i].start>vs[i-1].start+vs[i-1].duration+.05){seek(vs[i-1].start+vs[i-1].duration+.01);return !!document.querySelector('#gapAddMedia')&&!!document.querySelector('#gapCandidates')}return true})()");c.shot('ui_editor_gap.png')
  visible=c.js("document.body.innerText");r['encoding']=not any(x in visible for x in ('Ã','â€','ï¼','ðŸ','Â·','�'))
  errors=[x for x in c.events if x.get('method')=='Runtime.exceptionThrown'];failed=[x for x in c.events if x.get('method')=='Network.responseReceived' and x.get('params',{}).get('response',{}).get('status',200)>=400]
  r['console_errors']=len(errors);r['failed_requests']=len(failed);r['PASS']=all(v is True for k,v in r.items() if k not in ('console_errors','failed_requests')) and not errors and not failed
 finally:
  chrome.terminate();chrome.wait(timeout=10)
 (ROOT/'qa_artifacts'/'UI_GIT_POLISH_BROWSER_QA.json').write_text(json.dumps(r,indent=2),encoding='utf8');print(json.dumps(r,indent=2));raise SystemExit(0 if r.get('PASS') else 1)
if __name__=='__main__':main()
