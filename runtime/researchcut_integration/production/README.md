# ResearchCut Editor 2.1

ResearchCut is a focused, local-first 16:9 editor for long-form research videos. The human editor controls media selection, clip timing, layers, trim, crop, framing and audio. The Automate workspace then applies a reproducible style plan with transitions, motion, frame backgrounds, optional narration-synced VText and final 1080p or 4K rendering.

## Start

1. On a configured PC, double-click START_EDITOR.bat.
2. The app opens at http://127.0.0.1:43127.
3. Keep the launcher window open. Closing it stops only the local server; projects remain saved.
4. On a new Windows PC, read SETUP_NEW_WINDOWS_LAPTOP.md or run INSTALL_ON_NEW_PC.ps1 from PowerShell.

No npm install is required. The editor server has zero third-party Node packages.

## Editor workflow

- Import images, videos, voiceover, music and SFX.
- V1 is the magnetic main visual lane and is muted by default.
- V2 and V3 are overlay lanes. A visual dropped on an occupied overlay position is moved to the next available lane/time instead of being hidden under another clip.
- A1 is voiceover; A2 is music and SFX. Both have waveforms and split support.
- Drag clips between compatible lanes, trim either edge, split at the playhead, move/resize on canvas, or use exact Inspector values.
- Use Crop on canvas for manual four-edge cropping.
- Use the player scrubber, previous/next cut, minus/plus five seconds, volume and fullscreen controls.
- Hold Ctrl while scrolling over the timeline to zoom around the pointer.
- Dark and light themes are stored locally.
- The media bin remains independently scrollable with hundreds of imported assets.
- The timeline scrolls vertically, and additional visual/audio layers can be added from its toolbar.

## Automate workflow

- Choose from 60 deterministic style recipes grouped into ten visual families.
- Select subtle, balanced or energetic motion.
- Toggle automatic motion or transitions independently.
- Choose automatic, blurred, built-in image/video, project-media, solid or black frame backgrounds.
- Upload one VText instruction .txt file only when narration-synced video text is required. Text can remain completely off.
- Replace the layout, motion or outgoing transition for any individual visual.
- Premium framed shots vary size and position, use seven edge treatments, and can enter from the left, right, top, bottom or with a scale pop.
- Render a real 12-second FFmpeg sample before committing to a long export.
- Select 1080p or 4K and fast, balanced or maximum encoding quality.

## Persistent overnight queue

Use Add to overnight queue for every finished project during the day. Jobs and progress are stored in the local application-data folder. At night, reopen ResearchCut, open any finished project, enter Automate and press Start all. The queue renders one project at a time and survives app restarts; an interrupted running job returns to waiting.

Completed jobs provide Play, Download and Show file actions. The player uses native timeline seeking, volume, playback and fullscreen controls.

## Background library discovery

The Automate page rescans `backgrounds\Images` and `backgrounds\Videos` whenever it is opened. Supported images/videos added to those folders appear automatically; removed files disappear and cannot be selected or rendered. If an older saved plan references a removed background, rendering safely falls back to the current-visual blur rather than using a missing file.

For office and employee deployment, read `OFFICE_AND_EMPLOYEE_DEPLOYMENT.md`. For this release's changes, read `UPDATE_NOTES_2.1.md`.

## Optional VText

The bundled VText engine consumes:

- the automated base render;
- the project narration audio already mixed into that render;
- one VText instruction file containing NARRATION_CUE and DISPLAY_TEXT events;
- an optional clean narration script.

If the optional script is omitted, ResearchCut derives it from the NARRATION_CUE lines. VText uses faster-whisper to align English narration, analyzes safe frame zones and renders the instruction file's exact display text. Python and the packages in tools\vtext\requirements.txt are required only when the VText toggle is enabled.

## Saving, recovery and storage

Projects, copied source media, automation settings, render queue and output files are stored under:

    %LOCALAPPDATA%\ResearchCut Editor

Every edit is debounced to an atomic JSON replacement, immediate crash recovery is also kept in browser local storage, and server-side revision snapshots protect longer sessions. Original source media remains non-destructive.

Back up the whole ResearchCut Editor folder inside LocalAppData to preserve all projects and renders.

## Keyboard shortcuts

- Space: play or pause
- S: split selected video/audio at the playhead
- Delete or Backspace: remove selected clip
- Ctrl+Z / Ctrl+Y: undo / redo
- Left / Right: one-frame playhead step
- F: enter or leave fullscreen preview

## Verification

Run CHECK_SYSTEM.bat for dependency readiness. For development acceptance tests:

    npm.cmd test
    npm.cmd run test:render
    npm.cmd run test:vtext
    npm.cmd run test:4k

The tests verify real-media editing/recovery, a framed transition sample, integrated one-file Akatsuki VText, and an exact 3840x2160 UHD renderer smoke output.
