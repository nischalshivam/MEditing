# Sprint 6 — Retrieval Contract Integration + Candidate Ranking V3

## Verdict

**FAIL**

Development Recall@5 reached the requested minimum, but Recall@20 remained below the 95% prerequisite. Per instruction, no new final holdout was created or spent, and editor/timeline work was not started.

## Result

| Development metric | V3 |
|---|---:|
| Recall@1 | 29.41% |
| Recall@3 | 70.59% |
| Recall@5 | **76.47%** |
| Recall@20 | **82.35%** |
| MRR | 0.4555 |
| Top-5 near-duplicate pair rate | 1.76% |
| Wrong auto-accept | 0% |

Compared with pre-V3 ordering on the same 34 positives, Recall@5 improved from 32.35% to 76.47%. Recall@20 did not improve because several correct moments are absent from the 24 generated candidates, not merely ranked low.

## Built

- Explicit `region-discovery-contract/3.0`: Sprint 3 ABSTAIN/CONTEXTUAL regions may be inspected; they grant no export authority.
- Deterministic structured request representation: subject, target, action family, object, location, reaction fields, temporal relation, visual/forbidden state.
- Local synonym families for enter/leave, transfer, pickup/putdown, observe, search, eat, turn, react, cut, wear, open and pour.
- Deterministic component reranker: entity, action, object, relation, temporal, evidence, dialogue, bounded motion and local semantic similarity.
- Every candidate records component scores and structured request provenance.
- Diversity suppression prevents Top-5 from becoming overlapping duplicates.
- Existing 3s/1.5s overlapping cross-shot generator and 24-candidate design preserved.
- Evidence fragments now create per-evidence-shot hypotheses instead of one long min/max envelope.
- Candidate reel builder: up to 10 cached microvideos, burned-in opaque IDs, concatenated into one bounded reel.
- Existing Files API microvideo, frame refinement and final-crop fail-closed verification preserved.

## Development failure taxonomy

Six of 34 positive development requests remained absent from Top-20. These concentrate in:

- wrong/insufficient frozen scene regions;
- long scene fragments where event-specific evidence is missing or incorrect;
- reactions without structured trigger fields;
- boundary-sensitive ending material;
- specific enter/leave/action requests whose correct region is a lower-ranked scene and does not survive 24-slot generation.

This is candidate-generation/scene-region recall, not a Gemini prompt problem. More verifier calls cannot recover missing candidates.

## Gemini reel status

The reel builder is implemented with opaque burned-in IDs and bounded source clips. The underlying official Files API motion verification already passed the Sprint 5 smoke test. A new expensive tournament evaluation was intentionally not run because Recall@20 failed the required local gate.

## Final holdout

Not reached. The user explicitly required Recall@20 ≥95% and Recall@5 ≥75% before creating a new holdout. V3 achieved the latter only. Sprint 4/5 final holdouts were not reused as untouched proof.

Therefore final holdout Recall, VERIFIED_EXACT coverage and REVIEW_REQUIRED coverage are **not available**, rather than fabricated from development data.

## Safety

- Sprint 3 remains byte/logically frozen.
- ABSTAIN regions allow search only.
- VERIFIED_EXACT still requires bounded microvideo selection, valid opaque ID, supporting frames, locally derived interval, and independent actual-crop verification.
- Invalid IDs/timestamps/schema/provider failures remain fail closed.
- Wrong auto-accept remained zero during V3 development because no safety gate was weakened.

## Verification

- Full regression suite: **52/52 PASS**.
- `compileall`: PASS.
- V3 fingerprint: `78b01fce302cd5aa28e66ae2ce23320943f06685d652614b27ff568c30ff6701`.
- Development artifact: `runtime/retrieval_v3/development_v3.json`.
- Frozen development receipt: `runtime/retrieval_v3/frozen_v3_development_receipt.json`.

## Remaining bottleneck

The dominant bottleneck is **region/candidate generation recall**: correct events are sometimes outside the frozen top-3/neighbor region set or lack reliable event-level evidence inside those regions. Local reranking successfully promotes candidates that exist, but cannot rank a candidate that was never generated.

## Recommendation

Do not start editor work. The next improvement must target bounded region recovery and missing event evidence while keeping the exact verifier unchanged—for example, an explicit lower-ranked-scene recovery lane or local subtitle/action-proposal expansion with a strict logged recovery budget. Only create another holdout after development Recall@20 exceeds 95%.
