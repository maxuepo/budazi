"""Load settings and the LLM API key.

Settings: config.toml (your own, git-ignored) or, if it doesn't exist, config.example.toml.
Word list: dictionary.txt (your own, git-ignored) or dictionary.example.txt.
API key (first found): env var named by `api_key_env`, BUDAZI_API_KEY, api_key.txt,
fireworks.txt. Local servers (Ollama, LM Studio) need no key.
"""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Config:
    hotkey: str = "ctrl_r"            # pynput key name held to talk
    min_hold_ms: int = 300            # shorter presses are ignored
    ui_delay_ms: int = 200            # show indicator/beep only after Ctrl is held this long
    sample_rate: int = 16000
    language: str = "auto"            # SenseVoice: auto / zh / en / ja / ko / yue
    asr_threads: int = 4
    polish: bool = True               # send transcript to the LLM for cleanup
    polish_level: str = "strong"     # light: fillers/corrections; strong: also merge & smooth
    polish_model: str = "accounts/fireworks/routers/deepseek-v4p1-flash-1017-ultrafast"
    long_model: str = "accounts/fireworks/routers/kimi-k3-fast"  # smarter, ~0.7s
    long_min_chars: int = 60          # transcripts this long go to long_model
    long_model_levels: list[str] = field(default_factory=lambda: ["light", "strong"])
    level_models: dict[str, str] = field(default_factory=lambda: {
        "restructure": "accounts/fireworks/routers/kimi-k3-fast"})  # level -> model, any length
    polish_base_url: str = "https://api.fireworks.ai/inference/v1"  # any OpenAI-compatible API
    api_key_env: str = "FIREWORKS_API_KEY"   # env var holding the key (optional)
    backend: str = "cloud"                   # "cloud" or "local" (switchable from the tray menu)
    local_base_url: str = "http://localhost:11434/v1"   # Ollama; LM Studio: http://localhost:1234/v1
    local_model: str = "qwen3:8b"
    local_timeout_s: float = 60.0            # first request loads the model into VRAM
    polish_timeout_s: float = 6.0
    skip_polish_under_chars: int = 6  # very short phrases are pasted raw
    keep_recordings: int = 20         # save last N takes to recordings/ (0 = off)
    beep: bool = True
    overlay: bool = True              # floating "recording / processing" pill on screen
    restore_clipboard: bool = True
    dictionary: list[str] = field(default_factory=list)
    app_styles: dict[str, str] = field(default_factory=dict)
    model_dir: Path = ROOT / "models" / "sensevoice"


def _read_key(env_name: str) -> str | None:
    for name in (env_name, "BUDAZI_API_KEY"):
        key = os.environ.get(name) if name else None
        if key:
            return key.strip()
    for fname in ("api_key.txt", "fireworks.txt"):
        path = ROOT / fname
        if not path.exists():
            continue
        lines = [l.strip() for l in path.read_text(encoding="utf-8").splitlines()]
        lines = [l for l in lines if l and not l.startswith("#")]
        if lines:
            text = lines[0].split("=", 1)[1] if "=" in lines[0] else lines[0]
            return text.strip().strip("\"'") or None
    return None


def is_local_url(url: str) -> bool:
    return any(h in url for h in ("://localhost", "://127.0.0.1", "://[::1]"))


def _first_existing(*names: str) -> Path | None:
    for n in names:
        if (ROOT / n).exists():
            return ROOT / n
    return None


def load() -> tuple[Config, str | None]:
    cfg = Config()
    path = _first_existing("config.toml", "config.example.toml")
    if path:
        data = tomllib.loads(path.read_text(encoding="utf-8-sig"))
        for k, v in data.items():
            if k == "model_dir":
                v = (ROOT / v).resolve()
            if hasattr(cfg, k):
                setattr(cfg, k, v)
    dict_file = _first_existing("dictionary.txt", "dictionary.example.txt")
    if dict_file:
        words = [w.strip() for w in dict_file.read_text(encoding="utf-8-sig").splitlines()]
        cfg.dictionary += [w for w in words if w and not w.startswith("#")]
    return cfg, _read_key(cfg.api_key_env)
