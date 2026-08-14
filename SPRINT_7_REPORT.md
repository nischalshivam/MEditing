# Sprint 7 — Bounded Scene Recovery + Candidate Recall

## Verdict

**FAIL**

The required development gates were not reached. The working V3 path remains preserved at Recall@5 **76.47%** and Recall@20 **82.35%**, with zero wrong auto-accepts. Gemini and a new holdout were correctly skipped.

## Six-miss diagnosis

All six original Top-20 misses were machine-audited. In every case the correct canonical scene was already inside Sprint 3 Top-3; the failure was **event evidence/candidate generation inside the correct coarse scene**, not lower-ranked-scene exclusion:

- MH13A — Skyler enters unlocked house
- MH22A — Gus approaches Victor
- MH24A — Walter/Jesse reaction
- MH32A — Jesse eats at diner
- MH33A — Walter arrives/approaches Skyler
- MH34A — investigators process apartment

Machine-readable table: `runtime/retrieval_v3/sprint7_failure_taxonomy.json`.

## Recovery experiment

Implemented bounded, opt-in recovery lanes:

- lower-ranked Sprint 3 scenes up to rank 8;
- normalized subtitle cue neighborhoods;
- per-evidence-shot fragment hypotheses;
- six-second scene heads/tails;
- post-trigger reaction neighborhoods;
- logged scene rank and admission reason.

The experiment recovered three original misses via fragment recovery (MH13A, MH24A, MH32A), but introduced other candidate-cap/ranking regressions. Net Recall@20 fell to 79.41%, so it was **not adopted as the production default**. Lower-ranked scenes, subtitles and boundary lanes recovered zero of the six original misses. This confirms that blindly adding recovery hypotheses consumes the compact 24-candidate budget without solving missing event evidence.

## Final development metrics

| Metric | Preserved V3 |
|---|---:|
| Recall@3 | 70.59% |
| Recall@5 | **76.47%** |
| Recall@20 | **82.35%** |
| Missing positives | **6/34** |
| Wrong auto-accept | **0%** |

Target gates were Recall@5 ≥75% and Recall@20 ≥95%. Only the first passed.

## Gemini / final holdout

Not run. The local recall prerequisite failed, so Gemini tournament calls could not recover absent candidates and would waste usage. No new final holdout was created.

## Verification

- Full regression suite: **52/52 PASS**.
- `compileall`: PASS.
- Existing caches, frozen results, source media and fail-closed exact verification remain intact.

## Main blocker

The correct scene is usually already known, but long/coarse scenes lack reliable fine-grained action evidence and the fixed 24-slot pool cannot include enough uniform temporal coverage plus semantic hypotheses. The next viable approach is a two-level bounded search inside the correct scene: cheap coarse temporal scoring over the complete scene followed by dense windows only in several selected subregions, rather than adding more flat lanes to the same 24-slot pool.

Editor work must not start.
