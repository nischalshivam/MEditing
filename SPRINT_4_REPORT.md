# Sprint 4 Report — Bounded Exact Shot / Moment Resolver

## Verdict

**FAIL**

The prototype is precision-first and its three automatically accepted holdout crops were correct, but it cannot yet reliably locate and verify exact usable moments at useful coverage. Frozen holdout candidate Recall@5 was only **76.47%** and VERIFIED_EXACT coverage was **17.65%**. Do not build an automatic editor on this version.

Sprint 5/editor was not started.

## Architecture

`SceneRetrievalRequest` plus the complete frozen Sprint 3 result enters a separate Shot Resolver. It consumes up to three ranked scenes and declared neighbors; it never changes Sprint 3. Evidence-shot provenance, matching fragments and verified subtitle cues seed bounded physical-shot neighborhoods. Candidate groups are locally ranked, deduplicated and capped at 12. Gemini receives batches of four bounded candidates, can select only an opaque candidate ID or NONE, and an independently generated final crop is checked by a second verifier pass.

Outputs are `VERIFIED_EXACT`, `REVIEW_REQUIRED`, or `ABSTAIN`. Sprint 3 CONTEXTUAL cannot become exact. Sprint 3 ABSTAIN cannot export. SC013 is boundary-sensitive and cannot auto-promote in v1.

## Frozen inputs and fingerprints

- Source SHA-256: `29b0c732612d06d750bdd7b94cd3973bbf2b792e871d5eb53c5bfbd946f46e3a`
- Sprint 3 resolver fingerprint: `a034568b3dccbddedfee81c7f41e7edd673f172c6ce6c2eff0e1115681f41847`
- Shot Resolver input fingerprint: `ea83382c917cdd2e19bbc36f86f7087f46bc852b9a679ffe236135aa2cf0b115`
- Shot Resolver fingerprint: `b8d6fedf926ca226eb769574039104e055c60f079f2cfd0fae7f8a2b6c314585`
- Holdout SHA-256: `3a471932f8f9253386193e77f02dde76e7883b302512186673fd51ff9c2ba118`
- Immutable evaluation SHA-256: `a909810f2bc85c69d5bcca11dec6975fc389980bcff1fa795566b4c4df2e86db`

No Sprint 3 ranking, thresholds, prompt, resolver artifact, Scene Atlas record, or heldout result was modified.

## Shot benchmark

36 new human-reviewed requests were prepared from local episode frames:

- `SHOT_RESOLVER_DEV_V1`: 18
- `S04E01_SHOT_HOLDOUT_V1`: 18, frozen before final evaluation

Combined coverage includes exact actions, object use, reactions, entrances/exits, dialogue-linked visuals, close-up inserts, adjacent confusing moments, and NONE requests. Positive records contain acceptable shot ranges, derived local time intervals, multiple-shot allowance and human-review evidence. The holdout was separate from the scene-level benchmark.

Limitation: the target was 35–60 total queries, but the final holdout itself has only 18 (17 positive, one NONE). These results are useful diagnostic evidence, not a production-grade confidence interval.

## Candidate pool

Normal path:

1. frozen Sprint 3 top-3 scenes and neighbors;
2. matched evidence-shot IDs;
3. matching typed fragments inside only those supplied regions;
4. subtitle cue to active shot plus ±2 shots for exact dialogue;
5. evidence seed ±2 physical shots;
6. overlapping range collapse and top-12 ranking.

No ordinary whole-episode search and no global frame embedding were added. Recovery outside supplied regions was not enabled.

## Temporal evidence

For queried candidate ranges only, the system content-addresses:

- low-resolution H.264 preview clips;
- dense sequential contact sheets at configurable 3 FPS;
- final verification sheets at 5 FPS;
- previous/current/next context through contiguous multi-shot groups.

372 artifact receipts were generated. Source media remained read-only. Static representative keyframes are not treated as sufficient proof of an action.

## Reaction and dialogue handling

`ShotRequest` supports `reaction_subject`, `reaction_trigger`, and BEFORE/DURING/AFTER direction. The bounded pool can prioritize event-adjacent evidence. Exact dialogue maps verified cues to the physically active shot and neighboring cuts; it never assumes the speaker is on screen. The benchmark did not contain enough structured exact-dialogue/reaction cases to validate these paths robustly.

## Candidate verifier

- Model: `gemini-3.1-flash-lite`
- Prompt: `shot-candidate-verifier/1.0`
- Batch size: 4
- Allowed decisions: LITERAL_MATCH, PARTIAL_MATCH, NONE_OF_THESE
- Candidate and shot IDs are validated; timestamps are forbidden.
- PARTIAL_MATCH never exports.

Dense temporal frame sheets are sent to the provider; cached MP4 previews are retained for human review. Inline MP4 calls initially failed at the provider/runtime boundary, so temporal sequential frames became the stable transport.

## Final crop verifier

- Prompt: `final-crop-verifier/1.0`
- Allowed decisions: VERIFIED_CROP, REVIEW_REQUIRED, REJECTED
- It independently checks literal action, object, explicitly required character, temporal relation and usability.
- It sees only the actual selected crop evidence and cannot substitute a different candidate.
- Model timestamps are neither requested nor accepted; local shot bounds derive all times.

Crop usability flags cover too short/long, mid-motion start, missing reaction, transition, better neighbor and usable.

## Crop derivation

V1 crops use exact local physical-shot-group bounds. The implementation stores configurable editorial handles, but cannot extend beyond the authoritative selected group in this version. This is safe but contributes to low coverage and occasional crop rejection. It is not frame-perfect refinement.

## Frozen holdout metrics

| Metric | Result |
|---|---:|
| Candidate Recall@1 | 58.82% |
| Candidate Recall@3 | 70.59% |
| Candidate Recall@5 | 76.47% |
| VERIFIED_EXACT precision | **100% (3/3)** |
| VERIFIED_EXACT coverage | **17.65% (3/17 positives)** |
| Wrong auto-accept rate | **0%** |
| REVIEW_REQUIRED rate | 0% |
| ABSTAIN rate | **83.33%** |
| NONE correct abstention | 1/1 |
| NONE false positive | 0 |

The correct interpretation is “high observed precision at very low coverage,” not 100% accuracy.

### By category

| Category | N | Candidate Recall@5 | VERIFIED_EXACT |
|---|---:|---:|---:|
| Enter/leave | 3 | 100% | 0 |
| Exact visible action | 4 | 25% | 1 |
| Object/action | 8 | 100% | 2 |
| Reaction | 2 | 50% | 0 |
| NONE | 1 | N/A | 0 |

The three accepted crops were manually inspected after immutable evaluation:

- SR10: Saul visibly searches the office floor — correct and usable.
- SR16: Hank visibly uses the laptop/mineral page — correct context/action.
- SR32: Jesse visibly eats at the diner — correct and usable.

## Failure taxonomy

- **Correct scene, exact moment absent from candidate top-5:** dominant problem for long/coarse scenes and exact visible actions.
- **Correct candidate present, verifier false negative/conservative rejection:** common; many candidate hits still became ABSTAIN.
- **Reaction failure:** reaction Recall@5 was 50%, with no reaction auto-accepted.
- **Object visible but requested action unproven:** correctly rejected rather than hidden with contextual footage.
- **Correct shot but crop rejected:** occurred where the local group had relevant frames but second pass did not establish literal/usable action.
- **SC013 boundary effects:** remained fail-closed; known atlas issues were not manually repaired.
- **Verifier false positives:** zero among final accepted crops in this small holdout.
- **Verifier false negatives:** materially high, inferred from human-ground-truth candidate hits followed by ABSTAIN.

The evaluation’s first execution attempt stopped before artifact commit when Gemini returned an invented/cross-candidate shot ID. The response was correctly detected, but validation raised instead of producing ABSTAIN. Only this fail-closed plumbing was corrected; ranking, K, prompts, sampling and thresholds remained frozen. The resumed run reused identical cached responses. This interruption is recorded in the immutable evaluation artifact.

## Cost, cache and speed

Recorded Sprint 4 development plus holdout attempts:

- Candidate verifier records: 114
- Final crop verifier records: 11
- Total recorded calls/attempts: 125
- Input tokens: 471,961
- Output tokens: 8,323
- Total tokens: 480,284
- Estimated cost: **$0.0505253**

Holdout completion time after cached partial attempt: **200.57 seconds**. Exact artifacts and successful verifier outputs are content-addressed. Tests verify tamper rejection and deterministic schemas. A second full holdout replay was intentionally not run because the evaluation is immutable.

Local-only final resolution was effectively 0% for eligible exact positives; local logic generates candidates but does not claim literal verification without Gemini.

## Database/storage foundation

Migration 5 adds:

- `shot_resolver_input_freezes`
- `shot_resolver_versions`
- `shot_temporal_artifacts`
- `shot_resolver_runs`
- `shot_verifier_runs`
- `shot_resolver_evaluations`
- `shot_editorial_memory`

Editorial memory supports APPROVE/REJECT provenance, event signatures, scenes, shot ranges, local intervals, aliases, evidence class and source hash. No automatic global memory ranking was added.

## CLI and inspection

`scene-brain resolve-shot request.json` consumes a typed request containing the frozen Sprint 3 result. Output contains candidates, exact physical shots/range, local source interval, decision, evidence, Gemini passes, usability flags and preview path.

Each benchmark request has review sheets; every accepted result has the actual MP4 crop and a manually inspected tiled preview.

## Automated tests

Full Sprint 1–4 regression suite:

- **45/45 PASS**
- Runtime: 0.891 seconds
- `compileall`: PASS

Sprint 4 additions cover typed Sprint 3 ingestion, evidence expansion, bounded K, invalid IDs, stale resolver version, NONE schema, forbidden model timestamps, contextual/ABSTAIN gates, local crop bounds and SC013 sensitivity. Runtime paths additionally validate candidate IDs/shots, source-bound artifacts, cache seals and independent crop decisions.

## Unresolved risks

1. Candidate recall is insufficient; increasing verifier strictness cannot recover an event absent from candidate K.
2. Lexical fragment matching is weak for paraphrases and temporal actions.
3. Reaction candidate construction is not sufficiently developed/calibrated.
4. Dense sheets lose motion information compared with true video understanding and can cause false negatives.
5. Crop refinement is shot-bound, not first/last-supporting-frame refinement.
6. Review-required behavior is underused: ambiguous literal candidates often collapse to ABSTAIN.
7. One episode and an 18-query holdout are too narrow for generalization.

## Exact recommendation

Do **not** proceed to editor/timeline work.

The next sprint should remain an exact-moment retrieval improvement sprint:

1. Build event-aware candidate lanes inside supplied scenes: typed action/object/reaction/dialogue lanes with guaranteed diversity, not one lexical pool.
2. Use overlapping temporal micro-windows (for example 2–4 seconds with overlap) inside evidence neighborhoods, retaining at least 20 diverse candidates before tournament verification.
3. Upload bounded microvideos through a robust file-upload path so motion—not only sequential stills—is verified.
4. Add local optical-flow/change cues for pickup/drop/entry/weapon/reaction timing, strictly within candidate regions.
5. Expand reaction development labels and explicitly model trigger-to-reaction adjacency.
6. Derive first/last supporting frames locally, add handles, then verify the actual crop.
7. Create a new, larger shot holdout before evaluating a changed resolver; this holdout is now development feedback and must not be reused as untouched evidence.

Answer to “Can the system reliably locate and verify the exact usable source moment inside correctly retrieved Film/TV scenes?”:

**FAIL.** It demonstrated that fail-closed exact verification can avoid wrong auto-accepts, but candidate recall and exact coverage are not yet adequate for an automated editor.
