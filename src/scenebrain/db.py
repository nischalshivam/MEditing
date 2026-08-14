from __future__ import annotations

import sqlite3
from pathlib import Path

MIGRATIONS = [
    (1, """
    CREATE TABLE titles(
      id INTEGER PRIMARY KEY, canonical_name TEXT NOT NULL, kind TEXT NOT NULL,
      year INTEGER, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(canonical_name, kind, year));
    CREATE TABLE source_files(
      id INTEGER PRIMARY KEY, title_id INTEGER NOT NULL REFERENCES titles(id),
      season INTEGER, episode INTEGER, path TEXT NOT NULL UNIQUE,
      bytes INTEGER NOT NULL, mtime_ns INTEGER NOT NULL, sha256 TEXT NOT NULL,
      duration_ms INTEGER NOT NULL, width INTEGER, height INTEGER,
      fps_num INTEGER, fps_den INTEGER, video_codec TEXT, audio_codec TEXT,
      probe_json TEXT NOT NULL, indexed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE analysis_runs(
      id INTEGER PRIMARY KEY, source_file_id INTEGER REFERENCES source_files(id),
      stage TEXT NOT NULL, input_fingerprint TEXT NOT NULL,
      tool_version TEXT NOT NULL, status TEXT NOT NULL, details_json TEXT NOT NULL,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(stage, input_fingerprint));
    CREATE TABLE subtitle_tracks(
      id INTEGER PRIMARY KEY, source_file_id INTEGER NOT NULL REFERENCES source_files(id),
      path TEXT NOT NULL, origin TEXT NOT NULL, language TEXT,
      bytes INTEGER NOT NULL, sha256 TEXT NOT NULL, cue_count INTEGER NOT NULL,
      first_ms INTEGER, last_ms INTEGER, parse_status TEXT NOT NULL,
      identity_status TEXT NOT NULL, sync_status TEXT NOT NULL,
      sync_offset_ms INTEGER, selection_score REAL NOT NULL,
      selection_evidence_json TEXT NOT NULL, selected INTEGER NOT NULL DEFAULT 0,
      UNIQUE(source_file_id, path, sha256));
    CREATE TABLE subtitle_cues(
      id INTEGER PRIMARY KEY, track_id INTEGER NOT NULL REFERENCES subtitle_tracks(id) ON DELETE CASCADE,
      cue_index INTEGER NOT NULL, start_ms INTEGER NOT NULL, end_ms INTEGER NOT NULL,
      raw_text TEXT NOT NULL, normalized_text TEXT NOT NULL,
      UNIQUE(track_id, cue_index));
    CREATE VIRTUAL TABLE subtitle_cues_fts USING fts5(
      normalized_text, content='subtitle_cues', content_rowid='id', tokenize='unicode61');
    CREATE TRIGGER subtitle_cues_ai AFTER INSERT ON subtitle_cues BEGIN
      INSERT INTO subtitle_cues_fts(rowid,normalized_text) VALUES(new.id,new.normalized_text);
    END;
    CREATE TRIGGER subtitle_cues_ad AFTER DELETE ON subtitle_cues BEGIN
      INSERT INTO subtitle_cues_fts(subtitle_cues_fts,rowid,normalized_text)
      VALUES('delete',old.id,old.normalized_text);
    END;
    CREATE TRIGGER subtitle_cues_au AFTER UPDATE ON subtitle_cues BEGIN
      INSERT INTO subtitle_cues_fts(subtitle_cues_fts,rowid,normalized_text)
      VALUES('delete',old.id,old.normalized_text);
      INSERT INTO subtitle_cues_fts(rowid,normalized_text) VALUES(new.id,new.normalized_text);
    END;
    CREATE TABLE shots(
      id INTEGER PRIMARY KEY, source_file_id INTEGER NOT NULL REFERENCES source_files(id),
      ordinal INTEGER NOT NULL, start_ms INTEGER NOT NULL, end_ms INTEGER NOT NULL,
      detector TEXT NOT NULL, detector_version TEXT NOT NULL,
      input_fingerprint TEXT NOT NULL, UNIQUE(source_file_id, ordinal, input_fingerprint));
    CREATE TABLE keyframes(
      id INTEGER PRIMARY KEY, shot_id INTEGER NOT NULL REFERENCES shots(id) ON DELETE CASCADE,
      timestamp_ms INTEGER NOT NULL, path TEXT NOT NULL, bytes INTEGER NOT NULL,
      sha256 TEXT NOT NULL, extraction_fingerprint TEXT NOT NULL,
      UNIQUE(shot_id, extraction_fingerprint));
    CREATE TABLE benchmark_freezes(
      id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, schema_version TEXT NOT NULL,
      questions_path TEXT NOT NULL, questions_sha256 TEXT NOT NULL,
      source_manifest_sha256 TEXT NOT NULL, question_count INTEGER NOT NULL,
      frozen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    """),
    (2, """
    CREATE TABLE scene_input_freezes(
      id INTEGER PRIMARY KEY, source_file_id INTEGER NOT NULL REFERENCES source_files(id),
      freeze_version TEXT NOT NULL, input_fingerprint TEXT NOT NULL UNIQUE,
      manifest_path TEXT NOT NULL, manifest_sha256 TEXT NOT NULL,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE scene_analysis_windows(
      id INTEGER PRIMARY KEY, source_file_id INTEGER NOT NULL REFERENCES source_files(id),
      freeze_id INTEGER NOT NULL REFERENCES scene_input_freezes(id), window_id TEXT NOT NULL UNIQUE,
      first_shot_id INTEGER NOT NULL REFERENCES shots(id), last_shot_id INTEGER NOT NULL REFERENCES shots(id),
      shot_ids_json TEXT NOT NULL, dialogue_json TEXT NOT NULL, package_path TEXT NOT NULL,
      package_sha256 TEXT NOT NULL, input_fingerprint TEXT NOT NULL UNIQUE,
      status TEXT NOT NULL DEFAULT 'PENDING');
    CREATE TABLE scene_analysis_runs(
      id INTEGER PRIMARY KEY, window_id INTEGER NOT NULL REFERENCES scene_analysis_windows(id),
      provider TEXT NOT NULL, model TEXT NOT NULL, prompt_version TEXT NOT NULL,
      schema_version TEXT NOT NULL, input_fingerprint TEXT NOT NULL,
      output_fingerprint TEXT, cache_hit INTEGER NOT NULL, status TEXT NOT NULL,
      input_tokens INTEGER, output_tokens INTEGER, total_tokens INTEGER,
      estimated_cost_usd REAL, sanitized_error TEXT,
      started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, finished_at TEXT,
      UNIQUE(provider,model,prompt_version,schema_version,input_fingerprint));
    CREATE TABLE scene_window_proposals(
      id INTEGER PRIMARY KEY, run_id INTEGER NOT NULL REFERENCES scene_analysis_runs(id),
      proposal_index INTEGER NOT NULL, start_shot_id INTEGER NOT NULL REFERENCES shots(id),
      end_shot_id INTEGER NOT NULL REFERENCES shots(id), boundary_status TEXT NOT NULL,
      scene_type TEXT NOT NULL, visual_summary TEXT NOT NULL, raw_json TEXT NOT NULL,
      UNIQUE(run_id,proposal_index));
    CREATE TABLE scenes(
      id INTEGER PRIMARY KEY, source_file_id INTEGER NOT NULL REFERENCES source_files(id),
      scene_uid TEXT NOT NULL UNIQUE, ordinal INTEGER NOT NULL, start_shot_id INTEGER NOT NULL REFERENCES shots(id),
      end_shot_id INTEGER NOT NULL REFERENCES shots(id), start_ms INTEGER NOT NULL, end_ms INTEGER NOT NULL,
      boundary_status TEXT NOT NULL, scene_type TEXT NOT NULL, visual_summary TEXT NOT NULL,
      atlas_fingerprint TEXT NOT NULL, analysis_status TEXT NOT NULL,
      UNIQUE(source_file_id,ordinal,atlas_fingerprint));
    CREATE TABLE scene_shots(scene_id INTEGER NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
      shot_id INTEGER NOT NULL REFERENCES shots(id), ordinal INTEGER NOT NULL,
      state TEXT NOT NULL DEFAULT 'COVERED', PRIMARY KEY(scene_id,shot_id));
    CREATE TABLE scene_characters(id INTEGER PRIMARY KEY,scene_id INTEGER NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
      name TEXT NOT NULL,evidence_shot_ids_json TEXT NOT NULL,provenance_json TEXT NOT NULL);
    CREATE TABLE scene_locations(id INTEGER PRIMARY KEY,scene_id INTEGER NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
      name TEXT NOT NULL,evidence_shot_ids_json TEXT NOT NULL,provenance_json TEXT NOT NULL);
    CREATE TABLE scene_actions(id INTEGER PRIMARY KEY,scene_id INTEGER NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
      description TEXT NOT NULL,evidence_shot_ids_json TEXT NOT NULL,provenance_json TEXT NOT NULL);
    CREATE TABLE scene_objects(id INTEGER PRIMARY KEY,scene_id INTEGER NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
      name TEXT NOT NULL,evidence_shot_ids_json TEXT NOT NULL,provenance_json TEXT NOT NULL);
    CREATE TABLE scene_semantics(id INTEGER PRIMARY KEY,scene_id INTEGER NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
      main_event TEXT NOT NULL,evidence_shot_ids_json TEXT NOT NULL,provenance_json TEXT NOT NULL);
    CREATE TABLE scene_flags(id INTEGER PRIMARY KEY,scene_id INTEGER NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
      flag TEXT NOT NULL,provenance_json TEXT NOT NULL);
    CREATE TABLE scene_uncertainties(id INTEGER PRIMARY KEY,scene_id INTEGER NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
      code TEXT NOT NULL,description TEXT NOT NULL,evidence_shot_ids_json TEXT NOT NULL,provenance_json TEXT NOT NULL);
    CREATE TABLE scene_provenance(scene_id INTEGER NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
      proposal_id INTEGER NOT NULL REFERENCES scene_window_proposals(id), PRIMARY KEY(scene_id,proposal_id));
    """),
    (3, """
    CREATE TABLE resolver_input_freezes(
      id INTEGER PRIMARY KEY,source_file_id INTEGER NOT NULL REFERENCES source_files(id),
      freeze_version TEXT NOT NULL,input_fingerprint TEXT NOT NULL UNIQUE,
      manifest_path TEXT NOT NULL,manifest_sha256 TEXT NOT NULL,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE scene_retrieval_fragments(
      id INTEGER PRIMARY KEY,scene_id INTEGER NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
      proposal_id INTEGER REFERENCES scene_window_proposals(id),fragment_type TEXT NOT NULL,
      objective_text TEXT NOT NULL,normalized_text TEXT NOT NULL,evidence_shot_ids_json TEXT NOT NULL,
      trust_status TEXT NOT NULL,source_fingerprint TEXT NOT NULL,provenance_json TEXT NOT NULL,
      fragment_fingerprint TEXT NOT NULL UNIQUE);
    CREATE VIRTUAL TABLE scene_retrieval_fts USING fts5(
      normalized_text,content='scene_retrieval_fragments',content_rowid='id',tokenize='unicode61');
    CREATE TRIGGER scene_retrieval_ai AFTER INSERT ON scene_retrieval_fragments BEGIN
      INSERT INTO scene_retrieval_fts(rowid,normalized_text) VALUES(new.id,new.normalized_text);
    END;
    CREATE TRIGGER scene_retrieval_ad AFTER DELETE ON scene_retrieval_fragments BEGIN
      INSERT INTO scene_retrieval_fts(scene_retrieval_fts,rowid,normalized_text) VALUES('delete',old.id,old.normalized_text);
    END;
    CREATE TABLE scene_fragment_embeddings(
      fragment_id INTEGER NOT NULL REFERENCES scene_retrieval_fragments(id) ON DELETE CASCADE,
      embedding_model TEXT NOT NULL,vector_json TEXT NOT NULL,input_fingerprint TEXT NOT NULL,
      PRIMARY KEY(fragment_id,embedding_model));
    CREATE TABLE resolver_versions(
      id INTEGER PRIMARY KEY,version TEXT NOT NULL UNIQUE,input_freeze_id INTEGER NOT NULL REFERENCES resolver_input_freezes(id),
      schema_version TEXT NOT NULL,ranking_config_json TEXT NOT NULL,embedding_model TEXT NOT NULL,
      verifier_model TEXT,verifier_prompt_version TEXT,resolver_fingerprint TEXT NOT NULL UNIQUE,
      frozen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE resolver_runs(
      id INTEGER PRIMARY KEY,resolver_version_id INTEGER NOT NULL REFERENCES resolver_versions(id),
      request_id TEXT NOT NULL,request_fingerprint TEXT NOT NULL,decision TEXT NOT NULL,
      primary_scene_id INTEGER REFERENCES scenes(id),result_json TEXT NOT NULL,
      verifier_used INTEGER NOT NULL DEFAULT 0,cache_hit INTEGER NOT NULL DEFAULT 0,
      input_tokens INTEGER,output_tokens INTEGER,total_tokens INTEGER,estimated_cost_usd REAL,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(resolver_version_id,request_fingerprint));
    CREATE TABLE resolver_evaluations(
      id INTEGER PRIMARY KEY,resolver_version_id INTEGER NOT NULL REFERENCES resolver_versions(id),
      evaluation_name TEXT NOT NULL UNIQUE,dataset_path TEXT NOT NULL,dataset_sha256 TEXT NOT NULL,
      result_path TEXT NOT NULL,result_sha256 TEXT NOT NULL,metrics_json TEXT NOT NULL,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    """),
    (4, """
    CREATE TABLE resolver_verifier_runs(
      id INTEGER PRIMARY KEY,resolver_version TEXT NOT NULL,request_fingerprint TEXT NOT NULL,
      provider TEXT NOT NULL,model TEXT NOT NULL,prompt_version TEXT NOT NULL,
      input_fingerprint TEXT NOT NULL UNIQUE,output_fingerprint TEXT,
      decision TEXT NOT NULL,selected_scene_uid TEXT,cache_hit INTEGER NOT NULL,
      input_tokens INTEGER,output_tokens INTEGER,total_tokens INTEGER,estimated_cost_usd REAL,
      sanitized_error TEXT,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    """),
    (5, """
    CREATE TABLE shot_resolver_input_freezes(
      id INTEGER PRIMARY KEY,source_file_id INTEGER NOT NULL REFERENCES source_files(id),
      resolver_version_id INTEGER NOT NULL REFERENCES resolver_versions(id),
      freeze_version TEXT NOT NULL,input_fingerprint TEXT NOT NULL UNIQUE,
      manifest_path TEXT NOT NULL,manifest_sha256 TEXT NOT NULL,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE shot_resolver_versions(
      id INTEGER PRIMARY KEY,version TEXT NOT NULL UNIQUE,input_freeze_id INTEGER NOT NULL REFERENCES shot_resolver_input_freezes(id),
      config_json TEXT NOT NULL,candidate_prompt_version TEXT NOT NULL,crop_prompt_version TEXT NOT NULL,
      provider_model TEXT NOT NULL,resolver_fingerprint TEXT NOT NULL UNIQUE,
      frozen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE shot_temporal_artifacts(
      id INTEGER PRIMARY KEY,source_file_id INTEGER NOT NULL REFERENCES source_files(id),
      start_shot_id INTEGER NOT NULL REFERENCES shots(id),end_shot_id INTEGER NOT NULL REFERENCES shots(id),
      artifact_type TEXT NOT NULL,config_version TEXT NOT NULL,input_fingerprint TEXT NOT NULL UNIQUE,
      path TEXT NOT NULL,sha256 TEXT NOT NULL,bytes INTEGER NOT NULL,duration_ms INTEGER,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE shot_resolver_runs(
      id INTEGER PRIMARY KEY,shot_resolver_version_id INTEGER REFERENCES shot_resolver_versions(id),
      request_id TEXT NOT NULL,request_fingerprint TEXT NOT NULL,sprint3_result_fingerprint TEXT NOT NULL,
      decision TEXT NOT NULL,selected_range_json TEXT,result_json TEXT NOT NULL,
      candidate_verifier_used INTEGER NOT NULL DEFAULT 0,crop_verifier_used INTEGER NOT NULL DEFAULT 0,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(shot_resolver_version_id,request_fingerprint));
    CREATE TABLE shot_verifier_runs(
      id INTEGER PRIMARY KEY,stage TEXT NOT NULL,request_fingerprint TEXT NOT NULL,
      provider TEXT NOT NULL,model TEXT NOT NULL,prompt_version TEXT NOT NULL,
      input_fingerprint TEXT NOT NULL UNIQUE,output_fingerprint TEXT,decision TEXT NOT NULL,
      cache_hit INTEGER NOT NULL,input_tokens INTEGER,output_tokens INTEGER,total_tokens INTEGER,
      estimated_cost_usd REAL,sanitized_error TEXT,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE shot_resolver_evaluations(
      id INTEGER PRIMARY KEY,shot_resolver_version_id INTEGER NOT NULL REFERENCES shot_resolver_versions(id),
      evaluation_name TEXT NOT NULL UNIQUE,dataset_path TEXT NOT NULL,dataset_sha256 TEXT NOT NULL,
      result_path TEXT NOT NULL,result_sha256 TEXT NOT NULL,metrics_json TEXT NOT NULL,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE shot_editorial_memory(
      id INTEGER PRIMARY KEY,event_signature TEXT NOT NULL,scene_uid TEXT NOT NULL,
      start_shot_uid TEXT NOT NULL,end_shot_uid TEXT NOT NULL,start_ms INTEGER NOT NULL,end_ms INTEGER NOT NULL,
      aliases_json TEXT NOT NULL,evidence_class TEXT NOT NULL,verdict TEXT NOT NULL,
      provenance_json TEXT NOT NULL,source_sha256 TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    """),
    (6, """
    CREATE TABLE scene_micro_windows(
      id INTEGER PRIMARY KEY,scene_id INTEGER NOT NULL REFERENCES scenes(id),micro_window_uid TEXT NOT NULL UNIQUE,
      start_ms INTEGER NOT NULL,end_ms INTEGER NOT NULL,shot_ids_json TEXT NOT NULL,dialogue_json TEXT NOT NULL,
      source_sha256 TEXT NOT NULL,index_version TEXT NOT NULL,input_fingerprint TEXT NOT NULL UNIQUE,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE micro_events(
      id INTEGER PRIMARY KEY,micro_window_id INTEGER NOT NULL REFERENCES scene_micro_windows(id) ON DELETE CASCADE,
      action_text TEXT NOT NULL,action_type TEXT NOT NULL,characters_json TEXT NOT NULL,objects_json TEXT NOT NULL,
      evidence_shot_ids_json TEXT NOT NULL,derived_start_ms INTEGER NOT NULL,derived_end_ms INTEGER NOT NULL,
      support_status TEXT NOT NULL,provider TEXT NOT NULL,model TEXT NOT NULL,prompt_version TEXT NOT NULL,
      input_hash TEXT NOT NULL,source_hash TEXT NOT NULL,raw_json TEXT NOT NULL,
      UNIQUE(micro_window_id,input_hash,action_text));
    CREATE TABLE micro_index_runs(
      id INTEGER PRIMARY KEY,micro_window_id INTEGER NOT NULL REFERENCES scene_micro_windows(id),provider TEXT NOT NULL,
      model TEXT NOT NULL,prompt_version TEXT NOT NULL,input_fingerprint TEXT NOT NULL UNIQUE,status TEXT NOT NULL,
      cache_hit INTEGER NOT NULL,input_tokens INTEGER,output_tokens INTEGER,total_tokens INTEGER,estimated_cost_usd REAL,
      sanitized_error TEXT,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    """),
    (7, """
    CREATE TABLE project_slot_decisions(
      project_fingerprint TEXT NOT NULL, slot_id TEXT NOT NULL,
      decision_type TEXT NOT NULL, asset_id TEXT, decision_json TEXT NOT NULL,
      audit_receipt_sha256 TEXT NOT NULL, locked INTEGER NOT NULL DEFAULT 1,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY(project_fingerprint,slot_id));
    CREATE TABLE project_repair_decisions(
      project_fingerprint TEXT NOT NULL, slot_id TEXT NOT NULL,
      decision TEXT NOT NULL, asset_id TEXT, decision_json TEXT NOT NULL,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY(project_fingerprint,slot_id));
    """),
]


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
    for version, sql in MIGRATIONS:
        if not conn.execute("SELECT 1 FROM schema_migrations WHERE version=?", (version,)).fetchone():
            with conn:
                conn.executescript(sql)
                conn.execute("INSERT INTO schema_migrations(version) VALUES(?)", (version,))
    return conn
