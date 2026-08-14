# Scene Brain Clue Script V4 Master Prompt

Create a `production-clue-script/4.0` JSON search plan for the supplied clean narration and selected Film/TV source scope.

## Ground rules

- Preserve the narration exactly and cover it once, in order. Do not improve, paraphrase, omit, or duplicate narration.
- A clue is a search plan, never timestamp or episode authority.
- Do not invent timestamps, physical shot IDs, episode certainty, visible actions, dialogue, or character identity.
- Use `UNKNOWN`, `AMBIGUOUS`, contextual intent, or manual review when local evidence will be required.
- Prefer title hints only within the supplied source scope. Exact events must never borrow from another title.

## Required top-level fields

`schema_version`, `project`, `source_scope`, `canonical_events`, `beats`, and `validation`.

Each beat must have a unique ordered `beat_id`, the exact `narration`, `evidence_class`, visual intent, subjects, objects/actions/locations when supported, optional canonical event references, source-title preference within scope, and explicit fallbacks. Supported evidence classes are `EXACT_DIALOGUE`, `EXACT_EVENT`, `EVENT_CONTEXT`, `EDITORIAL_CONTEXT`, and `CHARACTER_CONTEXT`.

Never include source timestamps as clue truth. Keep face requirements selective; missing character galleries must remain non-blocking. Return JSON only, followed by no commentary.

## Inputs appended by Scene Brain

Scene Brain will append the current source scope, selected titles, and clean script below this prompt. Treat those appended values as authoritative project inputs.
