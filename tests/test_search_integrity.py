import unittest
from pathlib import Path
from scenebrain.portable_library import episode
from scenebrain.search_integrity import digest
class SearchIntegrityTests(unittest.TestCase):
 def test_season_episode_composite(self):self.assertNotEqual(episode('S01E07')[:2],episode('S05E07')[:2])
 def test_episode_one_not_ten(self):self.assertNotEqual(episode('Season 2 Episode 1')[:2],episode('Season 2 Episode 10')[:2])
 def test_normalized_duplicate_detection(self):self.assertEqual(digest('Hello,  world!'),digest('hello world'))
 def test_failed_index_preserved(self):
  p=Path(__file__).resolve().parents[1]/'runtime/search_integrity_repair/SEARCH_INDEX_REPAIR_RECEIPT.json';self.assertIn('CANDIDATE_REJECTED_NOT_PROMOTED',p.read_text())
