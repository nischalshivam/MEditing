from __future__ import annotations

import json, re, sqlite3, subprocess, time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .db import connect
from .hashing import fingerprint, sha256_file
from .real_script_v12 import discover, episode_hints, proxy_image, proxy_video, words

VERSION = "sprint13-repair/1.0"
CALLBACKS = re.compile(r"\b(that|the same|earlier|the money|the bills|that failure|that refusal|this whole story|that skill|it|her skill|the trap)\b", re.I)
EP_RE = re.compile(r"S(\d{2})E(\d{2})", re.I)

def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")

def compile_v2(beats: list[dict]) -> list[dict]:
    """Resolve callbacks from the complete ordered script without beat-specific rules."""
    out, recent_events, recent_subjects, recent_locations = [], [], [], []
    for beat in beats:
        item = dict(beat); event = beat.get("canonical_event_id")
        concrete = bool(event and not str(event).startswith("NONE"))
        callback = bool(CALLBACKS.search(beat.get("exact_narration", ""))) or beat.get("active_scene_relation") != "NEW_EVENT"
        anchors = [event] if concrete else (recent_events[:3] if callback else [])
        subjects = list(dict.fromkeys((beat.get("primary_subjects") or []) + (recent_subjects[:3] if callback else [])))
        locations = list(dict.fromkeys((beat.get("location_clues") or []) + (recent_locations[:2] if callback else [])))
        item.update({
            "context_anchor_event_ids": anchors,
            "bridge_event_ids": [x for x in recent_events[:3] if x not in anchors],
            "fallback_subjects": subjects,
            "fallback_locations": locations,
            "callback_relation": "CONTEXTUAL_CALLBACK" if callback else "NEW_EVENT",
            "reuse_previous_event_visual": bool(callback and anchors),
            "reuse_prior_project_visual": True,
            "literal_event_required": beat.get("evidence_class") in {"EXACT_EVENT", "EXACT_DIALOGUE"},
        })
        out.append(item)
        if concrete: recent_events = [event] + [x for x in recent_events if x != event]
        if beat.get("primary_subjects"): recent_subjects = list(dict.fromkeys(beat["primary_subjects"] + recent_subjects))
        if beat.get("location_clues"): recent_locations = list(dict.fromkeys(beat["location_clues"] + recent_locations))
    return out

def repair_set(audit: dict) -> list[dict]:
    # NONE_GOOD is the sole authority. ORANGE_UNRESOLVED is not a second queue.
    return [x for x in audit["decisions"] if x["decision"] == "NONE_GOOD"]

def taxonomy(decision: dict, clue: dict) -> str:
    options = decision.get("all_presented_options") or []
    if decision["original_color"] == "ORANGE_UNRESOLVED": return "ORANGE_CONTEXT_FAILURE"
    if clue.get("evidence_class") in {"CHARACTER_CONTEXT"} and not options: return "CHARACTER_VISUAL_MISSING"
    if clue.get("evidence_class") in {"EDITORIAL_CONTEXT", "CHARACTER_CONTEXT"}: return "CLUE_CONTEXT_ANCHOR_MISSING"
    if not options: return "MISSING_V2_SCENE_ATLAS"
    eps = set(episode_hints(clue)); offered = {str(x.get("episode_code")) for x in options}
    if eps and not (eps & offered): return "WRONG_EPISODE_ROUTING"
    return "RIGHT_EPISODE_WRONG_CUE"

def _cue_candidates(conn, media: dict, clue: dict, limit: int = 8) -> list[dict]:
    terms = words(" ".join((clue.get("search_clues") or []) + (clue.get("dialogue_clues") or []) +
                           (clue.get("required_visible_facts") or []) + (clue.get("objects") or []) +
                           [clue.get("visual_intent", ""), clue.get("exact_narration", "")]))
    rows = [dict(x) for x in conn.execute("select start_ms,end_ms,text from cue where media_id=?", (media["id"],))]
    scored=[]
    for row in rows:
        overlap = terms & words(row["text"])
        if overlap: scored.append((len(overlap), row))
    return [x[1] for x in sorted(scored, key=lambda x:(-x[0], x[1]["start_ms"]))[:limit]]

def _asset_from_range(clue: dict, media: dict, episode: str, sha: str, a: int, b: int,
                      out: Path, ordinal: int, cue: dict | None, media_type: str = "VIDEO") -> dict:
    a=max(0,int(a)); b=max(a+1500,int(b)); src=Path(media["path"])
    if media_type == "IMAGE":
        t=(a+b)//2; preview,_=proxy_image(src,sha,t,out/"previews/images")
    else:
        t=None; preview,_=proxy_video(src,sha,a,b,out/"previews/video")
    return {"asset_id":f"S13_{clue['beat_id']}_{ordinal:02d}","media_type":media_type,"source_path":str(src),
            "source_hash":sha,"episode_code":episode,"source_in_ms":a if media_type=="VIDEO" else None,
            "source_out_ms":b if media_type=="VIDEO" else None,"frame_time_ms":t,"preview_path":str(preview.resolve()),
            "provenance":[{"authority":"REPAIR_SCOPED_LOCAL_SOURCE","cue_text":cue.get("text") if cue else None,
                           "cue_start_ms":cue.get("start_ms") if cue else None,"literal_visual_status":"UNVERIFIED_REVIEW_REQUIRED"}]}

def _context_bank(audit: dict, clue_by_beat: dict) -> list[dict]:
    bank=[]
    for d in audit["decisions"]:
        if d["decision"] != "PROJECT_SLOT_APPROVAL": continue
        clue=clue_by_beat[d["beat_id"]]
        chosen=next(x for x in d["all_presented_options"] if x["asset_id"]==d["chosen_asset_id"])
        bank.append({"slot_id":d["slot_id"],"beat_id":d["beat_id"],"asset":chosen,
                     "event_id":clue.get("canonical_event_id"),"subjects":clue.get("primary_subjects") or [],
                     "locations":clue.get("location_clues") or [],"objects":clue.get("objects") or []})
    return bank

def _context_options(clue: dict, bank: list[dict], count: int = 3) -> list[dict]:
    desired_events=set(clue.get("context_anchor_event_ids") or []) | ({clue.get("canonical_event_id")} if clue.get("canonical_event_id") else set())
    desired_sub=set(clue.get("fallback_subjects") or clue.get("primary_subjects") or [])
    desired_loc=set(clue.get("fallback_locations") or clue.get("location_clues") or [])
    ranked=[]
    for row in bank:
        score=7*bool(row["event_id"] in desired_events)+3*len(desired_sub&set(row["subjects"]))+2*len(desired_loc&set(row["locations"]))
        if score: ranked.append((score,row))
    chosen=[]; seen=set()
    for _,row in sorted(ranked,key=lambda x:(-x[0],x[1]["slot_id"])):
        asset=dict(row["asset"]); key=(asset.get("source_hash"),asset.get("source_in_ms"),asset.get("frame_time_ms"))
        if key in seen: continue
        seen.add(key); asset["asset_id"]="S13_%s_CTX_%02d"%(clue["beat_id"],len(chosen)+1)
        asset["provenance"]=(asset.get("provenance") or [])+[{"authority":"PROJECT_SLOT_APPROVAL_REUSE","approved_slot_id":row["slot_id"],"literal_visual_status":"CONTEXTUAL_ONLY"}]
        chosen.append(asset)
        if len(chosen)>=count: break
    return chosen

def build(root: Path, clue_path: Path, legacy_db: Path) -> dict:
    out=root/"runtime/sprint13_repair"; out.mkdir(parents=True,exist_ok=True)
    s12=root/"runtime/sprint12_real_script"; audit_path=s12/"audit/SPRINT12_HUMAN_AUDIT.json"; receipt_path=s12/"audit/SPRINT12_HUMAN_AUDIT_RECEIPT.json"
    audit=json.loads(audit_path.read_text(encoding="utf-8")); receipt=json.loads(receipt_path.read_text(encoding="utf-8"))
    if sha256_file(audit_path)!=receipt["audit_sha256"]: raise ValueError("frozen audit hash mismatch")
    repairs=repair_set(audit)
    if (len(audit["decisions"]),sum(x["decision"]=="PROJECT_SLOT_APPROVAL" for x in audit["decisions"]),len(repairs))!=(59,41,18):
        raise ValueError("frozen audit persisted counts differ from 59/41/18")
    clue_doc=json.loads(clue_path.read_text(encoding="utf-8-sig")); compiled=compile_v2(clue_doc["beats"]); clues={x["beat_id"]:x for x in compiled}
    _write(out/"CLUE_SCRIPT_V2.json",{"version":"production-clue-compiler/2.0","beats":compiled,"source_sha256":sha256_file(clue_path)})
    repair_receipt={"version":"repair-set/1.0","frozen_audit_sha256":sha256_file(audit_path),"count":18,
                    "slots":[{"slot_id":x["slot_id"],"beat_id":x["beat_id"],"previous_state":x["decision"],"original_color":x["original_color"]} for x in repairs]}
    repair_receipt["fingerprint"]=fingerprint(json.dumps(repair_receipt,sort_keys=True)); _write(out/"REPAIR_SET_RECEIPT.json",repair_receipt)
    taxonomy_rows=[{"slot_id":d["slot_id"],"beat_id":d["beat_id"],"failure":taxonomy(d,clues[d["beat_id"]]),
                    "old_option_count":len(d.get("all_presented_options") or []),"old_options":d.get("all_presented_options") or []} for d in repairs]
    _write(out/"REPAIR_FAILURE_TAXONOMY.json",{"version":"repair-taxonomy/1.0","items":taxonomy_rows,"counts":dict(Counter(x["failure"] for x in taxonomy_rows))})
    bank=_context_bank(audit,clues); legacy=sqlite3.connect(f"file:{legacy_db.as_posix()}?mode=ro",uri=True); legacy.row_factory=sqlite3.Row
    needed=sorted({e for d in repairs for e in episode_hints(clues[d["beat_id"]])})
    coverage=discover(legacy,needed); available={x["episode"]:x["matches"][0] for x in coverage if x["status"]=="FOUND_UNIQUE"}
    atlas=[]
    for ep,media in available.items():
        cues=[dict(x) for x in legacy.execute("select idx,start_ms,end_ms,text from cue where media_id=? order by idx",(media["id"],))]
        source_sha=sha256_file(Path(media["path"]))
        atlas_manifest={"version":"repair-scoped-episode-atlas/2.0","episode":ep,"source_path":media["path"],"source_sha256":source_sha,
                        "subtitle_path":media.get("sub_path"),"subtitle_sync_status":media.get("sync_conf"),"cue_count":len(cues),
                        "cue_neighborhoods":[{"scene_region_id":f"{ep}_CR{i+1:04d}","start_ms":x["start_ms"],"end_ms":x["end_ms"],"dialogue":x["text"]} for i,x in enumerate(cues)],
                        "scope":"REPAIR_ONLY_DETERMINISTIC_CUE_ATLAS","semantic_claim":"NONE_UNTIL_HUMAN_REVIEW"}
        ap=out/"atlases"/ep/"ATLAS_V2.json"; _write(ap,atlas_manifest); atlas.append({"episode":ep,"path":str(ap.resolve()),"sha256":sha256_file(ap),"source_sha256":source_sha,"cue_regions":len(cues),"status":"BUILT_REPAIR_SCOPED"})
    _write(out/"V2_ATLAS_BUILD_RECEIPT.json",{"version":"v2-atlas-build-receipt/1.0","episodes":atlas,"full_rich_scene_atlas_count":0,
           "note":"Permanent repair-scoped source/subtitle cue atlases built. They do not claim AI narrative semantics or physical-shot completeness."})
    plan_items=[]
    for d in repairs:
        clue=clues[d["beat_id"]]; options=[]; contextual=clue["evidence_class"] in {"EDITORIAL_CONTEXT","CHARACTER_CONTEXT"}
        if contextual: options=_context_options(clue,bank,3)
        for ep in episode_hints(clue):
            media=available.get(ep)
            if not media: continue
            sha=next(x["source_sha256"] for x in atlas if x["episode"]==ep)
            old={(x.get("source_in_ms"),x.get("source_out_ms"),x.get("frame_time_ms")) for x in d.get("all_presented_options") or []}
            for cue in _cue_candidates(legacy,media,clue):
                a=max(0,cue["start_ms"]-2500);b=cue["end_ms"]+4500
                if any(abs((oa or -999999)-a)<2500 for oa,_,_ in old): continue
                typ="IMAGE" if contextual and len(options)%2 else "VIDEO"
                options.append(_asset_from_range(clue,media,ep,sha,a,b,out,len(options)+1,cue,typ))
                if len(options)>=5:break
            if len(options)>=5:break
        options=options[:5]
        plan_items.append({"slot_id":d["slot_id"],"beat_id":d["beat_id"],"narration":d["narration"],"evidence_class":d["evidence_class"],
                           "status":"ORANGE" if contextual else "YELLOW","failure_class":next(x["failure"] for x in taxonomy_rows if x["slot_id"]==d["slot_id"]),
                           "required_visible_facts":clue.get("required_visible_facts") or [],"not_sufficient_facts":clue.get("not_sufficient_facts") or [],
                           "subjects":clue.get("fallback_subjects") or [],"context_anchor_event_ids":clue.get("context_anchor_event_ids") or [],
                           "options":options,"analysis":"CONTEXTUAL_NOT_LITERAL" if contextual else "REVIEW_REQUIRED_EXACT_HYPOTHESIS"})
    legacy.close(); plan={"version":"repaired-visual-plan/13.0","project_fingerprint":audit["project_fingerprint"],"audit_receipt_sha256":sha256_file(receipt_path),"items":plan_items}
    plan["fingerprint"]=fingerprint(json.dumps(plan,sort_keys=True)); _write(out/"REPAIRED_VISUAL_PLAN.json",plan)
    db=connect(root/"runtime/scene_brain.db")
    for d in audit["decisions"]:
        if d["decision"]=="PROJECT_SLOT_APPROVAL":
            existing=db.execute("select decision_json from project_slot_decisions where project_fingerprint=? and slot_id=?",(audit["project_fingerprint"],d["slot_id"])).fetchone()
            payload=json.dumps(d,sort_keys=True)
            if existing and existing[0]!=payload: raise ValueError(f"accepted lock collision: {d['slot_id']}")
            db.execute("insert or ignore into project_slot_decisions(project_fingerprint,slot_id,decision_type,asset_id,decision_json,audit_receipt_sha256,locked) values(?,?,?,?,?,?,1)",
                       (audit["project_fingerprint"],d["slot_id"],"PROJECT_SLOT_APPROVAL",d["chosen_asset_id"],payload,sha256_file(receipt_path)))
    db.commit(); db.close()
    merged={"version":"merged-project-state/13.0","project_fingerprint":audit["project_fingerprint"],"locked_accepted_count":41,"repair_pending_count":18,
            "slots":[{"slot_id":d["slot_id"],"state":"LOCKED_ACCEPTED","decision":d} for d in audit["decisions"] if d["decision"]=="PROJECT_SLOT_APPROVAL"]+
                    [{"slot_id":x["slot_id"],"state":"REPAIR_PENDING","repair_item":x} for x in plan_items]}
    _write(out/"MERGED_PROJECT_STATE.json",merged)
    metrics={"frozen_accepted":41,"repair_count":18,"repair_options_generated":sum(len(x["options"]) for x in plan_items),"repair_slots_without_options":sum(not x["options"] for x in plan_items),
             "v2_repair_scoped_episode_atlases":len(atlas),"full_rich_v2_atlases":0,"api":{"calls":0,"tokens":0,"cost_usd":0},"build_seconds":0}
    _write(out/"metrics.json",metrics); return {"plan":plan,"metrics":metrics,"receipt":repair_receipt}
