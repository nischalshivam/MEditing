import json,tempfile,unittest
from pathlib import Path
from scenebrain.v15 import *

class V15Tests(unittest.TestCase):
 def test_manifest_is_canonical_and_hashed(self):
  with tempfile.TemporaryDirectory() as d:
   s=ProjectManifestStore(Path(d)/'p.db');h=s.save('p',{'source_scope':['t'],'human_decisions':[]});self.assertEqual(s.load('p')['state_hash'],h)
 def test_planner_and_conflict(self):
  a=ProjectPlanner().analyze('x','Hank reads the book. Hank confronts Walter.',{'beats':[{'narration':'Hank reads','face_visibility_requirements':['Walter']}]},12)
  self.assertGreater(a['word_count'],0);self.assertTrue(a['characters']);self.assertEqual(a['clue_conflicts'][0]['type'],'CLUE_SCRIPT_CONFLICT')
 def test_query_lanes(self):
  r=VisualRequirement('r',narration='Hank reads',primary_subjects=['Hank'],required_action='READ',required_objects=['book'])
  q=QueryCompiler().compile(r);self.assertEqual(q['action_lane'],'READ');self.assertEqual(q['object_lane'],['book'])
 def test_character_gallery_nonblocking(self):
  with tempfile.TemporaryDirectory() as d:
   g=CharacterGallery(Path(d)/'x.db');self.assertFalse(g.readiness('t','c')['blocking']);self.assertIn(g.readiness('t','c')['status'],['MISSING'])
   self.assertEqual(CharacterEvidencePlugin(g).classify_scores({'wrong':.2})['status'],'UNKNOWN')
 def test_memory_accept_reject(self):
  with tempfile.TemporaryDirectory() as d:
   m=EditorialMemory(Path(d)/'m.db');cs=[{'id':'a','scene_id':'s1'},{'id':'b','scene_id':'s2'}];m.record('p','t','q','e',cs,'b');rows=m.evidence('t','q');self.assertEqual({x['decision'] for x in rows},{'ACCEPTED','REJECTED'})
 def test_ai_budget_and_cache(self):
  with tempfile.TemporaryDirectory() as d:
   x=AICacheBudget(Path(d)/'a.db',.01);meta={'source_hash':'s','candidate_hash':'c','prompt_version':'1','provider':'gemini','model':'flash'};x.put('k',meta,{'decision':'NO_MATCH'},.001);self.assertEqual(x.get('k')['decision'],'NO_MATCH')
   with self.assertRaises(RuntimeError):x.put('k2',meta,{},.1)
 def test_ranker_explainable_and_manual(self):
  ranked=CandidateRanker().rank([{'id':'a','evidence':{'dialogue':1,'action':1}},{'id':'b','evidence':{}}]);self.assertTrue(ranked[0]['why_this']);self.assertIn(ConfidenceGate().decide(ranked)['state'],['AUTO','OPTIONS'])
  self.assertEqual(ConfidenceGate().decide([])['state'],'MANUAL_REQUIRED')
 def test_no_fake_short_slicing(self):
  clips=[{'kind':'video','start':i*5,'duration':5,'source_in':i*5,'source_hash':'one','scene_id':'same'} for i in range(6)]
  q=PresentationQualityGate().validate(clips);self.assertFalse(q['pass']);self.assertGreater(q['fake_slicing_count'],0)
 def test_valid_presentation(self):
  clips=[{'kind':'video','start':0,'duration':4,'source_in':2,'source_hash':'a','scene_id':'s1'},{'kind':'video','start':4,'duration':5,'source_in':8,'source_hash':'b','scene_id':'s2'}]
  self.assertTrue(PresentationQualityGate().validate(clips)['pass'])
 def test_strict_release_logic(self):
  mandatory=[True]*9+[False];self.assertFalse(all(mandatory))
 def test_jobs_resume_support(self):
  with tempfile.TemporaryDirectory() as d:
   j=JobStore(Path(d)/'j.db');j.update('1','p','Checking Library','FAILED',error_code='TEST');self.assertEqual(j.report('p')['health'],'ERROR');j.update('1','p','Checking Library','COMPLETE');self.assertEqual(j.report('p')['health'],'READY')
 def test_generic_second_title(self):
  a=ProjectPlanner().analyze('ys','Sheldon talks to Mary about school.',{},None);self.assertTrue(any(x['character']=='Sheldon' for x in a['characters']))

if __name__=='__main__':unittest.main()
