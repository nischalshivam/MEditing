# Product Onboarding, GPU, Character Library, and Handoff Report

Verdict: PASS with stable CPU fallback for GPU-incompatible workloads.

## User journey

The normal `START_SCENE_BRAIN.bat` launcher served the real application. Real Chrome at 1366×768 completed Library navigation, temporary Movie onboarding, temporary two-episode Series onboarding, title availability in New Project, script upload, Analyze, Prepare gating/progress, Breaking Bad character management, GPU diagnostics, editor load, and support-report creation. Temporary sources and their exact catalog records were deleted after QA; the canonical library returned to six titles and 619 sources. Browser exceptions and failed network requests were zero.

Responsive overflow checks passed at 1366×768, 1440×900, and 1920×1080.

## Character library

The Desktop `Characters\Breaking Bad` tree was inspected read-only. Twenty-four unique images were copied to canonical SSD storage; one duplicate Walter image was suppressed by SHA-256. Seven stable character IDs were created. All references remain `PARTIAL`/suggested because conservative face and image-quality checks did not justify automatic trust. Original Desktop bytes were not modified.

## GPU and resource management

The physical GPU is an NVIDIA Quadro P1000 with 4096 MiB and driver 582.16. Framework enumeration maps it to `cuda:0`; Windows Task Manager’s GPU number is not used. Bounded tests covered PyTorch, faster-whisper, OpenCV, software FFmpeg, and NVENC. None produced a stable supported GPU production path with the installed stack. AUTO therefore chooses CPU. This is an explicit safe fallback, not a claim of GPU acceleration.

Resource policy limits CPU workers to four, GPU/heavy-GPU concurrency to one, and reserves 768 MiB VRAM headroom. CPU faster-whisper and software libx264 smoke tests passed.

## Editor hardening

The ResearchCut editor foundation remains intact. Performance is reachable from the editor. Preview distinguishes empty visual gaps and failed media from valid media. Video thumbnails probe bounded nearby frames when the primary timestamp is black. Existing replace, non-ripple, timeline, persistence, automation, and render behavior remains governed by the regression constitution.

## Validation

- Python regressions: 187 passed.
- Real Chrome product gate: PASS.
- Add Movie: PASS.
- Add Series: PASS.
- New Project responsive layout and Analyze/Prepare workflow: PASS.
- Character thumbnails: 24/24 loaded with nonzero natural dimensions.
- Console errors: 0.
- Failed requests: 0.
- Catalog after cleanup: six titles, 619 present sources.

Evidence is in `qa_artifacts/SCENE_BRAIN_PRODUCT_HARDENING_GATE.json`, `qa_artifacts/PRODUCT_ONBOARDING_BROWSER_QA.json`, GPU reports, and required screenshots.
