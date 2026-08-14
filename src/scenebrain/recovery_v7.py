from __future__ import annotations

import json,re
from pathlib import Path

from .moment_resolver_v2 import _windows
from .resolver import terms,vector,cosine
from .retrieval_contract_v3 import normalize_request
from .shot_models import ShotRequest

VERSION='bounded-scene-recovery/7.0'

def recovery_candidates(conn,req:ShotRequest):
    structured=normalize_request(req);q=' '.join(structured.normalized_terms);scenes=[]
    for rank,c in enumerate(req.sprint3_result.candidates[:8]):scenes.append((rank,c.scene_id))
    out=[];counts={'lower_ranked_scene':0,'subtitle':0,'boundary':0,'fragment':0,'reaction':0}
    for rank,sid in scenes:
        scene=conn.execute('select * from scenes where scene_uid=?',(sid,)).fetchone()
        if not scene:continue
        scored=[]
        for f in conn.execute('select * from scene_retrieval_fragments where scene_id=?',(scene['id'],)):
            text=f['objective_text'];lex=len(terms(q)&terms(text))/max(1,len(terms(q)));sem=cosine(vector(q),vector(text));score=.6*lex+.4*sem
            if score<=.08:continue
            for uid in json.loads(f['evidence_shot_ids_json']):
                if not re.fullmatch(r'S\d{4}',uid):continue
                sh=conn.execute('select start_ms,end_ms from shots where ordinal=?',(int(uid[1:]),)).fetchone()
                if sh:scored.append((score,sh['start_ms'],sh['end_ms'],f,uid))
        # Preserve distinct temporal hypotheses, including later evidence in long scenes.
        selected=[]
        for item in sorted(scored,key=lambda x:(-x[0],x[1])):
            if any(abs(item[1]-x[1])<2500 for x in selected):continue
            selected.append(item)
            if len(selected)>=8:break
        for score,a,b,f,uid in selected:
            lane='LOWER_SCENE' if rank>=3 else 'FRAGMENT_RECOVERY';counts['lower_ranked_scene' if rank>=3 else 'fragment']+=1
            out.extend(_windows(conn,max(scene['start_ms'],a-3000),min(scene['end_ms'],b+3000),lane,sid,{'scene_rank':rank+1,'admission_reason':'query-matched fragment evidence','fragment_id':f['id'],'text':f['objective_text'],'evidence_shots':[uid],'overlap':score},.65+score-.025*rank))
        # Subtitle neighborhoods inside the scene are locator-only.
        query_terms=terms(q)
        for cue in conn.execute('''select c.start_ms,c.end_ms,c.raw_text from subtitle_cues c join subtitle_tracks t on t.id=c.track_id where t.selected=1 and c.end_ms>? and c.start_ms<?''',(scene['start_ms'],scene['end_ms'])):
            ov=len(query_terms&terms(cue['raw_text']))/max(1,len(query_terms))
            if ov<.18:continue
            counts['subtitle']+=1;out.extend(_windows(conn,max(scene['start_ms'],cue['start_ms']-2500),min(scene['end_ms'],cue['end_ms']+4000),'SUBTITLE_RECOVERY',sid,{'scene_rank':rank+1,'admission_reason':'normalized subtitle proximity','cue':dict(cue),'overlap':ov},.58+ov))
        # Boundary tails/heads, strictly bounded.
        for a,b,label in [(scene['start_ms'],min(scene['end_ms'],scene['start_ms']+6000),'BOUNDARY_HEAD'),(max(scene['start_ms'],scene['end_ms']-6000),scene['end_ms'],'BOUNDARY_TAIL')]:
            counts['boundary']+=1;out.extend(_windows(conn,a,b,label,sid,{'scene_rank':rank+1,'admission_reason':'bounded atlas boundary recovery'},.42-.02*rank))
        # Reaction: distribute hypotheses after query-matched trigger/evidence.
        if structured.action_family=='react' or req.reaction_trigger:
            anchors=selected[:4]
            for _,a,b,f,uid in anchors:
                counts['reaction']+=1;out.extend(_windows(conn,b,min(scene['end_ms'],b+8000),'REACTION_RECOVERY',sid,{'scene_rank':rank+1,'admission_reason':'post-trigger reaction neighborhood','trigger':f['objective_text'],'evidence_shots':[uid]},.72))
    return out,counts
