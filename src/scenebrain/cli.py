from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from .benchmark import freeze, prepare_dialogue_questions
from .config import Settings
from .db import connect
from .hashing import fingerprint, sha256_file
from .logging_setup import configure
from .media import doctor, probe
from .shots import detect, detection_fingerprint, extract_keyframe, representative_time
from .subtitles import assess, discover, parse_srt, search_multi_cue
from .sync import verify_audio_sync
from .atlas import build_scene_inspection, build_windows, freeze_inputs, stitch_atlas
from .providers import GeminiProvider, credential_detected, run_window
from .visual_holdout import freeze_visual_holdout
from .resolver import build_fragments,freeze_resolver_inputs,freeze_resolver_version,resolve_local
from .resolver_models import SceneRetrievalRequest
from .shot_models import ShotRequest
from .shot_pipeline import resolve_shot


def emit(value) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False))


def add_source(conn, title: str, kind: str, media: Path) -> int:
    report = doctor(media)
    with conn:
        conn.execute("INSERT OR IGNORE INTO titles(canonical_name,kind) VALUES(?,?)", (title, kind))
        title_id = conn.execute("SELECT id FROM titles WHERE canonical_name=? AND kind=? AND year IS NULL", (title, kind)).fetchone()[0]
        conn.execute("""INSERT INTO source_files(title_id,season,episode,path,bytes,mtime_ns,sha256,duration_ms,width,height,
          fps_num,fps_den,video_codec,audio_codec,probe_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
          ON CONFLICT(path) DO UPDATE SET bytes=excluded.bytes,mtime_ns=excluded.mtime_ns,sha256=excluded.sha256,
          duration_ms=excluded.duration_ms,width=excluded.width,height=excluded.height,fps_num=excluded.fps_num,
          fps_den=excluded.fps_den,video_codec=excluded.video_codec,audio_codec=excluded.audio_codec,probe_json=excluded.probe_json""",
          (title_id, report["season"], report["episode"], report["path"], report["bytes"], report["mtime_ns"], report["sha256"],
           report["duration_ms"], report["width"], report["height"], *report["fps"], report["video_codec"], report["audio_codec"],
           json.dumps(report["probe"], sort_keys=True)))
    return conn.execute("SELECT id FROM source_files WHERE path=?", (report["path"],)).fetchone()[0]


def index_subtitles(conn, source_id: int) -> dict:
    source = conn.execute("SELECT * FROM source_files WHERE id=?", (source_id,)).fetchone()
    media = Path(source["path"])
    reports = [assess(p, media, source["duration_ms"]) for p in discover(media)]
    if not reports: raise RuntimeError("no matching subtitle candidates")
    winner = max(reports, key=lambda r: r["score"])
    # Never claim verified sync without measured audio evidence.
    tied = sum(r["score"] == winner["score"] for r in reports) > 1
    with conn:
        conn.execute("UPDATE subtitle_tracks SET selected=0 WHERE source_file_id=?", (source_id,))
        for report in reports:
            # Indexing nominates a candidate; only measured audio sync may promote it.
            selected = 0
            conn.execute("""INSERT INTO subtitle_tracks(source_file_id,path,origin,language,bytes,sha256,cue_count,first_ms,last_ms,
              parse_status,identity_status,sync_status,sync_offset_ms,selection_score,selection_evidence_json,selected)
              VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
              ON CONFLICT(source_file_id,path,sha256) DO UPDATE SET selection_score=excluded.selection_score,
              selection_evidence_json=excluded.selection_evidence_json,selected=excluded.selected""",
              (source_id, report["path"], report["origin"], report["language"], report["bytes"], report["sha256"], report["cue_count"],
               report["first_ms"], report["last_ms"], report["parse_status"], report["identity_status"], report["sync_status"],
               report["sync_offset_ms"], report["score"], json.dumps(report["evidence"], sort_keys=True), selected))
            track_id = conn.execute("SELECT id FROM subtitle_tracks WHERE source_file_id=? AND path=? AND sha256=?",
                                    (source_id, report["path"], report["sha256"])).fetchone()[0]
            conn.execute("DELETE FROM subtitle_cues WHERE track_id=?", (track_id,))
            conn.executemany("INSERT INTO subtitle_cues(track_id,cue_index,start_ms,end_ms,raw_text,normalized_text) VALUES(?,?,?,?,?,?)",
              [(track_id,c.index,c.start_ms,c.end_ms,c.raw_text,c.normalized_text) for c in parse_srt(Path(report["path"]))])
    return {"source_id": source_id, "candidates": reports, "nominated": None if tied else winner["path"], "selected": None,
            "sync_verified": False, "production_dialogue_authority": False}


def cmd_shots(conn, source_id: int, settings: Settings, threshold: float) -> dict:
    source = conn.execute("SELECT * FROM source_files WHERE id=?", (source_id,)).fetchone()
    fp = detection_fingerprint(source["sha256"], threshold)
    cached = conn.execute("SELECT ordinal,start_ms,end_ms FROM shots WHERE source_file_id=? AND input_fingerprint=? ORDER BY ordinal", (source_id, fp)).fetchall()
    cache_valid = bool(cached) and cached[0]["start_ms"] == 0 and cached[-1]["end_ms"] == source["duration_ms"] and all(
        row["ordinal"] == i and row["end_ms"] > row["start_ms"] and (i == 0 or cached[i-1]["end_ms"] == row["start_ms"])
        for i,row in enumerate(cached))
    if cache_valid:
        bounds = [(r["start_ms"],r["end_ms"]) for r in cached]
    else:
        fp, bounds = detect(Path(source["path"]), source["duration_ms"], source["sha256"], threshold)
    existing = len(cached) if cache_valid else conn.execute("SELECT COUNT(*) FROM shots WHERE source_file_id=? AND input_fingerprint=?", (source_id, fp)).fetchone()[0]
    if existing != len(bounds):
        with conn:
            conn.execute("DELETE FROM shots WHERE source_file_id=?", (source_id,))
            conn.executemany("INSERT INTO shots(source_file_id,ordinal,start_ms,end_ms,detector,detector_version,input_fingerprint) VALUES(?,?,?,?,?,?,?)",
              [(source_id,i,a,b,"ffmpeg-scene-select","8.1",fp) for i,(a,b) in enumerate(bounds)])
    frames = 0
    for row in conn.execute("SELECT * FROM shots WHERE source_file_id=? ORDER BY ordinal", (source_id,)):
        ts = representative_time(row["start_ms"], row["end_ms"])
        efp = fingerprint(source["sha256"], row["id"], ts, settings.keyframe_width, "ffmpeg/8.1")
        output = settings.cache / "keyframes" / source["sha256"][:16] / f"shot_{row['ordinal']:05d}_{efp[:12]}.jpg"
        current = conn.execute("SELECT * FROM keyframes WHERE shot_id=? AND extraction_fingerprint=?", (row["id"], efp)).fetchone()
        if not current or not output.is_file() or sha256_file(output) != current["sha256"]:
            info = extract_keyframe(Path(source["path"]), ts, output, settings.keyframe_width)
            with conn:
                conn.execute("DELETE FROM keyframes WHERE shot_id=?", (row["id"],))
                conn.execute("INSERT INTO keyframes(shot_id,timestamp_ms,path,bytes,sha256,extraction_fingerprint) VALUES(?,?,?,?,?,?)",
                             (row["id"],ts,info["path"],info["bytes"],info["sha256"],efp))
        frames += 1
    return {"source_id": source_id, "input_fingerprint": fp, "threshold": threshold, "shot_cache_hit": cache_valid,
            "shot_count": len(bounds), "keyframe_count": frames}


def parser() -> argparse.ArgumentParser:
    p=argparse.ArgumentParser(prog="scene-brain")
    p.add_argument("--root", type=Path)
    s=p.add_subparsers(dest="cmd", required=True)
    s.add_parser("init")
    d=s.add_parser("doctor"); d.add_argument("media", type=Path)
    a=s.add_parser("add-source"); a.add_argument("--title", required=True); a.add_argument("--kind", choices=["FILM","SERIES"], required=True); a.add_argument("media", type=Path)
    u=s.add_parser("index-subtitles"); u.add_argument("source_id", type=int)
    vs=s.add_parser("verify-subtitle-sync"); vs.add_argument("source_id",type=int); vs.add_argument("track_id",type=int)
    q=s.add_parser("search-dialogue"); q.add_argument("query"); q.add_argument("--limit", type=int, default=20)
    h=s.add_parser("detect-shots"); h.add_argument("source_id", type=int); h.add_argument("--threshold", type=float, default=0.15)
    b=s.add_parser("freeze-benchmark"); b.add_argument("questions", type=Path); b.add_argument("--source-manifest-sha", required=True); b.add_argument("--name", default="sprint1-v1")
    pb=s.add_parser("prepare-dialogue-benchmark"); pb.add_argument("source_id",type=int); pb.add_argument("output",type=Path); pb.add_argument("--count",type=int,default=40); pb.add_argument("--include-visual-seed",action="store_true")
    af=s.add_parser("atlas-freeze"); af.add_argument("source_id",type=int)
    aw=s.add_parser("atlas-build-windows"); aw.add_argument("source_id",type=int); aw.add_argument("freeze_id",type=int)
    ar=s.add_parser("atlas-run"); ar.add_argument("--limit",type=int); ar.add_argument("--window-id"); ar.add_argument("--model")
    ast=s.add_parser("atlas-stitch"); ast.add_argument("source_id",type=int); ast.add_argument("--freeze-fingerprint",required=True)
    ai=s.add_parser("atlas-inspection"); ai.add_argument("source_id",type=int)
    vh=s.add_parser("freeze-visual-holdout"); vh.add_argument("source_id",type=int); vh.add_argument("output",type=Path)
    rf=s.add_parser("resolver-freeze-inputs");rf.add_argument("source_id",type=int)
    rb=s.add_parser("resolver-build-fragments");rb.add_argument("source_id",type=int);rb.add_argument("--source-fingerprint",required=True)
    rv=s.add_parser("resolver-freeze-version");rv.add_argument("freeze_id",type=int)
    rr=s.add_parser("resolve-scene");rr.add_argument("--request",type=Path);rr.add_argument("--query");rr.add_argument("--evidence-class",default="EXACT_EVENT")
    rs=s.add_parser("resolve-shot");rs.add_argument("request",type=Path)
    return p


def main(argv=None) -> int:
    args=parser().parse_args(argv); settings=Settings.load(args.root); settings.ensure(); configure(settings.log_level)
    conn=connect(settings.database)
    if args.cmd=="init": emit({"status":"READY","database":str(settings.database),"schema_version":1})
    elif args.cmd=="doctor": emit(doctor(args.media))
    elif args.cmd=="add-source": emit({"source_id":add_source(conn,args.title,args.kind,args.media)})
    elif args.cmd=="index-subtitles": emit(index_subtitles(conn,args.source_id))
    elif args.cmd=="verify-subtitle-sync":
        source=conn.execute("SELECT * FROM source_files WHERE id=?",(args.source_id,)).fetchone()
        track=conn.execute("SELECT * FROM subtitle_tracks WHERE id=? AND source_file_id=?",(args.track_id,args.source_id)).fetchone()
        if not source or not track: raise SystemExit("source/track not found")
        result=verify_audio_sync(Path(source["path"]),parse_srt(Path(track["path"])),settings.cache)
        with conn:
            conn.execute("UPDATE subtitle_tracks SET sync_status=?,sync_offset_ms=?,selection_evidence_json=json_set(selection_evidence_json,'$.audio_sync',json(?)) WHERE id=?",
              (result["status"],result.get("offset_ms"),json.dumps(result,sort_keys=True),args.track_id))
            if result["status"] in {"VERIFIED","VERIFIED_WITH_OFFSET"} and track["identity_status"] == "MATCH":
                conn.execute("UPDATE subtitle_tracks SET selected=0 WHERE source_file_id=?",(args.source_id,))
                conn.execute("UPDATE subtitle_tracks SET selected=1 WHERE id=?",(args.track_id,))
        emit(result)
    elif args.cmd=="search-dialogue": emit(search_multi_cue(conn,args.query,args.limit))
    elif args.cmd=="detect-shots": emit(cmd_shots(conn,args.source_id,settings,args.threshold))
    elif args.cmd=="freeze-benchmark":
        receipt=freeze(args.questions,args.source_manifest_sha)
        with conn:
            conn.execute("INSERT INTO benchmark_freezes(name,schema_version,questions_path,questions_sha256,source_manifest_sha256,question_count) VALUES(?,?,?,?,?,?)",
                         (args.name,receipt["schema_version"],receipt["questions_path"],receipt["questions_sha256"],receipt["source_manifest_sha256"],receipt["question_count"]))
        emit(receipt)
    elif args.cmd=="prepare-dialogue-benchmark": emit(prepare_dialogue_questions(conn,args.source_id,args.output,args.count,args.include_visual_seed))
    elif args.cmd=="atlas-freeze": emit(freeze_inputs(conn,args.source_id,settings.root))
    elif args.cmd=="atlas-build-windows": emit({"windows":len(build_windows(conn,args.source_id,args.freeze_id,settings.root,
      settings.scene_window_target_seconds*1000,settings.scene_window_min_shots,settings.scene_window_max_shots,settings.scene_window_overlap_shots))})
    elif args.cmd=="atlas-run":
        if not credential_detected(): emit({"gemini_connection":"STOPPED","credential_detected":False,"credential_printed":False}); return 2
        model=args.model or settings.gemini_model; provider=GeminiProvider(model)
        sql="SELECT package_path FROM scene_analysis_windows"; params=[]
        if args.window_id: sql+=" WHERE window_id=?"; params=[args.window_id]
        sql+=" ORDER BY window_id"
        rows=conn.execute(sql,params).fetchall(); rows=rows[:args.limit] if args.limit else rows
        results=[]
        for row in rows:
            if len(results)>=settings.gemini_max_calls: break
            package=json.loads(Path(row["package_path"]).read_text(encoding="utf-8")); results.append(run_window(conn,provider,package,settings.root,model,settings.gemini_max_cost_usd))
        emit({"gemini_connection":"PASS","model":model,"credential_detected":True,"credential_printed":False,"windows":len(results),"results":results})
    elif args.cmd=="atlas-stitch": emit(stitch_atlas(conn,args.source_id,args.freeze_fingerprint,settings.root))
    elif args.cmd=="atlas-inspection": emit(build_scene_inspection(conn,args.source_id,settings.root))
    elif args.cmd=="freeze-visual-holdout":
        source=conn.execute('SELECT sha256 FROM source_files WHERE id=?',(args.source_id,)).fetchone(); emit(freeze_visual_holdout(source[0],args.output))
    elif args.cmd=="resolver-freeze-inputs":emit(freeze_resolver_inputs(conn,args.source_id,settings.root))
    elif args.cmd=="resolver-build-fragments":emit(build_fragments(conn,args.source_id,args.source_fingerprint))
    elif args.cmd=="resolver-freeze-version":emit(freeze_resolver_version(conn,args.freeze_id,settings.root))
    elif args.cmd=="resolve-scene":
        if args.request:req=SceneRetrievalRequest.model_validate_json(args.request.read_text(encoding='utf8'))
        elif args.query:req=SceneRetrievalRequest(request_id='cli-query',query_text=args.query,evidence_class=args.evidence_class)
        else:raise SystemExit('--request or --query required')
        emit(resolve_local(conn,req).model_dump())
    elif args.cmd=="resolve-shot":emit(resolve_shot(conn,settings.root,ShotRequest.model_validate_json(args.request.read_text(encoding='utf8'))).model_dump())
    return 0
