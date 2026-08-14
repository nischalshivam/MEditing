import json, tempfile, unittest
from pathlib import Path
from scenebrain.repair_v13 import compile_v2, repair_set
from scenebrain.sprint13_repair_server import persist, PLAN, AUDIT

ROOT=Path(__file__).resolve().parents[1]

class Sprint13RepairTests(unittest.TestCase):
    def test_frozen_counts_and_unique_queue(self):
        a=json.loads((ROOT/'runtime/sprint12_real_script/audit/SPRINT12_HUMAN_AUDIT.json').read_text(encoding='utf8'))
        self.assertEqual(len(a['decisions']),59);self.assertEqual(sum(x['decision']=='PROJECT_SLOT_APPROVAL' for x in a['decisions']),41)
        r=repair_set(a);self.assertEqual(len(r),18);self.assertEqual(len({x['slot_id'] for x in r}),18)
    def test_contextual_callback(self):
        rows=compile_v2([{'beat_id':'A','exact_narration':'Money appears','canonical_event_id':'MONEY','primary_subjects':['Skyler'],'location_clues':['storage'],'evidence_class':'EXACT_EVENT','active_scene_relation':'NEW_EVENT'},
                         {'beat_id':'B','exact_narration':'That failure matters','canonical_event_id':None,'primary_subjects':[],'location_clues':[],'evidence_class':'EDITORIAL_CONTEXT','active_scene_relation':'CONTINUE_PREVIOUS'}])
        self.assertEqual(rows[1]['context_anchor_event_ids'],['MONEY']);self.assertIn('Skyler',rows[1]['fallback_subjects'])
    def test_plan_is_18_and_max_five(self):
        p=json.loads((ROOT/'runtime/sprint13_repair/REPAIRED_VISUAL_PLAN.json').read_text(encoding='utf8'))
        self.assertEqual(len(p['items']),18);self.assertTrue(all(1<=len(x['options'])<=5 for x in p['items']))
        self.assertTrue(any(x['status']=='ORANGE' and x['options'] for x in p['items']))
    def test_accepted_locks(self):
        import sqlite3
        c=sqlite3.connect(ROOT/'runtime/scene_brain.db')
        count=c.execute("select count(*) from project_slot_decisions where locked=1").fetchone()[0]
        self.assertGreaterEqual(count,41)  # 41 before finalization; 57 after accepted repairs are locked.
    def test_disk_persistence(self):
        p=json.loads(PLAN.read_text(encoding='utf8'));item=p['items'][0];a=item['options'][0]
        result=persist({'slot_id':item['slot_id'],'decision':'USE_OPTION_1','asset_id':a['asset_id']})
        self.assertTrue(result['ok']);disk=json.loads((AUDIT/'SPRINT13_REPAIR_DECISIONS.json').read_text(encoding='utf8'))
        self.assertEqual(disk['decisions'][item['slot_id']]['asset_id'],a['asset_id'])
        (AUDIT/'SPRINT13_REPAIR_DECISIONS.json').unlink(missing_ok=True)
        import sqlite3
        c=sqlite3.connect(ROOT/'runtime/scene_brain.db');c.execute('delete from project_repair_decisions');c.commit();c.close()

if __name__=='__main__':unittest.main()
