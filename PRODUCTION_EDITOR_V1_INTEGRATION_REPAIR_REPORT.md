# Production Editor V1 Integration Repair

## Root causes

1. The launcher opened the browser after a blind two-second delay, did not set the application package path reliably, had no health endpoint, and suppressed backend startup failures.
2. The frontend used a bootstrap path that could fail before registering usable navigation and then swallowed the exception, leaving the status permanently at `Connecting`.
3. Rescan returned a placeholder response rather than executing the incremental catalog scan.
4. Earlier browser QA established only that HTML rendered; it did not exercise navigation or playback.

## Repair

- Added `/api/health` and health-gated startup.
- Replaced arbitrary launcher delay with bounded health polling and persistent launcher/server logs.
- Added explicit CONNECTING, CONNECTED, CONNECTION ERROR, and MEDIA DRIVE MISSING states with Retry and visible details.
- Implemented hash-based four-screen navigation and refresh-safe screen state.
- Connected the Library, Projects, New Project, Editor, rescan, project-load, timeline, audio/video preview, edit and disk-persistence flows.
- Real rescan now runs the incremental portable-library scanner.
- Added HTTP byte-range media serving and production-copy duplication for safe editor smoke tests.

## Real production-path QA

- Exact launcher: PASS
- Backend health: PASS
- Connected SSD: `E:\Movies`
- Six real titles: PASS
- Library / Projects / New Project / Editor navigation: PASS
- Rescan: 619 checked, 619 unchanged
- Skyler: 145 composition slots, B002/B022 manual markers
- Preview media: ready, 887.3 seconds
- Playback: 2.95 seconds observed
- Scrub: moved to 11.75 seconds
- QA-copy split persisted after reload: 145 -> 146
- Browser console errors: 0
- Automated tests: 139 passed

Frozen retrieval and the historical Skyler project were not modified.
