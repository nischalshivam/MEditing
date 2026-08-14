# Sprint 1 decisions

- Local media remains immutable and read-only; generated artifacts live under `runtime/`.
- Every expensive artifact is bound to the physical source SHA-256 plus detector/extractor settings.
- Subtitle origin is evidence, never authority. A parseable sidecar is not automatically sync-verified.
- Dialogue search may span only contiguous cues from the same selected track and respects token boundaries.
- Shot timestamps come only from FFmpeg physical cut detection. No model invents timestamps.
- Benchmark freezes explicitly prohibit accuracy claims until Scene Atlas and Resolver exist.
- No Gemini credential or network integration is present in Sprint 1.

