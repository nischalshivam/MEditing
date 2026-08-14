from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from .atlas import validate_response
from .atlas_models import WindowResponse
from .hashing import fingerprint, sha256_file

PROMPT_VERSION="scene-atlas-prompt/1.0"
SCHEMA_VERSION="scene-atlas-schema/1.0"


class VisionProvider(ABC):
    @abstractmethod
    def analyze_scene_window(self, package: dict, contact_sheet: Path) -> tuple[dict,dict]: ...


def credential_detected() -> bool: return bool(os.environ.get("GEMINI_API_KEY"))


def validate_cache_envelope(envelope: dict, fp: str) -> dict:
    raw=envelope["response"]
    if envelope.get("input_fingerprint")!=fp or envelope.get("seal")!=fingerprint(json.dumps(raw,sort_keys=True,separators=(",",":")),fp):
        raise ValueError("tampered cached output")
    return raw


def _prompt(package: dict, repair_reason: str | None=None) -> str:
    shots=", ".join(x["shot_id"] for x in package["shots"])
    dialogue="\n".join(f"{c['cue_index']}: {c['raw_text']}" for c in package["dialogue"]) or "(no dialogue)"
    repair=f"\nPrior response failed validation: {repair_reason}. Return a fresh valid object.\n" if repair_reason else ""
    return f"""You create an objective narrative Scene Atlas from LOCAL evidence only.
Title: Breaking Bad. Season 4 Episode 1. Window: {package['window_id']}.
Authoritative ordered physical shot IDs: {shots}
The attached contact sheet labels every tile with its physical shot ID.
Verified local dialogue overlapping this window:\n{dialogue}

Group consecutive physical shots into coherent narrative scenes, not camera takes. A scene can contain many shots.
Never output timestamps. Never invent shot IDs, dialogue, characters, locations, actions, objects, or psychology.
Every semantic claim must cite evidence_shots inside that scene. Use UNKNOWN_CHARACTER, UNKNOWN_LOCATION, or UNKNOWN_EVENT when evidence is insufficient.
If a scene continues beyond this window, use UNKNOWN_START/UNKNOWN_END/UNKNOWN_BOTH. Mark needs_temporal_preview true only when motion ambiguity prevents reliable grouping or event description.
Allowed scene types: normal, montage, transition, recap, flashback, dream, cold_open, other.
Do not describe anything outside supplied evidence.{repair}"""


class GeminiProvider(VisionProvider):
    def __init__(self, model: str):
        if not credential_detected(): raise RuntimeError("Gemini credential unavailable")
        from google import genai
        self.model=model; self.client=genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    def analyze_scene_window(self, package: dict, contact_sheet: Path, repair_reason: str | None=None) -> tuple[dict,dict]:
        from google.genai import types
        part=types.Part.from_bytes(data=contact_sheet.read_bytes(),mime_type="image/jpeg")
        response=self.client.models.generate_content(model=self.model,contents=[_prompt(package,repair_reason),part],config=types.GenerateContentConfig(
          temperature=0.1,top_p=0.8,max_output_tokens=8192,response_mime_type="application/json",response_json_schema=WindowResponse.model_json_schema()))
        raw=json.loads(response.text)
        usage=response.usage_metadata
        meta={"input_tokens":getattr(usage,"prompt_token_count",None),"output_tokens":getattr(usage,"candidates_token_count",None),
          "total_tokens":getattr(usage,"total_token_count",None)}
        return raw,meta


def run_window(conn, provider: VisionProvider, package: dict, root: Path, model: str, max_cost_usd: float=2.0) -> dict:
    fp=fingerprint(package["input_fingerprint"],"gemini",model,PROMPT_VERSION,SCHEMA_VERSION,"temperature=.1,top_p=.8")
    cache=root/"runtime"/"scene_atlas"/"cache"/f"{fp}.json"; cache.parent.mkdir(parents=True,exist_ok=True)
    window=conn.execute("SELECT id FROM scene_analysis_windows WHERE window_id=?",(package["window_id"],)).fetchone()
    if cache.is_file():
        envelope=json.loads(cache.read_text(encoding="utf-8")); raw=validate_cache_envelope(envelope,fp)
        parsed=validate_response(package,raw)
        return {"window_id":package["window_id"],"cache_hit":True,"response":parsed.model_dump(),"usage":envelope["usage"],"input_fingerprint":fp}
    spent=conn.execute("SELECT COALESCE(SUM(estimated_cost_usd),0) FROM scene_analysis_runs WHERE status='SUCCESS'").fetchone()[0]
    if spent>=max_cost_usd: raise RuntimeError("configured Gemini cost ceiling reached")
    run_id=None
    with conn:
        prior=conn.execute("SELECT COUNT(*) FROM scene_analysis_runs WHERE input_fingerprint=? OR input_fingerprint LIKE ?",(fp,fp+":retry%" )).fetchone()[0]
        attempt_fp=fp if prior==0 else f"{fp}:retry{prior}"
        cur=conn.execute("INSERT INTO scene_analysis_runs(window_id,provider,model,prompt_version,schema_version,input_fingerprint,cache_hit,status) VALUES(?,?,?,?,?,?,0,'RUNNING')",
          (window["id"],"google-gemini",model,PROMPT_VERSION,SCHEMA_VERSION,attempt_fp)); run_id=cur.lastrowid
    last_error=None
    for attempt in range(2):
        try:
            raw,usage=provider.analyze_scene_window(package,Path(package["contact_sheet"]["path"]),last_error)
            parsed=validate_response(package,raw); output=parsed.model_dump(); outfp=fingerprint(json.dumps(output,sort_keys=True,separators=(",",":")))
            inp=usage.get("input_tokens") or 0; out=usage.get("output_tokens") or 0; cost=inp/1_000_000*.10+out/1_000_000*.40
            envelope={"input_fingerprint":fp,"response":output,"usage":usage,"estimated_cost_usd":cost}; envelope["seal"]=fingerprint(json.dumps(output,sort_keys=True,separators=(",",":")),fp)
            tmp=cache.with_suffix(".building"); tmp.write_text(json.dumps(envelope,indent=2),encoding="utf-8"); tmp.replace(cache)
            with conn:
                conn.execute("UPDATE scene_analysis_runs SET output_fingerprint=?,status='SUCCESS',input_tokens=?,output_tokens=?,total_tokens=?,estimated_cost_usd=?,finished_at=CURRENT_TIMESTAMP WHERE id=?",
                  (outfp,usage.get("input_tokens"),usage.get("output_tokens"),usage.get("total_tokens"),cost,run_id))
                for i,scene in enumerate(output["scenes"]):
                    ids={shot["shot_id"]:shot["db_id"] for shot in package["shots"]}
                    conn.execute("INSERT INTO scene_window_proposals(run_id,proposal_index,start_shot_id,end_shot_id,boundary_status,scene_type,visual_summary,raw_json) VALUES(?,?,?,?,?,?,?,?)",
                      (run_id,i,ids[scene["start_shot"]],ids[scene["end_shot"]],scene["boundary_status"],scene["scene_type"],scene["visual_summary"],json.dumps(scene)))
            return {"window_id":package["window_id"],"cache_hit":False,"response":output,"usage":usage,"estimated_cost_usd":cost,"input_fingerprint":fp}
        except ValueError as exc: last_error=str(exc)[:300]
        except Exception as exc:
            with conn: conn.execute("UPDATE scene_analysis_runs SET status='ERROR',sanitized_error=?,finished_at=CURRENT_TIMESTAMP WHERE id=?",(type(exc).__name__,run_id))
            raise RuntimeError(f"Gemini call failed: {type(exc).__name__}") from None
    with conn: conn.execute("UPDATE scene_analysis_runs SET status='UNRESOLVED',sanitized_error=?,finished_at=CURRENT_TIMESTAMP WHERE id=?",(last_error,run_id))
    return {"window_id":package["window_id"],"cache_hit":False,"status":"UNRESOLVED","sanitized_error":last_error}
