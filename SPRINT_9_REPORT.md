# Sprint 9 — Exact Temporal Tournament + Final Crop Verification

## Verdict

**FAIL (live DEV completed; holdout correctly not run)**

The Windows User credential was imported into the child-process environment without printing or persisting it. Live DEV completed. DEV performance is not strong enough to freeze and proceed to the untouched holdout, so the holdout was not run.

## Live DEV result

- Credential detected: yes; credential printed/logged/stored: no
- Requests: 19 (18 positive, 1 NONE)
- Candidate Recall@5/@10/@20/@24: 88.89% / 94.44% / 94.44% / 100%
- Tournament acceptable-interval selection: **27.78% (5/18)**
- VERIFIED_EXACT emitted: 6
- Interval-grounded VERIFIED_EXACT precision: **66.67% (4/6)**
- VERIFIED_EXACT coverage: **33.33% (6/18)**
- Wrong auto-accept by frozen interval labels: **33.33% (2/6)**
- REVIEW_REQUIRED: 0%
- ABSTAIN: 68.42%
- NONE: 1/1 correctly abstained
- Correct candidate / wrong crop: 0
- Cached call envelopes consumed: 104; input/output/total tokens: 137,911 / 30,153 / 168,064; estimated cost: $0.0258523

The first serial execution was terminated after exceeding 20 minutes without completing one request. It had nevertheless populated validated response caches. A bounded infrastructure-only repair pinned a Windows font for reel labels and executed the four fixed independent groups concurrently; it did not change candidates, prompts, thresholds, datasets, or decision semantics. The completed replay took 10.53 seconds with 104 cache hits.

## Human inspection of every DEV auto-accept

All six actual emitted crops were contact-sheet inspected:

- S9D15A: visually shows Skyler holding the glass eye; literal match, but outside the inherited frozen acceptable interval.
- S9D17A: Gus visibly enters/walks into the superlab in a dark suit; good.
- S9D19A: Gus is visibly changing into protective clothing; good.
- S9D24A: Walter and Jesse reaction close-ups are visible; good.
- S9D30A: character visibly mops the red spill; good.
- S9D32A: Jesse visibly raises food and eats; literal match, but outside the inherited frozen acceptable interval.

Thus visual inspection found 6/6 literal-looking crops, while immutable interval scoring counts 4/6. This conflict is important: the inherited benchmark has multiple genuinely equivalent moments but stores a single acceptable interval. It cannot be silently corrected during this evaluation. Formal precision therefore remains 66.67%, not 100%.

Failure taxonomy:

- Eight positives produced no group finalist (false-negative/coverage behavior).
- One final comparison returned NONE despite an available correct candidate.
- Four tournament winners were rejected by the independent crop verifier, preventing false accepts.
- No correct-candidate/wrong-crop case was observed.
- Two visually valid alternate occurrences were penalized by single-interval ground truth.

## Frozen inputs and datasets

- Frozen Sprint 8: `hierarchical-intra-scene/8.0`
- Freeze fingerprint: `b8598085221d7aab9147e77425a3515a33576ce4e4998350e57fe1a4487c1dd9`
- Sprint 8 code SHA-256: `db3e61366a1d23ee3f935019af8451ac40a19b05a566bb2ee01eedea81a83173`
- Sprint 8 evidence SHA-256: `c563ea56294d7c774327c809cccd5c3393a98e1540d5dda66516527fd93046a7`
- Dataset freeze fingerprint: `f0407d4559dc85e5113b0ae30ed1cf96bf367c391cddf2110b57a1126dbf8506`
- DEV: 19 requests (18 positive, 1 NONE)
- HOLDOUT: 17 requests (16 positive, 1 NONE)

The split was frozen before tournament evaluation. It is category-stratified and based on previously human-reviewed S04E01 intervals. Limitation: it is not episode-disjoint because Sprint 9 is explicitly restricted to one episode.

## Candidate availability

| Dataset | Recall@5 | Recall@10 | Recall@20 | Recall@24 |
|---|---:|---:|---:|---:|
| DEV | 88.89% | 94.44% | 94.44% | **100%** |
| frozen HOLDOUT, one candidate-only evaluation | 75.00% | 81.25% | **100%** | **100%** |

All acceptable holdout moments were present in the frozen 24-candidate set. The DEV brief insert S9D15A was preserved at rank 24 exactly as required; Sprint 8 was not retuned.

## Implemented tournament architecture

- All 24 candidates are preserved.
- Four group reels of six candidates each.
- Every reel burns opaque candidate IDs into the actual temporal video.
- Every group must classify every supplied candidate as `LITERAL_MATCH`, `PARTIAL_MATCH`, or `NO_MATCH`.
- `NONE_FROM_GROUP` is first-class.
- Only literal candidates can become finalists.
- Final comparison returns one supplied candidate or `NONE_OF_THESE`.
- Candidate/shot invention, missing candidates, inconsistent classifications and timestamps fail closed.
- Model: configured low-cost `gemini-3.1-flash-lite`.

## Temporal evidence and brief inserts

- Candidate reels contain bounded microvideos, not scene summaries.
- Frame refinement uses authoritative IDs (`F0001`, `F0002`, …), never model timestamps.
- Default dense rate is 8 FPS.
- Sub-3-second candidates use the same high-density policy, ensuring beginning/middle/end plus additional temporal frames.
- Frame manifests bind source SHA, candidate bounds, FPS and every extracted-frame hash.

## Crop refinement

- Gemini may return only first/last frame IDs.
- Local code maps frame IDs to source milliseconds.
- Category-aware deterministic handles:
  - default: 400 ms before / 600 ms after
  - reaction: 650 / 900 ms
  - brief insert: 180 / 250 ms
- Crops are clamped to the winning candidate and local source bounds.
- Final verification is an independent prompt receiving only the request facts and actual crop. Tournament reasoning, scores and ground truth are excluded.
- `PARTIAL_MATCH` can never auto-accept; rejected crops cannot silently become contextual footage.

## Final-stage metrics

Holdout final-stage metrics remain unmeasured because DEV did not reach an acceptable frozen design:

- tournament top-1 exact accuracy: **NOT MEASURED**
- VERIFIED_EXACT holdout precision/coverage: **NOT MEASURED**
- DEV formal wrong auto-accept: **33.33%** (two visually literal alternate occurrences not represented by frozen labels)
- REVIEW_REQUIRED rate: **NOT MEASURED**
- ABSTAIN: provider-dependent runs stop fail-closed
- NONE precision/recall: **NOT MEASURED**
- crop containment and human visual inspection: **NOT MEASURED**

## Gemini usage

- Credential detected: **yes**
- Credential printed/logged/saved: **NO**
- Validated cached call envelopes across DEV stages: 104
- Input/output/total tokens: 137,911 / 30,153 / 168,064
- Estimated cost: $0.0258523

## Cache and safety

Candidate packages, reels, calls, frame manifests and crops use content-addressed fingerprints. Gemini response caches are schema-validated and sealed; tampering fails closed. Exact replay is designed for zero calls after successful cached execution.

The real source SHA-256 was rechecked read-only and remains:
`29b0c732612d06d750bdd7b94cd3973bbf2b792e871d5eb53c5bfbd946f46e3a`.

## Tests

- Full Sprint 1–9 suite: **65/65 PASS**
- `compileall`: PASS
- Sprint 9 coverage includes all-24 preservation, grouping, NONE, PARTIAL exclusion, strict output schema, no model timestamps, frame-ID contract, brief sampling policy, crop bounds/handles and independent-verifier contract.

## Exact failure / next recommendation

The candidate generator is not the current blocker: frozen holdout Recall@24 is 100%. The only blocker is inability to execute the configured Gemini provider from this fresh process. Once the environment variable is visible to the process, run DEV live first, freeze the unchanged tournament fingerprint, then perform the already-frozen holdout exactly once and visually inspect every auto-accepted crop.

## Final answer

**Can the system select and independently verify the exact usable moment with high precision?**

**FAIL.** Candidate availability is sufficient, and the independent verifier prevented four questionable winners from shipping, but tournament selection/coverage is too weak on DEV and formal frozen-label precision is below the 95% gate. The untouched holdout was therefore not executed. Editor work must not begin.
