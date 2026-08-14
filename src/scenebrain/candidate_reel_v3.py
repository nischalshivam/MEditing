from __future__ import annotations

import subprocess
from pathlib import Path

from .hashing import fingerprint,sha256_file

VERSION='candidate-reel/3.0'

def build_reel(root:Path,videos:list[dict],candidate_ids:list[str])->dict:
    if not videos or len(videos)!=len(candidate_ids) or len(videos)>10:raise ValueError('reel requires 1-10 aligned candidates')
    fp=fingerprint(VERSION,*[x['sha256'] for x in videos],*candidate_ids);out=root/'runtime/retrieval_v3/reels'/f'{fp}.mp4';out.parent.mkdir(parents=True,exist_ok=True)
    if not out.exists():
        parts=[]
        for i,(v,cid) in enumerate(zip(videos,candidate_ids)):
            # Pin a real Windows font: relying on fontconfig made otherwise-valid
            # reels non-reproducible in isolated Codex/PowerShell processes.
            font="C\\:/Windows/Fonts/arial.ttf"
            vf=f"drawbox=x=0:y=0:w=iw:h=54:color=black@0.8:t=fill,drawtext=fontfile='{font}':text='{cid}':x=18:y=12:fontsize=28:fontcolor=white"
            p=out.parent/f'{fp}_{i}.mp4';subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-i',v['path'],'-vf',vf,'-an','-c:v','libx264','-crf','25','-y',str(p)],check=True);parts.append(p)
        listing=out.parent/f'{fp}.txt';listing.write_text('\n'.join("file '"+str(p).replace("'","''")+"'" for p in parts),encoding='utf8');tmp=out.with_suffix('.building.mp4');subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-f','concat','-safe','0','-i',str(listing),'-c','copy','-movflags','+faststart','-y',str(tmp)],check=True);tmp.replace(out);listing.unlink();[p.unlink() for p in parts]
    return {'path':str(out.resolve()),'sha256':sha256_file(out),'fingerprint':fp,'candidate_ids':candidate_ids,'cache_hit':True}
