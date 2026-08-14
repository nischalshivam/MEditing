import json, tempfile, unittest
from pathlib import Path

from scenebrain.config import Settings
from scenebrain.db import connect
from scenebrain.hierarchical_search_v8 import CONFIG, VERSION, build_scene_index


class HierarchicalV8Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root=Path(__file__).resolve().parents[1]
        cls.conn=connect(cls.root/'runtime/scene_brain.db')

    def test_complete_overlap_coverage(self):
        rows=build_scene_index(self.conn,'S04E01_SC011')
        scene=self.conn.execute("select * from scenes where scene_uid='S04E01_SC011'").fetchone()
        self.assertEqual(rows[0]['start_ms'],scene['start_ms'])
        self.assertEqual(rows[-1]['end_ms'],scene['end_ms'])
        self.assertTrue(all(a['end_ms']>=b['start_ms'] for a,b in zip(rows,rows[1:])))

    def test_windows_are_source_bound_and_shot_bound(self):
        rows=build_scene_index(self.conn,'S04E01_SC011')
        scene=self.conn.execute("select * from scenes where scene_uid='S04E01_SC011'").fetchone()
        for row in rows:
            self.assertGreaterEqual(row['start_ms'],scene['start_ms'])
            self.assertLessEqual(row['end_ms'],scene['end_ms'])
            self.assertTrue(json.loads(row['shot_ids_json']))

    def test_cache_replay_is_deterministic(self):
        first=[dict(x) for x in build_scene_index(self.conn,'S04E01_SC011')]
        second=[dict(x) for x in build_scene_index(self.conn,'S04E01_SC011')]
        self.assertEqual(first,second)
        self.assertEqual(len({x['micro_window_uid'] for x in first}),len(first))

    def test_version_and_overlap_are_explicit(self):
        self.assertEqual(VERSION,'hierarchical-intra-scene/8.0')
        self.assertGreater(CONFIG['overlap_ms'],0)
        self.assertLess(CONFIG['overlap_ms'],CONFIG['coarse_ms'])

    def test_source_media_unchanged_by_index_replay(self):
        before=self.conn.execute('select sha256,bytes,mtime_ns from source_files where id=1').fetchone()
        build_scene_index(self.conn,'S04E01_SC011')
        after=self.conn.execute('select sha256,bytes,mtime_ns from source_files where id=1').fetchone()
        self.assertEqual(tuple(before),tuple(after))


if __name__=='__main__': unittest.main()
