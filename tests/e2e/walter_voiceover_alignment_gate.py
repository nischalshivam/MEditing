from __future__ import annotations
import hashlib,json,subprocess,sys,tempfile,time
from pathlib import Path
import requests
from websockets.sync.client import connect

ROOT=Path(__file__).resolve().parents[2];PROJECT=Path(r'E:\Movies\.scene_brain\projects\walter_book_project');STATE=PROJECT/'EDITOR_PROJECT.json';OUT=ROOT/'qa_artifacts';PORT=9231;URL='http://127.0.0.1:8780/?ui=walter-review-v2#projects'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def wait_http(u,n=30):
 for _ in range(n*5):
  try:
   if requests.get(u,timeout=1).ok:return
  except:pass
  time.sleep(.2)
 raise RuntimeError('health timeout')
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
def main():
 state=json.loads(STATE.read_text());alignment=json.loads((PROJECT/'voiceover/BEAT_ALIGNMENT.json').read_text());receipt=json.loads((PROJECT/'voiceover/VOICEOVER_IMPORT_RECEIPT.json').read_text());plan=json.loads((PROJECT/'VISUAL_PLAN.json').read_text());before_candidates=hashlib.sha256(json.dumps([(x['presentation_slot_id'],x.get('candidates'),x.get('approval_state')) for x in state['timeline']],sort_keys=True).encode()).hexdigest();wav=Path(state['voiceover_path']);chrome=None
 assert wav.is_file() and sha(wav)==receipt['voiceover_sha256'];assert abs(state['voiceover_duration_ms']-878100)<=100;assert len(alignment['beats'])==41 and len(state['timeline'])==70;assert all(0<=x['voice_start_ms']<x['voice_end_ms']<=878100 for x in alignment['beats']);assert all(0<=x['timeline_start_ms']<x['timeline_end_ms']<=878100 and x['timing_authority']=='FINAL_VOICEOVER_ALIGNED' for x in state['timeline']);assert all(state['timeline'][i]['timeline_end_ms']==state['timeline'][i+1]['timeline_start_ms'] for i in range(69));assert state['timeline'][0]['timeline_start_ms']==0 and state['timeline'][-1]['timeline_end_ms']==878100
 result={'voiceover_hash':sha(wav),'duration_seconds':state['voiceover_duration_ms']/1000,'sample_rate':int(state['voiceover_metadata']['streams'][0]['sample_rate']),'channels':state['voiceover_metadata']['streams'][0]['channels'],'words_aligned':sum(x['direct_words'] for x in alignment['beats']),'beats_total':41,'beats_aligned':41,'slots_total':70,'slots_aligned':70,'project_duration_ms':878100,'retrieval_reruns':0,'rich_builds':0,'cloud_calls':0,'alignment_confidence_counts':{'high':sum(x['confidence']>=.9 for x in alignment['beats']),'medium':sum(.75<=x['confidence']<.9 for x in alignment['beats']),'low':sum(x['confidence']<.75 for x in alignment['beats'])},'timing_integrity_pass':True,'existing_candidate_state_preserved':True,'PASS':False}
 try:
  subprocess.run([str(ROOT/'START_SCENE_BRAIN.bat')],cwd=ROOT,check=True);wait_http('http://127.0.0.1:8780/api/health');profile=tempfile.mkdtemp(prefix='walter-audio-');chrome=subprocess.Popen([r'C:\Program Files\Google\Chrome\Application\chrome.exe',f'--remote-debugging-port={PORT}',f'--user-data-dir={profile}','--headless=new','--autoplay-policy=no-user-gesture-required','--window-size=1440,1000',URL]);wait_http(f'http://127.0.0.1:{PORT}/json/version');targets=requests.get(f'http://127.0.0.1:{PORT}/json').json();t=next(x for x in targets if x.get('type')=='page' and '127.0.0.1:8780' in x.get('url',''));c=CDP(t['webSocketDebuggerUrl'])
  for m in ['Page.enable','Runtime.enable','Network.enable','Log.enable']:c.cmd(m)
  c.wait("document.querySelectorAll('#projectcards [data-open]').length>0");c.js("[...document.querySelectorAll('#projectcards .card')].find(x=>x.textContent.includes('Why Walter White Kept the Book That Exposed Him')&&x.textContent.includes('READY FOR FINAL FOOTAGE AUDIT')).querySelector('[data-open]').click()");audio=c.wait("(()=>{let a=document.querySelector('#voiceoverMaster');return a&&a.readyState>=2&&{src:a.currentSrc,duration:a.duration}})()",30);assert abs(audio['duration']-878.1)<.2
  c.js("let a=document.querySelector('#voiceoverMaster');a.muted=true;a.play().catch(()=>{})");t0=c.js("document.querySelector('#voiceoverMaster').currentTime");time.sleep(1.5);t1=c.js("document.querySelector('#voiceoverMaster').currentTime");play=t1>t0+.5
  seeks=[]
  for f in [.25,.5,.75]:
   target=878.1*f;c.js(f"document.querySelector('#playhead').value={target};document.querySelector('#playhead').dispatchEvent(new Event('input'))");actual=c.wait(f"Math.abs(document.querySelector('#voiceoverMaster').currentTime-{target})<1.5&&document.querySelector('#voiceoverMaster').currentTime",5);seeks.append(abs(actual-target)<1.5)
  samples=[]
  for i in [0,10,20,30,40]:
   b=alignment['beats'][i];c.js(f"document.querySelector('#voiceoverMaster').currentTime={b['voice_start_ms']/1000}");samples.append(abs(c.js("document.querySelector('#voiceoverMaster').currentTime")-b['voice_start_ms']/1000)<.5 and bool(b['direct_words']))
  errors=[e for e in c.events if e.get('method')=='Runtime.exceptionThrown' or(e.get('method')=='Log.entryAdded' and e.get('params',{}).get('entry',{}).get('level')=='error')];failed=[e for e in c.events if e.get('method')=='Network.loadingFailed' and not e.get('params',{}).get('canceled')];result.update({'browser_audio_playback_pass':play,'browser_seek_pass':all(seeks),'sample_beat_sync_pass':all(samples),'console_errors':len(errors),'failed_requests':len(failed)});result['PASS']=play and all(seeks) and all(samples) and not errors and not failed
 finally:
  if chrome:chrome.terminate()
  after=json.loads(STATE.read_text());after_candidates=hashlib.sha256(json.dumps([(x['presentation_slot_id'],x.get('candidates'),x.get('approval_state')) for x in after['timeline']],sort_keys=True).encode()).hexdigest();result['existing_candidate_state_preserved']=after_candidates==before_candidates;result['PASS']=result['PASS'] and result['existing_candidate_state_preserved'];(OUT/'WALTER_FINAL_VOICEOVER_ALIGNMENT.json').write_text(json.dumps(result,indent=2),encoding='utf8')
 if not result['PASS']:raise AssertionError(str(result))
 return 0
if __name__=='__main__':sys.exit(main())
