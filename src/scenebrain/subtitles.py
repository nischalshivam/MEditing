from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from pathlib import Path

from .hashing import sha256_file
from .media import infer_episode

TAG_RE = re.compile(r"<[^>]+>|\{\\[^}]+\}")
SPACE_RE = re.compile(r"\s+")
TOKEN_RE = re.compile(r"[\w']+", re.UNICODE)


@dataclass(frozen=True)
class Cue:
    index: int
    start_ms: int
    end_ms: int
    raw_text: str
    normalized_text: str


def normalize(text: str) -> str:
    text = html.unescape(TAG_RE.sub(" ", text)).replace("♪", " ")
    return SPACE_RE.sub(" ", text).strip().casefold()


def _ms(value: str) -> int:
    h, m, rest = value.replace('.', ',').split(':')
    s, ms = rest.split(',')
    return ((int(h) * 60 + int(m)) * 60 + int(s)) * 1000 + int(ms.ljust(3, '0')[:3])


def parse_srt(path: Path) -> list[Cue]:
    text = path.read_text(encoding="utf-8-sig", errors="replace").replace("\r\n", "\n")
    cues: list[Cue] = []
    timing = re.compile(r"(?m)^(\d\d:\d\d:\d\d[,.]\d{1,3})\s+-->\s+(\d\d:\d\d:\d\d[,.]\d{1,3}).*$")
    matches = list(timing.finditer(text))
    for n, match in enumerate(matches):
        start_body = match.end() + (1 if match.end() < len(text) and text[match.end()] == '\n' else 0)
        end_body = matches[n + 1].start() if n + 1 < len(matches) else len(text)
        body_lines = [x.strip() for x in text[start_body:end_body].strip().splitlines()]
        while body_lines and body_lines[-1].isdigit(): body_lines.pop()
        raw = " ".join(x for x in body_lines if x)
        start, end = _ms(match.group(1)), _ms(match.group(2))
        if end <= start: raise ValueError(f"non-positive cue duration at {n + 1}")
        cues.append(Cue(n + 1, start, end, raw, normalize(raw)))
    if not cues: raise ValueError(f"no SRT cues parsed: {path}")
    return cues


def discover(media_path: Path) -> list[Path]:
    stem = media_path.stem
    candidates = []
    for ext in ("*.srt", "*.vtt"):
        for path in media_path.parent.glob(ext):
            if path.stem == stem or path.stem.startswith(stem + "."):
                candidates.append(path.resolve())
    return sorted(set(candidates), key=lambda p: str(p).casefold())


def assess(path: Path, media_path: Path, duration_ms: int) -> dict:
    cues = parse_srt(path)
    media_identity = infer_episode(media_path)
    subtitle_identity = infer_episode(path)
    identity = "MATCH" if media_identity == subtitle_identity and None not in media_identity else "UNRESOLVED"
    monotonic = all(a.start_ms <= b.start_ms for a, b in zip(cues, cues[1:]))
    in_bounds = cues[0].start_ms >= 0 and cues[-1].end_ms <= duration_ms + 2000
    density = len(cues) / max(duration_ms / 60000, 1)
    # Sync is deliberately not inferred from timestamps alone. A later audio verifier may attest it.
    sync_status = "UNVERIFIED"
    score = (40 if identity == "MATCH" else 0) + (20 if monotonic else -100) + (20 if in_bounds else -100) + min(density, 20)
    return {"path": str(path), "origin": "SIDECAR", "language": "en" if ".en." in path.name.lower() else None,
            "bytes": path.stat().st_size, "sha256": sha256_file(path), "cue_count": len(cues),
            "first_ms": cues[0].start_ms, "last_ms": cues[-1].end_ms, "parse_status": "PASS",
            "identity_status": identity, "sync_status": sync_status, "sync_offset_ms": None,
            "score": score, "evidence": {"monotonic": monotonic, "within_media_bounds": in_bounds,
            "cues_per_minute": round(density, 3), "sync_claimed": False}}


def search_multi_cue(conn, query: str, limit: int = 20, max_cues: int = 4, max_gap_ms: int = 4000) -> list[dict]:
    tokens = TOKEN_RE.findall(normalize(query))
    if not tokens: return []
    rows = conn.execute("""SELECT c.*, t.source_file_id FROM subtitle_cues c
      JOIN subtitle_tracks t ON t.id=c.track_id WHERE t.selected=1 ORDER BY c.track_id,c.cue_index""").fetchall()
    by_track: dict[int, list] = {}
    for row in rows: by_track.setdefault(row["track_id"], []).append(row)
    results = []
    for track_id, cues in by_track.items():
        for i in range(len(cues)):
            combined = ""
            for j in range(i, min(i + max_cues, len(cues))):
                if j > i and cues[j]["start_ms"] - cues[j-1]["end_ms"] > max_gap_ms: break
                combined = normalize(combined + " " + cues[j]["normalized_text"])
                combined_tokens = TOKEN_RE.findall(combined)
                contiguous = any(combined_tokens[k:k+len(tokens)] == tokens for k in range(len(combined_tokens)-len(tokens)+1))
                if contiguous:
                    results.append({"track_id": track_id, "source_file_id": cues[i]["source_file_id"],
                      "start_cue": cues[i]["cue_index"], "end_cue": cues[j]["cue_index"],
                      "start_ms": cues[i]["start_ms"], "end_ms": cues[j]["end_ms"], "text": combined,
                      "match": "NORMALIZED_CONTIGUOUS"})
                    break
    # The same occurrence can be rediscovered with several earlier context prefixes.
    # Keep the narrowest non-overlapping evidence window so callers do not mistake
    # one quote for several distinct occurrences.
    chosen = []
    for item in sorted(results, key=lambda x: (x["end_cue"]-x["start_cue"], x["end_ms"]-x["start_ms"], x["start_ms"])):
        if any(item["track_id"] == old["track_id"] and item["start_ms"] < old["end_ms"] and old["start_ms"] < item["end_ms"] for old in chosen):
            continue
        chosen.append(item)
    return sorted(chosen, key=lambda x: x["start_ms"])[:limit]
