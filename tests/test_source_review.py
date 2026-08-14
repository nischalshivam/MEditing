import json,tempfile,unittest
from pathlib import Path
from scenebrain.source_review import atomic
from scenebrain.router_v4 import search_windows

class SourceReviewTests(unittest.TestCase):
 def test_atomic_persistence(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'a.json';atomic(p,{'approvals':[1]});self.assertEqual(json.loads(p.read_text())['approvals'],[1]);self.assertFalse(p.with_suffix('.building.json').exists())
 def test_window_evidence_seek_fields(self):
  p=Path(r'E:\Movies\.scene_brain\libraries\breaking_bad_dialogue_windows_v4_0.db')
  if p.exists():
   x=search_windows(p,'tread lightly',1)[0];self.assertLess(x['start_ms'],x['end_ms']);self.assertIn('tread',x['normalized_text'])
 def test_all_episode_picker_source_count(self):
  import sqlite3
  p=Path(r'E:\Movies\.scene_brain\catalog.db')
  if p.exists():
   c=sqlite3.connect(p);self.assertEqual(c.execute("select count(*) from sources s join titles t on t.title_id=s.title_id where t.display_name='Breaking Bad'").fetchone()[0],62);c.close()
