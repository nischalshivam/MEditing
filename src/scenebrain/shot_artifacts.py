from __future__ import annotations

import json,subprocess
from pathlib import Path
from PIL import Image,ImageDraw

from .hashing import fingerprint,sha256_file
from .shot_models import ShotRange

ARTIFACT_VERSION='shot-temporal-artifacts/1.0'

def _source(conn):return conn.execute('select * from source_files where id=1').fetchone()

def preview(conn,root:Path,c:ShotRange,width:int=480)->dict:
    source=_source(conn);duration=c.end_ms-c.start_ms
    if duration<=0 or duration>120_000:raise ValueError('candidate preview duration invalid')
    fp=fingerprint(source['sha256'],c.start_shot,c.end_shot,c.start_ms,c.end_ms,width,'preview',ARTIFACT_VERSION)
    out=root/'runtime/shot_resolver/artifacts'/fp[:2]/f'{fp}.mp4';out.parent.mkdir(parents=True,exist_ok=True)
    if not out.exists():
        tmp=out.with_suffix('.building.mp4');cmd=['ffmpeg','-hide_banner','-loglevel','error','-ss',f'{c.start_ms/1000:.3f}','-i',source['path'],'-t',f'{duration/1000:.3f}','-vf',f'scale={width}:-2','-an','-c:v','libx264','-preset','veryfast','-crf','30','-movflags','+faststart','-y',str(tmp)]
        subprocess.run(cmd,check=True);tmp.replace(out)
    digest=sha256_file(out)
    with conn:conn.execute("insert or ignore into shot_temporal_artifacts(source_file_id,start_shot_id,end_shot_id,artifact_type,config_version,input_fingerprint,path,sha256,bytes,duration_ms) select 1,a.id,b.id,'PREVIEW',?,?,?,?,?,? from shots a,shots b where a.ordinal=? and b.ordinal=?",(ARTIFACT_VERSION,fp,str(out.resolve()),digest,out.stat().st_size,duration,int(c.start_shot[1:]),int(c.end_shot[1:])))
    return {'path':str(out.resolve()),'sha256':digest,'input_fingerprint':fp,'duration_ms':duration,'cache_hit':True}

def dense_sheet(conn,root:Path,c:ShotRange,fps:int=3,width:int=320,max_frames:int=24)->dict:
    source=_source(conn);duration=c.end_ms-c.start_ms
    fp=fingerprint(source['sha256'],c.start_shot,c.end_shot,c.start_ms,c.end_ms,fps,width,max_frames,'dense',ARTIFACT_VERSION)
    out=root/'runtime/shot_resolver/artifacts'/fp[:2]/f'{fp}.jpg';out.parent.mkdir(parents=True,exist_ok=True)
    if not out.exists():
        folder=out.parent/f'{fp}.frames';folder.mkdir(exist_ok=True);pattern=folder/'f_%03d.jpg'
        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-ss',f'{c.start_ms/1000:.3f}','-i',source['path'],'-t',f'{duration/1000:.3f}','-vf',f'fps={fps},scale={width}:-2','-frames:v',str(max_frames),'-q:v','4','-y',str(pattern)],check=True)
        frames=sorted(folder.glob('*.jpg'))
        if not frames:raise RuntimeError('no dense frames extracted')
        ims=[Image.open(x).convert('RGB') for x in frames];tile_w=max(x.width for x in ims);tile_h=max(x.height for x in ims)+24;cols=4;rows=(len(ims)+cols-1)//cols
        sheet=Image.new('RGB',(cols*tile_w,rows*tile_h),'black');draw=ImageDraw.Draw(sheet)
        for i,im in enumerate(ims):x=(i%cols)*tile_w;y=(i//cols)*tile_h;sheet.paste(im,(x,y));draw.text((x+4,y+im.height+3),f'{c.candidate_id} frame {i+1}',fill='white')
        tmp=out.with_suffix('.building.jpg');sheet.save(tmp,quality=88);tmp.replace(out)
        for im in ims:im.close()
        for x in frames:x.unlink()
        folder.rmdir()
    digest=sha256_file(out)
    with conn:conn.execute("insert or ignore into shot_temporal_artifacts(source_file_id,start_shot_id,end_shot_id,artifact_type,config_version,input_fingerprint,path,sha256,bytes,duration_ms) select 1,a.id,b.id,'DENSE_SHEET',?,?,?,?,?,? from shots a,shots b where a.ordinal=? and b.ordinal=?",(ARTIFACT_VERSION,fp,str(out.resolve()),digest,out.stat().st_size,duration,int(c.start_shot[1:]),int(c.end_shot[1:])))
    return {'path':str(out.resolve()),'sha256':digest,'input_fingerprint':fp,'duration_ms':duration,'cache_hit':True}
