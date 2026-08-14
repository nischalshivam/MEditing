import tempfile, unittest
from pathlib import Path

from scenebrain.confidence_visual_planner import *


def option(cid="A", a=1000, b=4000):
    return VisualOption(candidate_id=cid,title="Breaking Bad",season=4,episode=1,scene_id="S04E01_SC001",
                        source_start_ms=a,source_end_ms=b,shot_ids=["S0001"],preview_path="x.mp4",
                        source_path="source.mp4",source_sha256="a"*64)


class PlannerTests(unittest.TestCase):
    def test_green_needs_permitted_proof(self):
        beat=NarrationBeat(beat_id="b",narration="x",evidence_class="EXACT_EVENT")
        color,proof,_=route_color(beat,[option()])
        self.assertNotEqual(color,Color.GREEN);self.assertIsNone(proof)
        color,proof,_=route_color(beat,[option()],memory={"approval_type":"EXACT_EVENT_APPROVAL"})
        self.assertEqual((color,proof),(Color.GREEN,"GREEN_VERIFIED_EVENT_MEMORY"))

    def test_exact_dialogue_green(self):
        beat=NarrationBeat(beat_id="b",narration="Well?",evidence_class="EXACT_DIALOGUE")
        self.assertEqual(route_color(beat,[option()],exact_dialogue_proof=True)[0],Color.GREEN)

    def test_yellow_max_and_min(self):
        beat=NarrationBeat(beat_id="b",narration="x",evidence_class="EXACT_EVENT")
        with self.assertRaises(ValueError): PlannedBeat(beat=beat,color=Color.YELLOW,chosen_visual=option(),reason="x",review_required=True)
        with self.assertRaises(ValueError): PlannedBeat(beat=beat,color=Color.YELLOW,chosen_visual=option(),alternatives=[option(str(x),x*5000,x*5000+1000) for x in range(5)],reason="x",review_required=True)

    def test_overlap_dedup(self):
        xs=[option("a",0,3000),option("b",100,3100),option("c",5000,8000)]
        self.assertEqual([x.candidate_id for x in diverse(xs)], ["a","c"])

    def test_multiscale_source_bounds(self):
        shots=[{"ordinal":1,"start_ms":0,"end_ms":2000},{"ordinal":2,"start_ms":2000,"end_ms":5000},{"ordinal":3,"start_ms":5000,"end_ms":7000}]
        rows=multiscale_ranges({"start_ms":2100,"end_ms":4000,"start_shot":"S0002","end_shot":"S0002","shot_ids":["S0002"]},shots,7000)
        self.assertTrue(all(0<=a<b<=7000 for a,b,_,_ in rows));self.assertGreaterEqual(len(rows),3)

    def test_orange_unresolved(self):
        beat=NarrationBeat(beat_id="b",narration="unknown",evidence_class="CHARACTER_CONTEXT")
        self.assertEqual(route_color(beat,[])[0],Color.ORANGE_UNRESOLVED)

    def test_approval_types_are_distinct(self):
        beat=NarrationBeat(beat_id="b",narration="x",evidence_class="EXACT_EVENT")
        self.assertNotEqual(route_color(beat,[option()],memory={"approval_type":"CONTEXTUAL_VISUAL_APPROVAL"})[0],Color.GREEN)

    def test_plan_schema(self):
        beat=NarrationBeat(beat_id="b",narration="x",evidence_class="EXACT_EVENT")
        p=PlannedBeat(beat=beat,color=Color.YELLOW,chosen_visual=option(),alternatives=[option("b",5000,8000)],reason="x",review_required=True)
        plan=VisualPlan(project_id="p",script_hash="a",library_scope=[],beats=[p],source_receipt={},plan_fingerprint="f")
        self.assertEqual(plan.schema_version,"visual-plan/1.0")
