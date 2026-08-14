from __future__ import annotations

import re
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field

from .resolver import ALIASES
from .shot_models import ShotRequest

CONTRACT_VERSION='region-discovery-contract/3.0'

SYNONYMS={
 'leave':{'leave','leaves','left','exit','exits','depart','departs','walk away','walks away','drive away','drives away'},
 'enter':{'enter','enters','entered','walk in','walks in','come inside','comes inside','arrive','arrives','approach','approaches'},
 'transfer':{'hand','hands','give','gives','pass','passes','transfer','transfers','hand over','hands over'},
 'pickup':{'pick up','picks up','grab','grabs','lift','lifts','take','takes'},
 'putdown':{'put down','puts down','place','places','set down','sets down'},
 'observe':{'look at','looks at','watch','watches','observe','observes','look down','looks down'},
 'search':{'search','searches','look through','looks through','check','checks'},
 'eat':{'eat','eats','eating','take a bite','takes a bite'},
 'turn':{'turn','turns','turn around','turns around'},
 'react':{'react','reacts','shock','shocked','horror','horrified','terrified','distressed','response'},
 'cut':{'cut','cuts','slice','slices','slit','slits'},
 'wear':{'put on','puts on','wear','wears','change','changes'},
 'open':{'open','opens','unlock','unlocks'},
 'pour':{'pour','pours'},
 'move':{'move','moves','moving','carry','carries','drag','drags'},
}
OBJECTS=('knife','box cutter','sample','papers','cash','money','phone','door','mask','respirator','suit','clothes','gun','handgun','body','barrel','acid','laptop','mineral','food','spill','glass eye','car','taxi')
LOCATIONS=('front door','superlab','lab','office','house','home','diner','bedroom','driveway','phone booth')

class StructuredVisualRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    request_id:str
    required_subject:str|None=None
    secondary_subject:str|None=None
    action_family:str|None=None
    action:str|None=None
    object:str|None=None
    location:str|None=None
    reaction_subject:str|None=None
    reaction_trigger:str|None=None
    temporal_relation:Literal['BEFORE','DURING','AFTER']|None=None
    dialogue_anchor:str|None=None
    event_class:str
    required_visual_state:list[str]=Field(default_factory=list)
    forbidden_visual_state:list[str]=Field(default_factory=list)
    normalized_terms:list[str]=Field(default_factory=list)

def _find_phrase(text,values):
    return next((v for v in sorted(values,key=len,reverse=True) if re.search(r'\b'+re.escape(v)+r'\b',text)),None)

def normalize_request(req:ShotRequest)->StructuredVisualRequest:
    raw=' '.join(filter(None,[req.scene_request.query_text,req.scene_request.visible_action,req.scene_request.requested_event])).lower();expanded=raw
    chars=[]
    for alias,full in ALIASES.items():
        if re.search(r'\b'+re.escape(alias)+r'\b',raw) or full in raw:chars.append(full)
    family=action=None
    for canonical,variants in SYNONYMS.items():
        found=_find_phrase(raw,variants)
        if found:family=canonical;action=canonical;expanded+=' '+canonical;break
    obj=_find_phrase(raw,OBJECTS);loc=_find_phrase(raw,LOCATIONS)
    relation=req.reaction_direction
    if not relation:
        if ' before ' in f' {raw} ':relation='BEFORE'
        elif ' after ' in f' {raw} ':relation='AFTER'
        elif ' during ' in f' {raw} ':relation='DURING'
    forbidden=[]
    if family in {'leave','enter','transfer','pickup','putdown','turn'}:forbidden=['static presence only','before/after state without transition']
    if family in {'cut','pour','open','eat','search'}:forbidden=['object merely visible without requested action']
    return StructuredVisualRequest(request_id=req.scene_request.request_id,required_subject=(req.scene_request.characters_required[0] if req.scene_request.characters_required else (chars[0] if chars else None)),secondary_subject=(chars[1] if len(chars)>1 else None),action_family=family,action=action,object=obj,location=loc,reaction_subject=req.reaction_subject,reaction_trigger=req.reaction_trigger,temporal_relation=relation,dialogue_anchor=req.scene_request.dialogue_clue,event_class=req.scene_request.evidence_class,required_visual_state=[x for x in [family,obj,loc] if x],forbidden_visual_state=forbidden,normalized_terms=sorted(set(re.findall(r'[a-z0-9]+',expanded))))

def region_discovery_allowed(req:ShotRequest)->bool:
    """ABSTAIN/CONTEXTUAL may expose frozen ranked regions, never export authority."""
    return bool(req.sprint3_result.candidates)

def upstream_export_authorized(req:ShotRequest)->bool:
    return req.sprint3_result.decision=='VERIFIED'
