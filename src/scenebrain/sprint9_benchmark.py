from __future__ import annotations

import json
from pathlib import Path

from .hashing import fingerprint, sha256_file

VERSION='sprint9-exact-benchmark/1.0'

def freeze_from_human_reviewed_source(root:Path)->dict:
    source=root/'benchmark/development/MOMENT_RESOLVER_V2_DEV.jsonl'
    rows=[json.loads(x) for x in source.read_text(encoding='utf8').splitlines() if x.strip()]
    # Deterministic category-stratified split, frozen before any Sprint 9 evaluation.
    buckets={}
    for row in rows:buckets.setdefault(row['category'],[]).append(row)
    dev=[];hold=[]
    for category,items in sorted(buckets.items()):
        for i,row in enumerate(items):(dev if i%2==0 else hold).append(row)
    def convert(row,prefix):
        gt=row['ground_truth'];return {'schema_version':VERSION,'request_id':prefix+row['request_id'][2:],
          'query':row['query_text'],'category':row['category'],'evidence_class':row['evidence_class'],
          'acceptable_scene_ids':[], 'acceptable_source_intervals':[{'start_ms':x['start_ms'],'end_ms':x['end_ms']} for x in gt['acceptable_ranges']],
          'acceptable_shot_ranges':[{'start_shot':x['start_shot'],'end_shot':x['end_shot']} for x in gt['acceptable_ranges']],
          'multiple_ranges_acceptable':len(gt['acceptable_ranges'])>1,'required_visual_facts':[row['query_text']] if gt['verdict']=='EXACT' else [],
          'forbidden_visual_substitutions':['static object/person presence without requested action'] if gt['verdict']=='EXACT' else ['any exact clip'],
          'expected':'EXACT' if gt['verdict']=='EXACT' else 'NONE','notes':'Human-reviewed local-source interval inherited without timestamp invention.','source_sha256':row['source_sha256']}
    outdir=root/'benchmark/sprint9';outdir.mkdir(parents=True,exist_ok=True);devp=outdir/'SPRINT9_EXACT_DEV_V1.jsonl';holdp=outdir/'S04E01_EXACT_HOLDOUT_V1.jsonl'
    devp.write_text('\n'.join(json.dumps(convert(x,'S9D'),separators=(',',':')) for x in dev)+'\n',encoding='utf8')
    holdp.write_text('\n'.join(json.dumps(convert(x,'S9H'),separators=(',',':')) for x in hold)+'\n',encoding='utf8')
    receipt={'version':VERSION,'source_path':str(source.resolve()),'source_sha256':sha256_file(source),'dev_count':len(dev),'holdout_count':len(hold),'dev_sha256':sha256_file(devp),'holdout_sha256':sha256_file(holdp),'split':'category-stratified alternating, immutable','limitation':'Derived from an earlier human-reviewed S04E01 pool; episode-independent holdout is impossible with the currently authorized one-episode scope.'};receipt['fingerprint']=fingerprint(json.dumps(receipt,sort_keys=True));rp=outdir/'SPRINT9_BENCHMARK_FREEZE.json';rp.write_text(json.dumps(receipt,indent=2),encoding='utf8');return receipt
