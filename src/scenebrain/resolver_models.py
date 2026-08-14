from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

EvidenceClass=Literal["EXACT_DIALOGUE","EXACT_EVENT","EVENT_CONTEXT","EDITORIAL_CONTEXT","CHARACTER_CONTEXT"]
Decision=Literal["VERIFIED","CONTEXTUAL","ABSTAIN"]


class SceneRetrievalRequest(BaseModel):
    model_config=ConfigDict(extra="forbid")
    request_id: str
    query_text: str
    evidence_class: EvidenceClass
    allowed_title: str="Breaking Bad"
    season: int|None=4
    episode: int|None=1
    requested_event: str|None=None
    visible_action: str|None=None
    characters_required: list[str]=Field(default_factory=list)
    characters_optional: list[str]=Field(default_factory=list)
    objects: list[str]=Field(default_factory=list)
    location: str|None=None
    dialogue_clue: str|None=None
    negative_constraints: list[str]=Field(default_factory=list)
    continuity_context: str|None=None
    none_allowed: bool=True
    exactness_policy: Literal["LITERAL","CONTEXT_OK","EDITORIAL"]="LITERAL"


class CandidateResult(BaseModel):
    model_config=ConfigDict(extra="forbid")
    scene_id: str
    start_ms: int
    end_ms: int
    total_score: float
    channel_scores: dict[str,float]
    matched_fragments: list[dict]
    matched_dialogue: list[dict]
    evidence_shot_ids: list[str]
    atlas_status: str
    matches: list[str]
    conflicts: list[str]
    neighbors: list[str]
    neighbor_reason: str|None=None


class ResolverResult(BaseModel):
    model_config=ConfigDict(extra="forbid")
    request_id: str
    resolver_version: str
    decision: Decision
    primary_scene: str|None
    candidates: list[CandidateResult]
    decision_reason: str
    verifier: dict|None=None
    provenance: dict

