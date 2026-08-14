from __future__ import annotations

import json
import math
import sqlite3
import subprocess
from collections import deque
from enum import Enum
from pathlib import Path
from statistics import median
from typing import Literal

from PIL import Image, ImageFilter, ImageStat
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .confidence_visual_planner import Color
from .hashing import fingerprint, sha256_file

VERSION="production-visual-composer/11.0"
PLAN_VERSION="visual-plan/2.0"


class MediaType(str,Enum): VIDEO="VIDEO"; IMAGE="IMAGE"
class Presentation(str,Enum): VIDEO_PREFERRED="VIDEO_PREFERRED"; IMAGE_PREFERRED="IMAGE_PREFERRED"; EITHER="EITHER"


class Asset(BaseModel):
    model_config=ConfigDict(extra="forbid")
    asset_id:str; media_type:MediaType; source_path:str; source_hash:str; season:int; episode:int
    scene_id:str; shot_ids:list[str]; source_in_ms:int; source_out_ms:int|None=None
    frame_time_ms:int|None=None; derivative_path:str; preview_path:str; provenance:list[dict]=Field(default_factory=list)
    @model_validator(mode="after")
    def invariant(self):
        if self.media_type==MediaType.VIDEO and (self.source_out_ms is None or self.source_out_ms<=self.source_in_ms):raise ValueError("bad video range")
        if self.media_type==MediaType.IMAGE and self.frame_time_ms is None:raise ValueError("image needs frame time")
        return self


class VisualSlot(BaseModel):
    model_config=ConfigDict(extra="forbid")
    slot_id:str; timeline_start_ms:int; timeline_end_ms:int; color:Color; media_type:MediaType
    chosen_asset:Asset|None; alternatives:list[Asset]=Field(default_factory=list); reason:str; review_required:bool; provenance:list[dict]=Field(default_factory=list)
    @model_validator(mode="after")
    def invariant(self):
        if self.timeline_end_ms<=self.timeline_start_ms:raise ValueError("bad timeline range")
        if len(([self.chosen_asset] if self.chosen_asset else [])+self.alternatives)>5:raise ValueError("too many options")
        if self.color==Color.GREEN and self.review_required:raise ValueError("green review mismatch")
        return self


class BeatV2(BaseModel):
    model_config=ConfigDict(extra="forbid")
    beat_id:str;narration:str;timeline_start_ms:int;timeline_end_ms:int;evidence_class:str
    subjects:list[str]=Field(default_factory=list);active_scene:str|None=None;preferred_presentation:Presentation;visual_slots:list[VisualSlot]


class VisualPlanV2(BaseModel):
    model_config=ConfigDict(extra="forbid")
    schema_version:Literal["visual-plan/2.0"]=PLAN_VERSION;composer_version:Literal["production-visual-composer/11.0"]=VERSION
    project:dict;script_hash:str;voiceover_hash:str|None=None;library_scope:list[dict];pacing_profile:Literal["DOCUMENTARY_ANALYSIS"]="DOCUMENTARY_ANALYSIS"
    target_media_mix:dict=Field(default_factory=lambda:{"image":[.35,.50],"video":[.50,.65],"hard_quota":False});beats:list[BeatV2];source_receipt:dict;plan_fingerprint:str


def presentation_for(evidence_class:str,query:str)->Presentation:
    q=query.lower()
    if evidence_class in {"EXACT_DIALOGUE","EXACT_EVENT"} or any(x in q for x in ("walk","paces","hands","eats","react")):return Presentation.VIDEO_PREFERRED
    if evidence_class in {"EDITORIAL_CONTEXT","CHARACTER_CONTEXT"}:return Presentation.IMAGE_PREFERRED
    return Presentation.EITHER


def split_slots(start_ms:int,end_ms:int,semantic_density:int=1)->list[tuple[int,int]]:
    duration=end_ms-start_ms
    count=1 if duration<6500 else (2 if duration<10500 or semantic_density<3 else 3)
    base=duration//count;return [(start_ms+i*base,end_ms if i==count-1 else start_ms+(i+1)*base) for i in range(count)]


def natural_video_ranges(base:dict,shots:list[dict],source_duration:int)->list[dict]:
    by={x["ordinal"]:x for x in shots};lo=int(base["start_shot"][1:]);hi=int(base["end_shot"][1:]);spec=[]
    def add(a,b,shape):
        rows=[by[x] for x in range(a,b+1) if x in by]
        if not rows:return
        start=max(0,rows[0]["start_ms"]);end=min(source_duration,rows[-1]["end_ms"])
        # Natural cut ranges are capped only when an unusually long take would
        # create an unhelpful review option; durations are never forced to 3s.
        if end-start>8000:end=start+8000;shape+="_TRIMMED"
        if end-start>=1500:spec.append({"start_ms":start,"end_ms":end,"shot_ids":[f'S{x["ordinal"]:04d}' for x in rows],"shape":shape})
    add(lo,hi,"COMPLETE_SHOT");add(lo-1,hi,"PREVIOUS_CURRENT");add(lo,hi+1,"CURRENT_NEXT");add(lo-1,hi+1,"THREE_SHOT_CONTEXT")
    a=max(0,base["start_ms"]-800);b=min(source_duration,base["end_ms"]+1500)
    if b-a>=1500:spec.append({"start_ms":a,"end_ms":b,"shot_ids":list(base.get("shot_ids") or [base["start_shot"],base["end_shot"]]),"shape":"BOUNDED_SEMANTIC"})
    unique=[]
    for x in spec:
        if (x["start_ms"],x["end_ms"]) not in {(y["start_ms"],y["end_ms"]) for y in unique}:unique.append(x)
    return unique


def _quality(path:Path)->tuple[float,dict]:
    im=Image.open(path).convert("L");mean=ImageStat.Stat(im).mean[0];edges=im.filter(ImageFilter.FIND_EDGES);sharp=ImageStat.Stat(edges).var[0]
    hist=im.histogram();total=sum(hist);entropy=-sum((v/total)*math.log2(v/total) for v in hist if v)
    reject=mean<18 or mean>240 or sharp<65
    return (-1e9 if reject else sharp+18*entropy-abs(mean-125)*.25),{"brightness":mean,"sharpness":sharp,"entropy":entropy,"rejected":reject}


def select_still(source:Path,source_hash:str,scene_id:str,shot:dict,folder:Path)->dict:
    key=fingerprint(VERSION,"still-quality/1.0",source_hash,shot["ordinal"],shot["start_ms"],shot["end_ms"]);dest=folder/key;manifest=dest/"manifest.json"
    if manifest.exists():return {**json.loads(manifest.read_text()),"cache_hit":True}
    dest.mkdir(parents=True,exist_ok=True);duration=shot["end_ms"]-shot["start_ms"]
    fractions=[.15,.32,.5,.68,.85];items=[]
    for i,f in enumerate(fractions,1):
        ms=shot["start_ms"]+round(duration*f);p=dest/f"F{i:02d}.jpg"
        subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-ss",f"{ms/1000:.3f}","-i",str(source),"-frames:v","1","-vf","scale=1280:-2","-q:v","3","-y",str(p)],check=True)
        score,signals=_quality(p);items.append({"frame_id":f"F{i:02d}","frame_time_ms":ms,"path":str(p.resolve()),"sha256":sha256_file(p),"score":score,"signals":signals})
    valid=[x for x in items if not x["signals"]["rejected"]];chosen=max(valid or items,key=lambda x:x["score"])
    data={"version":"still-image-selector/1.0","scene_id":scene_id,"shot_id":f'S{shot["ordinal"]:04d}',"source_hash":source_hash,"samples":items,"chosen":chosen,"fingerprint":key}
    manifest.write_text(json.dumps(data,indent=2),encoding="utf8");return {**data,"cache_hit":False}


class RepetitionManager:
    def __init__(self,window:int=5):self.recent=deque(maxlen=window)
    def penalty(self,asset:Asset)->float:
        key=(asset.scene_id,tuple(asset.shot_ids),asset.media_type.value);return sum(1 for x in self.recent if x==key)
    def use(self,asset:Asset):self.recent.append((asset.scene_id,tuple(asset.shot_ids),asset.media_type.value))


def ensure_memory_schema(conn:sqlite3.Connection):
    conn.executescript('''CREATE TABLE IF NOT EXISTS editorial_memory_v2(
      id INTEGER PRIMARY KEY, intent_signature TEXT NOT NULL, canonical_event TEXT, approval_type TEXT NOT NULL,
      media_type TEXT NOT NULL, scene_id TEXT NOT NULL, shot_ids_json TEXT NOT NULL, source_in_ms INTEGER NOT NULL,
      source_out_ms INTEGER, frame_time_ms INTEGER, source_hash TEXT NOT NULL, selected_asset_json TEXT NOT NULL,
      rejected_assets_json TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(intent_signature,approval_type,source_hash));
    CREATE TABLE IF NOT EXISTS visual_review_audit(
      id INTEGER PRIMARY KEY,project_id TEXT NOT NULL,slot_id TEXT NOT NULL,decision TEXT NOT NULL,selected_asset_id TEXT,
      elapsed_ms INTEGER,details_json TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS green_false_positive_audit(
      id INTEGER PRIMARY KEY,project_id TEXT NOT NULL,slot_id TEXT NOT NULL,asset_id TEXT,reason TEXT NOT NULL,
      invalidated_memory_ids_json TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);''')
    conn.commit()


def persist_review(conn:sqlite3.Connection,plan:VisualPlanV2,slot_id:str,decision:str,asset_id:str|None,elapsed_ms:int|None=None,approval_type:str|None=None):
    ensure_memory_schema(conn);slot=next(s for b in plan.beats for s in b.visual_slots if s.slot_id==slot_id);assets=([slot.chosen_asset] if slot.chosen_asset else [])+slot.alternatives;selected=next((a for a in assets if a.asset_id==asset_id),None)
    if decision=="MARK_WRONG":
        rows=conn.execute("select id from editorial_memory_v2 where active=1 and selected_asset_json like ?",(f'%"asset_id": "{asset_id}"%',)).fetchall();ids=[r[0] for r in rows]
        if ids:conn.executemany("update editorial_memory_v2 set active=0 where id=?",[(x,) for x in ids])
        conn.execute("insert into green_false_positive_audit(project_id,slot_id,asset_id,reason,invalidated_memory_ids_json) values(?,?,?,?,?)",(plan.project["project_id"],slot_id,asset_id,"Human marked Green wrong",json.dumps(ids)))
    conn.execute("insert into visual_review_audit(project_id,slot_id,decision,selected_asset_id,elapsed_ms,details_json) values(?,?,?,?,?,?)",(plan.project["project_id"],slot_id,decision,asset_id,elapsed_ms,json.dumps({"color":slot.color.value})))
    if selected and approval_type:
        allowed={"EXACT_EVENT_APPROVAL","EXACT_DIALOGUE_APPROVAL","CONTEXTUAL_VISUAL_APPROVAL"}
        if approval_type not in allowed:raise ValueError("invalid approval type")
        conn.execute('''insert or replace into editorial_memory_v2(intent_signature,canonical_event,approval_type,media_type,scene_id,shot_ids_json,source_in_ms,source_out_ms,frame_time_ms,source_hash,selected_asset_json,rejected_assets_json,active) values(?,?,?,?,?,?,?,?,?,?,?,?,1)''',(fingerprint(slot_id,plan.script_hash),None,approval_type,selected.media_type.value,selected.scene_id,json.dumps(selected.shot_ids),selected.source_in_ms,selected.source_out_ms,selected.frame_time_ms,selected.source_hash,selected.model_dump_json(),json.dumps([a.asset_id for a in assets if a.asset_id!=selected.asset_id])))
    conn.commit()
