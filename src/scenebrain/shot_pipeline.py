from __future__ import annotations

import json
from pathlib import Path

from .hashing import fingerprint,sha256_file
from .shot_artifacts import dense_sheet,preview
from .shot_models import ShotRequest,ShotResolution
from .shot_resolver import SHOT_RESOLVER_VERSION,CONFIG,derive_crop,generate_candidates
from .shot_verifier import CANDIDATE_PROMPT,CROP_PROMPT,MODEL,verify_candidates,verify_crop

def resolve_shot(conn,root:Path,req:ShotRequest)->ShotResolution:
    base={'request_id':req.scene_request.request_id,'version':SHOT_RESOLVER_VERSION,'candidates':[],'provenance':{'sprint3_version':req.sprint3_result.resolver_version}}
    if req.sprint3_result.decision=='ABSTAIN':return ShotResolution(**base,decision='ABSTAIN',reason='Sprint 3 ABSTAIN cannot auto-resolve')
    if req.sprint3_result.decision=='CONTEXTUAL' or req.scene_request.evidence_class not in {'EXACT_EVENT','EXACT_DIALOGUE'}:
        return ShotResolution(**base,decision='REVIEW_REQUIRED',reason='contextual/non-exact Sprint 3 input cannot become exact')
    candidates=generate_candidates(conn,req);base['candidates']=candidates
    if not candidates:return ShotResolution(**base,decision='ABSTAIN',reason='no bounded physical candidates')
    # Batches keep candidate recall without one oversized request.
    verifications=[];selected=None;selected_v=None
    for start in range(0,len(candidates),4):
        batch=candidates[start:start+4];arts=[]
        for c in batch:arts.append({'preview':preview(conn,root,c),'sheet':dense_sheet(conn,root,c)})
        v=verify_candidates(conn,root,req,batch,arts);verifications.append(v)
        if v.get('status')=='SUCCESS' and v['response']['decision']=='LITERAL_MATCH':
            selected=next(x for x in batch if x.candidate_id==v['response']['candidate_id']);selected_v=v;break
    if not selected:
        partial=any(v.get('status')=='SUCCESS' and v['response']['decision']=='PARTIAL_MATCH' for v in verifications)
        return ShotResolution(**base,decision='REVIEW_REQUIRED' if partial else 'ABSTAIN',candidate_verifier={'batches':verifications},reason='no literal candidate verified')
    # The exported crop is derived from authoritative local bounds, then independently verified.
    crop=preview(conn,root,selected,width=720);crop_dense=dense_sheet(conn,root,selected,fps=5,max_frames=32);cv=verify_crop(conn,root,req,selected,crop,crop_dense)
    response=cv.get('response',{}) if cv.get('status')=='SUCCESS' else {};decision=response.get('decision')
    exact=decision=='VERIFIED_CROP' and not selected.boundary_sensitive
    if decision=='VERIFIED_CROP' and selected.boundary_sensitive:
        # Known atlas boundary requires review despite literal support in v1.
        final='REVIEW_REQUIRED';reason='literal crop found in known boundary-sensitive region'
    elif exact:final='VERIFIED_EXACT';reason='literal candidate and independently verified actual crop'
    elif decision=='REVIEW_REQUIRED':final='REVIEW_REQUIRED';reason='final crop verifier requires review'
    else:final='ABSTAIN';reason='final crop rejected or verifier failed closed'
    shots=response.get('supporting_shot_ids') or selected_v['response'].get('supporting_shot_ids',[])
    a,b=derive_crop(selected,shots)
    return ShotResolution(**base,decision=final,selected_candidate_id=selected.candidate_id,selected_shots=shots,source_interval_ms=[a,b],preview_path=crop['path'],literal_evidence=response.get('evidence_statement') or selected_v['response']['evidence_statement'],usability_flags=response.get('usability_flags',[]),candidate_verifier={'batches':verifications},crop_verifier=cv,reason=reason)

def freeze_version(conn,root:Path,freeze_id:int)->dict:
    config={'candidate':CONFIG,'model':MODEL,'candidate_prompt':CANDIDATE_PROMPT,'crop_prompt':CROP_PROMPT}
    fp=fingerprint(SHOT_RESOLVER_VERSION,json.dumps(config,sort_keys=True),str(freeze_id))
    with conn:conn.execute('insert or ignore into shot_resolver_versions(version,input_freeze_id,config_json,candidate_prompt_version,crop_prompt_version,provider_model,resolver_fingerprint) values(?,?,?,?,?,?,?)',(SHOT_RESOLVER_VERSION,freeze_id,json.dumps(config,sort_keys=True),CANDIDATE_PROMPT,CROP_PROMPT,MODEL,fp))
    out=root/'runtime/shot_resolver/frozen_shot_resolver_receipt.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps({'version':SHOT_RESOLVER_VERSION,'fingerprint':fp,'input_freeze_id':freeze_id,'config':config,'frozen_before_holdout':True},indent=2),encoding='utf8')
    return {'version':SHOT_RESOLVER_VERSION,'fingerprint':fp,'receipt':str(out.resolve()),'sha256':sha256_file(out)}
