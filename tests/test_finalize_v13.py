import json, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class FinalizeV13Tests(unittest.TestCase):
 def test_final_counts_and_unique_slots(self):
  p=json.loads((ROOT/'runtime/final_project/FINAL_LOCKED_VISUAL_PLAN.json').read_text(encoding='utf8'));q=json.loads((ROOT/'runtime/final_project/MANUAL_REPLACEMENT_QUEUE.json').read_text(encoding='utf8'))
  self.assertEqual((p['total_slots'],p['locked_accepted_count'],q['count']),(59,57,2));self.assertEqual(len({x['slot_id'] for x in p['slots']}),57)
 def test_approval_semantics_and_no_rerun(self):
  r=json.loads((ROOT/'runtime/final_project/FINAL_HUMAN_AUDIT_RECEIPT.json').read_text(encoding='utf8'))
  self.assertTrue(r['no_accepted_slot_rerun']);self.assertEqual(r['approval_semantics']['exact_event_approval'],'Not inferred')
 def test_all_selected_paths_and_hashes(self):
  r=json.loads((ROOT/'runtime/final_project/FINAL_HUMAN_AUDIT_RECEIPT.json').read_text(encoding='utf8'))
  self.assertTrue(all(x['exists'] and x['sha256_match'] for x in r['source_integrity']))
 def test_disk_authority_not_localstorage(self):
  s=json.loads((ROOT/'runtime/final_project/FINAL_PROJECT_STATE.json').read_text(encoding='utf8'))
  self.assertFalse(s['retrieval_mutation_allowed']);self.assertEqual(len(s['locked_slots']),57)
