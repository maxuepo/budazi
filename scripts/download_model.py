"""Download the SenseVoice-Small speech recognition model (int8 ONNX, ~230 MB).

Usage:  uv run python scripts/download_model.py
Source: https://huggingface.co/csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17
Model:  SenseVoice by FunAudioLLM (Alibaba), converted for sherpa-onnx by k2-fsa.
        Check the model's own license before any use beyond personal research.
"""
import sys
import urllib.request
from pathlib import Path

BASE = "https://huggingface.co/csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/resolve/main"
FILES = {"tokens.txt": "tokens.txt", "model.int8.onnx": "model.int8.onnx",
         "test_wavs/zh.wav": "test_wavs_zh.wav", "test_wavs/en.wav": "test_wavs_en.wav"}
DEST = Path(__file__).resolve().parent.parent / "models" / "sensevoice"


def fetch(url: str, out: Path) -> None:
    tmp = out.with_suffix(out.suffix + ".part")
    with urllib.request.urlopen(url) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length", 0))
        done = 0
        while chunk := r.read(1 << 20):
            f.write(chunk)
            done += len(chunk)
            if total:
                sys.stdout.write(f"\r  {out.name}: {done / 1e6:6.1f} / {total / 1e6:.1f} MB")
                sys.stdout.flush()
    tmp.replace(out)
    print()


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    for remote, local in FILES.items():
        out = DEST / local
        if out.exists() and out.stat().st_size > 0:
            print(f"  {local}: already there")
            continue
        fetch(f"{BASE}/{remote}", out)
    print(f"done -> {DEST}")


if __name__ == "__main__":
    main()
