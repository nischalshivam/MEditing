# Sprint 10 — Green / Yellow / Orange Visual Planner Backend

## Verdict

**PASS WITH ISSUES**

The existing S04E01 Scene Brain can produce a conservative, reviewable visual plan backed by real local media. It does not yet justify automatic placement of new exact visual events: this proof deliberately emitted zero Green beats because no qualifying human Editorial Memory or uniquely proved exact-dialogue approval exists in the current database.

## What was built

- New isolated `confidence-visual-planner/1.0` backend and typed `visual-plan/1.0` artifact.
- Exact narration/test-beat preservation and deterministic intent fields.
- Fail-closed Green policy limited to human exact approval or uniquely anchored local dialogue.
- Compact Yellow routing with a maximum of five options (three in this run).
- Multiscale footage candidates: bounded range, complete shot, adjacent-shot context.
- Overlap suppression so review options represent different temporal hypotheses.
- Honest Orange contextual fallback with no literal-action claim.
- Separate approval types for exact dialogue, exact event and contextual visual memory.
- Content-addressed 540p local preview clips, immutable source provenance and routing receipt.
- Diagnostic HTML with per-beat previews and local audit controls.

No Gemini calls, model tournament, holdout run, editor, timeline or renderer were used.

## Real S04E01 proof

The proof uses the eight human-reviewed Sprint 9C DEV requests and the frozen 192-candidate oracle. All media is derived from the indexed local S04E01 source.

| Metric | Result |
|---|---:|
| Beats | 8 |
| Green | 0 |
| Yellow | 7 |
| Orange | 1 |
| Orange unresolved | 0 |
| Wrong Green | 0 |
| Green precision | N/A (no qualifying Green evidence) |
| Green coverage / Auto Ready Rate | 0% |
| Yellow scene recall | 100%* |
| Yellow known-literal Top 3 | 66.67% (2/3 oracle-supported queries) |
| Yellow known-literal Top 5 | 66.67% (2/3) |
| Average Yellow options | 3.0 |
| Near-duplicate option rate | 0% |
| Reviewable Rate | 100% |
| Human Decision Load | 8/8 |
| Referenced preview clips | 24 |
| API calls / tokens / cost | 0 / 0 / $0 |

\* The current benchmark rows do not all carry complete canonical-scene labels; the metric confirms retained source-scene routing, not literal action accuracy. It must not be advertised as exact-clip accuracy.

## Safety findings

- No human `NO_MATCH` candidate was promoted to Green because no new action can become Green without permitted proof.
- The Orange result is the negative request “Mike lowers a visible gun after Victor is cut.” It uses local contextual footage, is marked review-required, and makes no claim that the requested action occurs.
- All options preserve title, season, episode, scene, physical shot IDs, source interval, source SHA-256 and retrieval provenance.
- Source SHA-256 remained unchanged after preview generation.
- Model confidence is absent from color routing.

## Representative outputs

- **Yellow:** “Skyler holds the glass eye” returns three distinct local candidate shapes/regions for review. It remains Yellow despite a human-LITERAL oracle candidate because the oracle is evaluation evidence, not stored product Editorial Memory approval.
- **Yellow:** “Jesse eats at the diner” returns compact local choices; a known literal option is present without being falsely auto-approved.
- **Orange:** the unsupported Mike gun-lowering request receives a transparent contextual option instead of fabricated exact footage.
- **Green:** none. This is the correct conservative outcome until explicit Editorial Memory approvals or fully validated unique dialogue anchors are stored.

## Runtime and cache

- First completed plan run: approximately 7 seconds. Exact fully cached replay: approximately 0.04 seconds and zero regenerated previews.
- Plan references 24 preview clips. The preview cache contains additional content-addressed files from an interrupted initial generation pass; they are unreferenced and harmless.
- Plan, metrics and source identity are bound in `COLOR_ROUTING_RECEIPT.json`.

## Tests

The full suite passes: **84/84** tests. Sprint 10 adds coverage for Green permitted provenance and downgrade, exact-dialogue Green, contextual/exact approval separation, Yellow option limits, overlap deduplication, multiscale source bounds, Orange unresolved behavior and visual-plan schema.

## Remaining blocker

Yellow usefulness is promising but not yet uniformly strong: only 2 of the 3 queries with known human-LITERAL candidates retain one in the displayed Top 3. The product can proceed to human audit of this diagnostic plan, but polished editor/timeline/export work should wait until those compact Yellow options are manually judged usable and the first explicit approvals seed Editorial Memory Green coverage.

## Final answer

The episode-wise Scene Brain can now create a trustworthy Green/Yellow/Orange backend plan with real local media and explicit uncertainty. **PASS WITH ISSUES**: safety and plan generation work; compact Yellow/Orange editorial usefulness still needs human audit before editor investment.
