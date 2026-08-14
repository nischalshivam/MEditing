# Employee update guide — ResearchCut 2.0 to 2.1

## Before updating

1. Finish or pause all render jobs.
2. Close every ResearchCut browser tab.
3. Close the START_EDITOR launcher window.
4. Confirm the current program folder contains server.js and START_EDITOR.bat.
5. Optionally back up %LOCALAPPDATA%\ResearchCut Editor.

## Applying the official update kit

Extract ResearchCut-Update-2.0-to-2.1.zip. Open PowerShell in the extracted folder and run:

    powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\APPLY_UPDATE_2.1.ps1 -Target "C:\path\to\ResearchCut Editor"

Use the real existing program-folder path. Do not point Target at LocalAppData or a project folder.

The updater:

- validates the target;
- creates a timestamped backup under the target's updates folder;
- replaces only versioned program/documentation files;
- does not alter backgrounds, project media or LocalAppData;
- runs Node syntax checks;
- verifies server version 2.1.0.

## After updating

1. Double-click START_EDITOR.bat.
2. Open an existing project.
3. Confirm media-bin scrolling.
4. Confirm timeline vertical scrolling.
5. Add one temporary visual/audio layer and verify autosave.
6. Open Automate and confirm edge/entrance selectors.
7. Render a short sample.

Read UPDATE_NOTES_2.1.md for the complete change list.

## Rollback

Close ResearchCut. The updater reports a timestamped backup folder. Copy those backed-up files to their original program paths. Do not modify LocalAppData. Restart the old version and verify.

