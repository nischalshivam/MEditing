import json,sqlite3,tempfile,unittest
from pathlib import Path
from scenebrain.production_preflight import search_title_dialogue,preflight_project,validate_transcript,enqueue_rich,promote_rich_atomic
ROOT=Path(__file__).resolve().parents[1];MEDIA=Path(r'E:\Movies');CAT=MEDIA/'.scene_brain/catalog.db';SCRIPT=next((Path.home()/'Downloads').glob('Skyler Saw Walt*Did.txt'))
class ProductionPreflightTests(unittest.TestCase):
 def test_legacy_truth(self):
  r=json.loads((MEDIA/'.scene_brain/receipts/LEGACY_INDEX_MIGRATION_RECEIPT.json').read_text());self.assertEqual([x['index_type'] for x in r['items']].count('FULL_RICH_ATLAS'),1);self.assertEqual([x['index_type'] for x in r['items']].count('PARTIAL_INDEX'),4)
 def test_title_search(self):self.assertTrue(search_title_dialogue(CAT,'Breaking Bad',['money'],3));self.assertTrue(search_title_dialogue(CAT,'Young Sheldon',['school'],3))
 def test_zero_searchable_blocks(self):self.assertFalse(preflight_project(CAT,'unit_tbbt',SCRIPT,['The Big Bang Theory'])['ready_for_retrieval'])
 def test_partial_searchable_not_whole_bootstrap(self):
  p=preflight_project(CAT,'unit_ys',SCRIPT,['Young Sheldon']);self.assertFalse(p['ready_for_retrieval']);self.assertEqual(p['searchability_bootstrap'],[]);self.assertEqual(p['ambiguous_sources'][0]['partial_searchability_gaps'],2)
 def test_model_hint_not_authority(self):self.assertEqual(preflight_project(CAT,'unit_hint',SCRIPT,['Breaking Bad'])['ambiguous_sources'][0]['state'],'UNRESOLVED')
 def test_asr_health(self):self.assertTrue(validate_transcript([{'token':'one','start_ms':0,'end_ms':10},{'token':'two','start_ms':10,'end_ms':20},{'token':'three','start_ms':20,'end_ms':30},{'token':'four','start_ms':30,'end_ms':40},{'token':'five','start_ms':40,'end_ms':50}],100)['healthy']);self.assertFalse(validate_transcript([],100)['healthy'])
 def test_old_project_immutable(self):self.assertEqual(json.loads((ROOT/'runtime/final_project/FINAL_PROJECT_STATE.json').read_text())['retrieval_status'],'RETRIEVAL_R_AND_D_FROZEN')
