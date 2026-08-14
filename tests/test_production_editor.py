import hashlib,json,unittest
from pathlib import Path
from scenebrain.production_editor import find_volume,import_skyler,library,projects,duplicate_project,edit
ROOT=Path(__file__).resolve().parents[1]
class ProductionEditorTests(unittest.TestCase):
 def test_volume_and_library(self):
  m=find_volume();self.assertIsNotNone(m);self.assertEqual(len(library(m)),6)
 def test_skyler_copy(self):
  p=import_skyler(find_volume());self.assertEqual((p['locked_source_count'],len(p['timeline']),p['manual_fix_count']),(57,145,2));self.assertEqual(sum(x['approval_state']=='MANUAL_FIX' for x in p['timeline']),2)
 def test_canonical_persistence(self):self.assertTrue((find_volume()/'.scene_brain/projects/skyler_money_production_copy/EDITOR_PROJECT.json').exists())
 def test_retrieval_frozen(self):self.assertEqual(hashlib.sha256((ROOT/'runtime/final_project/FINAL_LOCKED_VISUAL_PLAN.json').read_bytes()).hexdigest(),'08428494d51f7d6f9e75208dd6e2c8ca2007e2641d28ee4d975008392dc1d4e5')
 def test_export_configs_present(self):
  h=(ROOT/'runtime/production_editor/PRODUCTION_EDITOR.html').read_text();self.assertIn('1440p',h);self.assertIn('2160p / 4K',h);self.assertIn('FINAL PROJECT CHECK',h)
 def test_ui_core_controls(self):
  h=(ROOT/'runtime/production_editor/PRODUCTION_EDITOR.html').read_text();
  for x in ['LIBRARY','PROJECTS','NEW PROJECT','EDITOR','UNDO','REDO','SPLIT','VIDEO / IMAGE']:self.assertIn(x,h)
 def test_health_and_real_bootstrap_contract(self):
  h=(ROOT/'runtime/production_editor/PRODUCTION_EDITOR.html').read_text();self.assertIn("'/api/health'",h);self.assertIn('CONNECTION ERROR',h);self.assertIn('hashchange',h)
 def test_launcher_health_polling(self):
  p=(ROOT/'START_SCENE_BRAIN.ps1').read_text();self.assertIn('/api/health',p);self.assertIn('Backend did not become healthy',p)
 def test_duplicate_save_reload(self):
  m=find_volume();p=duplicate_project(m,'skyler_money_production_copy');n=len(p['timeline']);s=p['timeline'][0];p=edit(m,p['project_id'],{'action':'SPLIT','slot_id':s['presentation_slot_id'],'at_ms':(s['timeline_start_ms']+s['timeline_end_ms'])//2});self.assertEqual(len(p['timeline']),n+1);saved=json.loads((m/'.scene_brain/projects'/p['project_id']/'EDITOR_PROJECT.json').read_text());self.assertEqual(len(saved['timeline']),n+1)
 def test_v2_employee_controls(self):
  h=(ROOT/'runtime/production_editor/PRODUCTION_EDITOR.html').read_text()
  for token in ['type="file"','AUTO GENERATE CLUE SCRIPT','CUSTOM MULTI-TITLE','Sheldon Universe','RIPPLE ON','handle r','RESOLVE_UPLOAD','REVIEW ISSUES','A1 VOICEOVER']:self.assertIn(token,h)
 def test_v2_ripple_duration(self):
  m=find_volume();p=duplicate_project(m,'skyler_money_production_copy');x=p['timeline'][0];next_start=p['timeline'][1]['timeline_start_ms'];p=edit(m,p['project_id'],{'action':'DURATION','slot_id':x['presentation_slot_id'],'end_ms':x['timeline_end_ms']+500});self.assertEqual(p['timeline'][1]['timeline_start_ms'],next_start+500)
