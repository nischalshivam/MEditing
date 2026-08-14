import json
import unittest
from pathlib import Path

from scenebrain.ship_v1 import EVENTS, EXPECTED


MEDIA = Path(r"E:\Movies")
ROOT = Path(__file__).resolve().parents[1]


class ShipV1Tests(unittest.TestCase):
    def test_admin_event_map_has_expected_physical_episode_set(self):
        self.assertEqual(len(EVENTS), 15); self.assertEqual(set(EVENTS.values()), EXPECTED)

    def test_frozen_requirement_map_is_catalog_resolved(self):
        data=json.loads((ROOT/"FINAL_PROJECT_EPISODE_REQUIREMENT_MAP.json").read_text())
        self.assertEqual(data["authority"],"ADMIN_SOURCE_CORRECTION"); self.assertEqual(data["required_unique_episodes"],8)
        self.assertEqual({x["episode"] for x in data["episodes"]},EXPECTED); self.assertTrue(all(x["source_id"].startswith("src_") for x in data["episodes"]))

    def test_all_required_atlases_are_validated_and_source_bound(self):
        requirement=json.loads((ROOT/"FINAL_PROJECT_EPISODE_REQUIREMENT_MAP.json").read_text())
        for item in requirement["episodes"]:
            value=json.loads((MEDIA/".scene_brain/libraries"/item["source_id"]/"rich_atlas_v1/RICH_ATLAS_RECEIPT.json").read_text())
            self.assertEqual(value["status"],"VALIDATED"); self.assertTrue(all(value["checks"].values()))

    def test_walter_plan_is_complete_and_fail_closed(self):
        plan=json.loads((MEDIA/".scene_brain/projects/walter_book_project/VISUAL_PLAN.json").read_text())
        self.assertEqual(len(plan["slots"]),70); self.assertTrue(all(x["state"] in {"NEEDS_CHOICE","MANUAL_REQUIRED"} for x in plan["slots"])); self.assertTrue(all(len(x["candidates"])<=3 for x in plan["slots"])); self.assertTrue(all(not x["candidates"] or all(c["episode"]==x["approved_episode"] for c in x["candidates"]) for x in plan["slots"] if x["evidence_class"] in {"EXACT_EVENT","EXACT_DIALOGUE"}))

    def test_editor_project_exposes_all_slots_with_aligned_voiceover(self):
        value=json.loads((MEDIA/".scene_brain/projects/walter_book_project/EDITOR_PROJECT.json").read_text())
        self.assertEqual(len(value["timeline"]),70); self.assertTrue(Path(value["voiceover_path"]).is_file()); self.assertEqual(value["timing_status"],"FINAL_VOICEOVER_ALIGNED"); self.assertEqual(value["timeline"][-1]["timeline_end_ms"],878100)

    def test_review_ui_wiring(self):
        html=(ROOT/"runtime/production_editor/PRODUCTION_EDITOR.html").read_text()
        for token in ["CURRENT BEAT OPTIONS","previewCandidate","APPROVE_CANDIDATE","Needs Choice:","Manual clip required"]:self.assertIn(token,html)
