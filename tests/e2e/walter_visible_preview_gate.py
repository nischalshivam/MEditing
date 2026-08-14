from __future__ import annotations
import base64,hashlib,json,shutil,subprocess,sys,tempfile,time
from io import BytesIO
from pathlib import Path
import requests
from PIL import Image,ImageStat
from websockets.sync.client import connect

ROOT=Path(__file__).resolve().parents[2];PROJECT=Path(r'E:\Movies\.scene_brain\projects\walter_book_project');STATE=PROJECT/'EDITOR_PROJECT.json';OUT=ROOT/'qa_artifacts';PORT=9229;URL='http://127.0.0.1:8780/?ui=walter-review-v2#projects'
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
  r=self.cmd('Runtime.evaluate',{'expression':s,'awaitPromise':True,'returnByValue':True});
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
 def screenshot(self,clip=None):return base64.b64decode(self.cmd('Page.captureScreenshot',{'format':'png',**({'clip':clip} if clip else {})})['data'])
def pixels(data):
 im=Image.open(BytesIO(data)).convert('RGB');vals=[]
 for r,g,b in im.resize((min(320,im.width),min(180,im.height))).getdata():vals.append(.2126*r+.7152*g+.0722*b)
 mean=sum(vals)/len(vals);std=(sum((x-mean)**2 for x in vals)/len(vals))**.5;return {'mean_luminance':mean,'std_luminance':std,'nonblack_ratio':sum(x>15 for x in vals)/len(vals),'dimensions':f'{im.width}x{im.height}'}
def main():
 OUT.mkdir(exist_ok=True);backup=OUT/'walter_visible_gate_backup.json';shutil.copy2(STATE,backup);pre=sha(STATE);chrome=None;result={'project':'walter_book_project','pre_test_state_hash':pre,'PASS':False}
 try:
  subprocess.run([str(ROOT/'START_SCENE_BRAIN.bat')],cwd=ROOT,check=True);wait_http('http://127.0.0.1:8780/api/health');profile=tempfile.mkdtemp(prefix='walter-pixel-');chrome=subprocess.Popen([r'C:\Program Files\Google\Chrome\Application\chrome.exe',f'--remote-debugging-port={PORT}',f'--user-data-dir={profile}','--headless=new','--autoplay-policy=no-user-gesture-required','--window-size=1440,1000',URL]);wait_http(f'http://127.0.0.1:{PORT}/json/version');targets=requests.get(f'http://127.0.0.1:{PORT}/json').json();t=next(x for x in targets if x.get('type')=='page' and '127.0.0.1:8780' in x.get('url',''));c=CDP(t['webSocketDebuggerUrl'])
  for m in ['Page.enable','Runtime.enable','Network.enable','Log.enable']:c.cmd(m)
  c.wait("document.querySelectorAll('#projectcards [data-open]').length>0");c.js("[...document.querySelectorAll('#projectcards .card')].find(x=>x.textContent.includes('Why Walter White Kept the Book That Exposed Him')&&x.textContent.includes('READY FOR FINAL FOOTAGE AUDIT')).querySelector('[data-open]').click()");c.wait("document.querySelectorAll('#track .clip').length===70");c.js("document.querySelector('#issues').click()");c.wait("document.querySelectorAll('[data-preview-c]').length>0");slot=c.js("({id:P.timeline[sel].presentation_slot_id,count:P.timeline[sel].candidates.length,needs:P.timeline.filter(x=>x.approval_state==='NEEDS_CHOICE').length})");c.js("document.querySelector('[data-preview-c=\"0\"]').click()")
  info=c.wait("(()=>{let v=document.querySelector('#preview #player');if(!v||v.readyState<2)return null;let r=v.getBoundingClientRect(),s=getComputedStyle(v),p=getComputedStyle(v.parentElement),e=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);return {count:document.querySelectorAll('video').length,visibleCount:[...document.querySelectorAll('video')].filter(x=>{let q=x.getBoundingClientRect(),z=getComputedStyle(x);return q.width>0&&q.height>0&&z.display!='none'&&z.visibility==='visible'}).length,src:v.currentSrc,time:v.currentTime,rect:{x:r.x,y:r.y,width:r.width,height:r.height},display:s.display,visibility:s.visibility,opacity:s.opacity,zIndex:s.zIndex,objectFit:s.objectFit,parentVisibility:p.visibility,parentOpacity:p.opacity,parentOverflow:p.overflow,centerTag:e&&e.tagName,centerId:e&&e.id,classes:v.parentElement.className}})()",30)
  assert info['rect']['width']>200 and info['rect']['height']>100 and info['visibility']=='visible' and float(info['opacity'])>.9 and info['centerTag']=='VIDEO'
  samples=[];screens=[]
  for i,add in enumerate([1,2.5,4],1):
   c.js(f"(()=>{{let v=document.querySelector('#preview #player');v.currentTime={(info['time']+add):.3f};return new Promise(ok=>v.addEventListener('seeked',()=>ok(true),{{once:true}}))}})()")
   frame=c.js("(()=>{let v=document.querySelector('#preview #player'),q=document.createElement('canvas');q.width=v.videoWidth;q.height=v.videoHeight;let x=q.getContext('2d');x.drawImage(v,0,0);let d=x.getImageData(0,0,q.width,q.height).data,n=d.length/4,sum=0,sq=0,a15=0,a30=0;for(let i=0;i<d.length;i+=16){let y=.2126*d[i]+.7152*d[i+1]+.0722*d[i+2];sum+=y;sq+=y*y;a15+=y>15;a30+=y>30}let k=d.length/16,m=sum/k;return {time:v.currentTime,mean_luminance:m,std_luminance:Math.sqrt(sq/k-m*m),nonblack_ratio:a15/k,above30_ratio:a30/k}})()")
   samples.append(frame);r=info['rect'];clip={'x':r['x'],'y':r['y'],'width':r['width'],'height':r['height'],'scale':1};data=c.screenshot(clip);path=OUT/f'walter_visible_preview_{i}.png';path.write_bytes(data);metric={'file':str(path),**pixels(data)};screens.append(metric)
  full=c.screenshot();(OUT/'WALTER_PREVIEW_ACTUALLY_VISIBLE.png').write_bytes(full)
  video_ok=any(x['nonblack_ratio']>.08 and x['std_luminance']>8 for x in samples);screen_ok=any(x['nonblack_ratio']>.08 and x['std_luminance']>8 for x in screens);assert video_ok and screen_ok
  c.js("document.querySelector('[data-approve-c=\"0\"]').click()");c.wait(f"P.timeline.find(x=>x.presentation_slot_id==='{slot['id']}').approval_state==='APPROVED'&&P.timeline.filter(x=>x.approval_state==='NEEDS_CHOICE').length==={slot['needs']-1}");c.cmd('Page.reload',{'ignoreCache':True});c.wait("document.querySelectorAll('#projectcards [data-open]').length>0");c.js("[...document.querySelectorAll('#projectcards .card')].find(x=>x.textContent.includes('Why Walter White Kept the Book That Exposed Him')&&x.textContent.includes('READY FOR FINAL FOOTAGE AUDIT')).querySelector('[data-open]').click()");c.wait("document.querySelectorAll('#track .clip').length===70");persist=bool(c.js(f"P.timeline.find(x=>x.presentation_slot_id==='{slot['id']}').approval_state==='APPROVED'"));errors=[e for e in c.events if e.get('method')=='Runtime.exceptionThrown' or(e.get('method')=='Log.entryAdded' and e.get('params',{}).get('entry',{}).get('level')=='error')];failed=[e for e in c.events if e.get('method')=='Network.loadingFailed' and not e.get('params',{}).get('canceled')]
  result.update({'visible_video_element_count':info['visibleCount'],'all_video_elements':info['count'],'target_video_current_src':info['src'],'target_video_rect':info['rect'],'display':info['display'],'visibility':info['visibility'],'opacity':float(info['opacity']),'element_at_preview_center':f"{info['centerTag']}#{info['centerId']}",'object_fit':info['objectFit'],'parent_visibility':info['parentVisibility'],'parent_opacity':info['parentOpacity'],'parent_clipping':info['parentOverflow'],'preview_container_classes':info['classes'],'video_frame_samples':samples,'visible_screenshot_samples':screens,'video_pixels_nonblack':video_ok,'human_visible_preview_nonblack':screen_ok,'preview_playback_visible':video_ok and screen_ok,'approval_mutation_pass':True,'reload_persistence_pass':persist,'console_errors':len(errors),'failed_requests':len(failed)})
 finally:
  shutil.copy2(backup,STATE);post=sha(STATE);result.update({'post_restore_state_hash':post,'test_mutations_restored':post==pre});result['PASS']=bool(result.get('preview_playback_visible') and result.get('approval_mutation_pass') and result.get('reload_persistence_pass') and result['test_mutations_restored'] and result.get('console_errors')==0 and result.get('failed_requests')==0);(OUT/'REAL_WALTER_VISIBLE_PREVIEW_GATE.json').write_text(json.dumps(result,indent=2),encoding='utf8');
  if chrome:chrome.terminate()
 if not result['PASS']:raise AssertionError(str(result))
 return 0
if __name__=='__main__':sys.exit(main())
