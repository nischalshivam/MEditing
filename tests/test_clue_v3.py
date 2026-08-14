import json,tempfile,unittest
from pathlib import Path
from scenebrain.clue_v3 import validate
class ClueV3Tests(unittest.TestCase):
 def fixture(self):
  d=Path(tempfile.mkdtemp());s=d/'s.txt';c=d/'c.json';s.write_text('One two. Three four.');base={'schema_version':'production-clue-script/3.0','canonical_event_registry':[{'canonical_event_id':'E1'}],'beats':[{'beat_id':'B1','exact_narration':'One two.','evidence_class':'EXACT_EVENT','canonical_event_id':'E1','context_anchor_event_ids':[],'source_title_hints':[{'title':'Breaking Bad'}],'recommended_visual_slots':[{'slot_number':1,'preferred_media':'VIDEO'}]},{'beat_id':'B2','exact_narration':'Three four.','evidence_class':'EDITORIAL_CONTEXT','context_anchor_event_ids':['E1'],'source_title_hints':[{'title':'Breaking Bad'}],'recommended_visual_slots':[{'slot_number':1,'preferred_media':'IMAGE'}]}]};c.write_text(json.dumps(base));return s,c,base
 def test_valid_complete(self):s,c,_=self.fixture();self.assertFalse(validate(s,c,['Breaking Bad'])[1])
 def test_duplicate_narration_rejected(self):s,c,x=self.fixture();x['beats'][1]['exact_narration']='One two.';c.write_text(json.dumps(x));self.assertTrue(validate(s,c,['Breaking Bad'])[1])
 def test_missing_coverage_rejected(self):s,c,x=self.fixture();x['beats'].pop();c.write_text(json.dumps(x));self.assertTrue(validate(s,c,['Breaking Bad'])[1])
 def test_event_reference_rejected(self):s,c,x=self.fixture();x['beats'][0]['canonical_event_id']='NO';c.write_text(json.dumps(x));self.assertTrue(validate(s,c,['Breaking Bad'])[1])
 def test_scope_rejected(self):s,c,x=self.fixture();x['beats'][0]['source_title_hints'][0]['title']='Other';c.write_text(json.dumps(x));self.assertTrue(validate(s,c,['Breaking Bad'])[1])
 def test_provider_agnostic(self):s,c,x=self.fixture();x['provider_name']='anything';c.write_text(json.dumps(x));self.assertFalse(validate(s,c,['Breaking Bad'])[1])
