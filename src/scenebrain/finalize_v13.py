from __future__ import annotations
import json, sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from .db import connect
from .hashing import fingerprint, sha256_file

def _write(path:Path,obj:object):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(obj,indent=2,ensure_ascii=False),encoding='utf-8')

def finalize(root:Path)->dict:
    s12=root/'runtime/sprint12_real_script';s13=root/'runtime/sprint13_repair';out=root/'runtime/final_project'
    original=json.loads((s12/'audit/SPRINT12_HUMAN_AUDIT.json').read_text(encoding='utf-8'))
    original_receipt=json.loads((s12/'audit/SPRINT12_HUMAN_AUDIT_RECEIPT.json').read_text(encoding='utf-8'))
    repair_plan=json.loads((s13/'REPAIRED_VISUAL_PLAN.json').read_text(encoding='utf-8'))
    disk_path=s13/'audit/SPRINT13_REPAIR_DECISIONS.json';disk=json.loads(disk_path.read_text(encoding='utf-8'))
    if len(original['decisions'])!=59 or original_receipt['accepted_count']!=41 or original_receipt['none_good_count']!=18: raise ValueError('Sprint 12 frozen counts invalid')
    if sha256_file(s12/'audit/SPRINT12_HUMAN_AUDIT.json')!=original_receipt['audit_sha256']: raise ValueError('Sprint 12 audit receipt mismatch')
    if len(disk.get('decisions',{}))!=18: raise ValueError('exactly 18 repair decisions required')
    items={x['slot_id']:x for x in repair_plan['items']};decisions=disk['decisions']
    if set(items)!=set(decisions): raise ValueError('repair decision coverage mismatch')
    db=connect(root/'runtime/scene_brain.db');sql={r['slot_id']:dict(r) for r in db.execute('select * from project_repair_decisions')}
    if set(sql)!=set(decisions): raise ValueError('disk/SQLite repair coverage mismatch')
    accepted=[];manual=[]
    for sid in sorted(items):
        d=decisions[sid];s=sql[sid]
        if d['decision']!=s['decision'] or d.get('asset_id')!=s['asset_id']: raise ValueError(f'disk/SQLite mismatch: {sid}')
        item=items[sid]
        if d['decision']=='NONE_GOOD':
            manual.append({'slot_id':sid,'beat_id':item['beat_id'],'state':'MANUAL_REPLACEMENT_REQUIRED','narration':item['narration'],'previous_failure_class':item['failure_class']});continue
        asset=next((a for a in item['options'] if a['asset_id']==d['asset_id']),None)
        if not asset: raise ValueError(f'accepted asset not presented: {sid}')
        row={'beat_id':item['beat_id'],'slot_id':sid,'narration':item['narration'],'evidence_class':item['evidence_class'],'original_color':item['status'],
             'decision':'PROJECT_SLOT_APPROVAL','approval_scope':'PROJECT_SLOT_APPROVAL','chosen_asset_id':asset['asset_id'],'chosen_media_type':asset['media_type'],
             'chosen_source':asset['source_path'],'chosen_episode':asset.get('episode_code'),'chosen_source_range_or_frame':{'source_in_ms':asset.get('source_in_ms'),'source_out_ms':asset.get('source_out_ms'),'frame_time_ms':asset.get('frame_time_ms')},
             'chosen_asset':asset,'repair_decision_saved_at':d['saved_at']}
        accepted.append(row)
        payload=json.dumps(row,sort_keys=True)
        db.execute('insert or ignore into project_slot_decisions(project_fingerprint,slot_id,decision_type,asset_id,decision_json,audit_receipt_sha256,locked) values(?,?,?,?,?,?,1)',
                   (original['project_fingerprint'],sid,'PROJECT_SLOT_APPROVAL',asset['asset_id'],payload,sha256_file(disk_path)))
    originals=[dict(x,state='LOCKED_ACCEPTED',approval_scope='PROJECT_SLOT_APPROVAL') for x in original['decisions'] if x['decision']=='PROJECT_SLOT_APPROVAL']
    final=[]
    for x in originals:
        chosen=next(a for a in x['all_presented_options'] if a['asset_id']==x['chosen_asset_id']);x['chosen_asset']=chosen;final.append(x)
    final += accepted
    if len(final)!=57 or len(manual)!=2: raise ValueError('unexpected final counts')
    # Full physical source integrity, deduplicated by source path and expected SHA.
    integrity=[]
    sources={x['chosen_asset']['source_path']:x['chosen_asset']['source_hash'] for x in final}
    for raw,expected in sorted(sources.items()):
        p=Path(raw);actual=sha256_file(p) if p.is_file() else None
        integrity.append({'path':raw,'exists':p.is_file(),'expected_sha256':expected,'actual_sha256':actual,'sha256_match':actual==expected})
    if not all(x['exists'] and x['sha256_match'] for x in integrity): raise ValueError('selected source integrity failed')
    db.commit()
    lock_count=db.execute('select count(*) from project_slot_decisions where project_fingerprint=? and locked=1',(original['project_fingerprint'],)).fetchone()[0]
    db.close()
    final=sorted(final,key=lambda x:x['slot_id']);types=Counter(x['chosen_media_type'] for x in final);colors=Counter(x['original_color'].replace('_UNRESOLVED','') for x in final)
    plan={'version':'final-locked-visual-plan/1.0','project_fingerprint':original['project_fingerprint'],'status':'RETRIEVAL_R_AND_D_FROZEN','total_slots':59,
          'locked_accepted_count':57,'manual_replacement_count':2,'rerun_policy':'FORBIDDEN_UNLESS_USER_EXPLICITLY_REPLACES','slots':final}
    plan['fingerprint']=fingerprint(json.dumps(plan,sort_keys=True));_write(out/'FINAL_LOCKED_VISUAL_PLAN.json',plan)
    queue={'version':'manual-replacement-queue/1.0','count':len(manual),'items':manual};queue['fingerprint']=fingerprint(json.dumps(queue,sort_keys=True));_write(out/'MANUAL_REPLACEMENT_QUEUE.json',queue)
    state={'version':'final-project-state/1.0','project_fingerprint':original['project_fingerprint'],'retrieval_status':'RETRIEVAL_R_AND_D_FROZEN',
           'locked_slots':[{'slot_id':x['slot_id'],'state':'LOCKED_ACCEPTED','asset_id':x['chosen_asset_id']} for x in final],
           'manual_slots':[{'slot_id':x['slot_id'],'state':'MANUAL_REPLACEMENT_REQUIRED'} for x in manual],
           'next_phase':'REAL_VOICEOVER_ALIGNMENT','retrieval_mutation_allowed':False};_write(out/'FINAL_PROJECT_STATE.json',state)
    receipt={'version':'final-human-audit-receipt/1.0','created_at':datetime.now(timezone.utc).isoformat(),'sprint12_audit_sha256':sha256_file(s12/'audit/SPRINT12_HUMAN_AUDIT.json'),
             'sprint12_receipt_sha256':sha256_file(s12/'audit/SPRINT12_HUMAN_AUDIT_RECEIPT.json'),'sprint13_decisions_sha256':sha256_file(disk_path),
             'sprint13_plan_sha256':sha256_file(s13/'REPAIRED_VISUAL_PLAN.json'),'original_locked':41,'repair_accepted':16,'repair_none_good':2,'final_locked':57,
             'manual_required':2,'coverage':57/59,'sqlite_locked_count':lock_count,'browser_local_storage_required':False,'approval_semantics':{
                 'project_slot_approval':'Reusable only within this project','exact_event_approval':'Not inferred','exact_dialogue_approval':'Not inferred','contextual_visual_approval':'Not promoted globally'},
             'source_integrity':integrity,'no_accepted_slot_rerun':True}
    receipt['fingerprint']=fingerprint(json.dumps(receipt,sort_keys=True));_write(out/'FINAL_HUMAN_AUDIT_RECEIPT.json',receipt)
    metrics={'total_slots':59,'original_accepted':41,'repair_accepted':16,'repair_none_good':2,'final_accepted':57,'remaining_manual':2,'usable_coverage':57/59,
             'media_types':dict(types),'statuses':dict(colors),'source_files_checked':len(integrity),'source_integrity_pass':True,'persistent_sqlite_locks':lock_count,
             'retrieval_status':'RETRIEVAL_R_AND_D_FROZEN'};_write(out/'metrics.json',metrics)
    return {'metrics':metrics,'receipt':receipt,'manual':manual}
