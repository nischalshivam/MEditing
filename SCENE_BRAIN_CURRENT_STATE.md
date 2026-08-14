# Scene Brain Current State

Updated: 2026-08-14

Scene Brain is a local-first Film/TV research and production system. The canonical media foundation is the registered external volume `b844b9d0-31d9-488f-afd8-2da7c57ce781`; its current mount is `E:\Movies`, but code and receipts identify it by volume UUID and relative paths rather than by drive letter.

## Production state

- 619 source files across six titles are catalogued.
- 273 sources are locally searchable and nine have atomic `RICH_ATLAS_READY` maturity.
- Breaking Bad has 62/62 searchable sources and nine rich indexes.
- Existing Skyler and Walter project decisions, receipts, source routing, and timelines remain frozen.
- ResearchCut 2.1 is the production editor shell. It uses canonical project state and does not make browser storage authoritative.
- The app is launched with `START_SCENE_BRAIN.bat` and served only on loopback.

## Product hardening delivered

- Library cards expose catalog, search, rich-index, and character readiness.
- Add Movie/Series wizard performs explicit local onboarding; no indexing starts merely by opening it.
- New Project intake separates project, input, source, optional intelligence, analysis, and preparation stages.
- Breaking Bad character references were copied read-only from the operator’s Desktop into the portable SSD character gallery. All are `PARTIAL` pending human trust review.
- GPU diagnostics identify the physical NVIDIA Quadro P1000. The installed runtime stack cannot reliably accelerate current workloads, so AUTO selects validated CPU paths.
- Editor preview now renders explicit empty-gap and media-error states rather than silent black frames.
- Editor transport uses local SVG controls with a prominent accessible Play/Pause button. Playback, pause, scrub, visual switching, image/video boundaries, and gap behavior pass the real-browser gate.
- New Project now distinguishes Single Title, registry-backed Franchise expansion, and Custom Multi-Title (minimum two unique titles).
- The canonical Clue V4 prompt is available from New Project. Copy Ready Prompt combines it locally with source scope, selected titles, and the clean script.
- Imported clues are independently checked for schema, beat IDs, references, scope, prohibited timestamp authority, narration coverage/order, and exact/punctuation/word mismatch.
- Character cards now provide per-character reference management, dedupe, conservative quality validation, and disk-persisted Trust/Reject actions.

## Known limitations

- Quadro P1000 acceleration is not currently safe: PyTorch kernels exclude compute capability 6.1, faster-whisper CUDA modes were unstable, OpenCV lacks CUDA DNN, and FFmpeg NVENC requires a newer driver API.
- Character face validation is conservative. Zero imported references were auto-trusted.
- Rich Atlas building remains lazy and source-bound; there is no mass indexing.
- The New Project preparation UI is a staged foundation. Retrieval and employee approval retain their existing fail-closed gates.
- Custom scope is validated during intake; durable project-scope persistence is applied when the prepared project is created by the existing planner.
- Character reference bulk Trust/Reject is not yet exposed; individual persistent decisions are supported.

## Safe next work

Use the application for employee onboarding and normal project operation. Hardware acceleration should only be enabled after a fresh runtime proof passes on this exact machine. Do not modify frozen project artifacts to improve new benchmarks.
