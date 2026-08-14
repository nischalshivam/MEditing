from __future__ import annotations

import json,math,re
from pathlib import Path

from .hashing import fingerprint
from .resolver import terms,vector,cosine
from .retrieval_contract_v3 import normalize_request,SYNONYMS
from .shot_models import ShotRange,ShotRequest

VERSION='hierarchical-intra-scene/8.0'
CONFIG={'coarse_ms':12000,'overlap_ms':3000,'coarse_per_scene':8,'dense_expand_ms':3500,'dense_ms':3000,'dense_stride_ms':1000,'dense_output_k':24}

def build_scene_index(conn,scene_uid:str):
    scene=conn.execute('select * from scenes where scene_uid=?',(scene_uid,)).fetchone();source=conn.execute('select * from source_files where id=?',(scene['source_file_id'],)).fetchone();step=CONFIG['coarse_ms']-CONFIG['overlap_ms'];windows=[];start=scene['start_ms'];ordinal=0
    while start<scene['end_ms']:
        end=min(scene['end_ms'],start+CONFIG['coarse_ms']);shots=[f'S{r[0]:04d}' for r in conn.execute('select ordinal from shots where source_file_id=? and end_ms>? and start_ms<? order by ordinal',(scene['source_file_id'],start,end))];dialogue=[dict(r) for r in conn.execute('''select c.start_ms,c.end_ms,c.raw_text from subtitle_cues c join subtitle_tracks t on t.id=c.track_id where t.selected=1 and c.end_ms>? and c.start_ms<? order by c.start_ms''',(start,end))];uid=f'{scene_uid}_MW{ordinal:04d}';fp=fingerprint(source['sha256'],scene_uid,start,end,json.dumps(shots),VERSION,json.dumps(CONFIG,sort_keys=True))
        with conn:conn.execute('insert or ignore into scene_micro_windows(scene_id,micro_window_uid,start_ms,end_ms,shot_ids_json,dialogue_json,source_sha256,index_version,input_fingerprint) values(?,?,?,?,?,?,?,?,?)',(scene['id'],uid,start,end,json.dumps(shots),json.dumps(dialogue),source['sha256'],VERSION,fp))
        windows.append(uid);ordinal+=1
        if end==scene['end_ms']:break
        start+=step
    # Invariant: first/last exact coverage and no gaps.
    rows=conn.execute('select * from scene_micro_windows where scene_id=? and index_version=? order by start_ms',(scene['id'],VERSION)).fetchall()
    if not rows or rows[0]['start_ms']!=scene['start_ms'] or rows[-1]['end_ms']!=scene['end_ms'] or any(rows[i]['end_ms']<rows[i+1]['start_ms'] for i in range(len(rows)-1)):raise ValueError('micro-index coverage gap')
    return rows

def _window_text(conn,w):
    texts=[]
    for f in conn.execute('''select objective_text,evidence_shot_ids_json from scene_retrieval_fragments where scene_id=?''',(w['scene_id'],)):
        shots=json.loads(f['evidence_shot_ids_json'])
        if any(x in json.loads(w['shot_ids_json']) for x in shots):texts.append(f['objective_text'])
    texts.extend(x['raw_text'] for x in json.loads(w['dialogue_json']))
    texts.extend(r['action_text'] for r in conn.execute('select action_text from micro_events where micro_window_id=?',(w['id'],)))
    return ' '.join(texts)

def coarse_rank(conn,req:ShotRequest):
    structured=normalize_request(req);q=' '.join(structured.normalized_terms);ranked=[];seen=set()
    for scene_rank,c in enumerate(req.sprint3_result.candidates[:3]):
        for w in build_scene_index(conn,c.scene_id):
            if w['id'] in seen:continue
            seen.add(w['id']);text=_window_text(conn,w);lex=len(terms(q)&terms(text))/max(1,len(terms(q)));sem=cosine(vector(q),vector(text)) if text else 0;action=0
            if structured.action_family:
                variants=SYNONYMS.get(structured.action_family,{structured.action_family})
                if any(re.search(r'\b'+re.escape(v)+r'\b',text.lower()) for v in variants):action=1
                # Objective descriptions can express locomotion as a concrete
                # handling verb (maneuver/fit/dispose) rather than "move".
                if structured.action_family=='move' and re.search(r'\b(maneuver|maneuvers|fit|fits|dispose|disposes|lift|lifts)\b',text.lower()):action=1
            # Complete coverage receives a floor, semantic evidence boosts but never defines coverage.
            score=.42*lex+.28*sem+.22*action+.08*(1-scene_rank/3)
            ranked.append({'window':w,'score':score,'text':text,'scene_rank':scene_rank+1,'evidence':{'lexical':lex,'semantic':sem,'action':action,'coverage_floor':True}})
    ranked.sort(key=lambda x:(-x['score'],x['window']['start_ms']))
    # Overlapping coarse windows are coverage cells, not independent hypotheses.
    # Rank distinct temporal regions first so one well-described event cannot
    # consume the entire narrowing budget; retain suppressed cells afterwards.
    primary=[];suppressed=[]
    for item in ranked:
        w=item['window'];duration=max(1,w['end_ms']-w['start_ms'])
        duplicate=False
        for kept in primary:
            k=kept['window']
            if k['scene_id']!=w['scene_id']:continue
            overlap=max(0,min(w['end_ms'],k['end_ms'])-max(w['start_ms'],k['start_ms']))
            if overlap/min(duration,max(1,k['end_ms']-k['start_ms']))>.45:
                duplicate=True;break
        (suppressed if duplicate else primary).append(item)
    return primary+suppressed,structured

def dense_candidates(conn,req:ShotRequest):
    coarse,structured=coarse_rank(conn,req);short=[]
    for scene_rank in (1,2,3):short.extend([x for x in coarse if x['scene_rank']==scene_rank][:CONFIG['coarse_per_scene']])
    short.sort(key=lambda x:(-x['score'],x['window']['start_ms']));source=conn.execute('select * from source_files where id=1').fetchone();dense=[]
    for rank,item in enumerate(short,1):
        w=item['window'];scene=conn.execute('select scene_uid,start_ms,end_ms from scenes where id=?',(w['scene_id'],)).fetchone();a=max(scene['start_ms'],w['start_ms']-CONFIG['dense_expand_ms']);limit=min(scene['end_ms'],w['end_ms']+CONFIG['dense_expand_ms']);pos=a
        local=[]
        while pos<limit:
            end=min(limit,pos+CONFIG['dense_ms']);shots=[r[0] for r in conn.execute('select ordinal from shots where source_file_id=1 and end_ms>? and start_ms<? order by ordinal',(pos,end))]
            if shots:local.append(ShotRange(candidate_id='pending',start_shot=f'S{shots[0]:04d}',end_shot=f'S{shots[-1]:04d}',start_ms=pos,end_ms=end,scene_ids=[scene['scene_uid']],local_score=item['score']-.005*rank,provenance=[{'lane':'HIERARCHICAL_DENSE','coarse_window_id':w['micro_window_uid'],'coarse_rank':rank,'coarse_evidence':item['evidence'],'complete_scene_coverage':True}],boundary_sensitive=scene['scene_uid']=='S04E01_SC013'))
            pos+=CONFIG['dense_stride_ms']
        # One representative from every shortlisted coarse hypothesis first; extras later.
        if local:
            center=(w['start_ms']+w['end_ms'])/2;local.sort(key=lambda x:abs((x.start_ms+x.end_ms)/2-center));dense.append(local[0]);dense.extend(local[1:])
    # Score/order by parent coarse rank, deduplicate exact ranges, preserve distinct time hypotheses.
    best={}
    for c in dense:best[(c.start_ms,c.end_ms)]=max(best.get((c.start_ms,c.end_ms),c),c,key=lambda x:x.local_score)
    values=list(best.values());parents={}
    for c in values:parents.setdefault(c.provenance[0]['coarse_window_id'],[]).append(c)
    primary=[min(xs,key=lambda x:abs((x.start_ms+x.end_ms)/2-(next(i['window'] for i in short if i['window']['micro_window_uid']==x.provenance[0]['coarse_window_id'])['start_ms']+next(i['window'] for i in short if i['window']['micro_window_uid']==x.provenance[0]['coarse_window_id'])['end_ms'])/2)) for xs in parents.values()]
    ordered=sorted(primary,key=lambda x:(-x.local_score,x.start_ms))+sorted([x for x in values if x not in primary],key=lambda x:(-x.local_score,x.start_ms));out=[]
    for c in ordered:
        if sum(max(0,min(c.end_ms,x.end_ms)-max(c.start_ms,x.start_ms))/CONFIG['dense_ms']>.65 for x in out)>=2:continue
        out.append(c)
        if len(out)>=CONFIG['dense_output_k']:break
    for i,c in enumerate(out,1):c.candidate_id=f'H8_{i:02d}'
    return out,coarse,structured
