from __future__ import annotations

import json,re
from collections import defaultdict
from pathlib import Path

from .hashing import fingerprint,sha256_file
from .resolver import terms
from .shot_models import ShotRange,ShotRequest

SHOT_RESOLVER_VERSION='shot-resolver/1.0'
CANDIDATE_VERSION='bounded-shot-candidates/1.0'
CONFIG={'scene_top_k':3,'evidence_neighbor_shots':2,'dialogue_neighbor_shots':2,'candidate_k':12,
        'max_group_shots':5,'preview_max_seconds':12.0,'dense_fps':3,'crop_handle_before_ms':500,
        'crop_handle_after_ms':700,'boundary_sensitive_scenes':['S04E01_SC013']}

def _uid(n:int)->str:return f'S{n:04d}'
def _ord(uid:str)->int:
    if not re.fullmatch(r'S\d{4}',uid):raise ValueError('invalid physical shot ID')
    return int(uid[1:])

def freeze_inputs(conn,root:Path,source_id:int=1)->dict:
    source=conn.execute('select * from source_files where id=?',(source_id,)).fetchone()
    rv=conn.execute("select * from resolver_versions where version='scene-resolver/1.0'").fetchone()
    if not source or not rv:raise ValueError('frozen Sprint 3 foundation required')
    shots=[dict(x) for x in conn.execute('select ordinal,start_ms,end_ms,input_fingerprint from shots where source_file_id=? order by ordinal',(source_id,))]
    if len(shots)!=460:raise ValueError('expected frozen 460-shot source')
    payload={'freeze_version':'shot-resolver-input/1.0','source_id':source_id,'source_path':source['path'],
      'source_sha256':source['sha256'],'duration_ms':source['duration_ms'],'shot_manifest':shots,
      'sprint3_version':rv['version'],'sprint3_fingerprint':rv['resolver_fingerprint'],
      'sprint3_receipt_sha256':sha256_file(root/'runtime/resolver/frozen_resolver_receipt.json'),
      'atlas_fingerprint':conn.execute('select distinct atlas_fingerprint from scenes').fetchone()[0]}
    fp=fingerprint(json.dumps(payload,sort_keys=True));out=root/'runtime/shot_resolver/freezes'/f'{fp}.json';out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(payload,indent=2),encoding='utf8');digest=sha256_file(out)
    with conn:conn.execute('insert or ignore into shot_resolver_input_freezes(source_file_id,resolver_version_id,freeze_version,input_fingerprint,manifest_path,manifest_sha256) values(?,?,?,?,?,?)',(source_id,rv['id'],payload['freeze_version'],fp,str(out.resolve()),digest))
    return {'input_fingerprint':fp,'manifest_path':str(out.resolve()),'manifest_sha256':digest}

def _allowed_scene_ids(req:ShotRequest)->list[str]:
    ids=[]
    for c in req.sprint3_result.candidates[:CONFIG['scene_top_k']]:
        if c.scene_id not in ids:ids.append(c.scene_id)
        for n in c.neighbors:
            if n not in ids:ids.append(n)
    return ids

def generate_candidates(conn,req:ShotRequest)->list[ShotRange]:
    if req.sprint3_result.resolver_version!='scene-resolver/1.0':raise ValueError('stale scene resolver version')
    frozen=conn.execute("select resolver_fingerprint from resolver_versions where version='scene-resolver/1.0'").fetchone()
    if not frozen:raise ValueError('missing frozen Sprint 3 resolver')
    allowed=_allowed_scene_ids(req); scene_ord={r['scene_uid']:(r['start_shot_id'],r['end_shot_id']) for r in conn.execute('select scene_uid,start_shot_id,end_shot_id from scenes where scene_uid in (%s)'%','.join('?'*len(allowed)),allowed)} if allowed else {}
    if not scene_ord:return []
    qterms=terms(' '.join(filter(None,[req.scene_request.query_text,req.scene_request.requested_event,req.scene_request.visible_action,*req.scene_request.objects])))
    seeds=defaultdict(list)
    for c in req.sprint3_result.candidates[:CONFIG['scene_top_k']]:
        if c.scene_id not in scene_ord:continue
        for f in c.matched_fragments:
            text=f.get('text') or f.get('objective_text') or ''
            overlap=len(qterms&terms(text))/max(1,len(qterms))
            if overlap<=0:continue
            for uid in f.get('evidence_shots',[]):
                if re.fullmatch(r'S\d{4}',uid):seeds[_ord(uid)].append({'kind':'fragment','scene':c.scene_id,'text':text,'overlap':overlap})
        for d in c.matched_dialogue:
            for row in conn.execute('select ordinal from shots where start_ms<=? and end_ms>=?',(d.get('end_ms',-1),d.get('start_ms',-1))):seeds[row[0]].append({'kind':'dialogue','scene':c.scene_id,'cue':d})
    # Exact dialogue request uses authoritative cue mapping even when Sprint 3 explanation omitted it.
    if req.scene_request.evidence_class=='EXACT_DIALOGUE' and req.scene_request.dialogue_clue:
        from .subtitles import search_multi_cue
        for d in search_multi_cue(conn,req.scene_request.dialogue_clue,10):
            for row in conn.execute('select ordinal from shots where source_file_id=1 and start_ms<=? and end_ms>=?',(d['end_ms'],d['start_ms'])):seeds[row[0]].append({'kind':'dialogue','cue':d})
    # Search all typed fragments inside the supplied top-K regions. This never expands globally;
    # it recovers evidence fragments omitted from the compact Sprint 3 explanation.
    if qterms:
        for sid in allowed:
            for f in conn.execute('''select f.objective_text,f.evidence_shot_ids_json from scene_retrieval_fragments f join scenes s on s.id=f.scene_id where s.scene_uid=?''',(sid,)):
                overlap=len(qterms&terms(f['objective_text']))/max(1,len(qterms))
                if overlap<.25:continue
                for uid in json.loads(f['evidence_shot_ids_json']):
                    if re.fullmatch(r'S\d{4}',uid):seeds[_ord(uid)].append({'kind':'fragment-index','scene':sid,'text':f['objective_text'],'overlap':overlap})
    allowed_ord=set()
    for sid in allowed:
        if sid not in scene_ord:continue
        a,b=scene_ord[sid];ao=conn.execute('select ordinal from shots where id=?',(a,)).fetchone()[0];bo=conn.execute('select ordinal from shots where id=?',(b,)).fetchone()[0];allowed_ord.update(range(ao,bo+1))
    ranges=[]
    for seed,prov in seeds.items():
        if seed not in allowed_ord:continue
        radius=CONFIG['dialogue_neighbor_shots'] if any(x['kind']=='dialogue' for x in prov) else CONFIG['evidence_neighbor_shots']
        a=max(min(allowed_ord),seed-radius);b=min(max(allowed_ord),seed+radius)
        # Do not bridge holes between non-neighbor regions.
        while a<seed and a not in allowed_ord:a+=1
        while b>seed and b not in allowed_ord:b-=1
        rows=conn.execute('select ordinal,start_ms,end_ms from shots where source_file_id=1 and ordinal between ? and ? order by ordinal',(a,b)).fetchall()
        if not rows or any(rows[i]['ordinal']+1!=rows[i+1]['ordinal'] for i in range(len(rows)-1)):continue
        local=.60+min(.25,max((x.get('overlap',0) for x in prov),default=0)*.25)+(.1 if any(x['kind']=='dialogue' for x in prov) else 0)
        # Preserve Sprint 3 scene order as a modest tie-break, not a hard gate.
        best_scene=next((x.get('scene') for x in prov if x.get('scene')),None)
        if best_scene in allowed:local+=max(0,.06-.02*allowed.index(best_scene))
        scene_ids=[s for s,(si,ei) in scene_ord.items() if conn.execute('select 1 from shots where id=? and ordinal between ? and ?',(si,a,b)).fetchone() or conn.execute('select 1 from shots where id=? and ordinal between ? and ?',(ei,a,b)).fetchone()]
        ranges.append(ShotRange(candidate_id='pending',start_shot=_uid(a),end_shot=_uid(b),start_ms=rows[0]['start_ms'],end_ms=rows[-1]['end_ms'],scene_ids=scene_ids or [prov[0].get('scene','UNKNOWN')],local_score=min(1,local),provenance=prov,boundary_sensitive=any(s in CONFIG['boundary_sensitive_scenes'] for s in scene_ids)))
    # Collapse exact duplicate and heavily overlapping seed windows, retaining evidence.
    ranges.sort(key=lambda x:(-x.local_score,_ord(x.start_shot)))
    out=[]
    for r in ranges:
        duplicate=next((x for x in out if _ord(r.start_shot)<=_ord(x.end_shot) and _ord(x.start_shot)<=_ord(r.end_shot) and abs(_ord(r.start_shot)-_ord(x.start_shot))<=2),None)
        if duplicate:duplicate.provenance.extend(r.provenance);continue
        out.append(r)
    out=out[:CONFIG['candidate_k']]
    for i,r in enumerate(out,1):r.candidate_id=f'CANDIDATE_{i:02d}'
    return out

def derive_crop(candidate:ShotRange,supporting_shots:list[str])->tuple[int,int]:
    if not supporting_shots:return candidate.start_ms,candidate.end_ms
    # Times are selected from authoritative candidate shot bounds only; model timestamps are never accepted.
    return max(candidate.start_ms,candidate.start_ms-CONFIG['crop_handle_before_ms']),min(candidate.end_ms,candidate.end_ms+CONFIG['crop_handle_after_ms'])
