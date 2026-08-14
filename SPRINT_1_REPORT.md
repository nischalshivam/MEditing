# Sprint 1 completion report

Status: **complete within the approved Sprint 1 boundary**. Sprint 2 has not started.

## Built

- New independent Python project; no import or runtime dependency on either legacy editor.
- Typed settings, JSON logging, CLI, content hashing, deterministic fingerprints and read-only source policy.
- SQLite migration runner with WAL, foreign keys, integrity checks and FTS5.
- Title/source catalog with season/episode identity, full source SHA-256 and FFprobe metadata.
- Media doctor for video/audio presence, duration, dimensions, identity and source receipt.
- Same-source subtitle discovery, strict SRT parser, normalization, cue persistence and FTS5 index.
- Subtitle candidate evidence for filename identity, parse integrity, monotonicity and duration bounds.
- Independent sampled local faster-whisper audio verification. Origin alone never proves authority.
- Token-boundary-safe, same-track, contiguous multi-cue dialogue search with duplicate-prefix collapse.
- FFmpeg physical shot detection, exact coverage invariants and one midpoint keyframe per shot.
- Content/settings-addressed shot and keyframe caches. A detector threshold or source-byte change invalidates the result.
- Standalone frozen 40-question S04E01 benchmark: 8 human frame-reviewed visual/action/negative questions and 32 human-reviewed exact-dialogue occurrences. The freeze forbids accuracy claims in Sprint 1.
- Automated unit/integration tests for migrations, FTS, parsing, normalization, episode identity, multi-cue search, token boundaries, hashing, detector invalidation, benchmark constraints and representative timestamps.

## Real S04E01 result

Source: `D:\Breaking Bad\Breaking Bad Season 4\Breaking Bad Season 4 Episode 1.mp4`

- Doctor: PASS
- SHA-256: `29b0c732612d06d750bdd7b94cd3973bbf2b792e871d5eb53c5bfbd946f46e3a`
- 639,377,539 bytes; 2,851,294 ms; 1920x1080; 25 fps; H.264 + AAC
- Identity parsed: S04E01
- Matching subtitle candidates: 1 external English SRT; no embedded subtitle stream
- Parsed cues: 383
- Subtitle identity: MATCH
- Sampled audio verification: VERIFIED_WITH_OFFSET
- Measured median offset: -172 ms; median absolute deviation 706 ms
- 139 matched ASR/subtitle tokens across three separated episode windows
- Window sequence ratios: 0.786885, 0.754098, 0.967742
- Physical shots at threshold 0.15: 460
- Representative keyframes: 460 (10,721,113 bytes total)
- Identical cached rerun: 1.788 seconds; shot cache hit true
- SQLite integrity check: `ok`

## Dialogue search examples

- `how's it coming` -> cue 1, 44,127–45,670 ms
- `very very well it's a flurry of deliveries` -> contiguous cues 2–3, 46,838–52,218 ms
- `you kill jesse you don't have me` -> cue 306, 1,975,431–1,977,934 ms
- Word-boundary regression: query `no` does not match subtitle word `know`.

## Database tables

Logical tables: `schema_migrations`, `titles`, `source_files`, `analysis_runs`,
`subtitle_tracks`, `subtitle_cues`, `subtitle_cues_fts`, `shots`, `keyframes`,
`benchmark_freezes`. SQLite also creates four internal FTS5 support tables.

Current primary counts: 1 title, 1 source, 1 subtitle track, 383 cues,
460 shots, 460 keyframes, 2 benchmark freeze receipts. The final benchmark is
`s04e01-sprint1-mixed-v2`; the earlier dialogue-only V1 receipt is retained as
transparent superseded history, not the evaluation set.

## Verification

- `python -m unittest discover -s tests -v`: 12/12 PASS
- `python -m compileall -q src tests`: PASS
- Real media doctor, ingest, subtitle parse/index, ASR sync, FTS/multi-cue searches,
  full shot detection, all keyframe extractions, cache replay and benchmark freeze: PASS

## Honest limits / uncertainty

- No scene atlas or semantic scene retrieval exists yet, so there is no scene-retrieval accuracy number.
- The 0.15 cut threshold produced a structurally valid physical-shot index, but human boundary precision/recall is not yet scored.
- Subtitle sync was measured at three separated windows, not every spoken cue. It is strong title/track evidence, not a guarantee that every cue boundary is frame-perfect.
- Thirty-two benchmark items test exact dialogue occurrence; eight test visual/action/negative retrieval. This is a frozen development benchmark for S04E01, not evidence of generalisation across titles.
- No Gemini, TwelveLabs, renderer, timeline, filler, interpolation, invented timestamps, GUI or editing features were added.

## Exact Sprint 2 proposal (not started)

1. Freeze the Sprint 1 source, subtitle, shot and benchmark manifests as immutable inputs.
2. Add a versioned `scenes` / `scene_shots` schema whose boundaries can only reference existing physical shot IDs.
3. Build deterministic baseline grouping from temporal adjacency, shot duration, colour/motion discontinuity and subtitle-density gaps.
4. Produce review packages containing ordered keyframes, short temporal previews and nearby dialogue; a model may label/group proposals but may not return timestamps.
5. Represent uncertain boundaries explicitly as `UNKNOWN`, never force a confident scene.
6. Add human scene-boundary review/import tooling and provenance receipts.
7. Run the frozen 40 questions only for Scene Atlas coverage diagnostics—report coverage and abstention separately, and do not yet call it final resolver accuracy.
8. Add transition/montage flags and version/cost/model fingerprints for every semantic artifact.
9. Test invalid shot IDs, gaps, overlaps, stale source hashes, tampered artifacts, UNKNOWN boundaries and deterministic replay.
10. Stop after Scene Atlas acceptance; begin Sprint 3 Scene Search/Resolver only after explicit approval.

