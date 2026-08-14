# ResearchCut Editor 2.1 employee update

Release date: 2026-08-07

This file explains every user-visible change from 2.0 to 2.1. Existing projects, imported media, VText files, automation plans and completed renders remain in LocalAppData and are not deleted by the update.

## Editor fixes

- Project Media is now a fixed independent scroll area. Importing 100–200+ assets no longer pushes the timeline below the screen.
- The Inspector is independently scrollable.
- The preview and player transport have additional spacing, so controls no longer touch the visible 16:9 canvas.
- The entire editor is locked to the browser viewport instead of growing with media content.
- The timeline now has a real vertical scrollbar.
- Track names and timeline rows stay vertically synchronized while scrolling.
- Visual and audio layers hidden below the fold are accessible without changing browser zoom.
- The timeline toolbar now includes Add Visual Layer and Add Audio Layer.
- Added layers are autosaved and reopen with the project.
- The renderer and live preview support V4/V5/etc. and A3/A4/etc., up to 20 stored tracks per project.

## Premium automation framing

ResearchCut still contains 60 deterministic style recipes, but those recipes now draw from a much larger composition system.

New geometry:

- hero center;
- focus left and focus right;
- floating top-left and top-right;
- floating bottom-left and bottom-right;
- existing full, frame, screen and card layouts remain supported.

New professional edge treatments:

- clean;
- soft glass;
- neon;
- double line;
- cinema;
- paper;
- deep shadow.

New frame entrances:

- slide from left;
- slide from right;
- slide from top;
- slide from bottom;
- scale pop;
- none.

Every framed shot can now vary layout size, horizontal/vertical position, edge treatment, entrance direction, internal camera motion and outgoing transition independently. The Automate review table exposes all five choices per visual.

The actual FFmpeg export implements the same premium frame edge and entrance decisions shown in the preview. These are not UI-only mock effects.

## Background-folder behavior

ResearchCut scans backgrounds\Images and backgrounds\Videos every time Automate is opened and again before every render.

- Add a supported file: it appears after reopening Automate.
- Remove a file: it disappears and will not be rendered.
- Replace a file with another file of the same name: the new content is used on the next load/render.
- If an old saved plan references a deleted built-in background, the renderer falls back to a blurred copy of the current visual.

Supported built-in background images: JPG, JPEG, PNG, WebP and BMP.

Supported built-in background videos: MP4, MOV, MKV, WebM and M4V.

Keep background loops short and use 16:9 1080p assets where possible. Extremely large 4K loops increase decoding load.

## Existing behavior preserved

- local atomic autosave and crash recovery;
- V1 magnetic muted main track;
- A1 voiceover and other audio layers;
- trim, split, crop, resize, mute and volume;
- full-screen player and scrubber;
- optional one-file VText;
- per-shot automation replacement;
- 1080p and 4K output;
- persistent overnight queue.

## Employee action

Employees should close ResearchCut before applying an update. They can use either:

1. the complete ResearchCutEditor-2.1 folder/ZIP; or
2. the official ResearchCut-Update-2.0-to-2.1 ZIP, which contains the changed files, an automatic backup/apply script and this document.

An update-notes Markdown file by itself explains changes but cannot modify program code. The update ZIP or the complete updated folder must accompany it.

