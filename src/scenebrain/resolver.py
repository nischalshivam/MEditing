from __future__ import annotations

import hashlib,json,math,re
from collections import Counter,defaultdict
from pathlib import Path

from .hashing import fingerprint,sha256_file
from .resolver_models import CandidateResult,ResolverResult,SceneRetrievalRequest
from .subtitles import normalize,search_multi_cue

RESOLVER_VERSION="scene-resolver/1.0"
FRAGMENT_VERSION="scene-fragments/1.0"
EMBEDDING_MODEL="local-hashed-word-char-512/1.0"
RANKING_VERSION="evidence-ranking/1.0"

ALIASES={"gus":"gustavo fring","walt":"walter white","jesse":"jesse pinkman","mike":"mike ehrmantraut","saul":"saul goodman",
 "skyler":"skyler white","marie":"marie schrader","hank":"hank schrader","gale":"gale boetticher","victor":"victor"}

PROFILES={
 "EXACT_DIALOGUE":{"dialogue":0.70,"event":0.08,"action":0.05,"object":0.03,"character":0.05,"location":0.02,"semantic":0.07},
 "EXACT_EVENT":{"dialogue":0.05,"event":0.32,"action":0.22,"object":0.14,"character":0.10,"location":0.07,"semantic":0.10},
 "EVENT_CONTEXT":{"dialogue":0.07,"event":0.25,"action":0.16,"object":0.10,"character":0.12,"location":0.10,"semantic":0.20},
 "EDITORIAL_CONTEXT":{"dialogue":0.05,"event":0.18,"action":0.10,"object":0.07,"character":0.10,"location":0.10,"semantic":0.40},
 "CHARACTER_CONTEXT":{"dialogue":0.06,"event":0.14,"action":0.10,"object":0.05,"character":0.40,"location":0.08,"semantic":0.17},
}
THRESHOLDS={"verified":0.56,"verified_margin":0.10,"contextual":0.34,"exact_visual_floor":0.42,"negative_floor":0.58}
VERIFIER_POLICY={"evidence_classes":["EXACT_EVENT"],"local_decision":"ABSTAIN","minimum_top1_score":0.24,"top_k":3,"fail_closed":True}

def expand(text:str)->str:
    value=normalize(text)
    toks=value.split()
    return value+" "+" ".join(ALIASES[t] for t in toks if t in ALIASES)

def terms(text:str)->set[str]: return {x for x in re.findall(r"[a-z0-9']+",expand(text)) if len(x)>1}

def vector(text:str)->dict[int,float]:
    words=terms(text); feats=Counter()
    bucket=lambda value:int.from_bytes(hashlib.sha256(value.encode()).digest()[:4],'big')%512
    for word in words:
        feats[bucket("w:"+word)]+=1
        padded="^"+word+"$"
        for i in range(len(padded)-2):feats[bucket("c:"+padded[i:i+3])]+=.35
    norm=math.sqrt(sum(v*v for v in feats.values())) or 1
    return {k:v/norm for k,v in feats.items()}

def cosine(a:dict,b:dict)->float:return sum(v*b.get(k,0) for k,v in a.items())

def freeze_resolver_inputs(conn,source_id:int,root:Path)->dict:
    source=conn.execute('select * from source_files where id=?',(source_id,)).fetchone(); atlas=conn.execute('select distinct atlas_fingerprint from scenes where source_file_id=?',(source_id,)).fetchall()
    if len(atlas)!=1:raise ValueError('one frozen atlas required')
    files=[]
    for path in [root/'runtime/scene_atlas/S04E01_SCENE_CARDS.json',root/'runtime/scene_atlas/HUMAN_QUALITY_REVIEW.json',root/'benchmark/frozen/s04e01_sprint1_mixed_questions_v2.jsonl',root/'benchmark/frozen/S04E01_VISUAL_HOLDOUT_V1.jsonl']:
        files.append({'path':str(path.resolve()),'sha256':sha256_file(path)})
    runs=[dict(x) for x in conn.execute("select provider,model,prompt_version,schema_version,input_fingerprint,output_fingerprint,status from scene_analysis_runs order by id")]
    manifest={'freeze_version':'resolver-input-freeze/1.0','source_sha256':source['sha256'],'atlas_fingerprint':atlas[0][0],
      'scene_count':conn.execute('select count(*) from scenes where source_file_id=?',(source_id,)).fetchone()[0],
      'proposal_count':conn.execute('select count(*) from scene_window_proposals').fetchone()[0],'provider_runs':runs,'frozen_files':files}
    fp=fingerprint(json.dumps(manifest,sort_keys=True,separators=(',',':')));manifest['input_fingerprint']=fp
    out=root/'runtime/resolver/freezes'/f'{fp}.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(manifest,indent=2),encoding='utf8');digest=sha256_file(out)
    with conn:conn.execute('insert or ignore into resolver_input_freezes(source_file_id,freeze_version,input_fingerprint,manifest_path,manifest_sha256) values(?,?,?,?,?)',(source_id,manifest['freeze_version'],fp,str(out.resolve()),digest))
    return {'freeze_id':conn.execute('select id from resolver_input_freezes where input_fingerprint=?',(fp,)).fetchone()[0],'input_fingerprint':fp,'manifest_path':str(out.resolve()),'manifest_sha256':digest}

def _add_fragment(conn,scene_id,proposal_id,kind,text,evidence,trust,source_fp,provenance):
    if not text:return
    norm=normalize(text);fp=fingerprint(scene_id,proposal_id,kind,norm,json.dumps(evidence),trust,source_fp)
    conn.execute('''insert or ignore into scene_retrieval_fragments(scene_id,proposal_id,fragment_type,objective_text,normalized_text,evidence_shot_ids_json,trust_status,source_fingerprint,provenance_json,fragment_fingerprint) values(?,?,?,?,?,?,?,?,?,?)''',(scene_id,proposal_id,kind,text,norm,json.dumps(evidence),trust,source_fp,json.dumps(provenance),fp))

def build_fragments(conn,source_id:int,source_fp:str)->dict:
    with conn:
        conn.execute('delete from scene_retrieval_fragments where scene_id in (select id from scenes where source_file_id=?)',(source_id,))
        scenes=conn.execute('select * from scenes where source_file_id=? order by ordinal',(source_id,)).fetchall(); shots={r['id']:r for r in conn.execute('select * from shots where source_file_id=?',(source_id,))}
        for scene in scenes:
            _add_fragment(conn,scene['id'],None,'VISUAL_SUMMARY',scene['visual_summary'],[], 'ATLAS_PARTIAL' if scene['analysis_status']!='RESOLVED' else 'SUPPORTED_VISUAL',source_fp,{'scene_uid':scene['scene_uid']})
        for row in conn.execute('select p.* from scene_window_proposals p join scene_analysis_runs r on r.id=p.run_id where r.status="SUCCESS"'):
            raw=json.loads(row['raw_json']);pa,pb=shots[row['start_shot_id']]['ordinal'],shots[row['end_shot_id']]['ordinal']; best=None
            for s in scenes:
                a,b=shots[s['start_shot_id']]['ordinal'],shots[s['end_shot_id']]['ordinal'];ov=max(0,min(b,pb)-max(a,pa)+1)
                if not best or ov>best[0]:best=(ov,s)
            if not best or not best[0]:continue
            sid=best[1]['id'];prov={'proposal_id':row['id'],'boundary_status':raw['boundary_status'],'scene_uid':best[1]['scene_uid']}
            _add_fragment(conn,sid,row['id'],'EVENT',raw['main_event']['description'],raw['main_event']['evidence_shots'],'SUPPORTED_VISUAL',source_fp,prov)
            _add_fragment(conn,sid,row['id'],'VISUAL_SUMMARY',raw['visual_summary'],[], 'SUPPORTED_VISUAL',source_fp,prov)
            for x in raw['visible_actions']:_add_fragment(conn,sid,row['id'],'ACTION',x['description'],x['evidence_shots'],'SUPPORTED_VISUAL',source_fp,prov)
            for x in raw['important_objects']:_add_fragment(conn,sid,row['id'],'OBJECT',x['name'],x['evidence_shots'],'SUPPORTED_VISUAL',source_fp,prov)
            for x in raw['characters']:_add_fragment(conn,sid,row['id'],'CHARACTER',x['name'],x['evidence_shots'],'GENERATED_UNVERIFIED',source_fp,prov)
            _add_fragment(conn,sid,row['id'],'LOCATION',raw['location']['name'],raw['location']['evidence_shots'],'SUPPORTED_VISUAL',source_fp,prov)
        track=conn.execute('select id from subtitle_tracks where source_file_id=? and selected=1',(source_id,)).fetchone()[0]
        for cue in conn.execute('select * from subtitle_cues where track_id=?',(track,)):
            mapped=conn.execute('select * from scenes where source_file_id=? and start_ms<? and end_ms>? order by ordinal',(source_id,cue['end_ms'],cue['start_ms'])).fetchall()
            for scene in mapped:_add_fragment(conn,scene['id'],None,'DIALOGUE_CONTEXT',cue['raw_text'],[], 'SUPPORTED_LOCAL',source_fp,{'cue_index':cue['cue_index'],'start_ms':cue['start_ms'],'end_ms':cue['end_ms'],'boundary_overlap':len(mapped)>1})
        fragments=conn.execute('select * from scene_retrieval_fragments where scene_id in (select id from scenes where source_file_id=?)',(source_id,)).fetchall()
        for f in fragments:
            v=vector(f['objective_text']);conn.execute('insert or replace into scene_fragment_embeddings(fragment_id,embedding_model,vector_json,input_fingerprint) values(?,?,?,?)',(f['id'],EMBEDDING_MODEL,json.dumps(v),fingerprint(f['fragment_fingerprint'],EMBEDDING_MODEL)))
    return {'fragments':len(fragments),'scenes':len(scenes),'embedding_model':EMBEDDING_MODEL}

def _lex(query,text):
    q,t=terms(query),terms(text)
    return len(q&t)/max(1,len(q))

def resolve_local(conn,request:SceneRetrievalRequest,resolver_version=RESOLVER_VERSION,top_k=3)->ResolverResult:
    query=' '.join(filter(None,[request.query_text,request.requested_event,request.visible_action,' '.join(request.objects),request.location,' '.join(request.characters_required),request.continuity_context]));qv=vector(query);profile=PROFILES[request.evidence_class]
    fts_terms=sorted(terms(query));fts_rank={}
    if fts_terms:
        expression=' OR '.join('"'+x.replace('"','')+'"' for x in fts_terms)
        for rank,row in enumerate(conn.execute('''select f.scene_id,bm25(scene_retrieval_fts) score from scene_retrieval_fts join scene_retrieval_fragments f on f.id=scene_retrieval_fts.rowid where scene_retrieval_fts match ? order by score limit 200''',(expression,))):
            fts_rank[row['scene_id']]=max(fts_rank.get(row['scene_id'],0),1/(1+rank/10))
    scenes=conn.execute('select * from scenes order by ordinal').fetchall();candidates=[]
    dialogue_hits=search_multi_cue(conn,request.dialogue_clue or request.query_text,limit=20) if request.evidence_class=='EXACT_DIALOGUE' or request.dialogue_clue else []
    for scene in scenes:
        frags=conn.execute('select f.*,e.vector_json from scene_retrieval_fragments f join scene_fragment_embeddings e on e.fragment_id=f.id and e.embedding_model=? where f.scene_id=?',(EMBEDDING_MODEL,scene['id'])).fetchall();channels=defaultdict(float);matched=[];shots=set();matches=[];conflicts=[]
        for f in frags:
            lex=_lex(query,f['objective_text']);sem=cosine(qv,{int(k):v for k,v in json.loads(f['vector_json']).items()});kind=f['fragment_type']; key={'EVENT':'event','ACTION':'action','OBJECT':'object','CHARACTER':'character','LOCATION':'location','VISUAL_SUMMARY':'semantic','DIALOGUE_CONTEXT':'dialogue'}[kind]
            trust=.35 if f['trust_status']=='GENERATED_UNVERIFIED' else (0.75 if f['trust_status']=='ATLAS_PARTIAL' else 1.0);score=max(lex,sem*.75)*trust;channels[key]=max(channels[key],score)
            if score>=.34:matched.append({'fragment_id':f['id'],'type':kind,'text':f['objective_text'],'trust':f['trust_status'],'score':round(score,4),'evidence_shots':json.loads(f['evidence_shot_ids_json'])});shots.update(json.loads(f['evidence_shot_ids_json']))
        channels['semantic']=max(channels['semantic'],fts_rank.get(scene['id'],0)*.8)
        dh=[h for h in dialogue_hits if h['start_ms']<scene['end_ms'] and h['end_ms']>scene['start_ms']]
        if dh:channels['dialogue']=1.0;matches.append('exact/contiguous verified local dialogue')
        for neg in request.negative_constraints:
            if max((_lex(neg,f['objective_text']) for f in frags),default=0)>=.7:conflicts.append('negative constraint matched: '+neg)
        total=sum(profile[k]*channels[k] for k in profile)-.35*len(conflicts)
        if scene['analysis_status']!='RESOLVED':total*=.92
        candidates.append((total,scene,channels,matched,dh,shots,matches,conflicts))
    candidates.sort(key=lambda x:x[0],reverse=True);out=[]
    for total,scene,ch,matched,dh,shots,matches,conflicts in candidates[:top_k]:
        neighbors=[];reason=None
        if scene['analysis_status']!='RESOLVED' or scene['boundary_status'].startswith('UNKNOWN'):
            prev=conn.execute('select scene_uid from scenes where ordinal=?',(scene['ordinal']-1,)).fetchone();nxt=conn.execute('select scene_uid from scenes where ordinal=?',(scene['ordinal']+1,)).fetchone();neighbors=[x[0] for x in (prev,nxt) if x];reason='atlas semantic coverage or boundary is partial'
        out.append(CandidateResult(scene_id=scene['scene_uid'],start_ms=scene['start_ms'],end_ms=scene['end_ms'],total_score=round(max(0,total),4),channel_scores={k:round(ch[k],4) for k in profile},matched_fragments=matched,matched_dialogue=dh,evidence_shot_ids=sorted(shots),atlas_status=scene['analysis_status'],matches=matches+[f'{m["type"]} fragment' for m in matched[:5]],conflicts=conflicts,neighbors=neighbors,neighbor_reason=reason))
    first=out[0];second=out[1] if len(out)>1 else None;margin=first.total_score-(second.total_score if second else 0);visual=max(first.channel_scores.get(k,0) for k in ('event','action','object'))
    verified=first.total_score>=THRESHOLDS['verified'] and margin>=THRESHOLDS['verified_margin'] and (request.evidence_class!='EXACT_EVENT' or visual>=THRESHOLDS['exact_visual_floor']) and not first.conflicts
    contextual=first.total_score>=THRESHOLDS['contextual'] and not first.conflicts
    if request.none_allowed and first.total_score<THRESHOLDS['contextual']:decision='ABSTAIN';reason='insufficient locally grounded evidence'
    elif verified:decision='VERIFIED';reason='high local evidence with adequate top-candidate separation'
    elif contextual and request.exactness_policy!='LITERAL':decision='CONTEXTUAL';reason='relevant scene context found, literal evidence not strong enough'
    else:decision='ABSTAIN';reason='exact request lacks sufficient evidence or candidate separation'
    return ResolverResult(request_id=request.request_id,resolver_version=resolver_version,decision=decision,primary_scene=first.scene_id if decision!='ABSTAIN' else None,candidates=out,decision_reason=reason,provenance={'ranking_version':RANKING_VERSION,'embedding_model':EMBEDDING_MODEL,'profiles':profile,'thresholds':THRESHOLDS})

def freeze_resolver_version(conn,freeze_id:int,root:Path)->dict:
    config={'profiles':PROFILES,'thresholds':THRESHOLDS,'ranking_version':RANKING_VERSION,'verifier_policy':VERIFIER_POLICY};fp=fingerprint(RESOLVER_VERSION,json.dumps(config,sort_keys=True),EMBEDDING_MODEL,'scene-verifier/1.0','gemini-3.1-flash-lite')
    with conn:conn.execute('insert or ignore into resolver_versions(version,input_freeze_id,schema_version,ranking_config_json,embedding_model,verifier_model,verifier_prompt_version,resolver_fingerprint) values(?,?,?,?,?,?,?,?)',(RESOLVER_VERSION,freeze_id,'scene-retrieval-request/1.0',json.dumps(config,sort_keys=True),EMBEDDING_MODEL,'gemini-3.1-flash-lite','scene-verifier/1.0',fp))
    receipt={'resolver_version':RESOLVER_VERSION,'resolver_fingerprint':fp,'input_freeze_id':freeze_id,'config':config,'embedding_model':EMBEDDING_MODEL,'frozen_before_holdout':True};out=root/'runtime/resolver'/f'{RESOLVER_VERSION.replace("/","_")}_receipt.json';out.write_text(json.dumps(receipt,indent=2),encoding='utf8');return receipt
