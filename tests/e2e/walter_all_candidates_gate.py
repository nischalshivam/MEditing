from __future__ import annotations
import base64,hashlib,json,subprocess,sys,tempfile,time
from io import BytesIO
from pathlib import Path
import requests
from PIL import Image
from websockets.sync.client import connect

ROOT=Path(__file__).resolve().parents[2];STATE=Path(r'E:\Movies\.scene_brain\projects\walter_book_project\EDITOR_PROJECT.json');OUT=ROOT/'qa_artifacts';PORT=9230;URL='http://127.0.0.1:8780/?ui=walter-review-v2#projects'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def wait_http(u,n=30):
 for _ in range(n*5):
  try:
   if requests.get(u,timeout=1).ok:return
  except:pass
  time.sleep(.2)
 raise RuntimeError('health timeout '+u)
class CDP:
 def __init__(self,ws):self.ws=connect(ws,max_size=32*1024*1024);self.i=0;self.events=[]
 def cmd(self,m,p=None):
  self.i+=1;i=self.i;self.ws.send(json.dumps({'id':i,'method':m,'params':p or {}}))
  while 1:
   x=json.loads(self.ws.recv())
   if x.get('id')==i:
    if 'error'in x:raise RuntimeError(str(x['error']))
    return x.get('result',{})
   self.events.append(x)
 def js(self,s):
  r=self.cmd('Runtime.evaluate',{'expression':s,'awaitPromise':True,'returnByValue':True})
  if r.get('exceptionDetails'):raise RuntimeError(str(r['exceptionDetails']))
  return r.get('result',{}).get('value')
 def wait(self,e,n=20):
  for _ in range(n*10):
   try:
    v=self.js(e)
    if v:return v
   except:pass
   time.sleep(.1)
  raise AssertionError('timeout '+e)
 def shot(self,clip):return base64.b64decode(self.cmd('Page.captureScreenshot',{'format':'png','clip':clip})['data'])
def screenshot_metrics(data):
 im=Image.open(BytesIO(data)).convert('RGB');small=im.resize((min(240,im.width),min(135,im.height)));vals=[.2126*r+.7152*g+.0722*b for r,g,b in small.getdata()];m=sum(vals)/len(vals);sd=(sum((x-m)**2 for x in vals)/len(vals))**.5;return {'mean':m,'std':sd,'nonblack':sum(x>15 for x in vals)/len(vals),'size':f'{im.width}x{im.height}'}
def main():
 OUT.mkdir(exist_ok=True);pre=sha(STATE);chrome=None;rows=[];result={'total_needs_choice_slots':0,'total_candidates_tested':0,'video_candidates_tested':0,'image_candidates_tested':0,'passed_candidates':0,'black_preview_candidates':0,'broken_media_candidates':0,'failed_slot_ids':[],'failed_candidate_ids':[],'console_errors':0,'failed_requests':0,'pre_test_state_hash':pre,'PASS':False}
 try:
  subprocess.run([str(ROOT/'START_SCENE_BRAIN.bat')],cwd=ROOT,check=True);wait_http('http://127.0.0.1:8780/api/health');profile=tempfile.mkdtemp(prefix='walter-all-');chrome=subprocess.Popen([r'C:\Program Files\Google\Chrome\Application\chrome.exe',f'--remote-debugging-port={PORT}',f'--user-data-dir={profile}','--headless=new','--autoplay-policy=no-user-gesture-required','--window-size=1440,1000',URL]);wait_http(f'http://127.0.0.1:{PORT}/json/version');targets=requests.get(f'http://127.0.0.1:{PORT}/json').json();t=next(x for x in targets if x.get('type')=='page' and '127.0.0.1:8780' in x.get('url',''));c=CDP(t['webSocketDebuggerUrl'])
  for m in ['Page.enable','Runtime.enable','Network.enable','Log.enable']:c.cmd(m)
  c.wait("document.querySelectorAll('#projectcards [data-open]').length>0");c.js("[...document.querySelectorAll('#projectcards .card')].find(x=>x.textContent.includes('Why Walter White Kept the Book That Exposed Him')&&x.textContent.includes('READY FOR FINAL FOOTAGE AUDIT')).querySelector('[data-open]').click()");c.wait("document.querySelectorAll('#track .clip').length===70")
  queue=c.js("P.timeline.map((x,i)=>({i,id:x.presentation_slot_id,state:x.approval_state,count:(x.candidates||[]).length})).filter(x=>x.state==='NEEDS_CHOICE')");result['total_needs_choice_slots']=len(queue)
  for qi,q in enumerate(queue):
   c.js(f"selectClip({q['i']});openDrawer()")
   rendered=c.wait("document.querySelectorAll('#candidates .candidate').length")
   if rendered!=q['count']:raise AssertionError(f"card mismatch {q['id']}: {rendered}/{q['count']}")
   for ci in range(q['count']):
    cid=f"{q['id']}:CANDIDATE_{ci+1}";row={'slot_id':q['id'],'candidate_id':cid,'PASS':False}
    try:
     c.js(f"previewCandidate({ci})")
     kind=c.wait("(()=>{let v=document.querySelector('#preview video'),i=document.querySelector('#preview img');if(v&&v.readyState>=2&&v.videoWidth>0)return 'VIDEO';if(i&&i.complete&&i.naturalWidth>0)return 'IMAGE';return null})()",30);row['media_type']=kind
     if kind=='VIDEO':
      result['video_candidates_tested']+=1
      info=c.js("(()=>{let v=document.querySelector('#preview video'),r=v.getBoundingClientRect(),s=getComputedStyle(v),e=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);return {src:v.currentSrc,ready:v.readyState,duration:v.duration,width:v.videoWidth,height:v.videoHeight,rect:{x:r.x,y:r.y,width:r.width,height:r.height},visible:s.visibility==='visible'&&s.display!='none'&&+s.opacity>.9,center:e===v,start:v.currentTime}})()")
      c.js(f"(()=>{{let v=document.querySelector('#preview video');v.currentTime=Math.min(v.duration-.1,{info['start']}+2);return new Promise(ok=>v.addEventListener('seeked',()=>ok(true),{{once:true}}))}})()")
      frame=c.js("(()=>{let v=document.querySelector('#preview video'),q=document.createElement('canvas');q.width=v.videoWidth;q.height=v.videoHeight;let x=q.getContext('2d');x.drawImage(v,0,0);let d=x.getImageData(0,0,q.width,q.height).data,sum=0,sq=0,n=0,nb=0;for(let j=0;j<d.length;j+=16){let y=.2126*d[j]+.7152*d[j+1]+.0722*d[j+2];sum+=y;sq+=y*y;nb+=y>15;n++}let m=sum/n;return {mean:m,std:Math.sqrt(sq/n-m*m),nonblack:nb/n}})()")
      r=info['rect'];screen=screenshot_metrics(c.shot({'x':r['x'],'y':r['y'],'width':r['width'],'height':r['height'],'scale':1}));ok=info['visible'] and info['center'] and info['ready']>=2 and info['duration']>0 and frame['nonblack']>.05 and frame['std']>5 and screen['nonblack']>.05 and screen['std']>5;row.update({'source':info['src'],'ready_state':info['ready'],'duration':info['duration'],'dimensions':f"{info['width']}x{info['height']}",'canvas_pixels':frame,'visible_screenshot':screen,'PASS':ok})
      if not ok:result['black_preview_candidates']+=1
     else:
      result['image_candidates_tested']+=1;info=c.js("(()=>{let i=document.querySelector('#preview img'),r=i.getBoundingClientRect(),s=getComputedStyle(i);return {src:i.currentSrc,width:i.naturalWidth,height:i.naturalHeight,rect:{x:r.x,y:r.y,width:r.width,height:r.height},visible:s.visibility==='visible'&&s.display!='none'&&+s.opacity>.9}})()")
      r=info['rect'];screen=screenshot_metrics(c.shot({'x':r['x'],'y':r['y'],'width':r['width'],'height':r['height'],'scale':1}));ok=info['visible'] and info['width']>0 and info['height']>0 and screen['nonblack']>.05 and screen['std']>5;row.update({'source':info['src'],'dimensions':f"{info['width']}x{info['height']}",'visible_screenshot':screen,'PASS':ok})
      if not ok:result['black_preview_candidates']+=1
    except Exception as e:row['error']=str(e);result['broken_media_candidates']+=1
    rows.append(row);result['total_candidates_tested']+=1
    if row['PASS']:result['passed_candidates']+=1
    else:result['failed_candidate_ids'].append(cid);result['failed_slot_ids'].append(q['id'])
  errors=[e for e in c.events if e.get('method')=='Runtime.exceptionThrown' or(e.get('method')=='Log.entryAdded' and e.get('params',{}).get('entry',{}).get('level')=='error')];failed=[e for e in c.events if e.get('method')=='Network.loadingFailed' and not e.get('params',{}).get('canceled')];result['console_errors']=len(errors);result['failed_requests']=len(failed);result['candidates']=rows
 finally:
  post=sha(STATE);result['post_test_state_hash']=post;result['project_state_unchanged']=post==pre;result['failed_slot_ids']=sorted(set(result['failed_slot_ids']));result['PASS']=bool(result['total_needs_choice_slots']>0 and result['total_candidates_tested']==result['passed_candidates'] and not result['black_preview_candidates'] and not result['broken_media_candidates'] and not result['failed_slot_ids'] and result['console_errors']==0 and result['failed_requests']==0 and result['project_state_unchanged']);(OUT/'WALTER_ALL_CANDIDATES_QA.json').write_text(json.dumps(result,indent=2),encoding='utf8');
  if chrome:chrome.terminate()
 if not result['PASS']:raise AssertionError(json.dumps({k:v for k,v in result.items() if k!='candidates'},indent=2))
 return 0
if __name__=='__main__':sys.exit(main())
