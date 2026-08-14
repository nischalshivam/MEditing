# ResearchCut × SceneBrain Editor V1 Integration

ResearchCut Editor 2.1 is now the production editing engine launched by `START_SCENE_BRAIN.bat`. The original supplied package remains preserved under the read-only reference working directory; production uses a separate integration copy.

- Walter migrated: 70 V1 clips + final 878.1-second A1 voiceover.
- SceneBrain provenance and candidate lists remain attached to clips.
- Source media is referenced externally and remains read-only.
- ResearchCut trim, duration, source-in, framing, crop, transforms, split/delete, undo/redo, timeline zoom, media bin and transport are retained.
- Real 120-second playback and all 69 V1 boundaries passed.
- Responsive browser QA passed at 1366×768, 1440×900 and 1920×1080.
- Project-independent adapter fixture passed.
- Canonical migrated editor state was restored byte-for-byte after QA.
- SceneBrain regression tests: 172/172 PASS.
- ResearchCut integration and render tests: PASS.
