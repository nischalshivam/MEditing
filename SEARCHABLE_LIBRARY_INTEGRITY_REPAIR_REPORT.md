# Searchable Library Integrity Repair V1

Verdict: BLOCKED — corrected index candidate was rejected and not promoted.

## Proven root causes

1. `portable_library.scan()` used `p.parent.glob(p.stem + '*')`. Thus `Episode 1` matched subtitles for `Episode 10` through `Episode 16`. This created 23 exact cross-episode transcript duplicates and attached multiple complete transcripts to the Episode 1 source IDs.
2. After replacing that logic with exact parsed `(season, episode)` matching, four exact cross-season duplicate payloads remained. Local physical sidecar files for S02E02, S05E04, S05E06, and S05E07 contain the same complete normalized transcript as S01E02, S01E04, S01E06, and S01E07 respectively. These are source-sidecar integrity failures, not FTS display errors.

## Audit

- Physical Breaking Bad sources: 62
- Old Breaking Bad subtitle/FTS rows: 81
- Old cross-episode identical payload groups: 23
- FTS rows whose displayed payload differed from its subtitle row: 0
- Corrected candidate rows: 62
- Remaining unexplained exact cross-episode payload groups: 4
- SEARCHABLE_READY episodes: 0 (title-wide production gate remains closed)
- Whisper runs: 0
- Media/subtitle files modified: 0
- Rich builds: 0

The old index was preserved for audit and the corrected V2 tables remain unpromoted. Walter-book discovery V2 and smoke tests were intentionally not run because their evidence would still be untrusted.

## Required repair

The four invalid sidecars require a trustworthy replacement transcript source: a valid matching embedded stream/sidecar, or bounded local retranscription of only those four episodes. Only then can the corrected 62-episode index be validated, atomically promoted, smoke-tested, and used for Walter-book discovery V2.
