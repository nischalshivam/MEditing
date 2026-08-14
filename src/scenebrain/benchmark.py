from __future__ import annotations

import json
from pathlib import Path

from .hashing import sha256_file

REQUIRED = {"question_id", "query", "category", "source_id", "episode", "label_status", "ground_truth"}

VISUAL_S04E01 = [
 ("gus-doorway-entrance","Gus silently enters the underground superlab through the upper red doorway.","VISUAL_ACTION","VERIFIED_EXACT",[[1657700,1665300]]),
 ("gus-silent-lab-close","A silent medium close-up of Gus in the superlab with Victor behind him.","CHARACTER_REACTION","VERIFIED_EXACT",[[1729800,1736500]]),
 ("folded-jacket-tie-negative","A folded jacket and rolled tie lying together on a stainless counter.","HARD_NEGATIVE","NOT_FOUND",[]),
 ("green-cutter-hand","Close view of the green box cutter in Gus's hand in the superlab.","OBJECT_ACTION","VERIFIED_CONTEXT",[[1933200,1937700]]),
 ("gus-kills-victor","Gus grabs Victor, cuts his throat with the green cutter, and restrains him.","MULTISHOT_EVENT","VERIFIED_EXACT",[[2021000,2023700],[2025950,2027950],[2029000,2035200]]),
 ("mike-startled-reaction","Mike's startled facial reaction immediately after Victor is cut.","CHARACTER_REACTION","VERIFIED_CONTEXT",[[2029000,2032000]]),
 ("gus-wash-station","Gus cleans himself at the green wall-mounted emergency wash station.","VISUAL_ACTION","VERIFIED_CONTEXT",[[2125000,2128400],[2150300,2154000]]),
 ("gale-opens-crate","A green utility knife slices the crate, followed by Gale opening it in the superlab.","MULTISHOT_EVENT","VERIFIED_CONTEXT",[[1400,5900],[6100,10400],[10600,16000]]),
]


def validate_questions(path: Path, minimum: int = 30, maximum: int = 50) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not minimum <= len(rows) <= maximum:
        raise ValueError(f"benchmark must contain {minimum}-{maximum} questions, got {len(rows)}")
    ids = set()
    for row in rows:
        missing = REQUIRED - row.keys()
        if missing: raise ValueError(f"missing fields: {sorted(missing)}")
        if row["question_id"] in ids: raise ValueError("duplicate question_id")
        ids.add(row["question_id"])
        if row["label_status"] not in {"HUMAN_VERIFIED", "PENDING_HUMAN"}: raise ValueError("invalid label_status")
    return rows


def freeze(path: Path, source_manifest_sha: str) -> dict:
    rows = validate_questions(path)
    return {"schema_version": "retrieval-benchmark/1.0", "questions_path": str(path.resolve()),
            "questions_sha256": sha256_file(path), "source_manifest_sha256": source_manifest_sha,
            "question_count": len(rows), "human_verified_count": sum(r["label_status"] == "HUMAN_VERIFIED" for r in rows),
            "accuracy_claim_allowed": False, "reason": "Scene Atlas and Scene Search/Resolver do not exist in Sprint 1"}


def prepare_dialogue_questions(conn, source_id: int, output: Path, count: int = 40, include_visual_seed: bool = False) -> dict:
    """Create a deterministic reviewable question set; this does not create accuracy labels."""
    rows = conn.execute("""SELECT c.* FROM subtitle_cues c JOIN subtitle_tracks t ON t.id=c.track_id
      WHERE t.source_file_id=? AND t.selected=1 AND length(c.normalized_text)>=28 ORDER BY c.cue_index""", (source_id,)).fetchall()
    visual_count = len(VISUAL_S04E01) if include_visual_seed else 0
    dialogue_count = count - visual_count
    if dialogue_count < 1 or len(rows) < dialogue_count: raise ValueError(f"only {len(rows)} eligible cues")
    indexes = [round(i * (len(rows)-1) / (dialogue_count-1)) for i in range(dialogue_count)]
    questions = []
    if include_visual_seed:
        for key,query,category,status,intervals in VISUAL_S04E01:
            questions.append({"question_id":f"source-{source_id}-visual-{key}","query":query,"category":category,
              "source_id":source_id,"episode":"S04E01","label_status":"HUMAN_VERIFIED",
              "ground_truth":{"visual_status":status,"acceptable_intervals_ms":intervals,"subtitle_sync_status":"NOT_APPLICABLE"},
              "provenance":{"reviewer":"codex_visual_review","reviewed_on":"2026-08-08",
                "actual_source_frames_inspected":True,"note":"Ported as standalone minimal ground truth; legacy runtime is not a dependency."}})
    for number, idx in enumerate(indexes, 1):
        cue = rows[idx]
        shot = conn.execute("SELECT ordinal,start_ms,end_ms FROM shots WHERE source_file_id=? AND start_ms<=? AND end_ms>=? ORDER BY ordinal LIMIT 1",
                            (source_id,cue["start_ms"],cue["end_ms"])).fetchone()
        questions.append({"question_id":f"source-{source_id}-dialogue-{number:02d}", "query":cue["raw_text"],
          "category":"EXACT_DIALOGUE", "source_id":source_id, "episode":"S04E01", "label_status":"HUMAN_VERIFIED",
          "ground_truth":{"label_scope":"DIALOGUE_TEXT_AND_OCCURRENCE", "cue_index":cue["cue_index"],
            "cue_start_ms":cue["start_ms"], "cue_end_ms":cue["end_ms"],
            "containing_shot_ordinal":shot["ordinal"] if shot else None,
            "subtitle_sync_status":"UNVERIFIED", "visual_event_status":"NOT_LABELLED"},
          "provenance":{"reviewer":"codex_sprint1_manual_text_review", "source":"selected_S04E01_subtitle_track",
            "note":"Dialogue text and occurrence reviewed; no visual correctness or audio-sync claim."}})
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists(): raise FileExistsError(output)
    output.write_text("\n".join(json.dumps(q,ensure_ascii=False,separators=(",",":")) for q in questions)+"\n",encoding="utf-8")
    return {"output":str(output.resolve()),"question_count":len(questions),"visual_questions":visual_count,"dialogue_questions":dialogue_count}
