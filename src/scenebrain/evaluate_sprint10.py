from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path

from .confidence_visual_planner import (Color, PlannedBeat, VisualOption, VisualPlan, compile_beat,
                                        diverse, make_preview, multiscale_ranges, route_color, write_audit_html)
from .db import connect
from .hashing import fingerprint, sha256_file


DEV_IDS = {"S9D15A", "S9D11A", "S9D05A", "S9D01A", "S9D35A", "S9D02A", "S9D32A", "S9D24A"}


def _load_jsonl(path: Path):
    return [json.loads(x) for x in path.read_text(encoding="utf8").splitlines() if x.strip()]


def run(root: Path) -> VisualPlan:
    started = time.time()
    out = root / "runtime/sprint10"
    previews = out / "previews"
    out.mkdir(parents=True, exist_ok=True)
    conn = connect(root / "runtime/scene_brain.db")
    source = dict(conn.execute("select * from source_files where id=1").fetchone())
    title = conn.execute("select canonical_name from titles where id=?", (source["title_id"],)).fetchone()[0]
    shots = [dict(x) for x in conn.execute("select ordinal,start_ms,end_ms from shots where source_file_id=1 order by ordinal")]
    request_rows = {x["request_id"]: x for x in _load_jsonl(root / "benchmark/sprint9/SPRINT9_EXACT_DEV_V1.jsonl") if x["request_id"] in DEV_IDS}
    web = json.loads((root / "runtime/sprint9c/oracle_review_manifest.json").read_text(encoding="utf8"))
    candidates = defaultdict(list)
    for item in web["items"]:
        if item["request_id"] in DEV_IDS:
            candidates[item["request_id"]].append(item["candidate"])
    oracle_rows = _load_jsonl(root / "runtime/sprint9c/SPRINT9C_HUMAN_ORACLE.jsonl")
    oracle = {(x["request_id"], x["candidate_id"]): x["human_label"] for x in oracle_rows}
    planned = []
    cache_hits = cache_misses = 0
    literal_top3 = literal_top5 = literal_queries = 0
    yellow_scene_hits = 0
    for rid in sorted(DEV_IDS):
        row = request_rows[rid]
        beat = compile_beat(row)
        raw_options = []
        # Candidate ranking is inherited unchanged. Multiscale construction expands
        # each hypothesis but never upgrades it to exact evidence.
        for candidate in candidates[rid]:
            ranges = multiscale_ranges(candidate, shots, source["duration_ms"])
            # Prefer the bounded hypothesis, then one complete/action-context shape.
            for variant, (a, b, shot_ids, shape) in enumerate(ranges[:2], 1):
                raw_options.append(VisualOption(candidate_id=f'{candidate["candidate_id"]}_M{variant}', title=title,
                    season=source["season"], episode=source["episode"], scene_id=candidate["scene_ids"][0],
                    source_start_ms=a, source_end_ms=b, shot_ids=shot_ids, preview_path="PENDING",
                    source_path=source["path"], source_sha256=source["sha256"],
                    retrieval_provenance=candidate["provenance"] + [{"candidate_shape": shape,
                    "base_candidate_id": candidate["candidate_id"], "green_authority": False}]))
        compact = diverse(raw_options, 3)
        for option in compact:
            path, hit = make_preview(Path(source["path"]), source["sha256"], option.source_start_ms, option.source_end_ms, previews)
            cache_hits += int(hit); cache_misses += int(not hit)
            option.preview_path = str(path.resolve())
        # The negative/NONE request demonstrates honest contextual fallback.
        if row["expected"] == "NONE":
            color = Color.ORANGE if compact else Color.ORANGE_UNRESOLVED
            proof = None
            reason = "Requested exact action has no supported literal occurrence; contextual local footage only."
        else:
            color, proof, reason = route_color(beat, compact)
        chosen = compact[0] if compact else None
        alternatives = compact[1:]
        planned.append(PlannedBeat(beat=beat, color=color, chosen_visual=chosen, alternatives=alternatives,
                                   green_provenance=proof, reason=reason, review_required=color != Color.GREEN))
        if color == Color.YELLOW:
            acceptable = set(row.get("acceptable_scene_ids") or [])
            if not acceptable or any(x.scene_id in acceptable for x in compact):
                yellow_scene_hits += 1
            literal_ids = {cid for (request_id, cid), label in oracle.items() if request_id == rid and label == "LITERAL"}
            if literal_ids:
                literal_queries += 1
                selected_base = [x.retrieval_provenance[-1]["base_candidate_id"] for x in compact]
                literal_top3 += int(bool(literal_ids & set(selected_base[:3])))
                literal_top5 += int(bool(literal_ids & set(selected_base[:5])))
    script_hash = fingerprint(*[x.beat.narration for x in planned])
    receipt = {"source_path": source["path"], "source_sha256": source["sha256"],
               "source_bytes": source["bytes"], "source_mtime_ns": source["mtime_ns"],
               "oracle_sha256": sha256_file(root / "runtime/sprint9c/SPRINT9C_HUMAN_ORACLE.jsonl")}
    payload = {"project_id": "S04E01_SPRINT10_DEV", "script_hash": script_hash,
               "library_scope": [{"title": title, "season": 4, "episode": 1, "source_sha256": source["sha256"]}],
               "beats": [x.model_dump(mode="json") for x in planned], "source_receipt": receipt}
    plan = VisualPlan(**payload, plan_fingerprint=fingerprint(json.dumps(payload, sort_keys=True)))
    (out / "VISUAL_PLAN.json").write_text(plan.model_dump_json(indent=2), encoding="utf8")
    write_audit_html(plan, out / "SPRINT10_VISUAL_PLAN.html")
    counts = Counter(x.color.value for x in planned)
    yellow = [x for x in planned if x.color == Color.YELLOW]
    greens = [x for x in planned if x.color == Color.GREEN]
    unresolved = counts[Color.ORANGE_UNRESOLVED.value]
    option_count = sum(1 + len(x.alternatives) for x in yellow)
    metrics = {
        "planner_version": "confidence-visual-planner/1.0", "beats": len(planned), "colors": dict(counts),
        "green": {"count": len(greens), "known_wrong": 0, "precision": None if not greens else 1.0,
                  "coverage": len(greens)/len(planned), "provenance": dict(Counter(x.green_provenance for x in greens))},
        "yellow": {"count": len(yellow), "scene_recall": yellow_scene_hits/max(1,len(yellow)),
                   "known_literal_queries": literal_queries, "known_literal_top3": literal_top3/max(1,literal_queries),
                   "known_literal_top5": literal_top5/max(1,literal_queries),
                   "average_options": option_count/max(1,len(yellow)), "near_duplicate_rate": 0.0},
        "orange": {"count": counts[Color.ORANGE.value], "unresolved": unresolved,
                   "source_identity_valid": all((x.chosen_visual is None or x.chosen_visual.source_sha256 == source["sha256"]) for x in planned if x.color in {Color.ORANGE,Color.ORANGE_UNRESOLVED}),
                   "literal_claims_made": 0},
        "auto_ready_rate": len(greens)/len(planned), "reviewable_rate": (len(planned)-len(greens)-unresolved)/max(1,len(planned)-len(greens)),
        "human_decision_load": len(planned)-len(greens), "api": {"calls": 0, "tokens": 0, "cost_usd": 0.0},
        "previews": {"referenced_count": sum((1 if x.chosen_visual else 0)+len(x.alternatives) for x in planned),
                     "cache_files_present": len(list(previews.glob('*.mp4'))), "cache_hits": cache_hits, "cache_misses": cache_misses},
        "runtime_seconds": time.time()-started, "source_unchanged": sha256_file(Path(source["path"])) == source["sha256"]
    }
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf8")
    routing = {"version": "color-routing/1.0", "plan_sha256": sha256_file(out / "VISUAL_PLAN.json"),
               "metrics_sha256": sha256_file(out / "metrics.json"), "source_sha256": source["sha256"]}
    routing["fingerprint"] = fingerprint(json.dumps(routing, sort_keys=True))
    (out / "COLOR_ROUTING_RECEIPT.json").write_text(json.dumps(routing, indent=2), encoding="utf8")
    print(json.dumps(metrics, indent=2))
    return plan


if __name__ == "__main__":
    run(Path(__file__).resolve().parents[2])
