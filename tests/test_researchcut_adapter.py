import tempfile,unittest
from pathlib import Path
from scenebrain.researchcut_adapter import adapt_scene_brain_project,write_atomic

class AdapterTests(unittest.TestCase):
 def test_project_independent_mapping(self):
  p=adapt_scene_brain_project({'project_id':'fixture_project','name':'Fixture','voiceover_path':'C:/x.wav','voiceover_duration_ms':5000,'timeline':[{'presentation_slot_id':'S1','beat_id':'B1','timeline_start_ms':0,'timeline_end_ms':5000,'approval_state':'NEEDS_CHOICE','presentation_type':'VIDEO','candidates':[{'source_path':'C:/v.mp4','source_in_ms':1000,'source_out_ms':6000}]}]})
  self.assertEqual(p['id'],'fixture_project');self.assertEqual(len(p['clips']),2);self.assertEqual(p['clips'][0]['sourceIn'],1);self.assertEqual(p['clips'][0]['sceneBrain']['status'],'NEEDS_CHOICE')
  with tempfile.TemporaryDirectory() as d:
   out=Path(d)/'project.json';write_atomic(p,out);self.assertTrue(out.exists())

if __name__=='__main__': unittest.main()
