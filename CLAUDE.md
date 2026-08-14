# Claude Code rules for Scene Brain

Read `SCENE_BRAIN_MASTER_HANDOFF.md`, `SCENE_BRAIN_CURRENT_STATE.md`, `SCENE_BRAIN_REGRESSION_CONSTITUTION.md`, `AGENTS.md`, and `REPO_SYNC_POLICY.md` before modifying the product.

Every completed coding update must be committed and pushed to MEditing after its required tests pass. Do not leave successful local-only code as the new source of truth.

Source media is immutable. Evidence locations must remain local and deterministic. Missing/weak evidence is review/manual, not a guessed success. Do not invalidate Walter/Skyler locks or historical receipts. Never commit secrets, production media, SSD databases, character reference images, caches, or browser profiles. Run regressions and real-browser gates, update docs for workflow changes, then commit and push through the prescribed `claude/<task-name>` branch workflow.
