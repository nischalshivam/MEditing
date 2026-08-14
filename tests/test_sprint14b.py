import hashlib,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'runtime/sprint14b_polish'
class Sprint14BTests(unittest.TestCase):
 def test_retrieval_immutable(self):self.assertEqual(hashlib.sha256((ROOT/'runtime/final_project/FINAL_LOCKED_VISUAL_PLAN.json').read_bytes()).hexdigest(),'08428494d51f7d6f9e75208dd6e2c8ca2007e2641d28ee4d975008392dc1d4e5')
 def test_continuity_manual_and_mix(self):
  s=json.loads((OUT/'TIMELINE_PLAN_V2.json').read_text())['presentation_slots'];self.assertEqual((s[0]['timeline_start_ms'],s[-1]['timeline_end_ms']),(0,887300));self.assertTrue(all(s[i]['timeline_end_ms']==s[i+1]['timeline_start_ms'] for i in range(len(s)-1)));self.assertEqual([x['beat_id'] for x in s if x['approval_state']=='MANUAL_FIX'],['B002','B022'])
 def test_no_accidental_repeat(self):self.assertEqual(json.loads((OUT/'REPETITION_AUDIT.json').read_text())['accidental_repeat_slots'],[])
 def test_exact_never_borrowed(self):
  final=json.loads((ROOT/'runtime/final_project/FINAL_LOCKED_VISUAL_PLAN.json').read_text());exact={x['beat_id'] for x in final['slots'] if x['evidence_class'] in {'EXACT_EVENT','EXACT_DIALOGUE'}};s=json.loads((OUT/'TIMELINE_PLAN_V2.json').read_text())['presentation_slots'];self.assertTrue(all(x['reuse_provenance']!='SOURCE_REUSED_FROM_LOCKED_PROJECT_ASSET' for x in s if x['beat_id'] in exact and x['approval_state']=='APPROVED'))
 def test_subrange_and_render(self):
  s=json.loads((OUT/'TIMELINE_PLAN_V2.json').read_text())['presentation_slots'];self.assertTrue(all(x['source_out_ms'] is None or x['source_out_ms']>=x['source_in_ms'] for x in s if x['approval_state']=='APPROVED'));self.assertGreater((OUT/'SPRINT14B_POLISHED_DRAFT_720P.mp4').stat().st_size,1000000)
