# Sprint 3 Report — Precision-First Scene Search / Resolver

## Verdict

**PASS WITH ISSUES**

The system can retrieve a useful narrative-scene candidate region before exact shot/crop resolution. On the untouched 30-query visual holdout, the frozen resolver reached **96.30% Scene Recall@3**, **74.07% Recall@1**, and **93.75% VERIFIED precision**. However, two queries were wrongly auto-accepted. This is sufficient for a bounded, fail-closed Sprint 4 prototype, but not yet sufficient for unattended production placement.

Sprint 4 was **not** started.

## Evaluation integrity

- Sprint 1 source/index, Sprint 2 atlas, provider artifacts, benchmarks and fingerprints were sealed before resolver development.
- Resolver development used only `benchmark/development/S04E01_RESOLVER_DEV_V1.jsonl` (18 queries).
- `S04E01_VISUAL_HOLDOUT_V1` expected answers were not read while choosing ranking logic, weights, thresholds or verifier policy.
- Resolver version and verifier policy were frozen before holdout evaluation.
- The holdout was evaluated once and stored as immutable evaluation `S04E01_VISUAL_HOLDOUT_V1_EVAL`.
- No tuning or second holdout evaluation was performed after viewing results.

Key receipts:

- Input freeze fingerprint: `8fd4a234a01a434d237e2ec1a361494e5452ee4890e1734c65835cf75406134f`
- Frozen atlas fingerprint: `458203467c3afd0948bd64b65b8437385814c850a5f0efcb28c3707f545b3c37`
- Source video SHA-256: `29b0c732612d06d750bdd7b94cd3973bbf2b792e871d5eb53c5bfbd946f46e3a`
- Resolver fingerprint: `a034568b3dccbddedfee81c7f41e7edd673f172c6ce6c2eff0e1115681f41847`
- Holdout result SHA-256: `59ef648cef0731704e1c221be9ae92c9494fa1fc338b4fa9ffc09799d93e3365`

## Architecture built

The resolver is scene-first. It never chooses a final crop.

1. A typed `SceneRetrievalRequest` declares query text, evidence class, title/episode constraints, event/action/character/object/location/dialogue fields, negative constraints, continuity context, and NONE policy.
2. Sprint 2 proposals are converted into retrieval fragments while retaining canonical scene, originating proposal/window, evidence shots, trust and source fingerprint.
3. Cheap local channels independently retrieve dialogue, events, actions, objects, characters, locations, canonical summaries and semantic text.
4. Evidence-class-specific profiles rank top-K scenes. Dialogue never overwrites visual truth.
5. Weak boundaries may expose previous/next scene regions without changing the frozen atlas.
6. Local decisions are VERIFIED, CONTEXTUAL or ABSTAIN.
7. Only eligible ambiguous EXACT_EVENT requests are sent to Gemini with the top three local candidates and labelled local evidence. Gemini can return a supplied scene or `NONE_OF_THESE` only.

## Retrieval documents

The database contains **949 fragments and 949 local embeddings**:

| Fragment type | Count |
|---|---:|
| ACTION | 130 |
| CHARACTER | 144 |
| DIALOGUE_CONTEXT | 376 |
| EVENT | 62 |
| LOCATION | 62 |
| OBJECT | 100 |
| VISUAL_SUMMARY | 75 |

Every fragment retains canonical-scene and evidence-shot provenance. Unresolved canonical scenes remain searchable at reduced trust. AI-generated character names are `GENERATED_UNVERIFIED` and act only as soft evidence.

## Local search channels

- Verified subtitle exact/multi-cue search, followed by cue-to-scene mapping.
- SQLite FTS5/BM25 over typed scene fragments.
- Exact normalized structured entity/action/object/location evidence.
- Deterministic local text embedding at scene and fragment level.
- Atlas trust modifier, continuity signal and explicit negative penalties.

Embedding implementation: `local-hashed-word-char-512/1.0`. It is a deterministic SHA-256-bucketed word/character n-gram vector, adds no remote service or ML dependency, and is versioned/cacheable. It is intentionally lightweight rather than a whole-episode visual embedding system.

## Ranking profiles

Profiles are versioned as `evidence-ranking/1.0`:

- EXACT_DIALOGUE: dialogue dominates (0.70).
- EXACT_EVENT: event/action/object dominate; dialogue is supporting evidence only.
- EVENT_CONTEXT: event and semantic context share priority.
- EDITORIAL_CONTEXT: semantic/context evidence dominates.
- CHARACTER_CONTEXT: character evidence dominates, subject to trust.

Frozen decision thresholds:

- VERIFIED score: 0.56 with 0.10 separation.
- CONTEXTUAL score: 0.34.
- Exact visual floor: 0.42.
- Negative floor: 0.58.

Scores are ranking signals, not claimed probabilities.

## Abstention and neighbor expansion

- Exact requests without strong literal support ABSTAIN.
- Negative/NONE requests require affirmative evidence before selection.
- Low separation, contradictions, malformed verifier results and provider errors fail closed.
- Neighbor expansion is explanatory retrieval output only. It is triggered by weak/partial atlas support or boundary evidence and does not rewrite any Sprint 2 scene.

## Gemini verifier

- Provider: Google Gemini.
- Model: `gemini-3.1-flash-lite`.
- First-stage search remains entirely local and costs $0.
- Verifier sees only request + top-3 candidate scene packages, local metadata, contact sheets, dialogue and evidence shots.
- Allowed responses: `LITERAL_MATCH`, `CONTEXTUAL_MATCH`, or `NONE_OF_THESE`.
- Candidate IDs/evidence shots are validated; timestamps and extra fields are rejected.
- Every request is content-addressed and cached. Credential presence is boolean-only; the key is never logged or persisted.

Frozen verifier policy: invoke only for locally abstained EXACT_EVENT requests whose top candidate is at least 0.24. This is a cost/precision gate, not universal coverage.

## Development results

18 non-held-out development queries:

- Recall@1: **86.67%**
- Recall@3: **93.33%**
- VERIFIED precision: **100%**
- VERIFIED coverage: **60.00%**
- Abstention: **33.33%**
- NONE cases: **3/3 correctly abstained**
- Gemini verifier calls: **8**

An exact development replay completed in **2.24 seconds** with **8/8 verifier cache hits** and no new Gemini calls.

## One-time frozen holdout results

30 queries: 27 positive and 3 negative/NONE.

| Metric | Result |
|---|---:|
| Scene Recall@1 | **74.07%** |
| Scene Recall@3 | **96.30%** |
| MRR | **0.8395** |
| VERIFIED precision | **93.75%** |
| VERIFIED coverage (positive queries) | **59.26%** |
| Accepted precision (VERIFIED + CONTEXTUAL) | **90.00%** |
| Abstention rate | **33.33%** |
| Wrong auto-accept rate (all queries) | **6.67% (2/30)** |
| NONE correct abstentions | **3/3** |
| NONE false selections | **0** |
| Gemini calls | **24/30 (80%)** |
| Local-only requests | **6/30 (20%)** |

### Results by category

| Category | N | Recall@1 | Recall@3 | Abstention |
|---|---:|---:|---:|---:|
| Exact visible event | 12 | 83.33% | 100% | 16.67% |
| Object/action | 5 | 80% | 100% | 40% |
| Reaction | 4 | 50% | 75% | 50% |
| Scene context | 4 | 75% | 100% | 0% |
| Confusing/similar | 2 | 50% | 100% | 50% |
| Negative/NONE | 3 | N/A | N/A | 100% |

The most useful headline is not a single “accuracy” number: candidate generation is strong at top-3, while top-1 ranking and automatic acceptance still have meaningful failure risk.

## Gemini usage and cost

Heldout only:

- Calls: 24
- Input tokens: 115,565
- Output tokens: 3,132
- Total tokens: 118,697
- Estimated cost: **$0.0128093**

Entire Sprint 3 verifier database (development + holdout and recorded attempts):

- Calls: 33
- Input tokens: 165,729
- Output tokens: 4,628
- Total tokens: 170,357
- Estimated cost: **$0.0184241**

Usage is read from provider metadata where present and cost is an estimate using configured rates. Cache validation/replay is covered by automated tests; the development replay demonstrated real 8/8 cache reuse. The immutable holdout evaluation was not rerun merely to demonstrate caching.

## Representative successes

- Multiple exact visible-event requests resolved to SC005, SC006, SC007, SC008, SC009, SC010 and SC011 with literal visual/event support.
- One case whose local top-1 was wrong was corrected by the top-K Gemini verifier to SC009, demonstrating the value of retaining candidates instead of collapsing early.
- All three negative/NONE cases abstained; no least-bad scene was forced.
- Context queries successfully returned contextual scene regions rather than pretending to prove a literal event.

## Representative failures and taxonomy

1. **Wrong semantic auto-accept (V04):** SC013 was VERIFIED instead of expected SC003. The known imperfect atlas semantics around SC013 supplied plausible but wrong crime-scene evidence.
2. **Atlas boundary/bad-merge effect (V23):** SC009 was accepted contextually instead of SC013. The relevant moment crosses weak/coarse scene organization.
3. **Correct top-1 but conservative abstention:** several requests ranked the expected scene first but verifier/evidence gates did not establish literal support. This lowers coverage but is safer than wrong placement.
4. **Top-3 rescue needed:** reaction, object/action and similar-scene queries frequently had the correct scene below rank 1.
5. **One candidate-generation miss at top-3 (V24):** expected SC013 was absent from the top three.

Known Sprint 2 failures were preserved; no atlas card was manually beautified to improve these outcomes.

## Database changes

Migration 3 adds:

- `resolver_input_freezes`
- `scene_retrieval_fragments`
- `scene_retrieval_fts` and synchronization triggers
- `scene_fragment_embeddings`
- `resolver_versions`
- `resolver_runs`
- `resolver_evaluations`

Migration 4 adds `resolver_verifier_runs`.

All earlier Sprint 1 and Sprint 2 tables remain intact.

## CLI and inspection

The CLI supports:

- `resolver-freeze-inputs`
- `resolver-build-fragments`
- `resolver-freeze-version`
- `resolve-scene`

`resolve-scene` displays decision, ranked candidates, scene times, channel scores, matched fragments/dialogue, evidence shots, atlas status, neighbor expansion and provenance. It returns scenes/regions only—never a crop.

## Automated tests

Command:

```powershell
$env:PYTHONPATH='src'
python -m unittest discover -s tests -v
```

Result: **37/37 PASS** in 0.885 seconds.

Coverage includes Sprint 1 + Sprint 2 regressions plus fragment provenance, FTS ranking, dialogue mapping, embedding version/determinism, ranking profiles, unsupported character soft handling, negatives, unresolved scenes, neighbors, duplicate collapse, abstention, Gemini NONE, malformed response, stale fingerprints, timestamp rejection and cache behavior.

The source video remained read-only and is still bound to the frozen SHA-256 above. No source footage or frozen atlas semantics were modified.

## Unresolved risks

- VERIFIED precision of 93.75% is not high enough for blindly publishing every accepted scene.
- Gemini call rate of 80% is higher than desired; local retrieval primarily generates candidates but often cannot verify literal truth alone.
- Reaction shots and confusing similar scenes remain weakest.
- Known atlas bad merge/partial semantics can contaminate ranking and verification.
- Lightweight text embeddings improve reproducibility/cost, but do not provide genuine visual semantic representation.
- This benchmark covers one episode only; it does not prove series-wide generalization.

## Exact Sprint 4 recommendation

Proceed only with a **bounded Sprint 4 Shot Resolver prototype**, not a production editor.

Required safeguards:

1. Consume top-3 scene/neighbor regions and preserve the Sprint 3 evidence breakdown; do not trust only top-1.
2. Resolve exact moments only inside supplied scene/neighbor regions.
3. Verify the final exported crop independently and fail closed.
4. Do not auto-place crops originating from Sprint 3 CONTEXTUAL or ABSTAIN decisions.
5. Treat known SC013/boundary-sensitive results as review-required.
6. Build and freeze a separate shot-level development/holdout evaluation before claiming clip accuracy.
7. Keep character still/NEEDS VISUAL fallback separate from exact-motion correctness.

Therefore the answer to “Can this system reliably retrieve the correct narrative scene before we invest in exact shot/crop resolution?” is:

**PASS WITH ISSUES** — strong enough to justify a controlled exact-shot experiment because the correct scene appears in top-3 for 96.3% of positive holdout queries, but automatic top-1 acceptance is not yet safe enough for an unattended final-video workflow.
