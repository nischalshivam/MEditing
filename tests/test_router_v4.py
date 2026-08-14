import unittest
from scenebrain.router_v4 import token_f1,windows,canonical_text,decision,search_windows,query_parts
import sqlite3,tempfile
from pathlib import Path
class RouterV4Tests(unittest.TestCase):
 def test_alignment_similarity(self):self.assertGreater(token_f1('tread lightly now','now tread lightly'),.9)
 def test_wrong_unique_text_fails(self):self.assertEqual(token_f1('alpha beta','totally different'),0)
 def test_overlapping_windows(self):
  c=[{'start_ms':i*1000,'end_ms':i*1000+900,'text':str(i)} for i in range(20)];w=windows(c,8,4);self.assertLess(w[1]['first_cue_id'],w[0]['last_cue_id'])
 def test_evidence_window_terms(self):
  evidence='you should tread lightly';terms=['tread','lightly'];self.assertTrue(all(x in evidence for x in terms))
 def test_ww_normalization(self):self.assertEqual(canonical_text('W.W. and W W'),'ww_initials and ww_initials')
 def test_borderline_resolves(self):
  s=[{'token_f1':x} for x in [.5,.6,.7,.8,.2]];self.assertEqual(decision(s)[0],'AUDIO_TEXT_VERIFIED')
 def test_failed_resolves(self):
  s=[{'token_f1':x} for x in [.1,.2,.3,.8,.1]];self.assertEqual(decision(s)[0],'AUDIO_TEXT_FAILED')
 def test_visual_decomposition(self):
  p=query_parts({'description':'Walt finds a book and smiles','search_aliases':['Leaves of Grass']});self.assertIn('finds',p['visual_only_facts'])
 def test_search_never_claims_absent_term(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'w.db';c=sqlite3.connect(p);c.executescript('CREATE TABLE windows(window_id TEXT,title_id TEXT,source_id TEXT,season INT,episode INT,start_ms INT,end_ms INT,first_cue_id INT,last_cue_id INT,original_text TEXT,normalized_text TEXT,transcript_hash TEXT);CREATE VIRTUAL TABLE window_fts USING fts5(window_id UNINDEXED,normalized_text);');c.execute("insert into windows values('w','t','s',1,1,0,1,0,1,'Walt speaks','walt speaks','h')");c.commit();c.close();r=search_windows(p,'Walt Whitman');self.assertEqual(r[0]['matched_terms'],['walt'])
