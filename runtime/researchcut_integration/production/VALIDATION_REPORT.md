# ResearchCut Editor 2.1 validation report

Validation date: 2026-08-07

## Static checks

- server.js: passed Node syntax check
- renderer.js: passed Node syntax check
- render-queue.js: passed Node syntax check
- automation-catalog.js: passed Node syntax check
- public\app.js: passed Node syntax check
- INSTALL_ON_NEW_PC.ps1: passed PowerShell parser check

## Editor integration

Passed with real media from the supplied Data folder:

- image/video/audio import and FFprobe metadata
- five visual/audio layers
- crop persistence
- autosave revision advance
- schema v3 handoff
- project rename
- full server restart and reopen recovery
- independently scrollable bulk-media panel
- vertically scrollable timeline with synchronized labels
- added V4 and A3 layers persisted through autosave and restart

## Automation render

Passed with real image, video and voiceover:

- 60-preset catalog available
- background catalog rescanned on demand: temporary add changed 24 to 25 entries; removal returned it to 24
- selected recipe persisted
- framed built-in background rendered
- motion and automated transition applied
- audio mixed
- 1280x720 exact 16:9 preview
- 6.000-second exact output
- FFprobe validation passed
- premium rounded cinema edge and slide-right entrance rendered
- seven premium edge systems and six entrance choices exposed for per-shot replacement

## Integrated VText

Passed using the supplied Akatsuki English narration:

- one VText instruction file uploaded
- three events parsed
- clean narration script intentionally omitted
- script derived from NARRATION_CUE lines
- faster-whisper alignment completed
- audio/script match: 82.8%
- events rendered: 3/3
- 12.000-second 1280x720 output
- VText report generated beside the output

## 4K export

- real renderer path (not a metadata-only check)
- built-in framed background and motion
- exact 3840x2160 UHD output
- exact 1.000-second smoke render
- FFprobe validation passed

## Visual browser QA

Verified interactively:

- project desk and reopen
- exact player scrub to a selected time
- previous/next cut and five-second controls
- volume and mute controls
- true 16:9 fullscreen visual stage
- fullscreen overlay scrubber
- 60-recipe Automate workspace
- per-visual layout, edge style, entrance, motion and transition selectors
- persistent queue status
- rendered-output player with native seek, volume and fullscreen controls

## Commands

    npm.cmd test
    npm.cmd run test:render
    npm.cmd run test:vtext
    npm.cmd run test:4k

All completed successfully on the validation machine.
