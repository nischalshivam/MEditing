from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PUBLIC=ROOT/"runtime/researchcut_integration/production/public"

def test_visible_ui_has_no_common_mojibake():
 text="\n".join((PUBLIC/x).read_text(encoding="utf8") for x in ("index.html","app.js","polish.js","styles.css"))
 for bad in ("Ã","â€","â†","ï¼","ðŸ","Â·","�"):
  assert bad not in text

def test_transport_is_accessible_and_svg_based():
 text=(PUBLIC/"app.js").read_text(encoding="utf8")
 assert 'id="playBtn" aria-label="Play"' in text
 assert "function svgIcon" in text
 assert "ariaLabel=playing?'Pause':'Play'" in text
 assert "e.code === 'Space'" in text

def test_guided_scope_and_clue_workflow_present():
 text=(PUBLIC/"polish.js").read_text(encoding="utf8")
 for marker in ("Custom Multi-Title","Franchise","Copy Ready Prompt","Get Clue Prompt","INPUT CONSISTENCY","Custom scope requires at least two titles"):
  assert marker in text

def test_character_reference_workflow_present():
 text=(PUBLIC/"polish.js").read_text(encoding="utf8")
 for marker in ("Manage References","+ Add Images","TRUSTED","REJECTED","reference-state"):
  assert marker in text

def test_clue_prompt_is_canonical_and_has_no_timestamp_authority():
 prompt=(ROOT/"docs/prompts/SCENE_BRAIN_CLUE_SCRIPT_V4_MASTER_PROMPT.md").read_text(encoding="utf8")
 assert "production-clue-script/4.0" in prompt
 assert "never timestamp" in prompt.lower()
