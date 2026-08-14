# Breaking Bad Discovery Router V4 — Final Report

Verdict: **BREAKING_BAD_SOURCE_ROUTER_V4_READY_FOR_HUMAN_SOURCE_REVIEW**

## Audio/text authority gate

- Physical episodes: 62
- AUDIO_TEXT_VERIFIED: 62
- BORDERLINE: 0
- FAILED: 0
- Already verified episodes were not reprocessed.
- Expanded five-window checks were limited to S03E03, S03E10, S05E09 and S05E10.
- Existing source-bound replacements were verified for S01E02, S01E04, S01E06 and S01E07.
- Their five-window mean token F1 scores were 0.855, 0.802, 0.791 and 0.641 respectively.
- Four original mismatched Season-1 sidecars remain preserved; the canonical bindings now use managed Whisper replacements.
- Canonical authority: exactly one trusted transcript per episode, with `SIDECAR_VERIFIED` or `MANAGED_WHISPER_REPLACEMENT` provenance.

## Windowed router

- Trusted sources indexed: 62
- Overlapping dialogue windows: 7,963
- Window size/stride: 8 cues / 4 cues
- Production index: `.scene_brain/libraries/breaking_bad_dialogue_windows_v4_0.db`
- Exact phrase is attempted before local proximity search.
- `W.W.`, `W W`, `WW`, and `W. W.` normalize to one protected token.
- Every emitted matched term is asserted to occur inside its returned evidence window.
- Rejected sidecars cannot enter the window index because it is constructed only from the final authority map.

Dialogue smoke passed for `tread lightly`, `you got me`, `Learn'd Astronomer`, and `W.W.`. The first two resolve by exact phrase; Learn'd Astronomer resolves to S04E04 with a full local-window match. Visual smoke correctly abstains from treating dialogue as proof of silent physical actions.

## Walter-book discovery V4

- Clean script SHA-256: `5ab589901ad5c9029d568107ac48e9512826dbd1b3cad1f137632068a314e4cc`
- Validated clue SHA-256: `9354ae8b68d8aaa9f7ef0b7057daa993a76e6b482c7ca72ae44049902818bede`
- Beats: 41
- Canonical events resolved once: 15
- Recommended visual slots: 70
- STRONG_LOCAL_WINDOW: 7
- VISUAL_SOURCE_UNVERIFIED: 6
- AMBIGUOUS: 2
- Deduplicated human source-review events: 8

The queue is canonical-event based, has at most three episode options per item, and excludes duplicate beats and editorial-only beats. Visual-only events stay explicitly unverified even when dialogue supplies useful candidate episodes.

## Safety and verification

- Cloud API cost: $0
- Rich Atlas builds: 0
- Original media writes: 0
- Other titles processed: 0
- TBBT/BCS/YS jobs started: 0
- Skyler frozen retrieval SHA remains `08428494d51f7d6f9e75208dd6e2c8ca2007e2641d28ee4d975008392dc1d4e5`.
- Skyler timeline remains 145 presentation slots.
- Regression suite: 160/160 passed via `python -m unittest discover -s tests -q`.

## Artifacts

All requested receipts and outputs are under `runtime/bb_discovery_router_v4/`, including the final alignment, authority map, promotion receipt, window receipt, both smoke suites, canonical event map, unchanged-script discovery result, review queue, and metrics.

No Rich Atlas construction was started. The next action is the bounded eight-event human source review.
