"""Transcribe long takes piece by piece while the user is still talking.

SenseVoice gets slower per second as clips get longer (70 s takes ~2.5 s, 15 s takes ~0.2 s),
so every time ~15 s of new audio has piled up we cut it at the quietest moment and
transcribe it in the background. On release only the tail is left to do.
"""
from __future__ import annotations

import threading
import time

import numpy as np


def find_cut(audio: np.ndarray, lo: int, hi: int, sr: int) -> int:
    """Index of the quietest 100 ms frame between lo and hi (a pause, hopefully)."""
    frame = sr // 10
    seg = audio[lo:hi]
    n = len(seg) // frame
    if n < 2:
        return hi
    rms = np.sqrt((seg[: n * frame].reshape(n, frame) ** 2).mean(axis=1))
    return lo + int(rms.argmin()) * frame + frame // 2


def join_texts(parts: list[str]) -> str:
    out = ""
    for p in parts:
        if out and p and out[-1].isascii() and p[0].isascii() and out[-1] != " ":
            out += " "
        out += p
    return out


class LiveTranscriber:
    def __init__(self, asr, rec, sr: int, is_noise, chunk_s: float = 15, min_s: float = 10):
        self.asr, self.rec, self.sr, self.is_noise = asr, rec, sr, is_noise
        self.chunk, self.min = int(chunk_s * sr), int(min_s * sr)
        self.parts: list[str] = []
        self.pos = 0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        while not self._stop.wait(0.5):
            audio = self.rec.snapshot()
            if len(audio) - self.pos < self.chunk:
                continue
            cut = find_cut(audio, self.pos + self.min, self.pos + self.chunk, self.sr)
            self._add(audio[self.pos:cut])
            self.pos = cut

    def _add(self, audio: np.ndarray) -> None:
        text, _ = self.asr.transcribe(audio, self.sr)
        if not self.is_noise(text):
            self.parts.append(text)

    def cancel(self) -> None:
        self._stop.set()

    def finish(self, audio: np.ndarray) -> tuple[str, float, int]:
        """Wait for background pieces, transcribe the tail.

        Returns (text, seconds spent after release, number of pieces).
        """
        t0 = time.perf_counter()
        self._stop.set()
        self._thread.join()
        tail = audio[self.pos:]
        if len(tail) > self.sr // 4:
            self._add(tail)
        return join_texts(self.parts), time.perf_counter() - t0, len(self.parts)
