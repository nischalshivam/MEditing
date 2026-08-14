# Scene Brain V1.5 Architecture

Scene Brain produces a grounded first cut; it does not pretend weak evidence is complete automation. Canonical project state and human decisions remain on the portable SSD. Laptop caches are disposable, source media is read-only, and JSON outputs are receipts—not competing truth.

## Module contracts

1. **Project Planner** accepts script, optional clue/voiceover, and source scope. It emits estimates, character requirements, conflicts, readiness, and no retrieval side effects.
2. **Library + Memory** resolves portable source identities and supplies verified transcripts, Rich Atlas state, canonical events, and human editorial decisions.
3. **Clue / Script Intelligence** interprets the clean script independently, compares Clue V4 constraints, and lowers unsupported hard constraints.
4. **Source Discovery** returns locally cited source hypotheses. Hints never become episode or timestamp authority.
5. **Retrieval Engine** compiles independent text, character, object, action, source, and visual lanes.
6. **Evidence Plugins** add optional OpenCV character evidence and bounded Gemini evidence. Plugins cannot select timestamps or clips.
7. **Candidate Ranker** combines versioned, inspectable channel scores and emits `WHY THIS?` evidence.
8. **Confidence Gate** returns `AUTO`, `OPTIONS`, or `MANUAL_REQUIRED`; weak evidence creates a gap.
9. **Presentation Planner** uses distinct grounded shots/ranges, rejects fake sequential slicing, limits a scene to two uses, and caps video at ten seconds.
10. **Editor** is ResearchCut 2.1: replacement, import, trim, transforms, crop, non-ripple gaps, persistence, and export.
11. **Memory Updater** records accepted and rejected candidates separately with project/title/query/event provenance. Project approval is not silently promoted to exact-event truth.
12. **Job / Health / Support** stores stage, substage, work item, status, error code, and resumable state; support bundles contain sanitized receipts and never credentials.

## Optional intelligence

Character recognition uses OpenCV YuNet/SFace when models and trusted galleries exist. Missing galleries are neutral and non-blocking; `UNKNOWN` is valid. Gemini is disabled by default and only receives bounded candidates or deterministic dense frames after local retrieval. Every live result is content-addressed, budget-limited, and model/prompt/source bound.

## Version independence

Planner, clue compiler, character index, scene atlas, ranker, Gemini verifier, presentation planner, and editor versions are pinned independently. Old projects remain pinned until an explicit upgrade.
