# Sprint 5 Report — Exact Moment Resolver V2

## Verdict

**FAIL**

V2 materially improved deep candidate recall and fixed true bounded microvideo verification, but it did not clear the prerequisite for a useful exact-moment system. On the new 36-query frozen holdout, Candidate Recall@20 reached **85.29%**, while Recall@5 was only **32.35%**. More importantly, all 34 positive queries inherited Sprint 3 ABSTAIN because their new paraphrased requests were outside the frozen Sprint 3 acceptance envelope. Existing safety gates therefore correctly prevent automatic exact output.

Do not begin editor/timeline work.

## What was built

- `exact-moment-resolver/2.0`, separate from frozen Sprint 3 and Sprint 4.
- Overlapping 3-second temporal micro-windows with 1.5-second stride, including windows crossing physical shot boundaries.
- 24 retained candidates (target range 20–30).
- Diversified lanes: evidence, action, object/action, enter/leave, reaction, dialogue and uniform bounded coverage.
- Per-lane quotas before global score fill, preventing one lexical lane from occupying every candidate slot.
- Reaction trigger plus subject plus BEFORE/DURING/AFTER request contract support.
- Official Gemini Files API upload, ACTIVE-state polling, bounded microvideo analysis and best-effort remote-file deletion.
- Candidate verifier, uniform 5 FPS support-frame interval refiner, local first/last-frame conversion, editorial handles and independent actual-crop verifier.
- PARTIAL_MATCH and uncertain crops map to REVIEW_REQUIRED; wrong/invalid/provider failures remain ABSTAIN.
- Content-addressed microvideos, verifier outputs and final crops.

No editor, timeline, renderer, script compiler, filler, interpolation or TwelveLabs was built.

## Frozen configuration

- V2 fingerprint: `baed8b10a24d337f7a9f69115ac09d75573539b18490d7f0cac71c8607c1b5a6`
- Source SHA-256: `29b0c732612d06d750bdd7b94cd3973bbf2b792e871d5eb53c5bfbd946f46e3a`
- Model: `gemini-3.1-flash-lite`
- Candidate prompt: `microvideo-candidate/2.0`
- Frame refiner: `support-frame-refiner/2.0`
- Crop verifier: `final-microcrop/2.0`
- Candidate K: 24
- Window: 3,000 ms
- Stride: 1,500 ms
- Per-lane initial quota: 4

Sprint 3 and Sprint 4 frozen artifacts/results were not tuned or overwritten.

## Development evidence

On the 17-positive Sprint 4 development set, before new holdout freeze:

- Candidate Recall@1: 17.65%
- Candidate Recall@5: 41.18%
- Candidate Recall@20: **88.24%**

This established the important architectural improvement: a diverse 24-window pool recovers moments lost by V1’s small lexical pool. It also showed that ordering inside the pool remains weak.

A bounded Files API smoke test correctly selected the microvideo showing Gale cutting packaging with the utility knife. No whole episode was uploaded.

A five-query development pipeline probe produced:

- one VERIFIED_EXACT (`SR23`, Gus/Victor killing micro-event);
- four ABSTAIN;
- actual frame-index refinement and final crop verification executed successfully.

The probe demonstrated end-to-end mechanics, not acceptable coverage.

## New benchmark

The old Sprint 4 holdout was not reused as untouched final evidence.

New artifacts:

- `MOMENT_RESOLVER_V2_DEV`: 36 queries
- `S04E01_MOMENT_HOLDOUT_V2`: 36 separately worded queries
- Holdout SHA-256: `bd161cac6b81fc3fe678c6666a7b1c0f219f76c373f76fccf1ad6dfc7169175c`
- Receipt SHA-256: `76e8061fde1134a05fe7f55d24b18e4a362b6bad4c748b9673e7a54062899c70`

Composition: 34 positive and 2 NONE. Categories cover exact actions, object/action, enter/leave, reactions, dialogue-linked visuals and inserts. Labels reuse human-inspected local source intervals but the final queries are new paraphrases.

Limitation: development and holdout share underlying physical events, though wording is separate. This is larger and new relative to Sprint 4, but not episode-disjoint.

## Frozen holdout candidate gate

The immutable V2 candidate-gate artifact was run before expensive full verification:

| Metric | Result |
|---|---:|
| Positive queries | 34 |
| Candidate Recall@5 | **32.35%** |
| Candidate Recall@20 | **85.29%** |
| Positive requests with frozen Sprint 3 ABSTAIN | **34/34** |
| Runtime | 23.69 seconds |

Artifact SHA-256: `590b96aecdc6f108b51e0ad448c4d9b2a04ccf7ca78f7afa96f30bec415b62c7`

Because Sprint 3 ABSTAIN may not auto-produce exact output, final eligible automatic coverage is **0%** on this new holdout. Running hundreds of Gemini uploads could not legally change that result. The evaluation therefore stopped at the predeclared fail-fast candidate/safety gate rather than spending money to manufacture misleading downstream metrics.

## Requested metrics

| Metric | Frozen V2 result |
|---|---:|
| Candidate Recall@5 | 32.35% |
| Candidate Recall@20 | 85.29% |
| Verifier selection accuracy | Not validly measurable on final holdout; all positives upstream-ineligible |
| Crop verification accuracy | Not validly measurable on final holdout |
| VERIFIED_EXACT coverage | 0% after mandatory Sprint 3 safety gate |
| REVIEW_REQUIRED coverage | 0% in fail-fast final gate |
| Wrong auto-accept rate | 0% |

The missing downstream figures are reported as unavailable, not converted into fake zero-denominator precision.

## Why Recall@20 improved but Recall@5 did not

- Coverage and typed lanes preserve more of each supplied scene region.
- 1.5-second overlap captures brief actions and cut-crossing events.
- Local ranking still depends heavily on imperfect Sprint 2 fragments and lexical overlap.
- Similar micro-windows within long SC011 compete strongly.
- Uniform coverage creates recall but is not semantically ordered.
- Frozen Sprint 3 can return ABSTAIN for new query wording even when its candidate scenes contain the correct physical interval.

## Reaction handling

V2 can build post-trigger/before/during windows and carry reaction subject/direction. This is structurally correct, but the new benchmark does not provide structured trigger fields for most reaction queries, and frozen Sprint 3 rejects the paraphrases. Reaction accuracy is therefore not proven.

## Microvideo verification

Unlike Sprint 4’s sequential-sheet transport, V2 uses the Gemini Files API:

1. upload each bounded local H.264 microvideo;
2. wait for ACTIVE state;
3. analyze only supplied candidates;
4. delete remote temporary files best-effort;
5. validate candidate and physical-shot IDs;
6. cache by source/candidate/request/model/prompt/content hashes.

The working smoke test used 1,201 input and 100 output tokens, estimated at `$0.0001601`.

Throughput remains poor: four separate candidate uploads took roughly 38–41 seconds for the smoke call. A five-query development probe took about 398 seconds. This is an engineering bottleneck, though not the accuracy blocker.

## Interval refinement

The selected microvideo is indexed conceptually at 5 FPS. Gemini returns only first/last frame indices, never timestamps. Local code validates indices, converts them to source time, adds 450/650 ms handles bounded by the candidate, exports the crop, then independently reuploads/verifies that actual crop.

This is safer than model timestamps but still depends on approximate uniform frame indexing; exact decoded-frame receipts should replace conceptual indexing in a future version.

## Safety outcome

- Sprint 3 CONTEXTUAL cannot become exact.
- Sprint 3 ABSTAIN cannot become exact.
- PARTIAL_MATCH becomes REVIEW_REQUIRED.
- Invented candidate/shot/frame indices fail closed.
- SC013 remains review-required.
- Provider errors and malformed responses ABSTAIN.
- Wrong auto-accept stayed at zero in the frozen gate.

## Tests

Full regression suite: **49/49 PASS** after the final fixture correction.

New coverage includes:

- micro-window duration and overlap/cross-shot construction;
- 24-candidate cap;
- diversified lanes;
- stale Sprint 3 rejection;
- strict schemas and forbidden model timestamps;
- frame-index validation;
- contextual/ABSTAIN safety;
- boundary-sensitive handling;
- deterministic local candidate generation.

`compileall` passed.

## Remaining bottleneck

The primary bottleneck is now precisely identified:

**The exact moment is often somewhere in the top 20, but the frozen scene-level resolver rejects new exact request wording and local ordering cannot reliably put the right micro-window in the first verifier batch.**

Prompt tuning alone will not solve this.

## Recommendation

Do not build the editor.

The next work should be a retrieval-contract integration sprint, not another expensive verifier sprint:

1. Keep Sprint 3 independently frozen, but permit Sprint 5 to consume its top-3 candidate regions even when decision is ABSTAIN for evaluation, while still forbidding auto-export until independent exact proof. This requires explicit user approval because it changes the current safety interpretation, not Sprint 3 itself.
2. Add local action/entity synonym normalization and a learned/reranked micro-window text representation inside supplied regions.
3. Use one stitched candidate-reel upload with burned-in opaque IDs instead of 24 individual Files uploads, followed by individual verification of the chosen microvideo.
4. Require candidate Recall@20 above 95% and Recall@5 above 75% on development before creating another final holdout.
5. Build an episode-disjoint or at least event-disjoint larger holdout for the next unbiased evaluation.

Final answer to “Is exact-moment retrieval ready for editor work?”:

**FAIL.** V2 fixed motion transport and substantially improved deep recall, while preserving zero wrong auto-accepts, but useful verified/review coverage is not established and the Sprint 3 eligibility boundary blocks all new final requests.
