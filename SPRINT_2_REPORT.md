# Sprint 2 — One-Episode Narrative Scene Atlas

## Verdict

**PASS WITH ISSUES** for: “Is the S04E01 Scene Atlas reliable enough to build a retrieval engine on top of?”

It is reliable enough for a precision-first Sprint 3 experiment because 460/460 physical shots are covered, the core Box Cutter narrative scene is preserved as one coherent scene, and 11/13 canonical scenes passed full human inspection. It is not perfect: the final scene is a real bad merge and has wrong summary semantics. Sprint 3 must retain abstention and must not assume every atlas boundary is correct.

No Scene Search/Resolver, Shot Resolver, script compiler, timeline, renderer, editor, filler, interpolation, TwelveLabs, or GUI work was built.

## 1. Security and preflight

- `.gitignore` now covers `.env` and `.env.*`, while allowing `!.env.example`.
- Gemini credential detected: yes (value never stored)
- Gemini credential detected: yes (value never stored)
- Credential detected: yes. Credential printed/logged/stored/committed: no.
- No secret appears in config, SQLite, reports, cache keys, prompts, errors, or exception traces.
- Source SHA-256 after all work is unchanged: `29b0c732612d06d750bdd7b94cd3973bbf2b792e871d5eb53c5bfbd946f46e3a`.

## 2. Dependencies

Base: `Pillow>=11,<13`, `pydantic>=2.10,<3`.

Optional groups:

- `asr`: `faster-whisper>=1.1,<2`
- `gemini`: `google-genai>=1.30,<2`
- `dev`: reserved, currently empty because tests use `unittest`

FFmpeg and FFprobe remain documented system dependencies. Editable clean install with `[gemini,asr]` passed.

## 3. Frozen Sprint 1 inputs

Freeze fingerprint: `a077fbcc605fbc8cab15b3d3aceead64abb535748f6d1e495609af793c09e7a4`.

It binds the source bytes/SHA, selected subtitle track and measured sync evidence, 383 normalized cue records, detector fingerprint/configuration, all 460 physical shot boundaries, all 460 keyframe hashes/extraction fingerprints, and both Sprint 1 benchmark receipts. Gemini never mutated timestamps or shot boundaries.

## 4. Provider/model/config

- Swappable interface: `VisionProvider.analyze_scene_window()`.
- Provider: official Google GenAI SDK.
- Final model: `gemini-3.1-flash-lite`.
- Prompt: `scene-atlas-prompt/1.0`; schema: `scene-atlas-schema/1.0`.
- Temperature 0.1; top-p 0.8; maximum output 8,192 tokens.
- `gemini-2.5-flash-lite` was initially configured, but Google returned that it is unavailable to new users. It was not silently replaced by an expensive tier; the current stable Flash-Lite class was explicitly selected.
- First 3.1 schema attempt exposed a provider compatibility issue with Pydantic `additionalProperties`; switching to the SDK's JSON-schema field fixed it. A reconstructed audit row transparently records the failed call. Future retries preserve prior failed rows rather than deleting them.

## 5. Windows and evidence packages

- 39 ordered overlapping windows.
- Typically 15–23 shots; final edge window has 12 shots.
- Target duration 90 seconds; min 15, max 30 shots; overlap 5 shots.
- Every package contains title/episode context, ordered authoritative shot IDs, visible shot-ID-labelled contact sheet, verified local dialogue, keyframe/package hashes and freeze fingerprint.
- Model proposals covered every shot in each window; gaps, overlaps, invented IDs, reversed boundaries and out-of-span semantic evidence are rejected.
- No model requested a temporal preview (`needs_temporal_preview=0/39`). Temporal-preview plumbing was therefore not invoked; this remains a future quality lever, not fabricated evidence.

## 6. Gemini calls, cache, tokens and cost

- Validated successful atlas windows: 39/39.
- Stored pipeline failures: 1 retired-model failure plus 1 reconstructed schema-profile failure.
- Successful token usage: 62,714 input; 43,243 output; 105,957 total.
- Estimated paid-list cost: **$0.0235686** using the applicable Flash-Lite input/output rates. Actual billing may be zero under a free tier; the API did not return a charged-USD field.
- Full production pass contained 37 live misses and 2 earlier smoke cache hits.
- Exact replay: 39/39 cache hits in 2.452 seconds, zero new Gemini calls.
- Hard controls: maximum 40 windows per command and $2 cumulative estimated-cost ceiling.

Smoke evidence:

- Gemini connection: PASS
- Model: `gemini-3.1-flash-lite`
- Credential detected: yes
- Credential printed: no
- Smoke windows: 2
- W001 cache replay hit; W002 first-run miss
- Structured multimodal output and usage metadata: PASS

## 7. Scene Atlas result

- Canonical narrative scenes: 13.
- Physical-shot coverage: 460/460 exactly once.
- Canonical UNKNOWN boundary values: 0/13.
- Canonical scenes whose chosen semantic proposal covered less than half the stitched span: 3/13 (23.1%), retained as analysis `UNRESOLVED` rather than silently promoted.
- Window-proposal boundary statuses: 49 SUPPORTED, 6 UNKNOWN_END, 5 UNKNOWN_BOTH, 2 UNKNOWN_START.
- Canonical special types: 1 montage; 12 normal.
- Window proposals also contained 3 transition and 1 other classifications, but overlap stitching did not preserve all of them—this directly contributed to the final bad merge.

Human-readable packages exist for every scene with scene IDs, derived local times, shot range/count, semantics, characters, location, actions, objects, uncertainty, nearby dialogue and labelled contact sheet.

## 8. Human Scene Atlas inspection

All 13 canonical scenes were manually inspected using their shot-ID contact sheets—not a small cherry-picked sample.

Primary classifications:

- GOOD: 11
- MINOR_BOUNDARY_ERROR: 1
- BAD_SPLIT: 0
- BAD_MERGE: 1
- WRONG_SEMANTICS: 0 primary, 1 secondary
- UNKNOWN: 0
- TRANSITION_SPECIAL_CASE: 0 primary, 2 secondary

Strict GOOD rate: **84.6% (11/13)**. This is Scene Atlas inspection, not scene-retrieval accuracy.

### Good examples

- `SC001`: Gale gives Gus the initial superlab tour.
- `SC007`: Saul searches his office while Huell waits.
- `SC009`: Skyler and the locksmith enter the home.
- `SC011`: the long Box Cutter superlab sequence correctly remains one narrative scene across 160 physical shots, including Gus entering, changing, killing Victor, reactions and cleanup.
- `SC012`: Walter/Jesse diner conversation.

### Failures and hallucinations

- `SC002`: title shot was merged into Jesse's house montage—minor transition-boundary error.
- `SC013`: taxi/arrival, Walter-Skyler doorstep, Jesse aftermath montage and end credits were merged—BAD_MERGE.
- `SC013` summary called parts a crime-scene investigation—secondary WRONG_SEMANTICS.
- One proposal named Saul's receptionist “Francesca Liddy”; the surname is unsupported by provided local evidence and is treated as a character-name hallucination risk.
- W001 attributed the utility-knife action to Gale from scene context, though the tight insert alone does not prove hand identity. Evidence is useful but not independently sufficient for that character-action binding.

## 9. Stitching assessment

The conservative stitcher accepts a boundary only when supporting end-boundary votes exceed overlapping proposals that cross it. This prevented over-splitting the long lab sequence, but equal-vote cases at the episode end remained merged. Relaxing ties globally would create 49 scenes and severe over-splitting, so the failure was preserved instead of patched with a one-off rule.

Sprint 3 should treat an atlas scene as a candidate region, not unquestionable ground truth, and should expose neighboring scenes when boundary confidence is weak.

## 10. Database/migrations

Migration version 2 added:

`scene_input_freezes`, `scene_analysis_windows`, `scene_analysis_runs`,
`scene_window_proposals`, `scenes`, `scene_shots`, `scene_characters`,
`scene_locations`, `scene_actions`, `scene_objects`, `scene_semantics`,
`scene_flags`, `scene_uncertainties`, and `scene_provenance`.

Scene times are always derived from first/last existing physical shots. All semantic rows retain evidence shot IDs and provenance. Model/provider/prompt/schema/input/output fingerprints, usage, estimated cost, status and sanitized errors are stored; credentials are not.

## 11. Automated verification

- Full Sprint 1 + Sprint 2 suite: **23/23 PASS**.
- Compile-all: PASS.
- SQLite integrity: `ok`.
- Tested: credential boolean behavior, UNKNOWN values, invented/out-of-window IDs, reversed boundaries, proposal overlaps, omitted-shot gaps, invalid enums, extra timestamp-like fields, evidence outside scene span, prompt/model invalidation, tampered cache seal, FTS/multi-cue correctness, source hashing and detector invalidation.
- Real integration checks additionally verified 39-window cache replay, 460/460 canonical coverage, all source/keyframe hashes and unchanged source SHA.

## 12. Frozen visual-heavy holdout

- Name: `S04E01_VISUAL_HOLDOUT_V1`
- Questions: 30
- SHA-256: `e362338e034a07bc3411de2eff19d05c03ce8ee033d5ffa86cdb33a56938c396`
- Mix: 12 exact visible events, 4 reactions, 5 object/actions, 4 scene-context, 2 confusing-similar and 3 negative/NONE.
- It was frozen before any Sprint 3 resolver implementation and was not used to tune the Scene Atlas.
- The original Sprint 1 40-question benchmark remains unchanged.

## 13. Remaining technical risks

- Static contact sheets can misattribute tight hand/object inserts; optional temporal previews and neighboring-shot evidence should be evaluated.
- Character full names can leak from model memory despite local-evidence instructions; a future entity authority/alias layer must downgrade unsupported names.
- Conservative overlap stitching under-splits equal-vote transitions; global tie acceptance over-splits badly.
- Only one episode/title has been inspected; no generalisation claim is made.
- Flash-Lite model availability and pricing can change; fingerprints make such changes invalidate cached semantics.
- A scene-level search can only be as precise as the atlas region; `SC013` demonstrates why Sprint 3 needs neighbor expansion and abstention.

## 14. Exact proposed Sprint 3 — Scene Search/Resolver (not started)

1. Freeze this atlas, provider artifacts and both benchmarks; treat the visual holdout as evaluation-only.
2. Define a typed retrieval request with objective characters/actions/objects/location/dialogue evidence and UNKNOWN-safe constraints.
3. Build scene-level candidate generation from local subtitle FTS, structured atlas fields and separately versioned local scene embeddings—never whole-episode arbitrary-frame search.
4. Retrieve top-K scenes with per-channel scores and evidence; do not collapse to top-1 early.
5. Add hard filters for source/episode, required evidence, NONE queries, unsupported character identity and stale atlas fingerprints.
6. Expand weak/uncertain candidates to adjacent scenes so conservative stitching errors do not hide the correct region.
7. Use Gemini only as a fail-closed top-K scene verifier bound to the request and candidate scene evidence; it still may not invent timestamps.
8. Return VERIFIED, CONTEXTUAL or ABSTAIN plus evidence and alternatives. No shot/crop resolution yet.
9. Evaluate once on `S04E01_VISUAL_HOLDOUT_V1`, reporting exact precision, contextual precision, coverage, NONE precision, abstention and failure categories separately.
10. Stop after Scene Resolver evaluation. Start Shot Resolver only after explicit approval and only if scene-level results justify it.

