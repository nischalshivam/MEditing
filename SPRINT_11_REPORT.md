# Sprint 11 — Production Visual Composer

## Verdict

**PASS WITH ISSUES**

The Scene Brain now produces a real mixed-media, dynamic-duration, source-bound Green/Yellow/Orange review plan. The functional review workflow works, but the tiny human-known literal set still shows only 2/3 useful answers in the displayed Top 3/5, below the preferred target. No Green was emitted without qualifying authority.

## Real input

No legitimate connected 2–3 minute essay fixture exists in the repository. The product pipeline was therefore demonstrated as instructed on eight existing, human-reviewed S04E01 DEV requests arranged chronologically as one connected 86.5-second project. No narration or ground truth was fabricated, and no frozen holdout was opened or run.

## Product result

| Measure | Result |
|---|---:|
| Narration beats | 8 |
| Visual slots | 16 |
| Green | 0 |
| Yellow | 14 |
| Orange | 2 |
| Unresolved | 0 |
| Known wrong Green | 0 |
| Green precision | N/A — no qualifying approval evidence |
| Green coverage | 0% |
| Yellow known-literal Top 3 | 2/3 (66.67%) |
| Yellow known-literal Top 5 | 2/3 (66.67%) |
| Images | 9 (56.25%) |
| Videos | 7 (43.75%) |
| Video slot duration min / median / max | 5.0s / 5.0s / 6.0s |
| Image slot duration min / median / max | 5.0s / 5.25s / 6.75s |
| Repeated chosen-visual rate | 6.25% |
| Human decision load | 16 slots |
| API calls / tokens / cost | 0 / 0 / $0 |
| Warm run | approximately 3.2 seconds |
| Tests | 91/91 passed |

The initial derivative generation pass was bounded by the execution window and resumed safely from content-addressed cache. The first completed run took approximately 72 seconds; subsequent exact replays take roughly 3.2 seconds with zero regenerated video/still assets.

## What was built

- `production-visual-composer/11.0` and typed `visual-plan/2.0`.
- `MEDIA_RANGE_COMPOSER_V1`: complete shot, trimmed shot, adjacent-shot and wider context shapes. Final video ranges vary and are not fixed to three seconds.
- `STILL_IMAGE_SELECTOR_V1`: five frames sampled per source shot, with black/fade, brightness, blur/sharpness and entropy checks; best local frame retains source/episode/scene/shot/time/hash.
- Beat-to-multiple-VisualSlot planning with documentary pacing and dynamic slot duration.
- Independent color and media dimensions: Yellow/Orange can each carry VIDEO or IMAGE.
- Mixed-media project guidance without a hard quota.
- Active scene IDs and recent-asset repetition penalties.
- Production Editorial Memory schema with distinct `EXACT_EVENT_APPROVAL`, `EXACT_DIALOGUE_APPROVAL`, and `CONTEXTUAL_VISUAL_APPROVAL`.
- Review/audit persistence, selected/rejected asset records, and Green false-positive invalidation/audit support.
- Cached 540p video proxies and optimized local JPEG stills. Original source remains unchanged.
- Functional localhost review page with 16:9 preview, 1–5 choice keys, K/N, arrows, local autosave and automatic advancement.

## Safety and examples

- **Green:** none. Current database contains no qualifying production-grade human approval or unique deterministic exact-dialogue proof. New exact actions remain Yellow.
- **Yellow VIDEO:** “Gale cuts open packaging with a utility knife” displays three distinct shot-aware video hypotheses plus a locally selected still; no option is declared exact.
- **Orange VIDEO alternative:** the unsupported “Mike lowers a visible gun after Victor is cut” is Orange and exposes contextual video choices without claiming the action occurred.
- **Orange IMAGE:** the same unsupported request defaults to a sharp source-bound contextual still with scene, shot and frame-time provenance.
- **Mixed-media:** 9 IMAGE and 7 VIDEO chosen slots demonstrate that images are first-class.

## Review app verification

The page was opened through localhost in a real browser. JavaScript initialized, the first narration/slot rendered, the main MP4 reached ready state 4, all currently rendered images were valid, four choices appeared, and keyboard/localStorage navigation code was verified. Review decisions are human-owned; none were fabricated during this run.

Start it by double-clicking:

`runtime/sprint11/START_SPRINT11_REVIEW.bat`

## Remaining blockers

1. Yellow known-literal display recall is 2/3 on the very small oracle-supported subset, not the preferred 90–95%. This requires human review of the displayed production ranges before any ranking change.
2. There is no real connected 2–3 minute narration plus voiceover fixture yet, so voiceover alignment was implemented in the schema/timeline contract but not demonstrated with real audio.
3. The browser currently persists decisions locally. Backend Editorial Memory persistence is implemented and tested, but a lightweight localhost POST endpoint is still needed before browser selections can write SQLite directly.
4. Media mix is 56.25% images / 43.75% video for this short exact-action-heavy fixture—outside guidance but intentionally not forced.

## Final answer

The core production direction is viable: dynamic video ranges, first-class stills, compact Yellow/Orange options, fast review and compounding memory all work without unsafe Green claims. **PASS WITH ISSUES**. Do not process the full series or build polished 4K export yet; first complete the 16-slot human review and provide a real connected narration/voiceover fixture.
