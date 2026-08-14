# Repository synchronization policy

Canonical repository: `https://github.com/nischalshivam/MEditing`
Stable branch: `main`

For each Codex task: fetch `origin/main`, inspect the working state, use `codex/<task-name>` for nontrivial work, implement, test, commit, reconcile latest main without force-pushing, integrate only after gates pass, and push resulting main. Claude uses `claude/<task-name>`.

Never force-push main or rewrite public history without explicit authorization and a safe backup. If the remote changed, fetch, inspect and resolve from source authority, rerun affected tests, then push. Never push credentials, source media, voiceovers, character galleries, production DBs, generated previews, caches, models, or machine-specific state.

Every coding-agent final response reports branch, commit SHA, tests, push verification, and remaining known defects.
