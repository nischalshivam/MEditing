from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    root: Path
    runtime: Path
    database: Path
    cache: Path
    reports: Path
    log_level: str = "INFO"
    shot_threshold: float = 0.15
    keyframe_width: int = 640
    gemini_model: str = "gemini-3.1-flash-lite"
    gemini_max_calls: int = 40
    gemini_max_cost_usd: float = 2.0
    scene_window_target_seconds: int = 90
    scene_window_min_shots: int = 15
    scene_window_max_shots: int = 30
    scene_window_overlap_shots: int = 5

    @classmethod
    def load(cls, root: Path | None = None) -> "Settings":
        root = (root or Path(__file__).resolve().parents[2]).resolve()
        runtime = root / "runtime"
        return cls(root, runtime, runtime / "scene_brain.db", runtime / "cache", runtime / "reports")

    def ensure(self) -> None:
        for path in (self.runtime, self.cache, self.reports):
            path.mkdir(parents=True, exist_ok=True)
