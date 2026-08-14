from __future__ import annotations

import json
import re
import statistics
import subprocess
import tempfile
from difflib import SequenceMatcher
from pathlib import Path

from .hashing import fingerprint

WORDS = re.compile(r"[a-z0-9']+")


def tokens(text: str) -> list[str]: return WORDS.findall(text.casefold())


def verify_audio_sync(media: Path, cues, cache_dir: Path, model_name: str = "base.en") -> dict:
    """Measure subtitle identity and global timing offset against sampled local ASR."""
    try:
        from faster_whisper import WhisperModel
    except Exception as exc:
        return {"status":"INCONCLUSIVE","reason":f"faster-whisper unavailable: {type(exc).__name__}"}
    eligible = [c for c in cues if len(tokens(c.raw_text)) >= 5]
    if len(eligible) < 3: return {"status":"INCONCLUSIVE","reason":"not enough distinctive cues"}
    chosen = [eligible[round(q*(len(eligible)-1))] for q in (0.2,0.5,0.8)]
    model = WhisperModel(model_name, device="cpu", compute_type="int8", local_files_only=True)
    samples=[]; all_offsets=[]
    with tempfile.TemporaryDirectory(dir=cache_dir) as tmpdir:
        for n, anchor in enumerate(chosen):
            begin=max(0,anchor.start_ms/1000-8); duration=20.0
            wav=Path(tmpdir)/f"sample{n}.wav"
            proc=subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-ss",f"{begin:.3f}","-i",str(media),
              "-t",str(duration),"-vn","-ac","1","-ar","16000","-c:a","pcm_s16le","-y",str(wav)],capture_output=True,text=True)
            if proc.returncode: return {"status":"INCONCLUSIVE","reason":"audio extraction failed"}
            segments,_=model.transcribe(str(wav),language="en",beam_size=5,word_timestamps=True,vad_filter=True)
            asr=[]
            for seg in segments:
                for w in seg.words or []:
                    for tok in tokens(w.word): asr.append((tok,round((begin+w.start)*1000)))
            nearby=[c for c in cues if c.end_ms>=begin*1000 and c.start_ms<=(begin+duration)*1000]
            sub=[]
            for cue in nearby:
                mid=(cue.start_ms+cue.end_ms)//2
                for tok in tokens(cue.raw_text): sub.append((tok,mid))
            matcher=SequenceMatcher(None,[x[0] for x in sub],[x[0] for x in asr],autojunk=False)
            pairs=[]
            for block in matcher.get_matching_blocks():
                for k in range(block.size): pairs.append((sub[block.a+k],asr[block.b+k]))
            ratio=matcher.ratio() if sub and asr else 0.0
            offsets=[a[1]-s[1] for s,a in pairs]
            all_offsets.extend(offsets)
            samples.append({"anchor_cue":anchor.index,"window_start_ms":round(begin*1000),"subtitle_tokens":len(sub),
              "asr_tokens":len(asr),"matched_tokens":len(pairs),"sequence_ratio":round(ratio,6),
              "median_offset_ms":round(statistics.median(offsets)) if offsets else None})
    ratios=[s["sequence_ratio"] for s in samples]
    offset=round(statistics.median(all_offsets)) if all_offsets else None
    spread=round(statistics.median(abs(x-offset) for x in all_offsets)) if all_offsets else None
    passed=min(ratios)>=0.45 and len(all_offsets)>=30 and spread is not None and spread<=1500
    return {"status":"VERIFIED_WITH_OFFSET" if passed else "FAIL", "offset_ms":offset, "median_abs_deviation_ms":spread,
      "matched_tokens":len(all_offsets),"samples":samples,"model":model_name,"verifier":"sampled-asr-sync/1.0"}

