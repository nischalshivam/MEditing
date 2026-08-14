from __future__ import annotations

import subprocess
from pathlib import Path

from .hashing import fingerprint,sha256_file
from .moment_resolver_v2 import VERSION,CONFIG,generate_v2
from .moment_verifier_v2 import select_batch,refine_frames,verify_crop_v2
from .shot_artifacts import preview
from .shot_models import ShotRequest,ShotResolution

def _micro(conn,root,c):return preview(conn,root,c,width=480)

def _refined_crop(conn,root,c,first,last,fps=5):
    source=conn.execute('select * from source_files where id=1').fetchone();before,after=CONFIG['crop_handles_ms'];a=max(c.start_ms,c.start_ms+round(first*1000/fps)-before);b=min(c.end_ms,c.start_ms+round((last+1)*1000/fps)+after)
    if b<=a:raise ValueError('invalid refined crop')
    fp=fingerprint(source['sha256'],a,b,'refined-crop/2.0');out=root/'runtime/moment_v2/crops'/f'{fp}.mp4';out.parent.mkdir(parents=True,exist_ok=True)
    if not out.exists():
        tmp=out.with_suffix('.building.mp4');subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-ss',f'{a/1000:.3f}','-i',source['path'],'-t',f'{(b-a)/1000:.3f}','-vf','scale=720:-2','-an','-c:v','libx264','-preset','veryfast','-crf','25','-movflags','+faststart','-y',str(tmp)],check=True);tmp.replace(out)
    return {'path':str(out.resolve()),'sha256':sha256_file(out),'start_ms':a,'end_ms':b}

def resolve_v2(conn,root:Path,req:ShotRequest)->ShotResolution:
    base={'request_id':req.scene_request.request_id,'version':VERSION,'candidates':[],'provenance':{'sprint3':req.sprint3_result.resolver_version}}
    if req.sprint3_result.decision=='ABSTAIN':return ShotResolution(**base,decision='ABSTAIN',reason='Sprint 3 ABSTAIN gate')
    if req.sprint3_result.decision=='CONTEXTUAL' or req.scene_request.evidence_class not in {'EXACT_EVENT','EXACT_DIALOGUE'}:return ShotResolution(**base,decision='REVIEW_REQUIRED',reason='non-exact upstream result')
    candidates=generate_v2(conn,req);base['candidates']=candidates
    if not candidates:return ShotResolution(**base,decision='ABSTAIN',reason='no bounded micro-windows')
    selected=None;sv=None;partial=None;batches=[]
    for i in range(0,len(candidates),4):
        group=candidates[i:i+4];videos=[_micro(conn,root,x) for x in group];v=select_batch(root,req,group,videos);batches.append(v)
        if v.get('status')=='SUCCESS' and v['response']['decision']=='LITERAL_MATCH':selected=next(x for x in group if x.candidate_id==v['response']['candidate_id']);sv=v;break
        if v.get('status')=='SUCCESS' and v['response']['decision']=='PARTIAL_MATCH' and partial is None:partial=(next(x for x in group if x.candidate_id==v['response']['candidate_id']),v)
    if selected is None:
        if partial:
            return ShotResolution(**base,decision='REVIEW_REQUIRED',selected_candidate_id=partial[0].candidate_id,selected_shots=partial[1]['response']['supporting_shot_ids'],preview_path=_micro(conn,root,partial[0])['path'],candidate_verifier={'batches':batches},literal_evidence=partial[1]['response']['evidence_statement'],reason='plausible partial motion requires review')
        return ShotResolution(**base,decision='ABSTAIN',candidate_verifier={'batches':batches},reason='no literal microvideo selected')
    micro=_micro(conn,root,selected);frame_count=max(1,min(60,round((selected.end_ms-selected.start_ms)/200)));ref=refine_frames(root,req,selected,micro,frame_count)
    if ref.get('status')!='SUCCESS' or ref['response']['decision']!='SUPPORTED_INTERVAL':return ShotResolution(**base,decision='REVIEW_REQUIRED' if ref.get('status')=='SUCCESS' and ref['response']['decision']=='PARTIAL' else 'ABSTAIN',selected_candidate_id=selected.candidate_id,selected_shots=sv['response']['supporting_shot_ids'],preview_path=micro['path'],candidate_verifier={'batches':batches},literal_evidence=sv['response']['evidence_statement'],reason='support interval not proven')
    crop=_refined_crop(conn,root,selected,ref['response']['first_frame_index'],ref['response']['last_frame_index']);cv=verify_crop_v2(root,req,selected,crop)
    if cv.get('status')!='SUCCESS':decision='ABSTAIN';reason='crop verifier failed closed';response={}
    else:
        response=cv['response'];decision={'VERIFIED_CROP':'VERIFIED_EXACT','REVIEW_REQUIRED':'REVIEW_REQUIRED','REJECTED':'ABSTAIN'}[response['decision']];reason='independently verified refined crop' if decision=='VERIFIED_EXACT' else 'final crop unproven/rejected'
    if selected.boundary_sensitive and decision=='VERIFIED_EXACT':decision='REVIEW_REQUIRED';reason='known boundary-sensitive region'
    return ShotResolution(**base,decision=decision,selected_candidate_id=selected.candidate_id,selected_shots=response.get('supporting_shot_ids',sv['response']['supporting_shot_ids']),source_interval_ms=[crop['start_ms'],crop['end_ms']],preview_path=crop['path'],literal_evidence=response.get('evidence_statement',sv['response']['evidence_statement']),usability_flags=response.get('usability_flags',[]),candidate_verifier={'batches':batches,'refinement':ref},crop_verifier=cv,reason=reason)
