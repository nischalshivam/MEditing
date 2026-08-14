from __future__ import annotations

import copy
import os
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from scenebrain.atlas import validate_response
from scenebrain.hashing import fingerprint
from scenebrain.providers import credential_detected, validate_cache_envelope


def package():
    return {"window_id":"S04E01_W001","shots":[{"shot_id":f"S{i:04d}","db_id":i} for i in range(5)],"dialogue":[],"contact_sheet":{"path":"x","sha256":"a"},"input_fingerprint":"f"}


def response():
    return {"window_id":"S04E01_W001","needs_temporal_preview":False,"preview_reason":"",
      "scenes":[{"start_shot":"S0000","end_shot":"S0004","boundary_status":"SUPPORTED",
      "characters":[{"name":"UNKNOWN_CHARACTER","evidence_shots":[]}],"location":{"name":"UNKNOWN_LOCATION","evidence_shots":[]},
      "main_event":{"description":"UNKNOWN_EVENT","evidence_shots":[]},"visible_actions":[],"important_objects":[],
      "visual_summary":"Uncertain visual event.","scene_type":"normal","uncertainties":[]}]}


class AtlasValidationTests(unittest.TestCase):
    def test_valid_unknowns(self): self.assertEqual(validate_response(package(),response()).scenes[0].boundary_status,"SUPPORTED")
    def test_invented_shot(self):
        r=response();r["scenes"][0]["end_shot"]="S9999"
        with self.assertRaisesRegex(ValueError,"invented"): validate_response(package(),r)
    def test_reversed_boundary(self):
        r=response();r["scenes"][0]["start_shot"]="S0003";r["scenes"][0]["end_shot"]="S0002"
        with self.assertRaisesRegex(ValueError,"reversed"): validate_response(package(),r)
    def test_overlap_rejected(self):
        r=response();r["scenes"][0]["end_shot"]="S0002";second=copy.deepcopy(r["scenes"][0]);second["start_shot"]="S0002";second["end_shot"]="S0004";r["scenes"].append(second)
        with self.assertRaisesRegex(ValueError,"overlapping"): validate_response(package(),r)
    def test_gap_rejected(self):
        r=response();r["scenes"][0]["end_shot"]="S0001"
        with self.assertRaisesRegex(ValueError,"gaps"): validate_response(package(),r)
    def test_evidence_outside_span(self):
        r=response();r["scenes"][0]["end_shot"]="S0002";r["scenes"][0]["characters"]=[{"name":"Walter White","evidence_shots":["S0004"]}]
        with self.assertRaisesRegex(ValueError,"evidence outside"): validate_response(package(),r)
    def test_malformed_extra_field(self):
        r=response();r["absolute_timestamp"]=123
        with self.assertRaises(ValidationError): validate_response(package(),r)
    def test_invalid_enum(self):
        r=response();r["scenes"][0]["scene_type"]="psychological"
        with self.assertRaises(ValidationError): validate_response(package(),r)
    def test_credential_boolean_only(self):
        with patch.dict(os.environ,{"GEMINI_API_KEY":"secret-test-value"}): self.assertTrue(credential_detected())
        with patch.dict(os.environ,{},clear=True): self.assertFalse(credential_detected())
    def test_prompt_or_model_change_invalidates(self):
        self.assertNotEqual(fingerprint("input","prompt-v1","model-a"),fingerprint("input","prompt-v2","model-a"))
        self.assertNotEqual(fingerprint("input","prompt-v1","model-a"),fingerprint("input","prompt-v1","model-b"))
    def test_tampered_cache_rejected(self):
        import json
        raw=response();fp="abc";seal=fingerprint(json.dumps(raw,sort_keys=True,separators=(",",":")),fp)
        self.assertEqual(validate_cache_envelope({"input_fingerprint":fp,"seal":seal,"response":raw},fp),raw)
        raw["window_id"]="tampered"
        with self.assertRaisesRegex(ValueError,"tampered"): validate_cache_envelope({"input_fingerprint":fp,"seal":seal,"response":raw},fp)


if __name__=="__main__": unittest.main()
