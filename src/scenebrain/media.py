from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .hashing import sha256_file


@dataclass(frozen=True)
class MediaProbe:
    duration_ms: int
    width: int
    height: int
    fps_num: int
    fps_den: int
    video_codec: str
    audio_codec: str
    raw: dict


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")


def probe(path: Path) -> MediaProbe:
    if not path.is_file():
        raise FileNotFoundError(path)
    if not shutil.which("ffprobe"):
        raise RuntimeError("ffprobe not found")
    result = run(["ffprobe", "-v", "error", "-show_entries",
        "format=duration:stream=index,codec_type,codec_name,width,height,avg_frame_rate,channels:stream_tags=language,title",
        "-of", "json", str(path)])
    raw = json.loads(result.stdout)
    video = next((s for s in raw["streams"] if s.get("codec_type") == "video"), None)
    audio = next((s for s in raw["streams"] if s.get("codec_type") == "audio"), None)
    if not video or not audio:
        raise ValueError("source must have video and audio streams")
    num, den = (int(x) for x in video.get("avg_frame_rate", "0/1").split("/"))
    return MediaProbe(round(float(raw["format"]["duration"]) * 1000), int(video["width"]), int(video["height"]),
                      num, den, video["codec_name"], audio["codec_name"], raw)


def infer_episode(path: Path) -> tuple[int | None, int | None]:
    text = path.stem
    match = re.search(r"(?i)S(\d{1,2})E(\d{1,2})", text) or re.search(r"(?i)Season\s*(\d+).*Episode\s*(\d+)", text)
    return (int(match.group(1)), int(match.group(2))) if match else (None, None)


def doctor(path: Path) -> dict:
    p = probe(path)
    stat = path.stat()
    season, episode = infer_episode(path)
    checks = {
        "readable": True, "has_video": True, "has_audio": True,
        "duration_positive": p.duration_ms > 0, "dimensions_positive": p.width > 0 and p.height > 0,
        "episode_identity_parsed": season is not None and episode is not None,
    }
    return {"status": "PASS" if all(checks.values()) else "WARN", "path": str(path.resolve()),
            "bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns, "sha256": sha256_file(path),
            "season": season, "episode": episode, "duration_ms": p.duration_ms, "width": p.width,
            "height": p.height, "fps": [p.fps_num, p.fps_den], "video_codec": p.video_codec,
            "audio_codec": p.audio_codec, "checks": checks, "probe": p.raw}

