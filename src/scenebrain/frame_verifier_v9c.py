from __future__ import annotations
import base64,json,os,time,random,urllib.error
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field
from PIL import Image,ImageDraw
from .hashing import fingerprint,sha256_file

VERSION='frame-sequence-candidate-verifier/1.0';MODEL='gemini-3.1-flash-lite';PROMPT='ordered-frame-literal/1.0';FPS=5;FRAME_COUNT=15
class OracleLabel(BaseModel):
 model_config=ConfigDict(extra='forbid');request_id:str;candidate_id:str;human_label:Literal['LITERAL','PARTIAL','NO_MATCH'];required_facts_supported:list[str]=Field(default_factory=list);optional_note:str='';reviewed_at:str;source_fingerprint:str;candidate_fingerprint:str
class FrameDecision(BaseModel):
 model_config=ConfigDict(extra='forbid');request_id:str;candidate_id:str;classification:Literal['LITERAL_MATCH','PARTIAL_MATCH','NO_MATCH'];supported_fact_ids:list[str]=Field(default_factory=list);missing_fact_ids:list[str]=Field(default_factory=list);evidence_frame_ids:list[str]=Field(default_factory=list);evidence_statement:str

def extract_frames(conn,root,c):
 import subprocess
 src=conn.execute('select * from source_files where id=1').fetchone();fp=fingerprint(VERSION,src['sha256'],c.start_ms,c.end_ms,FPS,FRAME_COUNT);folder=root/'runtime/sprint9c/frames'/fp;manifest=folder/'manifest.json'
 if manifest.exists():
  x=json.loads(manifest.read_text());
  if x['seal']!=fingerprint(json.dumps(x['frames'],sort_keys=True),fp):raise ValueError('tampered frames')
  return {**x,'cache_hit':True}
 folder.mkdir(parents=True,exist_ok=True);duration=c.end_ms-c.start_ms;count=min(FRAME_COUNT,max(3,round(duration/1000*FPS)));times=[c.start_ms+round(i*max(0,duration-1)/max(1,count-1)) for i in range(count)];frames=[]
 for i,ms in enumerate(times,1):
  fid=f'F{i:02d}';p=folder/f'{fid}.jpg';subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-ss',f'{ms/1000:.3f}','-i',src['path'],'-frames:v','1','-vf','scale=480:-2','-q:v','3','-y',str(p)],check=True);frames.append({'frame_id':fid,'source_ms':ms,'path':str(p.resolve()),'sha256':sha256_file(p)})
 x={'version':VERSION,'candidate_id':c.candidate_id,'candidate_fingerprint':fingerprint(c.model_dump_json()),'source_fingerprint':src['sha256'],'frames':frames,'fingerprint':fp};x['seal']=fingerprint(json.dumps(frames,sort_keys=True),fp);manifest.write_text(json.dumps(x,indent=2));return {**x,'cache_hit':False}

def strip(root,manifest,request_id):
 fp=fingerprint(manifest['fingerprint'],'strip/1');out=root/'runtime/sprint9c/strips'/request_id/f"{manifest['candidate_id']}_{fp[:8]}.jpg";out.parent.mkdir(parents=True,exist_ok=True)
 if not out.exists():
  ims=[Image.open(x['path']).convert('RGB') for x in manifest['frames']];w=240;h=round(ims[0].height*w/ims[0].width);canvas=Image.new('RGB',(5*w,3*(h+22)),'black');d=ImageDraw.Draw(canvas)
  for i,(im,row) in enumerate(zip(ims,manifest['frames'])):im.thumbnail((w,h));x=(i%5)*w;y=(i//5)*(h+22);canvas.paste(im,(x,y));d.text((x+4,y+h+3),row['frame_id'],fill='white')
  canvas.save(out,quality=88);[im.close() for im in ims]
 return str(out.resolve())

def classify_error(exc):
 text=str(exc).lower();code=getattr(exc,'code',None) or getattr(exc,'status_code',None);retry=bool(code in {429,500,502,503,504} or any(x in text for x in ('429','resource_exhausted','rate','timeout','503','500','server')))
 if '429' in text or 'resource_exhausted' in text:kind='rate_limit'
 elif any(x in text for x in ('500','502','503','504')):kind='server_error'
 elif 'timeout' in text:kind='timeout'
 elif '400' in text:kind='malformed_request'
 elif '404' in text:kind='model_unavailable'
 else:kind='other'
 return {'error_class':type(exc).__name__,'status_code':code,'kind':kind,'retryable':retry}

def verify(root,visible,candidate,manifest,max_attempts=4):
 fp=fingerprint(VERSION,MODEL,PROMPT,visible.model_dump_json(),candidate.model_dump_json(),manifest['fingerprint'],json.dumps(FrameDecision.model_json_schema(),sort_keys=True));cache=root/'runtime/sprint9c/cache'/f'{fp}.json';cache.parent.mkdir(parents=True,exist_ok=True)
 if cache.exists():
  x=json.loads(cache.read_text());return {**x,'cache_hit':True}
 if not os.environ.get('GEMINI_API_KEY'):return {'status':'ABSTAIN','error':{'kind':'credential','retryable':False}}
 from google import genai
 from google.genai import types
 client=genai.Client(api_key=os.environ['GEMINI_API_KEY']);parts=[];ids=[]
 prompt=f'''Prompt {PROMPT}. These are chronological explicit images from ONE continuous candidate, ordered F01 onward. Request contract: {visible.model_dump_json()}. Candidate: {candidate.candidate_id}. Motion queries require visible change over time; static object/person presence is PARTIAL, never LITERAL. Judge only supplied images. No timestamps, invented IDs, ranking, show memory, or ground truth.''';parts.append(prompt)
 for row in manifest['frames']:
  ids.append(row['frame_id']);parts.extend([f"{row['frame_id']}",types.Part.from_bytes(data=Path(row['path']).read_bytes(),mime_type='image/jpeg')])
 errors=[]
 for attempt in range(1,max_attempts+1):
  try:
   t=time.time();r=client.models.generate_content(model=MODEL,contents=parts,config=types.GenerateContentConfig(temperature=.1,max_output_tokens=1200,response_mime_type='application/json',response_json_schema=FrameDecision.model_json_schema()));parsed=FrameDecision.model_validate_json(r.text)
   if parsed.request_id!=visible.request_id or parsed.candidate_id!=candidate.candidate_id or any(x not in ids for x in parsed.evidence_frame_ids):raise ValueError('invented id')
   u=r.usage_metadata;usage={'input_tokens':getattr(u,'prompt_token_count',0),'output_tokens':getattr(u,'candidates_token_count',0),'total_tokens':getattr(u,'total_token_count',0)};raw=parsed.model_dump();env={'status':'SUCCESS','response':raw,'usage':usage,'attempts':attempt,'latency_seconds':time.time()-t,'errors':errors,'seal':fingerprint(json.dumps(raw,sort_keys=True),fp)};tmp=cache.with_suffix('.building');tmp.write_text(json.dumps(env,indent=2));tmp.replace(cache);return {**env,'cache_hit':False}
  except Exception as exc:
   e=classify_error(exc);errors.append(e)
   if not e['retryable'] or attempt==max_attempts:return {'status':'ABSTAIN','attempts':attempt,'errors':errors,'cache_hit':False}
   time.sleep(min(8,.75*2**(attempt-1)+random.random()/4))
