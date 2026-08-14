from __future__ import annotations

import json,re
from collections import defaultdict
from pathlib import Path

from .hashing import fingerprint,sha256_file
from .resolver import terms
from .shot_models import ShotRange,ShotRequest

VERSION='exact-moment-resolver/2.0'
CONFIG={'scene_top_k':3,'window_ms':3000,'stride_ms':1500,'candidate_k':24,'lane_quota':4,
        'evidence_radius_ms':5000,'reaction_before_ms':2500,'reaction_after_ms':6000,
        'crop_handles_ms':[450,650],'boundary_sensitive':['S04E01_SC013']}
LANES=('EVIDENCE','ACTION','OBJECT_ACTION','ENTER_LEAVE','REACTION','DIALOGUE','COVERAGE')
ACTION_WORDS={'pick','picks','pickup','grab','grabs','cut','cuts','enter','enters','leave','leaves','walk','walks','raise','raises','drop','drops','hand','hands','pour','pours','put','puts','hold','holds','open','opens','unlock','unlocks','eat','eats','search','searches','change','changes','react','reacts','look','looks'}

def _uid(n):return f'S{n:04d}'
def _scene_regions(conn,req):
    ids=[]
    for c in req.sprint3_result.candidates[:CONFIG['scene_top_k']]:
        if c.scene_id not in ids:ids.append(c.scene_id)
        for n in c.neighbors:
            if n not in ids:ids.append(n)
    if not ids:return [],{}
    rows=conn.execute('select * from scenes where scene_uid in (%s)'%','.join('?'*len(ids)),ids).fetchall()
    return ids,{r['scene_uid']:r for r in rows}

def _shot_span(conn,a,b):
    rows=conn.execute('select ordinal,start_ms,end_ms from shots where source_file_id=1 and end_ms>? and start_ms<? order by ordinal',(a,b)).fetchall()
    if not rows:return None
    return _uid(rows[0]['ordinal']),_uid(rows[-1]['ordinal']),rows[0]['start_ms'],rows[-1]['end_ms']

def _windows(conn,start,end,lane,scene,provenance,score):
    out=[];pos=start
    while pos<end:
        stop=min(end,pos+CONFIG['window_ms']);span=_shot_span(conn,pos,stop)
        if span:
            out.append(ShotRange(candidate_id='pending',start_shot=span[0],end_shot=span[1],start_ms=max(pos,span[2]),end_ms=min(stop,span[3]),scene_ids=[scene],local_score=score,provenance=[{'lane':lane,**provenance}],boundary_sensitive=scene in CONFIG['boundary_sensitive']))
        pos+=CONFIG['stride_ms']
    return out

def generate_v2(conn,req:ShotRequest)->list[ShotRange]:
    if req.sprint3_result.resolver_version!='scene-resolver/1.0':raise ValueError('stale Sprint 3 result')
    ids,scenes=_scene_regions(conn,req)
    if not scenes:return []
    query=terms(' '.join(filter(None,[req.scene_request.query_text,req.scene_request.visible_action,req.scene_request.requested_event,*req.scene_request.objects,req.reaction_trigger,req.reaction_subject])))
    lane=defaultdict(list)
    # Typed evidence lanes from every fragment in supplied regions.
    for rank,sid in enumerate(ids):
        if sid not in scenes:continue
        for f in conn.execute('select * from scene_retrieval_fragments where scene_id=?',(scenes[sid]['id'],)):
            ft=terms(f['objective_text']);ov=len(query&ft)/max(1,len(query));shots=json.loads(f['evidence_shot_ids_json'])
            if not shots:continue
            ords=[int(x[1:]) for x in shots if re.fullmatch(r'S\d{4}',x)]
            if not ords:continue
            text=f['objective_text'].lower()
            kind='EVIDENCE'
            if f['fragment_type']=='OBJECT':kind='OBJECT_ACTION'
            if f['fragment_type']=='ACTION':kind='ACTION'
            if any(w in text for w in ('enter','leave','walk','arrive','depart')):kind='ENTER_LEAVE'
            if any(w in text for w in ('react','shock','terrified','distress','watch','look')):kind='REACTION'
            base=.55+.30*ov-.025*rank
            # Each evidence shot is an independent hypothesis. A min..max envelope over a
            # long fragment caused early windows to crowd out the actual later action.
            for evidence_ord in ords:
                sr=conn.execute('select start_ms,end_ms from shots where ordinal=?',(evidence_ord,)).fetchone();a=max(scenes[sid]['start_ms'],sr[0]-CONFIG['evidence_radius_ms']);b=min(scenes[sid]['end_ms'],sr[1]+CONFIG['evidence_radius_ms'])
                lane[kind].extend(_windows(conn,a,b,kind,sid,{'fragment_id':f['id'],'text':f['objective_text'],'evidence_shots':[f'S{evidence_ord:04d}'],'overlap':ov},base))
        # Uniform coverage lane prevents lexical omission; still bounded to supplied scene regions.
        coverage=_windows(conn,scenes[sid]['start_ms'],scenes[sid]['end_ms'],'COVERAGE',sid,{'scene_rank':rank},.25-.02*rank)
        if coverage:
            # Preserve evenly spaced coverage rather than only the scene beginning.
            take=min(8,len(coverage));lane['COVERAGE'].extend([coverage[round(i*(len(coverage)-1)/max(1,take-1))] for i in range(take)])
    # Dialogue lane.
    for c in req.sprint3_result.candidates[:3]:
        for d in c.matched_dialogue:
            a=max(scenes.get(c.scene_id,{'start_ms':0})['start_ms'],d.get('start_ms',0)-2500);b=min(scenes.get(c.scene_id,{'end_ms':0})['end_ms'],d.get('end_ms',0)+3500)
            lane['DIALOGUE'].extend(_windows(conn,a,b,'DIALOGUE',c.scene_id,{'cue':d},.72))
    # Reaction direction changes the trigger neighborhood.
    if req.reaction_trigger:
        trigger=terms(req.reaction_trigger)
        for sid in ids:
            if sid not in scenes:continue
            for f in conn.execute('select * from scene_retrieval_fragments where scene_id=?',(scenes[sid]['id'],)):
                if len(trigger&terms(f['objective_text']))/max(1,len(trigger))<.2:continue
                shots=json.loads(f['evidence_shot_ids_json']);ords=[int(x[1:]) for x in shots if re.fullmatch(r'S\d{4}',x)]
                if not ords:continue
                t=conn.execute('select max(end_ms) from shots where ordinal between ? and ?',(min(ords),max(ords))).fetchone()[0];direction=req.reaction_direction or 'AFTER';a=t-CONFIG['reaction_before_ms'] if direction!='AFTER' else t;b=t+CONFIG['reaction_after_ms'] if direction!='BEFORE' else t
                lane['REACTION'].extend(_windows(conn,max(scenes[sid]['start_ms'],a),min(scenes[sid]['end_ms'],b),'REACTION',sid,{'trigger':f['objective_text'],'direction':direction},.82))
    # Deduplicate exact time windows, then round-robin quotas for diversity, then score fill.
    for name in lane:
        best={}
        for x in lane[name]:
            key=(x.start_ms,x.end_ms);best[key]=max(best.get(key,x),x,key=lambda y:y.local_score)
        lane[name]=sorted(best.values(),key=lambda x:(-x.local_score,x.start_ms))
    out=[];seen=set()
    for name in LANES:
        for x in lane[name][:CONFIG['lane_quota']]:
            key=(x.start_ms,x.end_ms)
            if key not in seen:out.append(x);seen.add(key)
    # Reserve one query-relevant hypothesis per supplied scene. This prevents a strong but
    # wrong scene from consuming all 24 slots while retaining the frozen scene ranking.
    for sid in ids:
        options=[x for name in lane for x in lane[name] if sid in x.scene_ids and name!='COVERAGE' and x.provenance[0].get('overlap',0)>0]
        if options:
            x=max(options,key=lambda y:(y.local_score,y.start_ms));key=(x.start_ms,x.end_ms)
            if key not in seen:out.append(x);seen.add(key)
    rest=sorted((x for xs in lane.values() for x in xs if (x.start_ms,x.end_ms) not in seen),key=lambda x:(-x.local_score,x.start_ms))
    for x in rest:
        if len(out)>=CONFIG['candidate_k']:break
        key=(x.start_ms,x.end_ms)
        if key not in seen:out.append(x);seen.add(key)
    for i,x in enumerate(out[:CONFIG['candidate_k']],1):x.candidate_id=f'MICRO_{i:02d}'
    return out[:CONFIG['candidate_k']]

def freeze_v2(conn,root:Path,input_freeze_id:int,prompts:dict)->dict:
    payload={'version':VERSION,'input_freeze_id':input_freeze_id,'config':CONFIG,'prompts':prompts,'model':'gemini-3.1-flash-lite','frozen_before_new_holdout':True};fp=fingerprint(json.dumps(payload,sort_keys=True));out=root/'runtime/moment_v2/frozen_moment_v2_receipt.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps({**payload,'fingerprint':fp},indent=2),encoding='utf8');return {'fingerprint':fp,'path':str(out.resolve()),'sha256':sha256_file(out)}
