# Sprint 9C — Human Candidate Oracle + Ordered Frames

## Verdict

**FAIL**

Explicit ordered frames did not reliably classify literal actions on the human-labelled DEV subset, and provider availability deteriorated during the complete run. The frozen holdout was not run or inspected.

## Human oracle

- 8 stratified DEV requests × 24 frozen candidates = **192 labels**.
- LITERAL: **7**; PARTIAL: **10**; NO_MATCH: **175**.
- All records passed strict schema, unique ID, complete coverage, source fingerprint and candidate fingerprint validation.
- Oracle SHA-256: `4d300b1817984ac9348f790e8761f397b0df724936da4c2223d9138ae2627435`.
- Receipt fingerprint: `6c67da89891eacc83ac60f2e5963dc8aee2ae39d6877c1b67f969587e8156e90`.
- Receipt: `runtime/sprint9c/HUMAN_ORACLE_RECEIPT.json`.

This corrects the earlier interval-overlap confounder: only candidate clips personally labelled LITERAL count as literal truth.

## Provider taxonomy and reliability

Historical sanitized taxonomy is in `SPRINT9C_PROVIDER_ERROR_REPORT.json`. Sprint 9B retained error classes but not full HTTP payloads, so most old `ClientError` records cannot honestly be subdivided into RPM/TPM/quota.

The new ordered-frame provider preserves retry classification without credentials. A concurrency-1 smoke test ran 24 candidates:

- successful: **24/24**
- failed: **0**
- retries: **0**
- latency: **557.42s**

Because reliability was initially complete, evaluation continued conservatively. Across the full 192-item run:

- successful responses: **87**
- provider failures after bounded retries: **105**
- total attempts: **517**
- cache hits: **24**
- input/output tokens recorded: **1,451,991 / 8,128**
- runtime: **2,279.63s**

The late failure concentration means this complete run is also a provider-reliability failure. Errors are scored fail-closed, never as LITERAL.

## Representation

`frame-sequence-candidate-verifier/1.0` supplies 15 chronological inline JPEGs (`F01–F15`) across each three-second candidate. It does not use File API video sampling. The model sees one candidate only, with required/not-sufficient facts, and cannot return timestamps or unsupplied IDs.

## Old video vs ordered frames

Both are scored against the same immutable 192-item human oracle.

| Metric | Old single video | Ordered frames |
|---|---:|---:|
| LITERAL recall | **14.29%** (1/7) | **14.29%** (1/7) |
| LITERAL precision | **20.00%** (1/5) | **12.50%** (1/8) |
| LITERAL F1 | **16.67%** | **13.33%** |
| False positives | 4 | 7 |
| False negatives | 6 | 6 |

Ordered frames did **not** materially outperform video. They retained the same literal recall and reduced precision.

### Old-video confusion matrix

| Human \ Predicted | LITERAL | PARTIAL | NO_MATCH | ERROR |
|---|---:|---:|---:|---:|
| LITERAL | 1 | 0 | 0 | 6 |
| PARTIAL | 2 | 0 | 1 | 7 |
| NO_MATCH | 2 | 0 | 53 | 120 |

### Ordered-frame confusion matrix

| Human \ Predicted | LITERAL | PARTIAL | NO_MATCH | ERROR |
|---|---:|---:|---:|---:|
| LITERAL | 1 | 0 | 0 | 6 |
| PARTIAL | 3 | 1 | 3 | 3 |
| NO_MATCH | 4 | 0 | 75 | 96 |

## Category findings

- CLOSEUP_INSERT: ordered frames recalled 1/1 literal, but precision was 33.33% due two false positives.
- OBJECT_ACTION: 0/5 literal recall; one false positive.
- REACTION: 0/1 literal recall.
- ENTER_LEAVE: no human literal candidates in this selected request, but four false positives.
- EXACT_VISIBLE_ACTION, DIALOGUE_LINKED_VISUAL and NONE: no literal positives; no literal false accepts in their evaluated successful outputs.

The human oracle itself reveals an important issue: several selected query pools contain no LITERAL candidate despite prior interval Recall@24 claims. Temporal interval overlap was materially overstating literal candidate availability.

## Tests and artifacts

- Full evaluation: `runtime/sprint9c/SPRINT9C_EVALUATION.json`.
- Reliability: `runtime/sprint9c/PROVIDER_RELIABILITY_C1.json`.
- Human oracle receipt: `runtime/sprint9c/HUMAN_ORACLE_RECEIPT.json`.
- Provider taxonomy: `SPRINT9C_PROVIDER_ERROR_REPORT.json`.
- All existing regression tests plus Sprint 9C validation remain green.

## Conclusion

Poor Sprint 9B results were caused partly by inadequate candidate truth and provider failures, but explicit ordered frames did not solve literal classification. The experiment is below both 90% diagnostic gates and must stop. Do not run the holdout or begin editor work.

**Was poor Sprint 9B performance primarily short-video sampling, and can explicit frames reliably classify literal actions? FAIL.**
