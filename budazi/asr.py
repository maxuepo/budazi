"""Local speech recognition with SenseVoice-Small (int8 ONNX, CPU) via sherpa-onnx."""
from __future__ import annotations

import threading
import time
from pathlib import Path

import numpy as np
import sherpa_onnx


class SenseVoice:
    def __init__(self, model_dir: Path, language: str = "auto", threads: int = 4):
        model = model_dir / "model.int8.onnx"
        tokens = model_dir / "tokens.txt"
        if not model.exists():
            raise FileNotFoundError(
                f"找不到语音识别模型：{model}\n请先在项目目录运行：uv run python scripts/download_model.py")
        self.rec = sherpa_onnx.OfflineRecognizer.from_sense_voice(
            model=str(model),
            tokens=str(tokens),
            num_threads=threads,
            language="" if language == "auto" else language,
            use_itn=True,          # numbers/dates as digits, adds punctuation
            provider="cpu",
        )
        self._lock = threading.Lock()

    def transcribe(self, samples: np.ndarray, sample_rate: int = 16000) -> tuple[str, float]:
        """samples: float32 mono in [-1, 1]. Returns (text, seconds)."""
        with self._lock:  # background pieces and the worker share one recognizer
            t0 = time.perf_counter()
            stream = self.rec.create_stream()
            stream.accept_waveform(sample_rate, samples.astype(np.float32))
            self.rec.decode_stream(stream)
            return stream.result.text.strip(), time.perf_counter() - t0
