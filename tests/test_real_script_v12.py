import json,tempfile,unittest
from pathlib import Path
from scenebrain.real_script_v12 import words,episode_hints
class V12Tests(unittest.TestCase):
 def test_episode_hints(self):self.assertEqual(episode_hints({'episode_hints':['S04E11 — Crawl Space']}),['S04E11'])
 def test_words(self):self.assertIn('money',words('Skyler sees the money'))
 def test_no_timestamp_guess_api(self):
  import inspect,scenebrain.real_script_v12 as m
  self.assertNotIn('Gemini',inspect.getsource(m.build))
