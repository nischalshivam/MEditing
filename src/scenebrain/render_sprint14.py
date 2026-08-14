from __future__ import annotations
import json,subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

def run(root:Path,workers=4,runtime_name='sprint14_voiceover',plan_name='TIMELINE_PLAN.json',output_name='SPRINT14_SYNC_DRAFT_720P.mp4',resolution='1280:720'):
 out=root/'runtime'/runtime_name;plan=json.loads((out/plan_name).read_text());segdir=out/'video_proxies';segdir.mkdir(exist_ok=True)
 def one(pair):
  i,s=pair;dur=(s['timeline_end_ms']-s['timeline_start_ms'])/1000;p=segdir/f'{i:03d}_{s["presentation_slot_id"]}_{round(dur*1000)}_{resolution.replace(":","x")}.mp4'
  if p.exists():return p
  width,height=resolution.split(':');common=['-vf',f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1','-an','-c:v','libx264','-preset','veryfast','-crf','29','-pix_fmt','yuv420p','-r','24','-t',f'{dur:.3f}','-y',str(p)]
  if s['presentation_type']=='VIDEO':cmd=['ffmpeg','-hide_banner','-loglevel','error','-ss',f'{s["source_in_ms"]/1000:.3f}','-i',s['source_path'],*common]
  elif s['presentation_type']=='IMAGE':cmd=['ffmpeg','-hide_banner','-loglevel','error','-loop','1','-i',s['derived_asset_path'],*common]
  else:
   marker=out/'MANUAL_VISUAL_REQUIRED.jpg'
   if not marker.exists():
    from PIL import Image,ImageDraw,ImageFont
    im=Image.new('RGB',(1280,720),'#7f1d1d');d=ImageDraw.Draw(im);text='MANUAL VISUAL REQUIRED';font=ImageFont.truetype('arial.ttf',52);box=d.textbbox((0,0),text,font=font);d.text(((1280-(box[2]-box[0]))/2,(720-(box[3]-box[1]))/2),text,fill='white',font=font);im.save(marker)
   cmd=['ffmpeg','-hide_banner','-loglevel','error','-loop','1','-i',str(marker),'-an','-c:v','libx264','-preset','veryfast','-crf','29','-pix_fmt','yuv420p','-r','24','-t',f'{dur:.3f}','-y',str(p)]
  subprocess.run(cmd,check=True);return p
 with ThreadPoolExecutor(max_workers=workers) as ex:paths=list(ex.map(one,enumerate(plan['presentation_slots'])))
 concat=out/'concat.txt';concat.write_text(''.join("file '"+str(x.resolve()).replace("'","''")+"'\n" for x in paths),encoding='utf8')
 silent=out/'SILENT_TIMELINE_720P.mp4';subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-f','concat','-safe','0','-i',str(concat),'-c','copy','-y',str(silent)],check=True)
 final=out/output_name;subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-i',str(silent),'-i',plan['voiceover_path'],'-map','0:v','-map','1:a','-c:v','copy','-c:a','aac','-b:a','160k','-shortest','-movflags','+faststart','-y',str(final)],check=True);return final
