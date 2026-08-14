import json,subprocess,tempfile,time
from pathlib import Path
import requests
from websockets.sync.client import connect
ROOT=Path(__file__).resolve().parents[2];PORT=9561
class C:
 def __init__(self,u):self.w=connect(u,max_size=None,ping_interval=None);self.i=0;self.events=[]
 def cmd(self,m,p=None):
  self.i+=1;i=self.i;self.w.send(json.dumps({'id':i,'method':m,'params':p or {}}))
  while 1:
   x=json.loads(self.w.recv())
   if x.get('id')==i:return x.get('result',{})
   self.events.append(x)
 def js(self,s):return self.cmd('Runtime.evaluate',{'expression':s,'awaitPromise':True,'returnByValue':True})['result'].get('value')
def wait(u):
 for _ in range(100):
  try:
   if requests.get(u,timeout=.5).ok:return
  except:pass
  time.sleep(.2)
 raise RuntimeError(u)
def main():
 subprocess.run([str(ROOT/'START_SCENE_BRAIN.bat')],cwd=ROOT,check=True);wait('http://127.0.0.1:43127')
 d=Path(tempfile.mkdtemp());script=d/'script.txt';script.write_text('Hank Schrader reads the book while Walter White watches.')
 chrome=subprocess.Popen([r'C:\Program Files\Google\Chrome\Application\chrome.exe',f'--remote-debugging-port={PORT}',f'--user-data-dir={d/"profile"}','--headless=new','--window-size=1440,900','http://127.0.0.1:43127/'])
 try:
  wait(f'http://127.0.0.1:{PORT}/json');t=next(x for x in requests.get(f'http://127.0.0.1:{PORT}/json').json() if x['type']=='page');c=C(t['webSocketDebuggerUrl'])
  for x in ('Page.enable','Runtime.enable','Log.enable'):c.cmd(x)
  for _ in range(80):
   if c.js("!!document.querySelector('#newProject')"):break
   time.sleep(.1)
  c.js("document.querySelector('#libraryHome').click()");time.sleep(1);library=c.js("document.querySelectorAll('.project-card').length===6");c.js("document.querySelector('#projectsNav').click()");time.sleep(.5);c.js("document.querySelector('#newProject').click()");time.sleep(.5)
  root=c.cmd('DOM.getDocument')['root']['nodeId'];node=c.cmd('DOM.querySelector',{'nodeId':root,'selector':'#intakeScript'})['nodeId'];c.cmd('DOM.setFileInputFiles',{'nodeId':node,'files':[str(script)]});c.js("document.querySelector('#analyzeProject').click()");time.sleep(1);analysis=c.js("document.querySelector('#projectAnalysis').textContent.includes('Project Analysis')&&document.querySelector('#projectAnalysis').textContent.includes('Hank')")
  c.js("document.querySelector('#projectsNav').click()");time.sleep(.7);c.js("document.querySelector('[data-edit=\"walter_book_project\"]').click()");time.sleep(2);editor=c.js("!!document.querySelector('.timeline')&&!!document.querySelector('#stage')&&!!document.querySelector('#supportBtn')&&track('V1').magnetic===false")
  first=c.js("project.clips.find(x=>x.trackId==='V1')?.id");c.js(f"selectClip('{first}')");time.sleep(.2);operations=c.js("!!document.querySelector('#cropCanvas')&&!!document.querySelector('[data-clipnum=duration]')&&!!document.querySelector('#replaceSceneBrain')")
  errors=[e for e in c.events if e.get('method')=='Runtime.exceptionThrown'];r={'library':library,'analysis':analysis,'editor':editor,'operations':operations,'console_errors':len(errors),'PASS':all([library,analysis,editor,operations,not errors])}
  (ROOT/'qa_artifacts'/'V15_EMPLOYEE_BROWSER_QA.json').write_text(json.dumps(r,indent=2));
  if not r['PASS']:raise AssertionError(r)
 finally:chrome.terminate()
if __name__=='__main__':main()
