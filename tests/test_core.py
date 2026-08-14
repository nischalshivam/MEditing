from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scenebrain.benchmark import freeze, validate_questions
from scenebrain.db import connect
from scenebrain.hashing import fingerprint, sha256_file
from scenebrain.media import infer_episode
from scenebrain.shots import detection_fingerprint, representative_time
from scenebrain.subtitles import normalize, parse_srt, search_multi_cue


SRT = """1
00:00:01,000 --> 00:00:02,000
How's it

2
00:00:02,100 --> 00:00:03,000
coming?

3
00:00:07,500 --> 00:00:08,000
No.
"""


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self): self.tmp.cleanup()

    def test_migrations_and_fts(self):
        conn = connect(self.root / "x.db")
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
        self.assertTrue({"titles","source_files","subtitle_tracks","subtitle_cues","subtitle_cues_fts","shots","keyframes"} <= tables)
        self.assertEqual(conn.execute("SELECT version FROM schema_migrations").fetchone()[0], 1)
        conn.close()

    def test_normalize(self): self.assertEqual(normalize("<i>Hello</i>   WORLD &amp; all ♪"), "hello world & all")

    def test_parse_srt(self):
        p=self.root/"x.srt"; p.write_text(SRT, encoding="utf-8")
        cues=parse_srt(p); self.assertEqual(len(cues),3); self.assertEqual(cues[1].start_ms,2100)

    def test_parse_rejects_bad_duration(self):
        p=self.root/"x.srt"; p.write_text("1\n00:00:02,000 --> 00:00:01,000\nbad\n", encoding="utf-8")
        with self.assertRaises(ValueError): parse_srt(p)

    def test_episode_identity(self):
        self.assertEqual(infer_episode(Path("Breaking Bad Season 4 Episode 1.mp4")), (4,1))
        self.assertEqual(infer_episode(Path("S04E01.mkv")), (4,1))

    def test_multicue_search_and_word_boundary(self):
        conn=connect(self.root/"x.db")
        with conn:
            conn.execute("INSERT INTO titles(canonical_name,kind) VALUES('X','SERIES')")
            conn.execute("INSERT INTO source_files(title_id,path,bytes,mtime_ns,sha256,duration_ms,probe_json) VALUES(1,'x',1,1,'a',9000,'{}')")
            conn.execute("""INSERT INTO subtitle_tracks(source_file_id,path,origin,bytes,sha256,cue_count,parse_status,identity_status,sync_status,selection_score,selection_evidence_json,selected)
              VALUES(1,'x.srt','SIDECAR',1,'b',3,'PASS','MATCH','VERIFIED',100,'{}',1)""")
            conn.executemany("INSERT INTO subtitle_cues(track_id,cue_index,start_ms,end_ms,raw_text,normalized_text) VALUES(1,?,?,?,?,?)",
                [(1,1000,2000,"How's it","how's it"),(2,2100,3000,"coming?","coming"),(3,7500,8000,"know","know")])
        hits=search_multi_cue(conn,"how's it coming")
        self.assertEqual((hits[0]["start_cue"],hits[0]["end_cue"]),(1,2))
        self.assertEqual(search_multi_cue(conn,"no"),[])
        conn.close()

    def test_representative_time_stays_inside(self):
        self.assertTrue(1000 < representative_time(1000,2000) < 2000)

    def test_fingerprint_changes(self): self.assertNotEqual(fingerprint('a',1),fingerprint('a',2))

    def test_detector_settings_invalidate(self):
        self.assertNotEqual(detection_fingerprint("sha",0.15),detection_fingerprint("sha",0.25))

    def test_source_hash_changes_on_content_change(self):
        p=self.root/"source.bin"; p.write_bytes(b"first")
        before=sha256_file(p); p.write_bytes(b"second")
        self.assertNotEqual(before,sha256_file(p))

    def test_fts_index_receives_inserted_cue(self):
        conn=connect(self.root/"fts.db")
        with conn:
            conn.execute("INSERT INTO titles(canonical_name,kind) VALUES('X','FILM')")
            conn.execute("INSERT INTO source_files(title_id,path,bytes,mtime_ns,sha256,duration_ms,probe_json) VALUES(1,'x',1,1,'a',9,'{}')")
            conn.execute("""INSERT INTO subtitle_tracks(source_file_id,path,origin,bytes,sha256,cue_count,parse_status,identity_status,sync_status,selection_score,selection_evidence_json)
              VALUES(1,'x.srt','SIDECAR',1,'b',1,'PASS','MATCH','VERIFIED',1,'{}')""")
            conn.execute("INSERT INTO subtitle_cues(track_id,cue_index,start_ms,end_ms,raw_text,normalized_text) VALUES(1,1,0,1,'Blue meth','blue meth')")
        self.assertEqual(conn.execute("SELECT count(*) FROM subtitle_cues_fts WHERE subtitle_cues_fts MATCH 'blue' ").fetchone()[0],1)
        conn.close()

    def test_benchmark_freeze(self):
        p=self.root/"q.jsonl"
        rows=[{"question_id":f"q{i:02}","query":"x","category":"dialogue","source_id":1,"episode":"S04E01","label_status":"HUMAN_VERIFIED","ground_truth":{}} for i in range(30)]
        p.write_text("\n".join(json.dumps(x) for x in rows)+"\n",encoding="utf-8")
        receipt=freeze(p,"a"*64); self.assertEqual(receipt["question_count"],30); self.assertFalse(receipt["accuracy_claim_allowed"])


if __name__ == "__main__": unittest.main()
