import unittest
from scenebrain.independent_verifier_v9b import IndependentDecision,VisibleFacts,MODELS,facts

class IndependentVerifierTests(unittest.TestCase):
 def test_visible_fact_contract(self):
  x=facts({'request_id':'R','query':'Skyler enters house','required_visual_facts':['Skyler visible','threshold transition'],'category':'ENTER_LEAVE'})
  self.assertIn('threshold transition',x.required_visible_facts);self.assertTrue(x.not_sufficient)
 def test_strict_three_way_schema(self):
  x=IndependentDecision(request_id='R',candidate_id='C',classification='PARTIAL_MATCH',evidence_statement='static only')
  self.assertEqual(x.classification,'PARTIAL_MATCH')
 def test_timestamps_forbidden(self):
  with self.assertRaises(Exception):IndependentDecision.model_validate({'request_id':'R','candidate_id':'C','classification':'LITERAL_MATCH','evidence_statement':'x','timestamp_ms':3})
 def test_model_configs_are_separate(self):
  self.assertNotEqual(MODELS['gemini-3.1-flash-lite'],MODELS['gemini-2.5-flash'])
 def test_candidate_isolation_contract(self):
  self.assertNotIn('other_candidates',VisibleFacts.model_fields)

if __name__=='__main__':unittest.main()
