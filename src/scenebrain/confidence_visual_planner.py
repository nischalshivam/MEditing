from __future__ import annotations

import html
import json
import re
import subprocess
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .hashing import fingerprint, sha256_file

VERSION = "confidence-visual-planner/1.0"
PLAN_VERSION = "visual-plan/1.0"


class Color(str, Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    ORANGE = "ORANGE"
    ORANGE_UNRESOLVED = "ORANGE_UNRESOLVED"


class NarrationBeat(BaseModel):
    model_config = ConfigDict(extra="forbid")
    beat_id: str
    narration: str
    evidence_class: Literal["EXACT_DIALOGUE", "EXACT_EVENT", "EVENT_CONTEXT", "EDITORIAL_CONTEXT", "CHARACTER_CONTEXT"]
    primary_subject: str | None = None
    required_visible_facts: list[str] = Field(default_factory=list)
    negative_facts: list[str] = Field(default_factory=list)
    voice_start_ms: int | None = None
    voice_end_ms: int | None = None


class VisualOption(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidate_id: str
    media_type: Literal["VIDEO", "STILL"] = "VIDEO"
    title: str
    season: int
    episode: int
    scene_id: str
    source_start_ms: int
    source_end_ms: int
    shot_ids: list[str]
    preview_path: str
    source_path: str
    source_sha256: str
    retrieval_provenance: list[dict] = Field(default_factory=list)

    @model_validator(mode="after")
    def valid_range(self):
        if self.source_start_ms < 0 or self.source_end_ms <= self.source_start_ms:
            raise ValueError("invalid source range")
        if not self.shot_ids:
            raise ValueError("missing physical shot provenance")
        return self


class PlannedBeat(BaseModel):
    model_config = ConfigDict(extra="forbid")
    beat: NarrationBeat
    color: Color
    chosen_visual: VisualOption | None
    alternatives: list[VisualOption] = Field(default_factory=list)
    green_provenance: Literal["GREEN_HUMAN_MEMORY", "GREEN_EXACT_DIALOGUE", "GREEN_VERIFIED_EVENT_MEMORY"] | None = None
    reason: str
    review_required: bool

    @model_validator(mode="after")
    def policy(self):
        options = ([self.chosen_visual] if self.chosen_visual else []) + self.alternatives
        if self.color == Color.GREEN:
            if not self.green_provenance or not self.chosen_visual or self.review_required:
                raise ValueError("GREEN requires permitted proof and chosen visual")
        elif not self.review_required:
            raise ValueError("non-GREEN must require review")
        if self.color == Color.YELLOW and not 2 <= len(options) <= 5:
            raise ValueError("YELLOW requires 2-5 total options")
        if len(options) > 5:
            raise ValueError("maximum five visible options")
        return self


class VisualPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["visual-plan/1.0"] = PLAN_VERSION
    planner_version: Literal["confidence-visual-planner/1.0"] = VERSION
    project_id: str
    script_hash: str
    voiceover_hash: str | None = None
    library_scope: list[dict]
    beats: list[PlannedBeat]
    source_receipt: dict
    plan_fingerprint: str


def compile_beat(request: dict) -> NarrationBeat:
    query = request["query"].strip()
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", query)
    subject = words[0] if words and words[0][0].isupper() else None
    evidence = request.get("evidence_class", "EXACT_EVENT")
    return NarrationBeat(
        beat_id=request["request_id"], narration=query, evidence_class=evidence,
        primary_subject=subject,
        required_visible_facts=request.get("required_visual_facts", [query]),
        negative_facts=request.get("forbidden_visual_substitutions", []),
    )


def route_color(beat: NarrationBeat, options: list[VisualOption], *, memory: dict | None = None,
                exact_dialogue_proof: bool = False) -> tuple[Color, str | None, str]:
    memory = memory or {}
    approval = memory.get("approval_type")
    if options and approval in {"EXACT_EVENT_APPROVAL", "EXACT_DIALOGUE_APPROVAL"}:
        provenance = "GREEN_VERIFIED_EVENT_MEMORY" if approval == "EXACT_EVENT_APPROVAL" else "GREEN_HUMAN_MEMORY"
        return Color.GREEN, provenance, "Exact source-bound human approval exists."
    if options and beat.evidence_class == "EXACT_DIALOGUE" and exact_dialogue_proof:
        return Color.GREEN, "GREEN_EXACT_DIALOGUE", "Unique verified local subtitle occurrence overlaps this footage."
    if beat.evidence_class in {"EXACT_EVENT", "EVENT_CONTEXT", "EXACT_DIALOGUE"} and len(options) >= 2:
        return Color.YELLOW, None, "Likely source scene/moment is supported, but no permitted Green proof exists."
    if options:
        return Color.ORANGE, None, "Contextual local visual is supplied without claiming literal event proof."
    return Color.ORANGE_UNRESOLVED, None, "No safe source-bound contextual visual was found."


def _overlap_ratio(a: VisualOption, b: VisualOption) -> float:
    overlap = max(0, min(a.source_end_ms, b.source_end_ms) - max(a.source_start_ms, b.source_start_ms))
    return overlap / max(1, min(a.source_end_ms-a.source_start_ms, b.source_end_ms-b.source_start_ms))


def diverse(options: list[VisualOption], limit: int = 5) -> list[VisualOption]:
    out: list[VisualOption] = []
    for option in options:
        if any(_overlap_ratio(option, x) > .72 for x in out):
            continue
        out.append(option)
        if len(out) == limit:
            break
    return out


def multiscale_ranges(candidate: dict, shot_bounds: list[dict], source_duration_ms: int) -> list[tuple[int, int, list[str], str]]:
    start, end = candidate["start_ms"], candidate["end_ms"]
    ids = list(candidate.get("shot_ids") or [candidate["start_shot"], candidate["end_shot"]])
    results = [(start, end, ids, "BOUNDED_RANGE")]
    ordinals = sorted({int(x[1:]) for x in ids})
    by_ord = {x["ordinal"]: x for x in shot_bounds}
    if ordinals:
        lo, hi = min(ordinals), max(ordinals)
        for a, b, label in [(lo, hi, "COMPLETE_SHOT"), (lo-1, hi, "PREVIOUS_CURRENT"),
                            (lo, hi+1, "CURRENT_NEXT"), (lo-1, hi+1, "THREE_SHOT_CONTEXT")]:
            rows = [by_ord[x] for x in range(a, b+1) if x in by_ord]
            if rows:
                results.append((max(0, rows[0]["start_ms"]), min(source_duration_ms, rows[-1]["end_ms"]),
                                [f'S{x["ordinal"]:04d}' for x in rows], label))
    unique = []
    for x in results:
        if x[1] > x[0] and (x[0], x[1]) not in {(y[0], y[1]) for y in unique}:
            unique.append(x)
    return unique


def make_preview(source: Path, source_sha: str, start_ms: int, end_ms: int, folder: Path) -> tuple[Path, bool]:
    key = fingerprint(VERSION, source_sha, start_ms, end_ms, "preview-540p-h264-crf28")
    out = folder / f"{key}.mp4"
    if out.exists():
        return out, True
    folder.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".building.mp4")
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{start_ms/1000:.3f}",
                    "-i", str(source), "-t", f"{(end_ms-start_ms)/1000:.3f}", "-vf", "scale=960:-2",
                    "-an", "-c:v", "libx264", "-crf", "28", "-movflags", "+faststart", "-y", str(tmp)], check=True)
    tmp.replace(out)
    return out, False


def write_audit_html(plan: VisualPlan, out: Path) -> None:
    cards = []
    for p in plan.beats:
        opts = ([p.chosen_visual] if p.chosen_visual else []) + p.alternatives
        media = "".join(f'<article><video controls preload="metadata" src="./previews/{html.escape(Path(x.preview_path).name)}"></video>'
                        f'<small>{html.escape(x.candidate_id)} · {x.scene_id} · {x.source_start_ms}–{x.source_end_ms} ms · {", ".join(x.shot_ids)}</small></article>' for x in opts)
        buttons = '<button>Correct</button><button>Wrong</button>' if p.color == Color.GREEN else (
            ''.join(f'<button>Best {i+1}</button>' for i in range(len(opts)))+'<button>None good</button>' if p.color == Color.YELLOW else '<button>Usable</button><button>Not usable</button>')
        cards.append(f'<section data-beat="{p.beat.beat_id}"><h2>{html.escape(p.beat.narration)}</h2><b class="{p.color.value}">{p.color.value}</b><p>{html.escape(p.reason)}</p><div class="grid">{media}</div><div class="audit">{buttons}</div></section>')
    doc = f'''<!doctype html><meta charset="utf-8"><title>Sprint 10 Visual Plan</title><style>
body{{font:15px system-ui;background:#111827;color:#e5e7eb;max-width:1300px;margin:auto;padding:24px}}section{{background:#1f2937;padding:18px;margin:18px 0;border-radius:12px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}}video{{width:100%;background:#000}}article small{{display:block;padding:6px}}b{{padding:5px 10px;border-radius:12px}}.GREEN{{background:#15803d}}.YELLOW{{background:#ca8a04}}.ORANGE,.ORANGE_UNRESOLVED{{background:#c2410c}}button{{margin:8px 5px 0 0}} </style>
<h1>SPRINT 10 · GREEN / YELLOW / ORANGE VISUAL PLAN</h1><p>{len(plan.beats)} real S04E01 evidence beats · audit choices save locally.</p>{''.join(cards)}<script>document.querySelectorAll('section').forEach(s=>s.querySelectorAll('button').forEach(b=>b.onclick=()=>{{localStorage.setItem('s10:'+s.dataset.beat,b.textContent);b.parentNode.dataset.saved=b.textContent}}));</script>'''
    out.write_text(doc, encoding="utf8")
