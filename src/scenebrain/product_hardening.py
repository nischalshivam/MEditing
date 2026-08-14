"""Portable product onboarding, character galleries, and compute policy."""
from __future__ import annotations
import hashlib,json,os,re,shutil,subprocess,time
from dataclasses import dataclass,asdict
from pathlib import Path
from PIL import Image,ImageStat,ImageFilter

IMAGE_EXT={'.jpg','.jpeg','.png','.webp','.bmp'}
ALIASES={'gus':'Gus Fring','hank':'Hank Schrader','jesse pinkman':'Jesse Pinkman','mike':'Mike Ehrmantraut','saul goodman':'Saul Goodman','skyler white':'Skyler White','walter white':'Walter White'}
def slug(s):return re.sub(r'[^a-z0-9]+','_',s.lower()).strip('_')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()

def validate_reference(path:Path)->dict:
 try:
  im=Image.open(path).convert('RGB');im.verify();im=Image.open(path).convert('RGB');w,h=im.size
  gray=im.convert('L');exposure=ImageStat.Stat(gray).mean[0];edges=gray.filter(ImageFilter.FIND_EDGES);sharpness=ImageStat.Stat(edges).var[0]
  faces=[]
  try:
   import cv2,numpy as np
   cascade=cv2.CascadeClassifier(cv2.data.haarcascades+'haarcascade_frontalface_default.xml');faces=cascade.detectMultiScale(np.array(gray),1.1,5,minSize=(48,48)).tolist()
  except Exception:pass
  largest=max((fw*fh for _,_,fw,fh in faces),default=0);ratio=largest/max(1,w*h)
  issues=[]
  if not faces:issues.append('NO_FACE_DETECTED')
  if len(faces)>1:issues.append('MULTIPLE_FACES_NEEDS_REVIEW')
  if ratio and ratio<.025:issues.append('FACE_TOO_SMALL')
  if sharpness<18:issues.append('BLURRY')
  if exposure<25 or exposure>235:issues.append('EXPOSURE')
  return {'readable':True,'width':w,'height':h,'faces':len(faces),'face_ratio':round(ratio,4),'sharpness':round(sharpness,2),'exposure':round(exposure,2),'issues':issues,'approval_state':'TRUSTED' if not issues else 'NEEDS_REVIEW'}
 except Exception as e:return {'readable':False,'issues':['UNREADABLE_IMAGE'],'error':type(e).__name__,'approval_state':'REJECTED'}

def import_character_folder(media_root:Path,title_name:str,source:Path)->dict:
 title_id='ttl_'+hashlib.sha256(title_name.lower().encode()).hexdigest()[:16];root=media_root/'.scene_brain/memory/character_galleries'/title_id;root.mkdir(parents=True,exist_ok=True);characters=[];seen=set()
 for folder in sorted(x for x in source.iterdir() if x.is_dir()):
  display=ALIASES.get(folder.name.lower(),folder.name.strip().title());cid=slug(display);rows=[]
  for p in sorted(x for x in folder.iterdir() if x.is_file() and x.suffix.lower() in IMAGE_EXT):
   h=sha(p)
   if h in seen:continue
   seen.add(h);v=validate_reference(p);bucket='trusted' if v['approval_state']=='TRUSTED' else 'suggested' if v['approval_state']=='NEEDS_REVIEW' else 'rejected';dest=root/cid/bucket/(h[:16]+p.suffix.lower());dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
   rows.append({'image_hash':h,'source_reference_hash':h,'canonical_path':str(dest),'import_source':str(p),'approval_state':v['approval_state'],'face_quality':v,'embedding_version':None})
  trusted=sum(x['approval_state']=='TRUSTED' for x in rows);total=len(rows);status='STRONG' if trusted>=15 else 'READY' if trusted>=10 else 'PARTIAL' if total else 'MISSING';characters.append({'character_id':cid,'display_name':display,'references':rows,'trusted_references':trusted,'total_references':total,'gallery_status':status,'embedding_status':'PENDING' if total else 'NOT_AVAILABLE'})
 manifest={'version':'character-gallery/1.0','title_id':title_id,'title':title_name,'import_source':str(source),'originals_modified':False,'characters':characters,'created_at':time.time()};(root/'gallery_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8');return manifest

def gpu_capabilities()->dict:
 def run(args):
  try:return subprocess.run(args,capture_output=True,text=True,timeout=30).stdout.strip()
  except:return ''
 raw=run(['nvidia-smi','--query-gpu=name,driver_version,memory.total,uuid,pci.bus_id','--format=csv,noheader,nounits']);parts=[x.strip() for x in raw.split(',')] if raw else []
 torch_data={'installed':False,'cuda_available':False}
 try:
  import torch;torch_data={'installed':True,'cuda_available':torch.cuda.is_available(),'device_count':torch.cuda.device_count(),'devices':[torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())],'runtime_compatible':False}
  if torch.cuda.is_available():
   try:torch.ones(1,device='cuda');torch_data['runtime_compatible']=True
   except Exception as e:torch_data['runtime_error']=type(e).__name__
 except Exception:pass
 cv={'installed':False,'cuda':False}
 try:
  import cv2;b=cv2.getBuildInformation();cv={'installed':True,'version':cv2.__version__,'cuda':'NVIDIA CUDA:                   YES' in b,'cudnn':'cuDNN:                         YES' in b}
 except Exception:pass
 try:
  import ctranslate2;ct={'installed':True,'cuda_devices':ctranslate2.get_cuda_device_count(),'version':ctranslate2.__version__}
 except Exception:ct={'installed':False,'cuda_devices':0}
 return {'gpu_detected':bool(parts),'gpu_name':parts[0] if parts else None,'driver':parts[1] if len(parts)>1 else None,'vram_mib':int(parts[2]) if len(parts)>2 else 0,'uuid':parts[3] if len(parts)>3 else None,'pci_bus_id':parts[4] if len(parts)>4 else None,'torch':torch_data,'ctranslate2':ct,'opencv':cv,'ffmpeg_hwaccels':run(['ffmpeg','-hide_banner','-hwaccels']),'cuda_device_rule':'match runtime GPU name/UUID/PCI; never Windows Task Manager index'}

@dataclass
class ResourcePolicy:
 profile:str='AUTO';cpu_workers:int=max(1,min(4,(os.cpu_count() or 4)//2));gpu_workers:int=1;min_vram_headroom_mib:int=768;heavy_gpu_concurrency:int=1
 def backend(self,workload,caps):
  if self.profile=='CPU_ONLY':return 'CPU'
  if workload=='ffmpeg_encode' and caps.get('nvenc_runtime_pass'):return 'NVIDIA_NVENC'
  if workload=='whisper' and caps.get('whisper_cuda_runtime_pass'):return 'CUDA'
  if workload=='face_id' and caps.get('opencv',{}).get('cuda'):return 'OPENCV_CUDA'
  return 'CPU'

def inventory_gallery(media_root:Path)->dict:
 root=media_root/'.scene_brain/memory/character_galleries';out=[]
 for p in root.glob('*/gallery_manifest.json') if root.exists() else []:
  try:out.append(json.loads(p.read_text(encoding='utf8')))
  except:pass
 return {'titles':out,'gallery_count':len(out)}
