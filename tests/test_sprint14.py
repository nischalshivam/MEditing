import json,hashlib,subprocess,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'runtime/sprint14_voiceover'
class Sprint14Tests(unittest.TestCase):
 def test_frozen_retrieval_immutable(self):
  self.assertEqual(hashlib.sha256((ROOT/'runtime/final_project/FINAL_LOCKED_VISUAL_PLAN.json').read_bytes()).hexdigest(),'08428494d51f7d6f9e75208dd6e2c8ca2007e2641d28ee4d975008392dc1d4e5')
 def test_all_beats_aligned_monotonic(self):
  b=json.loads((OUT/'BEAT_ALIGNMENT.json').read_text())['beats'];self.assertEqual(len(b),59);self.assertTrue(all(x['alignment_status']!='UNALIGNED' for x in b));self.assertTrue(all(b[i]['voice_start_ms']<=b[i+1]['voice_start_ms'] for i in range(58)))
 def test_timeline_contiguous_and_manual(self):
  p=json.loads((OUT/'TIMELINE_PLAN.json').read_text());s=p['presentation_slots'];self.assertEqual(s[0]['timeline_start_ms'],0);self.assertEqual(s[-1]['timeline_end_ms'],887300);self.assertTrue(all(s[i]['timeline_end_ms']==s[i+1]['timeline_start_ms'] for i in range(len(s)-1)));self.assertEqual([x['beat_id'] for x in s if x['approval_state']=='MANUAL_FIX'],['B002','B022'])
 def test_derivatives_inside_lock(self):
  p=json.loads((OUT/'TIMELINE_PLAN.json').read_text());self.assertTrue(all(x['source_in_ms']<=x['frame_time_ms']<=x['source_out_ms'] for x in p['presentation_slots'] if x['presentation_type']=='IMAGE' and x['source_in_ms'] is not None and x['source_out_ms'] is not None))
 def test_draft_and_page(self):
  self.assertGreater((OUT/'SPRINT14_SYNC_DRAFT_720P.mp4').stat().st_size,1000000);h=(OUT/'SPRINT14_TIMELINE_REVIEW.html').read_text();self.assertIn('Previous Manual Issue',h);self.assertIn('ontimeupdate',h)
