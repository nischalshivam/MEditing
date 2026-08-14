# ResearchCut Automation Variation Blueprint

## Version 2 implementation status

The modular recipe approach below is now implemented in ResearchCut 2.1 as 60
deterministic presets: ten visual packs with six energy/density variants each.
The working Automate page includes real 12-second FFmpeg samples, per-visual layout/
motion/transition replacement, built-in and project background sources, optional
one-file VText, 1080p/4K export and a persistent multi-project overnight queue.

## Decision

The automation stage should consume ResearchCut's structured timeline, not a single
flat exported video. The timeline already knows every clip boundary, layer, source
trim, crop, mute choice and voiceover gap. A flat video would force us to detect
those facts again and would make reliable per-shot edits much harder.

The right implementation is a recipe engine: a small set of independent layout,
background, motion, transition and color modules combined into 50+ curated presets.
This produces more variety and is easier to improve than maintaining 50 unrelated
render pipelines.

## What the supplied samples are doing

The seven competitor sample recordings repeatedly use these visual families:

1. Full-bleed footage with subtle push-in, pan or drift.
2. Rounded rectangular footage over a themed animated background, with border and
   soft shadow.
3. Sharp-edged framed footage with a grid, paper, tech or abstract background.
4. Off-center picture-in-picture compositions with deliberate negative space.
5. Polaroid/card compositions using paper texture, rotation and layered shadows.
6. TV/HUD or screen-within-screen compositions with graphic framing elements.
7. Short montage/callout moments that use a stronger punch zoom or flash transition.

The perceived variety comes mainly from changing the frame world around the same
source clip: corner radius, border, shadow, position, scale, background family and
camera movement. It is not necessary to invent a unique renderer for every style.

## Existing engine audit

The older project already contains a useful base:

- 8 motion behaviors.
- 7 transition choices.
- 8 style packs.
- Deterministic seeded selection.
- Exact-duration planning.
- 12 framed-shot variants.
- Static-image and looping-video background support.

The next version should keep those proven pieces but fix four limits:

- Add a real overlap-based cross-dissolve when adjacent sources have enough handles.
- Show a short styled preview before a long render.
- Allow per-shot and per-boundary replacement after automation.
- Support off-center, split, card, perspective and PIP layouts instead of keeping
  every framed shot centered.

## Modular variation system

### Layout modules

| ID | Result | Best use |
|---|---|---|
| `full_bleed` | Media covers the 16:9 canvas | Strong native footage |
| `soft_frame` | Rounded frame, border, shadow | General documentary shots |
| `sharp_frame` | Rectangular editorial frame | Serious/research topics |
| `card` | Paper/polaroid frame with small rotation | Archive and history imagery |
| `pip_left` | Smaller visual left, open space right | Later text/callout support |
| `pip_right` | Smaller visual right, open space left | Later text/callout support |
| `split_60_40` | Primary visual plus secondary visual | Two related timeline layers |
| `perspective_screen` | Mild perspective/skew and deep shadow | Tech/screen footage |
| `tv_hud` | Graphic monitor/HUD housing | Technology and surveillance |
| `stacked_cards` | Two or three layered media cards | Short montage moments |

### Background modules

- Blurred self: a blurred/enlarged copy of the current clip.
- Static asset: tagged images from the supplied `backgrounds` library.
- Looping asset: tagged video loops from that library.
- Generated gradient: two or three colors derived from the clip palette.
- Paper/editorial: cream paper, grain, grid and archival treatments.
- Tech: cyan grid, HUD, hex, data and particle treatments.
- Atmospheric: moon, smoke, particles and abstract slow motion.

Every background asset should have a small manifest with `id`, `type`, `tags`,
`dominantColors`, `brightness`, `loopSafe` and `energy`. Selection then becomes
intentional instead of random file picking.

### Motion modules

- Slow zoom in / slow zoom out.
- Pan left / pan right.
- Vertical drift.
- Diagonal drift.
- Parallax between foreground frame and background.
- Short punch-in for an emphasized moment.
- Gentle card float/rotation.
- Locked/no motion when the source already contains strong movement.

Motion amplitude must be content-safe: images can move more than videos, and a
subject-near-edge check should reduce pan distance to avoid cutting off faces or
important objects.

### Transition modules

- Hard cut.
- Cross-dissolve.
- Dip to black or theme color.
- Directional slide.
- Blur dissolve.
- Luma/shape wipe.
- Flash cut.
- Push/zoom handoff.

Research videos should not transition on every cut. The recommended default density
is 30–45%, with hard cuts between the rest. Strong transitions should be separated
by at least two ordinary cuts.

For video-to-video cross-dissolve, the renderer needs source handles before/after
the visible cut. If a source has no handle, it should automatically fall back to a
short blur dissolve, freeze-frame dissolve or hard cut rather than changing the
approved timeline duration.

## 50+ presets without 50 code paths

A curated preset is a constrained combination, for example:

```json
{
  "id": "tech_cyan_focus_03",
  "layouts": ["full_bleed", "perspective_screen", "pip_right"],
  "backgroundTags": ["tech", "grid", "cyan"],
  "motions": ["slow_push", "parallax", "locked"],
  "transitions": ["hard", "blur_dissolve", "push"],
  "transitionDensity": 0.35,
  "cornerRadius": [0, 18],
  "border": { "width": 2, "color": "#54e2d2" },
  "shadow": "deep_soft",
  "seed": 40318
}
```

Ten layout families × six visual packs already give 60 controlled presets while
sharing the same renderer. Each preset should have fixed constraints and a seed so
the same project can be reproduced exactly.

Recommended first packs:

1. Clean Documentary
2. Dark Research
3. Editorial Paper
4. Archive Polaroid
5. Cyan Technology
6. Green Data Grid
7. Cinematic Atmosphere
8. Minimal Monochrome
9. Bold Explainer
10. Soft Modern

## Automation plan format

The automation step should create and save a non-destructive plan before rendering:

```json
{
  "version": 1,
  "projectId": "p_example",
  "presetId": "clean_documentary_04",
  "seed": 812930,
  "shots": [
    {
      "clipId": "c_example",
      "layoutId": "soft_frame",
      "backgroundId": "bg_paper_grid_02",
      "motionId": "slow_push",
      "transitionOut": { "id": "blur_dissolve", "duration": 0.38 },
      "overrides": {}
    }
  ]
}
```

This plan is the key to autosave, reproducible renders and individual replacement.
The renderer should never make new random decisions after the plan is approved.

## Recommended Next tab

1. Select style pack: show 4–6 strong cards, not 50 tiny options.
2. Select intensity: Subtle, Balanced or Energetic.
3. Generate plan: deterministic and instant.
4. Preview a 10–20 second representative section using low-resolution proxies.
5. Review timeline markers: click a shot or boundary to replace only its layout,
   background, motion or transition.
6. Choose 1080p or 4K and render.

The review screen should offer `Replace`, `Disable`, `Apply to similar shots` and
`Regenerate from this point`. Text automation can later attach to the same shot plan
without changing the clip-alignment editor.

## Quality rules

- Never repeat the same motion on more than two adjacent shots.
- Never use a strong transition on consecutive boundaries.
- Keep framed-layout runs short; return to full bleed regularly.
- Preserve exact project duration and all user-approved audio gaps.
- Respect V1 mute, overlay audio, A1 voiceover and A2 music/SFX independently.
- Duck A2 under A1 by a configurable amount; never alter source files.
- Use proxy previews, but render from original media.
- Persist every automation choice before rendering so a crash can resume safely.

## Implementation order

1. Versioned automation-plan schema and migration.
2. Background manifest/tagger for the supplied asset library.
3. Layout and motion renderer modules.
4. True transitions with handle-aware fallback.
5. Proxy preview and cached preview segments.
6. Per-shot/per-boundary review controls.
7. 10 initial packs, expanded into 50+ curated presets.
8. 1080p/4K render queue with resume and clear progress reporting.
