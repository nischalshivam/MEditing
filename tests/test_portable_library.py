import json,sqlite3,tempfile,unittest
from pathlib import Path
from scenebrain.portable_library import episode,preflight,resolve_volume
ROOT=Path(__file__).resolve().parents[1];MEDIA=Path(r'E:\Movies');CAT=MEDIA/'.scene_brain/catalog.db'
class PortableLibraryTests(unittest.TestCase):
 def test_episode_and_combined(self):self.assertEqual(episode('Show.S02E03-E04.mkv'),(2,3,4))
 def test_volume_identity_and_portability(self):
  m=MEDIA/'.scene_brain/volume_manifest.json';x=json.loads(m.read_text());self.assertNotEqual(x['scene_brain_volume_id'],'E:');self.assertEqual(resolve_volume(m,[ROOT/'runtime/library_foundation/portable_sim']),ROOT/'runtime/library_foundation/portable_sim')
 def test_catalog_counts_and_states(self):
    c=sqlite3.connect(CAT);self.assertEqual(c.execute('select count(*) from sources where present=1').fetchone()[0],619);self.assertEqual(c.execute("select count(*) from sources where maturity='RICH_ATLAS_READY'").fetchone()[0],9);self.assertGreater(c.execute('select count(*) from subtitle_fts').fetchone()[0],0)
 def test_preflight_fail_closed(self):
  p=preflight(CAT,[{'title':'The Big Bang Theory','season':1,'episode':1,'requires_rich':True}]);self.assertFalse(p['ready_for_retrieval']);self.assertGreaterEqual(p['new_rich_builds_required'],1)
 def test_franchise_separate(self):
  c=sqlite3.connect(CAT);self.assertEqual(c.execute('select count(*) from franchises').fetchone()[0],2);self.assertEqual(c.execute('select count(distinct title_id) from franchise_titles').fetchone()[0],4)
 def test_existing_project_preserved(self):
  r=json.loads((MEDIA/'.scene_brain/receipts/BREAKING_BAD_MIGRATION_RECEIPT.json').read_text());self.assertTrue(r['historical_unchanged']);self.assertEqual(r['locked_decisions'],57)
 def test_receipt_and_dashboard(self):
  self.assertTrue((MEDIA/'.scene_brain/receipts/LIBRARY_SCAN_RECEIPT.json').is_file());self.assertIn('RESCAN MEDIA DRIVE',(ROOT/'runtime/library_foundation/LIBRARY_FOUNDATION.html').read_text())
