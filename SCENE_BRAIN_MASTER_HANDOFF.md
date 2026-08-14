# Scene Brain Master Handoff

## Purpose and product boundary

Scene Brain converts local Film/TV libraries into evidence-grounded, reusable production assets. It catalogs media, ingests available dialogue, lazily builds rich indexes only for required sources, compiles script clues, routes sources, retrieves visual candidates, preserves human approvals, aligns voiceover, and exposes a timeline editor. It is not a cloud media search service and does not treat AI output as timestamp authority.

## Non-negotiable invariants

1. Original Film/TV files are read-only.
2. Physical source times and shot IDs are local authority.
3. AI may describe what is visible but may not invent where it occurs.
4. Unknown, review-required, and manual replacement are valid outcomes.
5. Expensive results are content-addressed and replayable.
6. Human approvals compound; accepted project choices are never silently rerun.
7. Catalog, memory, projects, and receipts live with the portable external library. Laptop caches are disposable.
8. Searchable and Rich Atlas maturity are distinct.
9. Project retrieval cannot start until its pinned preflight receipt is ready.
10. Frozen Skyler and Walter artifacts must not be tuned for later work.

## Canonical storage

The current media root is `E:\Movies`, registered as Scene Brain volume `b844b9d0-31d9-488f-afd8-2da7c57ce781`. The drive letter is incidental. Canonical state resides under `.scene_brain`:

- `catalog.db`: title, source, subtitle FTS, transcript job, rich job, preflight, franchise, and permanent-index records.
- `libraries/`: permanent source-level derived intelligence.
- `memory/`: editorial and character memory.
- `projects/`: portable project artifacts and approvals.
- `receipts/`: immutable scan/migration/build/preflight receipts.
- `logs/`: canonical operational logs where appropriate.

Local ResearchCut editor projects and caches are under `%LOCALAPPDATA%\ResearchCut Editor`; historical production project receipts also remain pinned on SSD. Do not conflate cache deletion with canonical deletion.

## Data model and maturity

Titles are canonical identities independent of folder spelling. Sources bind volume ID, relative path, quick fingerprint, stream metadata, and eventually strong hash. Source maturity is atomic: `CATALOGED`, `SEARCHABLE`, `RICH_BUILDING`, `RICH_ATLAS_READY`, or `ERROR`. A final validated receipt alone promotes a rich build.

Subtitle FTS is the lightweight episode-discovery layer. Missing dialogue requires an explicit resumable transcript job; there is no mass Whisper policy. Full Rich Atlas construction is lazy and limited to project-required sources.

## Project lifecycle

Clean Script → Clue Compiler → source scope → local episode discovery → episode requirement map → project preflight → required transcript/rich jobs → retrieval → human review → locked visual plan → voiceover alignment → composition timeline → editor → render.

At every transition, inputs and versions are fingerprinted. Discovery hints from models are candidates, not authority. Ambiguous sources block instead of guessing. Existing project decisions remain pinned when libraries improve.

## Retrieval lineage

Sprint 1 established deterministic shots/keyframes/subtitle evidence. Sprint 2 built the narrative Scene Atlas. Sprint 3 added precision-first scene retrieval and abstention. Sprints 4–9 investigated exact temporal selection and proved the importance of complete intra-scene coverage and fail-closed crop verification. Product strategy later shifted to human-approved project candidates rather than fully autonomous exact-clip claims. Sprints 12–14 froze project approvals, repaired only failed slots, aligned real voiceover, and polished composition without reopening retrieval.

The current production principle remains: AI tells us WHAT; local media evidence tells us WHERE.

## Production editor

`START_SCENE_BRAIN.bat` is the employee entry point. It starts and health-checks the loopback backend before opening the browser. ResearchCut 2.1 provides project navigation, media bin, preview, tracks, timeline, inspector, undo/redo, persistence, automation, and render queue. API authorization uses an ephemeral local session token. Mutating onboarding and character import endpoints are protected by the same token.

The editor explicitly distinguishes valid media, empty visual gaps, and media errors. Support reports are sanitized. Canonical saves are on disk; localStorage is convenience only.

## Onboarding and title preparation

The Add Title wizard separates type, metadata, source selection, discovery preview, validation, and commit. It does not alter media in place. Movies are atomic. Series naming is parsed conservatively, including season/episode patterns; uncertain names require review. Adding a title catalogs it but does not automatically transcribe or rich-index it.

## Character library

Portable character galleries live in `.scene_brain/memory/character_galleries/<title_id>`. References store content hash, copied canonical path, import provenance, face-quality diagnostics, approval state, and future embedding version. Desktop originals were read only. Duplicate images are suppressed by SHA-256.

Breaking Bad currently has seven character folders and 24 unique references (one duplicate suppressed). Conservative face/quality validation left all references in suggested/partial state; no generated or weak reference can act as a hard exclusion gate. Human trusted references are required for stronger use.

## GPU and resource policy

The host has an NVIDIA Quadro P1000, 4096 MiB, driver 582.16. Runtime identity maps this physical device to `cuda:0`; Windows Task Manager numbering is not used. Real tests found:

- PyTorch sees CUDA but installed kernels do not support the P1000 compute capability safely.
- CTranslate2 sees one CUDA device, while tested faster-whisper CUDA modes were unsupported or unstable.
- OpenCV is CPU-only for CUDA DNN.
- FFmpeg advertises NVENC but its required NVENC API exceeds the installed driver.
- CPU faster-whisper and software libx264 tests passed.

AUTO therefore selects CPU. Worker policy caps CPU workers at four, GPU workers/heavy GPU concurrency at one, and reserves 768 MiB headroom. GPU preference must never override a failed runtime proof.

## Security

Credentials belong only in environment variables. The application never stores API keys in SQLite, configs, reports, logs, exceptions, or support bundles. All local endpoints except health/config require the current session token. File names and identifiers are sanitized; uploaded paths are confined to intended roots. Original source containers are never rewritten.

## Testing and release evidence

The Python regression suite covers deterministic indexing, atlas, resolvers, audits, portable library, preflight, routing, editor, renderer, and product hardening. Browser evidence is stored in `qa_artifacts` and includes Library, Add Title, New Project, character gallery, GPU diagnostics, and editor screens. `tests/e2e/product_onboarding_gpu_handoff_gate.py` verifies the live health/library/GPU/gallery contract without mutating production media.

## Recovery and maintenance

On reconnect, locate the volume by stable identity and update only its resolved mount. Incremental scans distinguish new, missing, moved, changed, and unchanged sources. A drive-letter change is not a content change. Cache loss triggers regeneration, not catalog/project loss. Never edit historical receipts. Migrations are additive and produce receipts.

## Handoff checklist

- Connect SSD and verify volume ID.
- Launch with `START_SCENE_BRAIN.bat`.
- Confirm six title cards and 619 sources.
- Confirm Breaking Bad 62 searchable / nine rich.
- Keep AUTO performance profile.
- Confirm character gallery images render; leave partial references untrusted.
- Create projects through Analyze → Prepare gating.
- Never mass-transcribe or mass-build Rich Atlases.
- Never rerun locked project assets without explicit replacement instruction.
- Run regression and product e2e gates after changes.
- Preserve the `.scene_brain` canonical root and current project pins during any laptop migration.

## Future work permitted

Future engineering may improve employee polish, add explicit human character-reference review, validate a compatible GPU toolchain, and continue normal editor operation. Such work must preserve the invariants above. Retrieval R&D for frozen projects stays closed unless the user explicitly reopens it.
