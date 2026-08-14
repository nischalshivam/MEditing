from __future__ import annotations

from typing import Literal
from pydantic import BaseModel,ConfigDict,Field

from .resolver_models import SceneRetrievalRequest,ResolverResult

class ShotRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    scene_request:SceneRetrievalRequest
    sprint3_result:ResolverResult
    reaction_subject:str|None=None
    reaction_trigger:str|None=None
    reaction_direction:Literal['BEFORE','DURING','AFTER']|None=None

class ShotRange(BaseModel):
    model_config=ConfigDict(extra='forbid')
    candidate_id:str
    start_shot:str
    end_shot:str
    start_ms:int
    end_ms:int
    scene_ids:list[str]
    local_score:float
    provenance:list[dict]
    nearby_dialogue:list[dict]=Field(default_factory=list)
    boundary_sensitive:bool=False

class ShotResolution(BaseModel):
    model_config=ConfigDict(extra='forbid')
    request_id:str
    version:str
    decision:Literal['VERIFIED_EXACT','REVIEW_REQUIRED','ABSTAIN']
    candidates:list[ShotRange]
    selected_candidate_id:str|None=None
    selected_shots:list[str]=Field(default_factory=list)
    source_interval_ms:list[int]|None=None
    preview_path:str|None=None
    literal_evidence:str|None=None
    usability_flags:list[str]=Field(default_factory=list)
    candidate_verifier:dict|None=None
    crop_verifier:dict|None=None
    reason:str
    provenance:dict
