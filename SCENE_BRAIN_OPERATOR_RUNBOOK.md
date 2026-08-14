# Scene Brain Operator Runbook

## Start and stop

1. Connect the Scene Brain external SSD.
2. Double-click `START_SCENE_BRAIN.bat`.
3. Wait for the browser to open after the backend health check succeeds.
4. Confirm the Library lists six titles. If it reports a missing media drive, reconnect the registered volume and retry.
5. To stop, close the Scene Brain server window. Project saves are written to disk, not only to browser storage.

## Add a movie or series

1. Open Library and select **Add New Title**.
2. Choose Movie or Series / TV Show.
3. Enter the canonical title and optional year/franchise.
4. Choose one movie file or a series folder.
5. Review the discovery preview. Naming that cannot be parsed is marked for review rather than guessed.
6. Select **Add to Library**. Original media is copied into the registered media library; it is not rewritten or remuxed.
7. Confirm the title card appears. Searchability and Rich Atlas maturity remain separate.

## Create a project

1. Select New Project.
2. Name the project and attach a clean script. Voiceover and a prepared clue script are optional.
3. Select the intended title/franchise scope.
4. Leave Gemini disabled unless a production budget has explicitly been approved.
5. Select **Analyze Project**. Review beat, visual-opportunity, library, and character readiness results.
6. Select **Prepare Project** only after analysis. A failed prerequisite must remain visible and fail closed.

### Source scope

- **Single Title:** select exactly one registered Film/TV title.
- **Franchise:** select a franchise; Scene Brain visibly expands it to every registered member title (for example Breaking Bad + Better Call Saul).
- **Custom Multi-Title:** add at least two unique registered titles. Remove a chip with its `x` button. Exact events remain constrained to the correct title.

### Clue V4

Use **Get Clue Prompt** to download the canonical prompt. After attaching a clean script and selecting source scope, use **Copy Ready Prompt** to create a local prompt containing the master instructions, selected titles, and script. Scene Brain sends nothing automatically. Import the returned JSON with **Browse Clue**. Analyze independently validates narration and reports exact, punctuation-only, or word-sequence mismatch. Repair a blocked clue; do not silently rewrite narration.

## Character galleries

Breaking Bad’s current gallery is stored on the canonical SSD. Imported originals remain untouched. `PARTIAL` means references exist but are not sufficiently human-trusted for hard identity gates. Review suggested references before promoting them. Missing galleries are non-blocking unless a workflow explicitly requires face identity.

Open Library → title → Characters → **Manage References**. Use **Add Images** for multiple images of the existing character. Duplicate hashes are skipped. Every imported image remains suggested until an operator chooses **Trust** or **Reject**. Trust only a clear, dominant, correctly named face; partial galleries stay neutral in ranking.

## Review, manual clips, gaps, and export

Open a prepared project and use Review Issues for unresolved choices. Preview candidates before Use This. A saved approval is persisted on disk. For a manual visual, import an image/video in Project Media, drag it into the intended track position, and adjust duration/source-in in the Inspector. An `EMPTY VISUAL GAP` is intentional space: select Add Media or drag approved media into it; later clips stay in place because ripple is off by default. Use the Automate/Export area only after the timeline and voiceover play continuously. A failed render remains in the queue with retry/cancel controls.

The large center Play/Pause button controls the master clock; Spacebar is the shortcut. Previous/Next Cut and ±5 seconds surround it. Scrubbing updates voiceover and the active visual. A paused timeline must pause every active media element.

GitHub is developer infrastructure, not an employee workflow. Operators should not run Git commands.

## Performance

Open **System Health** or **Performance**. Keep processing profile on AUTO. On the current Quadro P1000 machine, AUTO uses CPU because real CUDA/NVENC tests did not pass. Do not select GPU Preferred merely because Windows displays a GPU number.

## Troubleshooting

- App does not open: inspect `runtime/production_editor/logs/launcher.log` and `server.log`.
- Library empty: confirm the external SSD volume is connected; do not create a replacement catalog on the laptop.
- Media error: use Retry, then confirm the resolved source exists and its fingerprint is unchanged.
- Black preview: an explicit EMPTY VISUAL GAP or MEDIA ERROR state should appear. If neither appears, capture a support report.
- Slow work: leave AUTO enabled and reduce other GPU-heavy applications. Do not increase worker counts beyond policy.
- Project conflict: reload the latest disk revision; browser localStorage is never the source of truth.

## Support package

Use the Support button to copy a sanitized status report. It excludes credentials. Never paste API keys into project files, logs, reports, or chat.

## Backup and recovery

Canonical catalog, memory, receipts, and projects live under `<media-root>\.scene_brain`. Laptop caches may be deleted. Before a migration, copy canonical state and preserve historical receipts byte-for-byte. Old projects remain pinned unless explicitly upgraded.
