# ResearchCut Editor 2.1 — complete new Windows laptop setup

## Purpose of this file

Give this complete file and the ResearchCut Editor 2.1 folder or ZIP to a capable GPT/Codex agent that has permission to use the new Windows PC. The agent should perform the setup itself, verify every dependency, place the finished tool on the current user's Desktop, run the acceptance checks, and report exact results.

This procedure is designed for a normal 64-bit Windows 10 or Windows 11 laptop with no Node.js, FFmpeg or Python already installed. Do not require Git, Visual Studio, Docker, WSL, a database, a cloud account or npm packages.

Official reference pages:

- Windows Package Manager: https://learn.microsoft.com/en-us/windows/package-manager/winget/
- Node.js LTS: https://nodejs.org/en/download
- Python for Windows: https://www.python.org/downloads/windows/
- FFmpeg downloads: https://ffmpeg.org/download.html
- VText source/behavior reference: https://github.com/nischalshivam/VText

## What the finished installation contains

ResearchCut is a local browser-based Windows application:

- Node.js runs a private server bound only to 127.0.0.1.
- The UI opens in the normal browser.
- FFmpeg and FFprobe probe media, create thumbnails/waveforms and render final videos.
- Python is used only for optional narration-synced VText.
- Projects and renders stay on the laptop under LocalAppData.
- No account, cloud database or internet connection is required after dependencies and the initial VText model have been downloaded.

The folder itself is portable. The user normally starts it through the Desktop shortcut or START_EDITOR.bat.

## Non-negotiable safety rules for the setup agent

1. Do not delete, reset, overwrite or move any existing user folder.
2. Do not run recursive deletion commands.
3. Resolve the current user's Desktop using the operating system API, not a guessed username.
4. If Desktop already contains a ResearchCut Editor folder, preserve it. Install into ResearchCut Editor 2, ResearchCut Editor 3, and so on.
5. Install only the named official dependencies.
6. Do not upload project media, credentials or LocalAppData anywhere.
7. Do not expose the local server to the LAN or change its host from 127.0.0.1.
8. Do not weaken PowerShell execution policy system-wide. If a script needs permission, use a one-process Bypass invocation only.
9. Do not install CUDA or GPU packages unless the user explicitly requests GPU acceleration later.
10. If a reboot is required, save a setup-status note on the Desktop and continue after reboot instead of guessing that PATH was updated.

## Hardware and storage guidance

Minimum practical setup:

- Windows 10 version 1809 or newer, or Windows 11
- 8 GB RAM for short projects; 16 GB or more strongly recommended for long 1080p/4K work
- modern four-core CPU or better
- SSD storage
- 1920x1080 display recommended

Free-space target:

- 5 GB for applications, Python packages, speech model and caches
- plus enough room for copied source media
- plus export headroom
- for one-to-two-hour 4K work, keep at least 50–100 GB free if possible

The editor remains lightweight while editing because source media is streamed and timeline data is stored as decisions. 4K encoding is intentionally compute-heavy and can take a long time on a laptop CPU, which is why the persistent overnight queue exists.

## Preferred fully automatic path

### 1. Confirm the supplied folder

Find the folder that contains all of these files:

    server.js
    renderer.js
    render-queue.js
    automation-catalog.js
    START_EDITOR.bat
    INSTALL_ON_NEW_PC.ps1
    public
    tools\vtext
    backgrounds

If any are missing, stop and request the complete ResearchCut Editor 2.1 package.

### 2. Run the bundled installer

Open a normal PowerShell window in the supplied folder. Administrator mode is not required unless Windows asks for elevation during a dependency installer.

Run:

    powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\INSTALL_ON_NEW_PC.ps1

Expected behavior:

- verifies WinGet;
- installs Node.js LTS using package ID OpenJS.NodeJS.LTS if missing;
- installs FFmpeg using package ID Gyan.FFmpeg if missing;
- installs Python 3.13 using package ID Python.Python.3.13 if missing;
- copies the complete editor to a new safe folder on the Desktop when needed;
- installs VText Python packages from the bundled requirements file;
- runs dependency checks;
- creates ResearchCut Editor.lnk on the Desktop.

If the user intentionally does not need video text, the setup agent may run:

    powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\INSTALL_ON_NEW_PC.ps1 -SkipVTextPackages

The editor, transitions, motion, backgrounds, audio mix, 1080p/4K render and queue still work. Only the VText toggle is unavailable until Python packages are installed.

## Manual fallback procedure

Use this only if the bundled installer reports a specific failure.

### A. Ensure WinGet exists

Run:

    winget --version

On modern Windows, WinGet arrives through Microsoft App Installer. If it is missing:

1. Open Microsoft Store.
2. Search for App Installer by Microsoft.
3. Install or update it.
4. Close and reopen PowerShell.
5. Run winget --version again.

On a newly created Windows account, registration can sometimes be triggered with:

    Add-AppxPackage -RegisterByFamilyName -MainPackage Microsoft.DesktopAppInstaller_8wekyb3d8bbwe

If Store access is unavailable, use Microsoft's official WinGet repair guidance from the reference page above.

### B. Install Node.js LTS

Run:

    winget install --id OpenJS.NodeJS.LTS --exact --silent --accept-source-agreements --accept-package-agreements

Close and reopen PowerShell, then verify:

    node --version

ResearchCut supports Node 18 or newer. Prefer the current official LTS release rather than a Current/EOL release.

### C. Install FFmpeg and FFprobe

Run:

    winget install --id Gyan.FFmpeg --exact --silent --accept-source-agreements --accept-package-agreements

Close and reopen PowerShell, then verify both commands:

    ffmpeg -version
    ffprobe -version

Both are mandatory. If FFmpeg exists but FFprobe does not, the package or PATH is incomplete; repair FFmpeg before starting the editor.

### D. Install Python for VText

Run:

    winget install --id Python.Python.3.13 --exact --silent --accept-source-agreements --accept-package-agreements

Close and reopen PowerShell, then verify:

    python --version
    python -m pip --version

Python is optional for text-free use, but mandatory when Enable VText is checked.

### E. Install VText packages

From the final ResearchCut folder:

    python -m pip install --upgrade pip
    python -m pip install -r .\tools\vtext\requirements.txt

Expected core packages include Pillow, NumPy, imageio-ffmpeg, faster-whisper and opencv-python-headless. Let pip choose compatible transitive versions; do not invent version pins.

Verify:

    pushd .\tools\vtext
    python check.py
    popd

Expected text:

    READY  - speech engine: faster-whisper

The first real text render downloads the English faster-whisper model. Keep internet available for that first run. Later runs use the local model cache.

### F. Copy the app safely to Desktop

Resolve Desktop:

    $desktopPath = [Environment]::GetFolderPath('Desktop')

Choose a new, non-existing folder under that exact path. Never overwrite an existing ResearchCut installation. Copy the complete supplied folder, including hidden files if present.

The final structure must resemble:

    Desktop\ResearchCut Editor\
      public\
      backgrounds\
      tools\vtext\
      tests\
      server.js
      renderer.js
      render-queue.js
      automation-catalog.js
      START_EDITOR.bat
      CHECK_SYSTEM.bat
      README.md

## Required verification — do not skip

### 1. Dependency check

Double-click CHECK_SYSTEM.bat or run it from Command Prompt.

Mandatory:

- Node version prints
- FFmpeg version prints
- FFprobe version prints

Optional VText:

- Python version prints
- VText says READY with faster-whisper

### 2. Syntax checks

From the app folder:

    node --check server.js
    node --check renderer.js
    node --check render-queue.js
    node --check automation-catalog.js
    node --check public\app.js

Every command must exit successfully without output.

### 3. Start test

Run:

    START_EDITOR.bat

Expected:

- a console window stays open;
- browser opens http://127.0.0.1:43127;
- ResearchCut project desk appears;
- no missing-dependency error appears.

Do not close the launcher during this test.

### 4. Functional smoke test

Perform these actions in the UI:

1. Create a test project.
2. Import one image, one short MP4 and one MP3/WAV.
3. Add visuals on V1 and audio on A1.
4. Move the player scrubber and verify the time changes.
5. Split a selected clip with S.
6. Undo with Ctrl+Z.
7. Crop or resize one visual.
8. Press F or View and verify the visual itself fills a true 16:9 fullscreen stage.
9. Exit fullscreen with Escape.
10. Close the browser and launcher.
11. Restart through START_EDITOR.bat.
12. Verify the project reopens with its edits.

### 5. Automation smoke test

1. Open the test project and click Next: Automate.
2. Verify 60 style recipes are present.
3. Choose a framed recipe and press Apply & regenerate.
4. Verify the preview changes.
5. Change one visual's layout, motion and transition selectors.
6. Render a 12-second sample.
7. Wait for Complete.
8. Click Play and verify the output player has scrub, volume and fullscreen controls.

### 6. Optional VText smoke test

Use a valid VText instruction file. It must contain:

    === VTEXT INSTRUCTION FILE v1 ===
    --- EVENT 001 ---
    NARRATION_CUE: "words actually spoken in the English narration"
    DISPLAY_TEXT: Exact / On Screen Text

In Automate:

1. Enable VText.
2. Upload the instruction .txt.
3. Keep the clean narration script empty to verify one-file mode.
4. Render a short sample.
5. Verify the job completes and text appears at narration-matched timing.

If alignment fails, inspect these first:

- narration must be English and audible;
- NARRATION_CUE text must closely match spoken words;
- instruction header must be present;
- use clean voiceover without background music for best alignment;
- confirm internet was available for the first model download.

### 7. Built-in automated acceptance tests

These development tests require the sample media folder referenced by the test files. If that media is available:

    npm.cmd test
    npm.cmd run test:render

Expected JSON contains ok: true. The render test must report:

- width 1280
- height 720
- duration 6

If sample media is not supplied on the new laptop, do not call that an app failure; perform the UI smoke tests using any local test media.

## How the user should work each day

1. Double-click ResearchCut Editor on the Desktop.
2. Create or reopen a project.
3. Import voiceover and media.
4. Align all clips manually.
5. Use V1 for the muted main line.
6. Use V2/V3 for overlays or video whose original audio may be used.
7. Use A1 for voiceover and A2 for BGM/SFX.
8. Click Next: Automate.
9. Select a recipe, backgrounds, optional VText and quality.
10. Review per-visual choices.
11. Render a short sample.
12. Add final work to the overnight queue.
13. At night, reopen any project's Automate page and press Start all.

The queue is global across projects and stored locally. Keep the laptop connected to power, disable sleep for the render window, and leave enough disk space. The screen may be turned off; Windows must not sleep.

## Autosave and backup

Project library:

    %LOCALAPPDATA%\ResearchCut Editor

Contains:

- projects and imported media copies;
- atomic project JSON;
- recovery revisions;
- VText instruction uploads;
- render queue state;
- intermediate render work;
- final MP4 output and manifests.

Backup:

1. Close ResearchCut.
2. Copy the entire LocalAppData ResearchCut Editor folder to another drive.
3. Preserve folder structure.

Restore:

1. Close ResearchCut on the target PC.
2. Install dependencies and the editor.
3. Copy the backed-up ResearchCut Editor data folder into the current user's LocalAppData.
4. Start the editor and verify projects.

Do not copy only project.json files; source media is stored beside them.

## Troubleshooting matrix

### START_EDITOR says Node.js missing

- Close all terminals.
- Reopen Command Prompt.
- Run where node and node --version.
- If absent, reinstall OpenJS.NodeJS.LTS through WinGet.
- Restart Windows if installation completed but PATH did not refresh.

### FFmpeg or FFprobe missing

- Run where ffmpeg and where ffprobe.
- Reinstall Gyan.FFmpeg.
- Reopen the terminal or reboot.
- Do not point ResearchCut at a random ffmpeg.exe without its matching ffprobe.exe.

### Browser does not open

- Keep START_EDITOR.bat running.
- Manually open http://127.0.0.1:43127.
- If the console says EADDRINUSE, another ResearchCut instance is likely running. Close the older launcher, then start once.

### Media import fails

- Verify ffprobe can open the source file.
- Prefer standard JPG/PNG/WebP, MP4/MOV/MKV/WebM and MP3/WAV/M4A.
- Confirm disk free space because ResearchCut copies imported source media into the project.
- A damaged/unsupported file is intentionally rejected rather than partially saved.

### VText says not ready

- Run python tools\vtext\check.py.
- Run python -m pip install -r tools\vtext\requirements.txt.
- Confirm the Python command points to the same installation used by pip.
- Prefer Python 3.13 for a new setup.

### VText text is early, late or missing

- Compare every NARRATION_CUE against the English voiceover.
- Keep cues distinctive and close to the exact spoken wording.
- Do not put desired display wording in NARRATION_CUE; DISPLAY_TEXT controls the visible text.
- Use an optional clean script when narration differs greatly from cue lines.
- Test a short sample before a long render.

### 4K render is slow

- This is expected on CPU-only laptops.
- Use fast quality for checks, balanced or quality for the final.
- Queue videos during the day and run Start all overnight.
- Keep power connected and Windows sleep disabled.
- 1080p is usually the best speed/quality choice for ordinary YouTube delivery.

### Queue recovered after a restart

This is intentional. A running job is converted back to waiting so it can restart safely. Open Automate and press Start all again.

### Project seems missing

- Check %LOCALAPPDATA%\ResearchCut Editor\projects.
- Make sure the editor is running as the same Windows user who created the project.
- Check whether the data folder was moved or the app was started under another account.

## Completion report the setup agent must give the user

Report all of the following:

- exact Desktop installation folder;
- shortcut path;
- Node version;
- FFmpeg and FFprobe availability;
- Python version;
- VText READY result or the explicit statement that VText was intentionally skipped;
- app URL;
- successful create/import/autosave/reopen smoke test;
- successful Automate sample render;
- exact location of LocalAppData project storage;
- any reboot or first-model-download still required.

Do not claim completion merely because packages installed. Completion requires the app to start and the smoke tests to pass.
