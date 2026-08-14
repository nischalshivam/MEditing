# Breaking Bad Transcript Repair V2

Verdict: BLOCKED at the post-promotion search smoke/discovery gate.

## Transcript repair passed

- Four bad original sidecars were preserved and marked `SIDECAR_REJECTED_WRONG_CONTENT`.
- No embedded subtitle streams existed for S02E02, S05E04, S05E06, or S05E07.
- Local faster-whisper base.en generated four source-hash-bound managed transcripts on the SSD.
- All replacements are non-empty, monotonic, within media duration, and have distinct full-transcript hashes.
- Candidate index has exactly 62 transcripts for 62 physical episodes and zero unexplained full-transcript duplicates.
- Corrected index was atomically promoted; failed rows remain in `subtitles_failed_integrity_v1` for audit.
- No media or original subtitle was modified. No API or Rich build was used.

## Measured ASR

- Audio processed: 11,418.226 seconds
- Sum of job wall times: 1,006.594 seconds (two-worker overlap)
- Real-time factors: 0.073–0.109

## Remaining blocker

The trustworthy index exposed a separate retrieval-quality problem. Of five smoke queries, only exact distinctive `tread lightly` routed and displayed correctly. Broad clues such as `you got me`, `W W Walt Whitman`, `Gale notebook`, and `Mike full measure` still fail because whole-transcript FTS cannot guarantee that all terms occur in the same local dialogue window.

The discovery contract was hardened: no Walter-book beat is now labelled VERIFIED_LOCAL from scattered/unrelated terms. V3 result is 2 STRONG_LOCAL, 5 AMBIGUOUS, 10 UNRESOLVED exact/event beats, and 24 editorial beats needing no exact episode. Absurd Season 2 routes are no longer verified.

Therefore the transcript/source integrity requirement is complete, but the requested final gate (sane smoke tests plus trustworthy 41-beat routing) is not complete. Rich Atlas construction remains stopped.
