import unittest
from pathlib import Path
from scenebrain.frame_verifier_v9c import FrameDecision,OracleLabel,classify_error
from scenebrain.oracle_review_v9c import freeze_labels
from scenebrain.oracle_review_v9c import validate_harness

class FrameVerifierV9CTests(unittest.TestCase):
 def test_frame_evidence_strict(self):
  x=FrameDecision(request_id='R',candidate_id='C',classification='LITERAL_MATCH',evidence_frame_ids=['F01'],evidence_statement='change')
  self.assertEqual(x.evidence_frame_ids,['F01'])
 def test_timestamp_rejected(self):
  with self.assertRaises(Exception):FrameDecision.model_validate({'request_id':'R','candidate_id':'C','classification':'NO_MATCH','evidence_statement':'x','timestamp':1})
 def test_oracle_schema(self):
  x=OracleLabel(request_id='R',candidate_id='C',human_label='PARTIAL',reviewed_at='now',source_fingerprint='s',candidate_fingerprint='c')
  self.assertEqual(x.human_label,'PARTIAL')
 def test_error_taxonomy(self):
  self.assertEqual(classify_error(RuntimeError('429 RESOURCE_EXHAUSTED'))['kind'],'rate_limit')
  self.assertTrue(classify_error(RuntimeError('503 server'))['retryable'])
 def test_incomplete_oracle_cannot_freeze(self):
  import tempfile
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'x';p.write_text('');
   with self.assertRaises(ValueError):freeze_labels(p,Path(d)/'r')
 def test_web_harness_preflight(self):
  root=Path(__file__).resolve().parents[1]/'runtime'/'sprint9c'
  result=validate_harness(root)
  self.assertEqual((result['requests'],result['candidates'],result['assets']),(8,192,192))

if __name__=='__main__':unittest.main()
