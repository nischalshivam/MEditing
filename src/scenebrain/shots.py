from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from .hashing import fingerprint, sha256_file

PTS_RE = re.compile(r"pts_time:([0-9.]+)")
DETECTOR = "ffmpeg-scene-select/8.1"


def detection_fingerprint(source_sha: str, threshold: float) -> str:
    return fingerprint(source_sha, DETECTOR, threshold)


def detect(media_path: Path, duration_ms: int, source_sha: str, threshold: float = 0.15) -> tuple[str, list[tuple[int,int]]]:
    fp = detection_fingerprint(source_sha, threshold)
    command = ["ffmpeg", "-hide_banner", "-nostdin", "-i", str(media_path), "-an",
               "-vf", f"select='gt(scene,{threshold})',showinfo", "-f", "null", "-"]
    proc = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[-3000:])
    cuts = sorted({round(float(x) * 1000) for x in PTS_RE.findall(proc.stderr) if 0 < float(x) * 1000 < duration_ms})
    bounds = [0, *cuts, duration_ms]
    shots = [(a, b) for a, b in zip(bounds, bounds[1:]) if b > a]
    if not shots or shots[0][0] != 0 or shots[-1][1] != duration_ms:
        raise RuntimeError("shot coverage invariant failed")
    return fp, shots


def extract_keyframe(media_path: Path, timestamp_ms: int, output: Path, width: int = 640) -> dict:
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_suffix(".building.jpg")
    if tmp.exists(): tmp.unlink()
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-ss", f"{timestamp_ms/1000:.3f}",
               "-i", str(media_path), "-frames:v", "1", "-vf", f"scale={width}:-2", "-q:v", "3", "-y", str(tmp)]
    proc = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0 or not tmp.is_file() or tmp.stat().st_size == 0:
        if tmp.exists(): tmp.unlink()
        raise RuntimeError(proc.stderr[-2000:])
    tmp.replace(output)
    return {"path": str(output.resolve()), "bytes": output.stat().st_size, "sha256": sha256_file(output)}


def representative_time(start_ms: int, end_ms: int) -> int:
    duration = end_ms - start_ms
    margin = min(500, max(50, duration // 10))
    return max(start_ms + margin, min(end_ms - margin, start_ms + duration // 2))
