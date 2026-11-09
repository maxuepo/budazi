"""Microphone recorder that keeps a short pre-roll so the first syllable isn't cut."""
from __future__ import annotations

import collections
import threading

import numpy as np
import sounddevice as sd


class Recorder:
    def __init__(self, sample_rate: int = 16000, preroll_ms: int = 300):
        self.sr = sample_rate
        block = 1024
        self._preroll = collections.deque(maxlen=max(1, preroll_ms * sample_rate // 1000 // block + 1))
        self._chunks: list[np.ndarray] = []
        self._recording = False
        self._lock = threading.Lock()
        self.level = 0.0  # last block RMS, for UI
        self._stream = sd.InputStream(samplerate=sample_rate, channels=1, dtype="float32",
                                      blocksize=block, callback=self._cb)
        self._stream.start()

    def _cb(self, indata, frames, time_info, status):
        data = indata[:, 0].copy()
        self.level = float(np.sqrt(np.mean(data * data)))
        with self._lock:
            if self._recording:
                self._chunks.append(data)
            else:
                self._preroll.append(data)

    def start(self) -> None:
        with self._lock:
            self._chunks = list(self._preroll)
            self._recording = True

    def snapshot(self) -> np.ndarray:
        """Audio recorded so far in the current take (empty when not recording)."""
        with self._lock:
            chunks = list(self._chunks) if self._recording else []
        return np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)

    def stop(self) -> np.ndarray:
        with self._lock:
            self._recording = False
            chunks, self._chunks = self._chunks, []
        if not chunks:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(chunks)

    def close(self) -> None:
        self._stream.stop()
        self._stream.close()
