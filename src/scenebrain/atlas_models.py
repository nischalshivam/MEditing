from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

Boundary = Literal["SUPPORTED","UNKNOWN_START","UNKNOWN_END","UNKNOWN_BOTH"]
SceneType = Literal["normal","montage","transition","recap","flashback","dream","cold_open","other"]


class EvidenceName(BaseModel):
    model_config=ConfigDict(extra="forbid")
    name: str
    evidence_shots: list[str]


class EvidenceDescription(BaseModel):
    model_config=ConfigDict(extra="forbid")
    description: str
    evidence_shots: list[str]


class Uncertainty(BaseModel):
    model_config=ConfigDict(extra="forbid")
    code: str
    description: str
    evidence_shots: list[str] = Field(default_factory=list)


class SceneProposal(BaseModel):
    model_config=ConfigDict(extra="forbid")
    start_shot: str
    end_shot: str
    boundary_status: Boundary
    characters: list[EvidenceName]
    location: EvidenceName
    main_event: EvidenceDescription
    visible_actions: list[EvidenceDescription]
    important_objects: list[EvidenceName]
    visual_summary: str
    scene_type: SceneType
    uncertainties: list[Uncertainty]


class WindowResponse(BaseModel):
    model_config=ConfigDict(extra="forbid")
    window_id: str
    needs_temporal_preview: bool
    preview_reason: str
    scenes: list[SceneProposal]

