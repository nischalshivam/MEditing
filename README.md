# Scene Brain

Scene Brain is a local-first Film/TV evidence, retrieval, human-review, and first-cut production system. Original media remains read-only; local source identity/timing is authority; weak evidence becomes an option or manual gap.

## Start

Connect the registered external library and double-click `START_SCENE_BRAIN.bat`. The launcher waits for `GET /api/health` before opening `http://127.0.0.1:43127/`.

Developer start:

```powershell
$env:PYTHONPATH="$PWD\src"
node runtime\researchcut_integration\production\server.js
```

Tests:

```powershell
python -m pytest -q
python tests\e2e\ui_git_polish_gate.py
```

Read `AGENTS.md`, `SCENE_BRAIN_MASTER_HANDOFF.md`, `SCENE_BRAIN_CURRENT_STATE.md`, and `SCENE_BRAIN_REGRESSION_CONSTITUTION.md` before changing code. Production media, SSD databases, voiceovers, character images, credentials, caches, and browser profiles are intentionally excluded from Git.
