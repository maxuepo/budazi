"""Compare whole-clip vs live (chunked) recognition on real saved recordings.

Usage: python scripts/compare_live.py [N]   # N most recent recordings, default 3
"""
import difflib
import sys
from pathlib import Path

import soundfile as sf

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from budazi import config
from budazi.app import _is_noise
from budazi.asr import SenseVoice
from budazi.live import find_cut, join_texts

cfg, _ = config.load()
asr = SenseVoice(cfg.model_dir, cfg.language, cfg.asr_threads)
n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
for wav in sorted((ROOT / "recordings").glob("*.wav"))[-n:]:
    audio, sr = sf.read(wav, dtype="float32")
    whole, t_whole = asr.transcribe(audio, sr)
    parts, pos, cuts = [], 0, []
    while len(audio) - pos >= 15 * sr:
        cut = find_cut(audio, pos + 10 * sr, pos + 15 * sr, sr)
        parts.append(asr.transcribe(audio[pos:cut], sr)[0])
        cuts.append(round(cut / sr, 1))
        pos = cut
    tail, t_tail = asr.transcribe(audio[pos:], sr)
    parts.append(tail)
    live = join_texts([p for p in parts if not _is_noise(p)])
    norm = lambda s: "".join(c for c in s.lower() if c.isalnum())
    sim = difflib.SequenceMatcher(None, norm(whole), norm(live)).ratio()
    print(f"\n=== {wav.name}  {len(audio)/sr:.1f}s  cuts at {cuts}  similarity {sim:.3f}")
    print(f"WHOLE ({t_whole*1000:.0f} ms): {whole}")
    print(f"LIVE  (tail {t_tail*1000:.0f} ms): {live}")
