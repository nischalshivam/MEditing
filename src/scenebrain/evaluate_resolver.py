from __future__ import annotations

import json,time
from pathlib import Path

from .hashing import sha256_file,fingerprint
from .resolver import RESOLVER_VERSION,VERIFIER_POLICY,resolve_local
from .resolver_models import SceneRetrievalRequest
from .scene_verifier import apply_verifier,verify_topk

def resolve_policy(conn,root:Path,req:SceneRetrievalRequest):
    result=resolve_local(conn,req)
    use=req.evidence_class in VERIFIER_POLICY['evidence_classes'] and result.decision==VERIFIER_POLICY['local_decision'] and result.candidates[0].total_score>=VERIFIER_POLICY['minimum_top1_score']
    if use:result=apply_verifier(result,verify_topk(conn,root,req,result),req)
    return result

def request_from_holdout(row):
    cat=row['category'];evidence='EVENT_CONTEXT' if cat=='SCENE_CONTEXT' else 'EXACT_EVENT';policy='CONTEXT_OK' if cat=='SCENE_CONTEXT' else 'LITERAL'
    return SceneRetrievalRequest(request_id=row['question_id'],query_text=row['query'],evidence_class=evidence,none_allowed=True,exactness_policy=policy)

def _expected_scenes(conn,row):
    if row['ground_truth']['verdict']=='NONE':return set()
    result=set()
    for rg in row['ground_truth']['acceptable_shot_ranges']:
        a,b=int(rg['start_shot'][1:]),int(rg['end_shot'][1:])
        for x in conn.execute('''select distinct sc.scene_uid from scenes sc join scene_shots ss on ss.scene_id=sc.id join shots s on s.id=ss.shot_id where s.ordinal between ? and ?''',(a,b)):result.add(x[0])
    return result

def evaluate_holdout_once(conn,root:Path,dataset:Path,evaluation_name:str='S04E01_VISUAL_HOLDOUT_V1_EVAL'):
    if conn.execute('select 1 from resolver_evaluations where evaluation_name=?',(evaluation_name,)).fetchone():raise RuntimeError('immutable evaluation already exists')
    version=conn.execute('select * from resolver_versions where version=?',(RESOLVER_VERSION,)).fetchone()
    if not version:raise RuntimeError('resolver version must be frozen first')
    rows=[json.loads(x) for x in dataset.read_text(encoding='utf8').splitlines() if x.strip()];results=[]
    for row in rows:
        req=request_from_holdout(row);expected=_expected_scenes(conn,row);res=resolve_policy(conn,root,req);ranked=[x.scene_id for x in res.candidates]
        record={'request_id':req.request_id,'category':row['category'],'expected_scenes':sorted(expected),'expected_none':not expected,'decision':res.decision,'primary_scene':res.primary_scene,'ranked_scenes':ranked,'top1_correct':bool(expected and ranked and ranked[0] in expected),'top3_correct':bool(expected and any(x in expected for x in ranked[:3])),'auto_correct':(res.primary_scene in expected if res.decision!='ABSTAIN' else not expected),'verifier_used':bool(res.verifier and res.verifier.get('used')),'result':res.model_dump()};results.append(record)
    positives=[x for x in results if not x['expected_none']];verified=[x for x in results if x['decision']=='VERIFIED'];accepted=[x for x in results if x['decision']!='ABSTAIN'];neg=[x for x in results if x['expected_none']]
    by={}
    for cat in sorted({x['category'] for x in results}):
        group=[x for x in results if x['category']==cat];by[cat]={'n':len(group),'recall_at_1':sum(x['top1_correct'] for x in group if not x['expected_none'])/max(1,sum(not x['expected_none'] for x in group)),'recall_at_3':sum(x['top3_correct'] for x in group if not x['expected_none'])/max(1,sum(not x['expected_none'] for x in group)),'abstention_rate':sum(x['decision']=='ABSTAIN' for x in group)/len(group)}
    metrics={'n':len(results),'positive_n':len(positives),'recall_at_1':sum(x['top1_correct'] for x in positives)/len(positives),'recall_at_3':sum(x['top3_correct'] for x in positives)/len(positives),'mrr':sum((1/(x['ranked_scenes'].index(next(s for s in x['ranked_scenes'] if s in x['expected_scenes']))+1) if any(s in x['expected_scenes'] for s in x['ranked_scenes']) else 0) for x in positives)/len(positives),'verified_precision':sum(x['auto_correct'] for x in verified)/max(1,len(verified)),'verified_coverage':len(verified)/len(positives),'accepted_precision':sum(x['auto_correct'] for x in accepted)/max(1,len(accepted)),'abstention_rate':sum(x['decision']=='ABSTAIN' for x in results)/len(results),'wrong_auto_accept_rate':sum(not x['auto_correct'] for x in accepted)/len(results),'none_correct_abstentions':sum(x['decision']=='ABSTAIN' for x in neg),'none_n':len(neg),'none_false_positive':sum(x['decision']!='ABSTAIN' for x in neg),'verifier_call_count':sum(x['verifier_used'] for x in results),'local_only_count':sum(not x['verifier_used'] for x in results),'by_category':by}
    artifact={'schema_version':'resolver-evaluation/1.0','evaluation_name':evaluation_name,'resolver_fingerprint':version['resolver_fingerprint'],'dataset_sha256':sha256_file(dataset),'run_order':'single frozen holdout evaluation','metrics':metrics,'results':results}
    out=root/'runtime/resolver/evaluations'/f'{evaluation_name}.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(artifact,indent=2,ensure_ascii=False),encoding='utf8');digest=sha256_file(out)
    with conn:conn.execute('insert into resolver_evaluations(resolver_version_id,evaluation_name,dataset_path,dataset_sha256,result_path,result_sha256,metrics_json) values(?,?,?,?,?,?,?)',(version['id'],evaluation_name,str(dataset.resolve()),artifact['dataset_sha256'],str(out.resolve()),digest,json.dumps(metrics)))
    return {'evaluation_name':evaluation_name,'result_path':str(out.resolve()),'result_sha256':digest,'metrics':metrics}
