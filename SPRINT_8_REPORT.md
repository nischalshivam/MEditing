# Sprint 8 — Hierarchical Intra-Scene Temporal Search

## Verdict

**PASS WITH ISSUES**

Hierarchical complete temporal coverage inside the frozen Sprint 3 Top-3 scenes solved the missing-action candidate problem on the development set. Recall@20 is **97.06% (33/34)** and Recall@5 is **82.35% (28/34)**. The required gates passed, but one previously successful two-second close-up (MH15A) fell outside Top-20, so this is not a claim of perfect retrieval.

No final Gemini tournament, new holdout, editor, timeline or renderer was started.

## Architecture implemented

- New isolated layer: `hierarchical-intra-scene/8.0`.
- Frozen Sprint 1–3 inputs and the preserved V3 path were consumed without rewriting their artifacts or metrics.
- Every Sprint 3 Top-3 scene is divided into persistent 12-second coarse windows with 3-second overlap.
- Windows are source-bound, shot-aware and collectively cover the complete scene without temporal gaps.
- All coarse windows are scored before narrowing. Existing fragments and verified dialogue are priors, not coverage gates.
- The best eight distinct coarse hypotheses per scene are retained; overlap suppression prevents adjacent duplicates from consuming the narrowing budget.
- Selected regions are expanded by 3.5 seconds and searched with 3-second dense windows at 1-second stride.
- Candidate caps apply only after complete coarse coverage and hierarchical narrowing.
- A generic locomotion/handling normalization (`move/carry/drag` and visually equivalent maneuver/fit/dispose/lift evidence) was added; no query ID, timestamp or benchmark-specific shot rule exists.

## Persistent data

Migration 6 added:

- `scene_micro_windows`
- `micro_events`
- `micro_index_runs`

Current cached index:

- Scenes indexed: **13**
- Coarse micro-windows: **320**
- Micro-events: **0**

Gemini micro-event indexing was deliberately not called: the local hierarchy passed the recall gates first. Therefore indexing calls/tokens/cost are **0 / 0 / $0**, and replay cost is $0. The schema remains ready for bounded, validated micro-events if future independent data proves them necessary.

## Development metrics (34 positives)

| Metric | Result |
|---|---:|
| Recall@1 | 52.94% (18/34) |
| Recall@3 | 79.41% (27/34) |
| Recall@5 | 82.35% (28/34) |
| Recall@10 | 88.24% (30/34) |
| Recall@20 | **97.06% (33/34)** |

Runtime was 11.43 seconds for the deterministic development evaluation after the index existed.

## Six original misses

| Request | Coarse rank | Dense rank | Top-20 recovered by |
|---|---:|---:|---|
| MH13A Skyler enters unlocked house | 14 | 9 | complete scene coverage + dense expansion |
| MH22A Gus approaches Victor | 4 | 4 | fragment prior + hierarchical temporal range |
| MH24A Walter/Jesse react | 1 | 1 | reaction/event evidence in bounded scene |
| MH32A Jesse eats at diner | 2 | 2 | action normalization + local scene evidence |
| MH33A Walter approaches Skyler | 28 | 17 | per-scene coarse quota + complete coverage |
| MH34A investigators process apartment | 13 | 13 | complete coverage + scene evidence |

All six are now present in Top-20. Five are in Top-10; four are in Top-5.

## Regression accounting

- Sprint 7/V3 Top-20 successes: 28
- Retained: 27
- Newly recovered: 6
- Old success lost: **MH15A** (very brief glass-eye insert)
- Final Top-20 miss: **MH15A only**

This is one non-catastrophic regression, explicitly preserved rather than hidden. The remaining bottleneck is extremely brief insert/action evidence whose duration is much smaller than a coarse cell and whose objective wording is weak.

## Tests and integrity

- Full Sprint 1–8 suite: **57/57 PASS**
- Added tests cover gap-free/overlapping coverage, source/shot bounds, deterministic cache replay, explicit versioned parameters and source-record immutability.
- Source media was not written or re-indexed.
- No model timestamps are accepted by this layer.
- Development evidence SHA-256: `c563ea56294d7c774327c809cccd5c3393a98e1540d5dda66516527fd93046a7`

## Cache replay

Rebuilding an already indexed scene returns byte-equivalent database rows with stable micro-window IDs and fingerprints. No external calls occur on replay.

## Honest conclusion

**Yes, with one known issue:** hierarchical complete temporal coverage inside already-correct scenes fixes the missing exact-action candidate problem on this development set. It passes both gates without Gemini indexing or query-specific patches. A later approved step should freeze this candidate-generation version, visually verify a bounded development sample, and then evaluate on genuinely new independent data. Editor work is still premature until final exact verification is measured on that independent set.
