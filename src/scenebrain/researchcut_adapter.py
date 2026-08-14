from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


TRACKS = [
    {"id": "V3", "kind": "video", "name": "Overlay 2", "muted": False, "locked": False, "magnetic": False},
    {"id": "V2", "kind": "video", "name": "Overlay 1", "muted": False, "locked": False, "magnetic": False},
    {"id": "V1", "kind": "video", "name": "Main Visual", "muted": True, "locked": False, "magnetic": False},
    {"id": "A1", "kind": "audio", "name": "Voiceover", "muted": False, "locked": False, "magnetic": False},
    {"id": "A2", "kind": "audio", "name": "Music & SFX", "muted": False, "locked": False, "magnetic": False},
]


def _asset_id(path: str, suffix: str = "") -> str:
    import hashlib
    return "sb_" + hashlib.sha256((os.path.normcase(path) + suffix).encode()).hexdigest()[:16]


def adapt_scene_brain_project(source: dict) -> dict:
    """Convert any SceneBrain editor project into ResearchCut schema v3."""
    now = datetime.now(timezone.utc).isoformat()
    assets: dict[str, dict] = {}

    def add(path: str, kind: str, duration: float = 0, *, provenance=None, variant: str = "") -> str:
        aid = _asset_id(path, kind + variant)
        if aid not in assets:
            assets[aid] = {
                "id": aid, "name": Path(path).name, "storedName": Path(path).name,
                "externalPath": path, "kind": kind, "duration": duration,
                "width": 1920 if kind != "audio" else 0, "height": 1080 if kind != "audio" else 0,
                "hasAudio": kind in {"video", "audio"}, "sceneBrainProvenance": provenance or {}, "thumbnailTime": float((provenance or {}).get("thumbnail_time", 2)),
            }
        return aid

    clips = []
    scene_uses: dict[str, int] = {}
    range_uses: set[tuple[str, int, int]] = set()
    voice_duration = source.get("voiceover_duration_ms", 0) / 1000
    source_end = max((s.get("timeline_end_ms", 0) for s in source.get("timeline", [])), default=0) / 1000
    timeline_scale = voice_duration / source_end if voice_duration and source_end and source_end > voice_duration else 1
    placeholder = str((Path(__file__).resolve().parents[2] / "runtime" / "researchcut_integration" / "production" / "public" / "manual-placeholder.svg"))
    for slot in source.get("timeline", []):
        candidates = slot.get("candidates") or []
        chosen = candidates[min(slot.get("selected_candidate") or 0, max(0, len(candidates)-1))] if candidates else {}
        path = slot.get("derived_asset_path") or slot.get("source_path") or chosen.get("source_path")
        state = slot.get("approval_state")
        start = slot["timeline_start_ms"] / 1000 * timeline_scale
        duration = (slot["timeline_end_ms"] - slot["timeline_start_ms"]) / 1000 * timeline_scale
        candidate_assets=[]
        for candidate in candidates:
            cp=candidate.get("source_path")
            if cp:
                candidate_assets.append(add(cp,"video",max(duration,(candidate.get("source_out_ms") or 0)/1000),provenance={"slot_id":slot["presentation_slot_id"],"candidate":len(candidate_assets),"thumbnail_time":((candidate.get("source_in_ms",0)+candidate.get("source_out_ms",0))/2000)},variant=f":{slot['presentation_slot_id']}:{len(candidate_assets)}"))
        if not path and state in {"MANUAL_FIX","MANUAL_REQUIRED"}:
            path=placeholder
        if path:
            kind = "image" if slot.get("derived_asset_path") or path==placeholder else "video"
            aid = add(path, kind, max(duration, (slot.get("source_out_ms") or 0)/1000), provenance={"slot_id": slot["presentation_slot_id"], "source_id": slot.get("source_id")})
            # Presentation plan: expand each semantic anchor into natural 3–5 second edits.
            options = candidates if kind == "video" and candidates else [chosen]
            parts=max(1,round(duration/4.2));cursor=start;remaining=duration
            for part in range(parts):
                if part >= len(options) and kind == "video": break
                option=options[min(part,len(options)-1)] or {};option_path=option.get("source_path") or path
                option_in=0 if kind=="image" else (option.get("source_in_ms") or slot.get("source_in_ms") or 0)/1000
                scene_key=str(option.get("scene_id") or option.get("region_id") or f"{os.path.normcase(option_path)}:{int(option_in//8)}")
                if scene_uses.get(scene_key,0)>=2: continue
                d=remaining/(parts-part);d=min(10,max(.25,d))
                range_key=(os.path.normcase(option_path),round(option_in*10),round((option_in+d)*10))
                if range_key in range_uses: continue
                part_aid=aid if option_path==path else add(option_path,"video",max(d,(option.get("source_out_ms") or 0)/1000),provenance={"slot_id":slot["presentation_slot_id"],"thumbnail_time":((option.get("source_in_ms",0)+option.get("source_out_ms",0))/2000)},variant=f":presentation:{slot['presentation_slot_id']}:{part}")
                clips.append({
                    "id": "clip_" + slot["presentation_slot_id"]+f"_{part+1:02d}", "assetId": part_aid, "trackId": "V1", "start": cursor,
                    "duration": d, "sourceIn": option_in,
                    "transform": {"x": 0, "y": 0, "scale": 1, "rotation": 0, "fit": "fill", "opacity": 1, "crop": {"top": 0, "right": 0, "bottom": 0, "left": 0}},
                    "muted": True, "volume": 0, "sceneBrain": {"slotId": slot["presentation_slot_id"], "semanticAnchor":slot.get("canonical_event_id"),"sceneKey":scene_key,"beatId": slot.get("beat_id"), "status": state, "narration": slot.get("exact_narration"), "candidates": candidates, "candidateAssetIds":candidate_assets},
                });scene_uses[scene_key]=scene_uses.get(scene_key,0)+1;range_uses.add(range_key);cursor+=d;remaining-=d
    voice = source.get("voiceover_path")
    if voice:
        duration = voice_duration
        aid = add(voice, "audio", duration, provenance={"role": "FINAL_VOICEOVER"})
        clips.append({"id": "clip_voiceover", "assetId": aid, "trackId": "A1", "start": 0, "duration": duration, "sourceIn": 0,
                      "transform": {"x": 0, "y": 0, "scale": 1, "rotation": 0, "fit": "fill", "opacity": 1, "crop": {"top": 0, "right": 0, "bottom": 0, "left": 0}}, "muted": False, "volume": 1})
    return {"schemaVersion": 3, "id": source.get("project_id", "scene_brain_project"), "name": source.get("name", "SceneBrain Project"),
            "createdAt": now, "updatedAt": now, "revision": 1, "settings": {"width": 1920, "height": 1080, "fps": 30, "aspect": "16:9", "background": "#090b10"},
            "assets": list(assets.values()), "tracks": TRACKS, "clips": clips, "automation": {}, "sceneBrainAdapterVersion": "1.0"}


def write_atomic(project: dict, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_suffix(output.suffix + ".tmp")
    tmp.write_text(json.dumps(project, indent=2), encoding="utf-8")
    os.replace(tmp, output)
