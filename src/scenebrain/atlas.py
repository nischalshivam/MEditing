from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from .atlas_models import WindowResponse
from .hashing import fingerprint, sha256_file

FREEZE_VERSION="scene-input-freeze/1.0"
WINDOW_VERSION="scene-window/1.0"


def shot_code(ordinal: int) -> str: return f"S{ordinal:04d}"


def freeze_inputs(conn, source_id: int, root: Path) -> dict:
    source=conn.execute("SELECT * FROM source_files WHERE id=?",(source_id,)).fetchone()
    track=conn.execute("SELECT * FROM subtitle_tracks WHERE source_file_id=? AND selected=1",(source_id,)).fetchone()
    if not source or not track or track["sync_status"] not in {"VERIFIED","VERIFIED_WITH_OFFSET"}: raise ValueError("verified source/subtitle required")
    shots=conn.execute("SELECT * FROM shots WHERE source_file_id=? ORDER BY ordinal",(source_id,)).fetchall()
    frames=conn.execute("SELECT k.*,s.ordinal FROM keyframes k JOIN shots s ON s.id=k.shot_id WHERE s.source_file_id=? ORDER BY s.ordinal",(source_id,)).fetchall()
    if len(shots)!=460 or len(frames)!=460: raise ValueError("expected frozen 460-shot/keyframe S04E01 foundation")
    cues=conn.execute("SELECT cue_index,start_ms,end_ms,normalized_text FROM subtitle_cues WHERE track_id=? ORDER BY cue_index",(track["id"],)).fetchall()
    freezes=[dict(x) for x in conn.execute("SELECT name,questions_path,questions_sha256,source_manifest_sha256,question_count FROM benchmark_freezes ORDER BY id")]
    manifest={"freeze_version":FREEZE_VERSION,"source":{"id":source_id,"path":source["path"],"bytes":source["bytes"],"sha256":source["sha256"]},
      "subtitle":{"track_id":track["id"],"path":track["path"],"sha256":track["sha256"],"identity_status":track["identity_status"],
        "sync_status":track["sync_status"],"sync_offset_ms":track["sync_offset_ms"],"evidence":json.loads(track["selection_evidence_json"])},
      "cue_manifest":[dict(x) for x in cues],"shots":[{"id":x["id"],"code":shot_code(x["ordinal"]),"ordinal":x["ordinal"],"start_ms":x["start_ms"],"end_ms":x["end_ms"],"input_fingerprint":x["input_fingerprint"]} for x in shots],
      "keyframes":[{"shot_id":x["shot_id"],"code":shot_code(x["ordinal"]),"timestamp_ms":x["timestamp_ms"],"path":x["path"],"sha256":x["sha256"],"extraction_fingerprint":x["extraction_fingerprint"]} for x in frames],
      "benchmark_receipts":freezes}
    fp=fingerprint(json.dumps(manifest,sort_keys=True,separators=(",",":")))
    manifest["input_fingerprint"]=fp
    out=root/"runtime"/"scene_atlas"/"freezes"/f"s04e01_{fp[:16]}.json"; out.parent.mkdir(parents=True,exist_ok=True)
    raw=json.dumps(manifest,indent=2,ensure_ascii=False); out.write_text(raw,encoding="utf-8")
    digest=sha256_file(out)
    with conn:
        conn.execute("INSERT OR IGNORE INTO scene_input_freezes(source_file_id,freeze_version,input_fingerprint,manifest_path,manifest_sha256) VALUES(?,?,?,?,?)",
          (source_id,FREEZE_VERSION,fp,str(out.resolve()),digest))
    freeze_id=conn.execute("SELECT id FROM scene_input_freezes WHERE input_fingerprint=?",(fp,)).fetchone()[0]
    return {"freeze_id":freeze_id,"manifest_path":str(out.resolve()),"manifest_sha256":digest,"input_fingerprint":fp,"shots":460,"keyframes":460,"cues":len(cues)}


def _make_sheet(frame_rows, output: Path, cols: int=5, tile_w: int=320, tile_h: int=190) -> None:
    rows=(len(frame_rows)+cols-1)//cols; sheet=Image.new("RGB",(cols*tile_w,rows*tile_h),(18,18,18)); draw=ImageDraw.Draw(sheet); font=ImageFont.load_default(size=20)
    for i,row in enumerate(frame_rows):
        image=Image.open(row["path"]).convert("RGB"); image.thumbnail((tile_w,tile_h-28))
        x=(i%cols)*tile_w+(tile_w-image.width)//2; y=(i//cols)*tile_h+28
        sheet.paste(image,(x,y)); draw.rectangle(((i%cols)*tile_w,(i//cols)*tile_h,(i%cols+1)*tile_w,(i//cols)*tile_h+28),fill=(0,0,0))
        draw.text(((i%cols)*tile_w+8,(i//cols)*tile_h+4),shot_code(row["ordinal"]),fill=(255,220,50),font=font)
    output.parent.mkdir(parents=True,exist_ok=True); sheet.save(output,"JPEG",quality=88,optimize=True)


def build_windows(conn, source_id: int, freeze_id: int, root: Path, target_ms=90000, min_shots=15, max_shots=30, overlap=5) -> list[dict]:
    freeze=conn.execute("SELECT * FROM scene_input_freezes WHERE id=?",(freeze_id,)).fetchone(); shots=conn.execute("SELECT * FROM shots WHERE source_file_id=? ORDER BY ordinal",(source_id,)).fetchall()
    keyframes={r["shot_id"]:r for r in conn.execute("SELECT k.*,s.ordinal FROM keyframes k JOIN shots s ON s.id=k.shot_id WHERE s.source_file_id=?",(source_id,))}
    track=conn.execute("SELECT id FROM subtitle_tracks WHERE source_file_id=? AND selected=1",(source_id,)).fetchone()
    windows=[]; start=0; number=1
    while start<len(shots):
        end=start
        while end+1<len(shots) and end-start+1<max_shots and ((shots[end]["end_ms"]-shots[start]["start_ms"]<target_ms) or end-start+1<min_shots): end+=1
        subset=shots[start:end+1]; first,last=subset[0],subset[-1]; wid=f"S04E01_W{number:03d}"
        cues=[dict(x) for x in conn.execute("SELECT cue_index,start_ms,end_ms,raw_text FROM subtitle_cues WHERE track_id=? AND end_ms>=? AND start_ms<=? ORDER BY cue_index",(track["id"],first["start_ms"],last["end_ms"]))]
        frame_rows=[keyframes[s["id"]] for s in subset]; sheet=root/"runtime"/"scene_atlas"/"windows"/wid/"contact_sheet.jpg"; _make_sheet(frame_rows,sheet)
        package={"schema_version":WINDOW_VERSION,"window_id":wid,"freeze_fingerprint":freeze["input_fingerprint"],"title":"Breaking Bad","season":4,"episode":1,
          "shots":[{"shot_id":shot_code(s["ordinal"]),"db_id":s["id"],"ordinal":s["ordinal"]} for s in subset],"dialogue":cues,
          "contact_sheet":{"path":str(sheet.resolve()),"sha256":sha256_file(sheet)}}
        package["input_fingerprint"]=fingerprint(json.dumps(package,sort_keys=True,separators=(",",":")),"scene-atlas-prompt/1.0","scene-atlas-schema/1.0")
        ppath=sheet.parent/"package.json"; ppath.write_text(json.dumps(package,indent=2,ensure_ascii=False),encoding="utf-8")
        with conn:
            conn.execute("""INSERT OR REPLACE INTO scene_analysis_windows(source_file_id,freeze_id,window_id,first_shot_id,last_shot_id,shot_ids_json,dialogue_json,package_path,package_sha256,input_fingerprint,status)
              VALUES(?,?,?,?,?,?,?,?,?,?,COALESCE((SELECT status FROM scene_analysis_windows WHERE window_id=?),'PENDING'))""",
              (source_id,freeze_id,wid,first["id"],last["id"],json.dumps([s["id"] for s in subset]),json.dumps(cues),str(ppath.resolve()),sha256_file(ppath),package["input_fingerprint"],wid))
        windows.append(package)
        if end==len(shots)-1: break
        start=max(start+1,end-overlap+1); number+=1
    return windows


def validate_response(package: dict, raw: dict) -> WindowResponse:
    parsed=WindowResponse.model_validate(raw)
    if parsed.window_id!=package["window_id"]: raise ValueError("window_id mismatch")
    allowed=[x["shot_id"] for x in package["shots"]]; pos={x:i for i,x in enumerate(allowed)}; occupied=set()
    for scene in parsed.scenes:
        if scene.start_shot not in pos or scene.end_shot not in pos: raise ValueError("invented or out-of-window shot id")
        if pos[scene.start_shot]>pos[scene.end_shot]: raise ValueError("reversed scene boundary")
        span=set(allowed[pos[scene.start_shot]:pos[scene.end_shot]+1])
        if occupied & span: raise ValueError("overlapping scene proposals")
        occupied |= span
        evidence=[]
        for x in scene.characters+[scene.location]+scene.important_objects: evidence.extend(x.evidence_shots)
        for x in [scene.main_event]+scene.visible_actions+scene.uncertainties: evidence.extend(x.evidence_shots)
        if any(x not in span for x in evidence): raise ValueError("semantic evidence outside scene span")
    if occupied != set(allowed): raise ValueError("scene proposals contain gaps or omit window shots")
    return parsed


def stitch_atlas(conn, source_id: int, freeze_fingerprint: str, root: Path) -> dict:
    shots=conn.execute("SELECT * FROM shots WHERE source_file_id=? ORDER BY ordinal",(source_id,)).fetchall(); by_id={s["id"]:s for s in shots}
    proposals=[]
    for row in conn.execute("""SELECT p.*,r.model,r.prompt_version,r.id run_id FROM scene_window_proposals p
      JOIN scene_analysis_runs r ON r.id=p.run_id JOIN scene_analysis_windows w ON w.id=r.window_id
      WHERE w.source_file_id=? AND r.status='SUCCESS'""",(source_id,)):
        item=json.loads(row["raw_json"]); item.update({"proposal_id":row["id"],"start_db":row["start_shot_id"],"end_db":row["end_shot_id"],"model":row["model"],"prompt_version":row["prompt_version"]}); proposals.append(item)
    if not proposals: raise ValueError("no validated proposals")
    boundaries=[]
    for left,right in zip(shots,shots[1:]):
        votes=sum(p["end_db"]==left["id"] and p["boundary_status"] in {"SUPPORTED","UNKNOWN_START"} for p in proposals)
        crosses=sum(by_id[p["start_db"]]["ordinal"]<=left["ordinal"] and by_id[p["end_db"]]["ordinal"]>=right["ordinal"] for p in proposals)
        if votes>crosses: boundaries.append(left["ordinal"])
    spans=[]; start=0
    for end in [*boundaries,shots[-1]["ordinal"]]:
        if end>=start: spans.append((start,end)); start=end+1
    atlas_fp=fingerprint(freeze_fingerprint,json.dumps(boundaries),"stitcher/1.0")
    with conn:
        old=[r[0] for r in conn.execute("SELECT id FROM scenes WHERE source_file_id=?",(source_id,))]
        for sid in old: conn.execute("DELETE FROM scenes WHERE id=?",(sid,))
        for n,(a,b) in enumerate(spans,1):
            candidates=[]
            for p in proposals:
                pa,pb=by_id[p["start_db"]]["ordinal"],by_id[p["end_db"]]["ordinal"]
                overlap=max(0,min(b,pb)-max(a,pa)+1)
                if overlap: candidates.append((overlap/(b-a+1),overlap,p))
            best=max(candidates,key=lambda x:(x[0],x[1]))[2] if candidates else None
            best_coverage=max((x[0] for x in candidates),default=0.0)
            status="RESOLVED" if best and best_coverage>=0.5 else "UNRESOLVED"
            boundary=best["boundary_status"] if best else "UNKNOWN_BOTH"; stype=best["scene_type"] if best else "transition"; summary=best["visual_summary"] if best else "UNRESOLVED physical-shot range"
            cur=conn.execute("INSERT INTO scenes(source_file_id,scene_uid,ordinal,start_shot_id,end_shot_id,start_ms,end_ms,boundary_status,scene_type,visual_summary,atlas_fingerprint,analysis_status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
              (source_id,f"S04E01_SC{n:03d}",n,shots[a]["id"],shots[b]["id"],shots[a]["start_ms"],shots[b]["end_ms"],boundary,stype,summary,atlas_fp,status)); scene_id=cur.lastrowid
            conn.executemany("INSERT INTO scene_shots(scene_id,shot_id,ordinal,state) VALUES(?,?,?,?)",[(scene_id,shots[i]["id"],i-a,"COVERED" if status=="RESOLVED" else "UNRESOLVED") for i in range(a,b+1)])
            if best:
                prov=json.dumps({"proposal_id":best["proposal_id"],"model":best["model"],"prompt_version":best["prompt_version"]})
                conn.execute("INSERT INTO scene_provenance(scene_id,proposal_id) VALUES(?,?)",(scene_id,best["proposal_id"]))
                for x in best["characters"]: conn.execute("INSERT INTO scene_characters(scene_id,name,evidence_shot_ids_json,provenance_json) VALUES(?,?,?,?)",(scene_id,x["name"],json.dumps(x["evidence_shots"]),prov))
                conn.execute("INSERT INTO scene_locations(scene_id,name,evidence_shot_ids_json,provenance_json) VALUES(?,?,?,?)",(scene_id,best["location"]["name"],json.dumps(best["location"]["evidence_shots"]),prov))
                conn.execute("INSERT INTO scene_semantics(scene_id,main_event,evidence_shot_ids_json,provenance_json) VALUES(?,?,?,?)",(scene_id,best["main_event"]["description"],json.dumps(best["main_event"]["evidence_shots"]),prov))
                for x in best["visible_actions"]: conn.execute("INSERT INTO scene_actions(scene_id,description,evidence_shot_ids_json,provenance_json) VALUES(?,?,?,?)",(scene_id,x["description"],json.dumps(x["evidence_shots"]),prov))
                for x in best["important_objects"]: conn.execute("INSERT INTO scene_objects(scene_id,name,evidence_shot_ids_json,provenance_json) VALUES(?,?,?,?)",(scene_id,x["name"],json.dumps(x["evidence_shots"]),prov))
                for x in best["uncertainties"]: conn.execute("INSERT INTO scene_uncertainties(scene_id,code,description,evidence_shot_ids_json,provenance_json) VALUES(?,?,?,?,?)",(scene_id,x["code"],x["description"],json.dumps(x["evidence_shots"]),prov))
                if stype!="normal": conn.execute("INSERT INTO scene_flags(scene_id,flag,provenance_json) VALUES(?,?,?)",(scene_id,stype,prov))
    cards=[]
    for scene in conn.execute("SELECT * FROM scenes WHERE source_file_id=? ORDER BY ordinal",(source_id,)):
        sid=scene["id"]
        cards.append({"scene_id":scene["scene_uid"],"episode":"S04E01","start_ms":scene["start_ms"],"end_ms":scene["end_ms"],
          "start_shot":shot_code(by_id[scene["start_shot_id"]]["ordinal"]),"end_shot":shot_code(by_id[scene["end_shot_id"]]["ordinal"]),
          "shot_count":by_id[scene["end_shot_id"]]["ordinal"]-by_id[scene["start_shot_id"]]["ordinal"]+1,
          "characters":[r[0] for r in conn.execute("SELECT name FROM scene_characters WHERE scene_id=?",(sid,))],
          "location":next((r[0] for r in conn.execute("SELECT name FROM scene_locations WHERE scene_id=?",(sid,))),"UNKNOWN_LOCATION"),
          "main_event":next((r[0] for r in conn.execute("SELECT main_event FROM scene_semantics WHERE scene_id=?",(sid,))),"UNKNOWN_EVENT"),
          "actions":[r[0] for r in conn.execute("SELECT description FROM scene_actions WHERE scene_id=?",(sid,))],"objects":[r[0] for r in conn.execute("SELECT name FROM scene_objects WHERE scene_id=?",(sid,))],
          "scene_type":scene["scene_type"],"boundary_status":scene["boundary_status"],"analysis_status":scene["analysis_status"],"visual_summary":scene["visual_summary"]})
    out=root/"runtime"/"scene_atlas"/"S04E01_SCENE_CARDS.json"; out.write_text(json.dumps(cards,indent=2,ensure_ascii=False),encoding="utf-8")
    return {"atlas_fingerprint":atlas_fp,"scene_count":len(cards),"covered_shots":sum(x["shot_count"] for x in cards),"unresolved_scenes":sum(x["analysis_status"]!="RESOLVED" for x in cards),"cards_path":str(out.resolve())}


def build_scene_inspection(conn, source_id: int, root: Path) -> dict:
    base=root/"runtime"/"scene_atlas"/"inspection"; base.mkdir(parents=True,exist_ok=True); count=0
    track=conn.execute("SELECT id FROM subtitle_tracks WHERE source_file_id=? AND selected=1",(source_id,)).fetchone()[0]
    for scene in conn.execute("SELECT * FROM scenes WHERE source_file_id=? ORDER BY ordinal",(source_id,)):
        frames=conn.execute("""SELECT k.path,s.ordinal FROM scene_shots ss JOIN shots s ON s.id=ss.shot_id JOIN keyframes k ON k.shot_id=s.id
          WHERE ss.scene_id=? ORDER BY ss.ordinal""",(scene["id"],)).fetchall()
        if len(frames)>20:
            indices=sorted({round(i*(len(frames)-1)/19) for i in range(20)}); frames=[frames[i] for i in indices]
        folder=base/scene["scene_uid"]; sheet=folder/"contact_sheet.jpg"; _make_sheet(frames,sheet,cols=5)
        dialogue=[dict(x) for x in conn.execute("SELECT cue_index,start_ms,end_ms,raw_text FROM subtitle_cues WHERE track_id=? AND end_ms>=? AND start_ms<=? ORDER BY cue_index",(track,scene["start_ms"],scene["end_ms"]))]
        card={"scene_id":scene["scene_uid"],"episode":"S04E01","derived_start_ms":scene["start_ms"],"derived_end_ms":scene["end_ms"],
          "start_shot":shot_code(conn.execute('SELECT ordinal FROM shots WHERE id=?',(scene['start_shot_id'],)).fetchone()[0]),
          "end_shot":shot_code(conn.execute('SELECT ordinal FROM shots WHERE id=?',(scene['end_shot_id'],)).fetchone()[0]),
          "scene_type":scene["scene_type"],"boundary_status":scene["boundary_status"],"analysis_status":scene["analysis_status"],
          "visual_summary":scene["visual_summary"],"characters":[r[0] for r in conn.execute('SELECT name FROM scene_characters WHERE scene_id=?',(scene['id'],))],
          "location":next((r[0] for r in conn.execute('SELECT name FROM scene_locations WHERE scene_id=?',(scene['id'],))),'UNKNOWN_LOCATION'),
          "main_event":next((r[0] for r in conn.execute('SELECT main_event FROM scene_semantics WHERE scene_id=?',(scene['id'],))),'UNKNOWN_EVENT'),
          "actions":[r[0] for r in conn.execute('SELECT description FROM scene_actions WHERE scene_id=?',(scene['id'],))],
          "objects":[r[0] for r in conn.execute('SELECT name FROM scene_objects WHERE scene_id=?',(scene['id'],))],
          "uncertainties":[dict(r) for r in conn.execute('SELECT code,description FROM scene_uncertainties WHERE scene_id=?',(scene['id'],))],
          "dialogue":dialogue,"contact_sheet":{"path":str(sheet.resolve()),"sha256":sha256_file(sheet)}}
        folder.mkdir(parents=True,exist_ok=True); (folder/"scene_card.json").write_text(json.dumps(card,indent=2,ensure_ascii=False),encoding="utf-8"); count+=1
    return {"scene_inspection_packages":count,"path":str(base.resolve())}
