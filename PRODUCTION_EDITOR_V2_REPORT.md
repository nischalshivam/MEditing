# Production Editor V2

## Employee workflow

- Real native clean-script and voiceover file inputs, paste-script alternative, previews and validation metadata.
- Uploaded inputs are copied into canonical SSD project folders; original laptop paths are not the authority.
- Automatic clue artifact generation is the default. Advanced clue controls remain separate.
- Single-title, franchise and custom multi-title scopes are supported without merging title libraries.
- Per-title readiness clearly identifies only the blocking title.

## Editing workspace

- Compact 1920x1080-oriented three-panel workspace with centered 16:9 preview and resizable timeline height.
- V1 visual track, A1 voiceover waveform strip, narration context, inspector, time ruler, zoom and issue navigation.
- Timeline selection, edge handles, video trim, image duration, ripple, split, close-gap delete, video/still switch, approved replacement, manual upload, undo and redo persist to SSD project state.
- B002/B022 remain explicit red manual blocks and open the replacement drawer.
- Playback controls include play/pause, Fit, Fill and Fullscreen.

## QA and safety

- Exact production launcher used.
- Sheldon Universe readiness rendered separately: TBBT needs preparation; Young Sheldon is partially ready.
- Real duplicated Skyler project: 145 -> split 146 -> undo 145 -> redo 146.
- Replacement drawer showed eight approved candidates; Review Issues selected B002.
- Timeline zoom changed from Fit to 1.5x.
- Regression suite: 141 passed.
- Frozen retrieval SHA remains `08428494d51f7d6f9e75208dd6e2c8ca2007e2641d28ee4d975008392dc1d4e5`.
- No mass transcription or Rich Atlas jobs were started.

## Known browser-automation limitation

The browser-control surface could not programmatically assign native file inputs, but both actual native Browse controls and the managed-upload backend are present and validated. A human OS file-dialog smoke test remains appropriate for the UX acceptance pass.
