from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "runtime/researchcut_integration/production/public/app.js").read_text(encoding="utf-8")
POLISH = (ROOT / "runtime/researchcut_integration/production/public/polish.js").read_text(encoding="utf-8")
SERVER = (ROOT / "runtime/researchcut_integration/production/server.js").read_text(encoding="utf-8")
CSS = (ROOT / "runtime/researchcut_integration/production/public/styles.css").read_text(encoding="utf-8")

def test_clue_upload_accepts_content_driven_txt_md_json():
    assert ".json,.txt,.md" in POLISH
    assert "clueDocumentFromText" in POLISH
    assert "production-clue-script/4.0" in POLISH
    assert "CLUE FILE INVALID" in POLISH
    assert "intakeClueState.document" in POLISH

def test_clue_is_persisted_in_project_intake():
    assert "clue:intakeClueState" in POLISH
    assert "document: input.intake.clue.document" in SERVER
    assert "beatCount" in SERVER and "sourceScope" in SERVER

def test_preview_uses_preparation_cache_and_preserves_visible_frame():
    assert "const previewPrepared = new Map()" in APP
    assert "function prewarmUpcoming" in APP
    assert "stage.replaceChildren" in APP
    assert "Preparing next clip..." in APP
    assert "stage.innerHTML = active.length ? ''" not in APP

def test_preview_has_distinct_fail_closed_states():
    assert "function renderUnavailableVisual" in APP
    assert "MANUAL VISUAL REQUIRED" in APP
    assert "CHOOSE VISUAL" in APP
    assert "MEDIA ERROR" in APP

def test_track_labels_have_separate_control_column():
    assert "track-controls" in APP and "track-controls" in CSS
    assert "Main Visual" in APP and "Main Visual" in SERVER
    assert "AUDIOC" not in APP and "MAMUTEDC" not in APP
    assert "--track-label:220px" in CSS

def test_compact_episode_label_and_range_server():
    assert "function compactAssetLabel" in APP
    assert "accept-ranges': 'bytes'" in SERVER
    assert "content-range" in SERVER and "206" in SERVER
