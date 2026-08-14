# Sprint 9B — Independent Candidate Verification (DEV only)

## Verdict

**FAIL**

On DEV, independently judging each bounded temporal candidate did not recover literal matches with sufficient recall and precision to justify touching the frozen holdout. The holdout was not run, inspected, or re-annotated.

## Preserved Sprint 9 evidence

The original Sprint 9 dataset, prompts, model, outputs and report remain unchanged. Its formal results remain: tournament exact selection 27.78%, frozen single-interval VERIFIED_EXACT precision 66.67%, coverage 33.33%, and human visual inspection 6/6 literal-looking emitted crops.

## DEV_V2 annotations

`SPRINT9_EXACT_DEV_V2` is a separate immutable annotation version derived only from DEV. All 19 rows retain the original evidence. Human inspection added two alternate literal occurrences:

- S9D15A — Skyler visibly holds the glass eye.
- S9D32A — Jesse visibly raises food and eats at the diner.

These were added as narrow actual crop intervals with physical shot ranges and explicit `ALTERNATE` provenance. The original intervals were not broadened or overwritten. Requests with multiple valid occurrences: **2**. DEV_V2 SHA-256: `ea6810431593da63a2e1a588442df7d152e3a70ee10e11f66be8737371515929`.

## Independent verifier

- One candidate video per request; no other candidates, rank, answer, prior judgment or ground truth.
- Strict `LITERAL_MATCH / PARTIAL_MATCH / NO_MATCH` schema.
- Required-visible-fact and not-sufficient decomposition.
- Candidate and shot IDs validated; timestamps forbidden.
- All 24 candidates assessed with a bounded worker pool.
- Cache separated by model, prompt, schema, request, candidate, video hash and model configuration.

## Model experiment

| Model | Literal query recall | Literal classification precision | FN rate | FP rate | Successful calls | Calls attempted | Tokens | Cost | Latency |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| gemini-3.1-flash-lite | 33.33% | 64.71% | 82.26% | 35.29% | 195 | 456 | 104,632 | $0.01873 | 682.5s |
| gemini-2.5-flash | unavailable | unavailable | — | — | 0 | 456 | 0 | $0 | 504.0s |
| gemini-3.6-flash | 5.56% | 50.00% | 98.39% | 50.00% | 22 | 456 | 11,562 | $0.00201 | 542.5s |

`gemini-2.5-flash` is listed but the official API returns 404 for new users and recommends migration; it cannot form a valid capability comparison. `gemini-3.6-flash` accepted only 22 calls before provider `ClientError` failures dominated. Flash-Lite completed 195 and then provider errors dominated. Errors remained fail-closed and no secret was logged.

Even on successful Flash-Lite judgments, independent classification was far below the >=95% preferred literal-candidate recall and produced material false positives. Therefore no final-literal comparison, crop rerun, or holdout run was justified.

## Old group-stage oracle audit

Frozen Sprint 8 had an acceptable interval in all 18 positive DEV Top-24 pools. The old tournament produced no group finalist for eight positives and lost one more in final comparison. The independent experiment confirms that early competition was not the sole cause: isolated judgments also reject most interval-positive candidates. The remaining causal combination is:

1. three-second candidates often overlap a labelled interval without containing the complete visible action;
2. the benchmark's interval-overlap oracle marks several adjacent/partial windows positive;
3. model/provider reliability is insufficient under 456 Files API judgments;
4. the single-video verifier remains conservative on short temporal evidence.

This makes naive interval-overlap an inadequate per-candidate human oracle. A true 24×19 human literal/partial/no-match annotation would be required before claiming exact candidate-classifier precision. This report does not falsely call every overlapping window literal.

## Final selection and crop behavior

The independent recall gate failed, so final comparison was correctly not executed. Existing frame-ID crop refinement and independent crop verifier were not weakened or changed. Sprint 9's independent verifier previously rejected four questionable winners and remains a valuable safety barrier.

## Calls, cache and security

- Credential detected via Windows User environment: yes.
- Credential printed/logged/persisted: no.
- Attempted isolated judgments: 456 per model.
- Exact replay uses model-specific caches for successful responses; provider failures are not cached as successes.
- Source and frozen holdout remained untouched.

## Tests

Regression tests include candidate isolation, strict three-way output, visible-fact schema, timestamp rejection and model-config separation, in addition to all prior Sprint tests.

## Recommendation

Do **not** run the frozen holdout and do **not** start the editor. Before another model experiment, build a small genuinely human-labelled candidate-level oracle (literal/partial/no-match) for a stratified subset and verify provider rate-limit/error behavior. The current data can prove candidate interval availability, but it cannot reliably supervise exact per-window literal classification.

## Final answer

**Can independently verifying bounded temporal candidates recover literal matches with sufficient precision and recall to justify one untouched holdout run?**

**FAIL.**
