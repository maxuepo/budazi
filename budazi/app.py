"""不打字 (budazi) for Windows: hold a key, speak, release -> cleaned text is pasted at the cursor."""
from __future__ import annotations

import json
import logging
import queue
import threading
import time
import winsound
from datetime import datetime

import pystray
from PIL import Image, ImageDraw
from pynput import keyboard

from . import config
from .asr import SenseVoice
from .audio import Recorder
from .live import LiveTranscriber
from .overlay import AMBER, GREEN, GREY, RED, Overlay
from .polish import Polisher
from .winput import foreground_exe, paste_text

log = logging.getLogger("budazi")
HISTORY = config.ROOT / "history.jsonl"


def _icon(color: str) -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((22, 6, 42, 38), radius=10, fill=color)       # mic head
    d.arc((14, 18, 50, 48), 0, 180, fill=color, width=4)               # holder
    d.line((32, 48, 32, 58), fill=color, width=4)
    d.line((22, 58, 42, 58), fill=color, width=4)
    return img


IDLE, REC, BUSY = _icon("#9aa4b2"), _icon("#e5484d"), _icon("#f5a524")


_FILLERS = {"", "yeah", "oh", "uh", "um", "hmm", "the", "a", "i",
            "嗯", "啊", "呃", "哦", "唉", "诶", "嗯嗯", "啊啊"}


def _is_noise(raw: str) -> bool:
    """SenseVoice turns silence/breath into 'Yeah.' or '嗯。' -- don't paste those."""
    core = "".join(ch for ch in raw.lower() if ch.isalnum())
    return core in _FILLERS


def load_voice_samples(path, n: int = 3, exclude_raw: str | None = None) -> list[str]:
    """Recent cleaned texts that still sound like the user (not concise/restructured)."""
    out = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return out
    for line in reversed(lines):
        try:
            h = json.loads(line)
        except ValueError:
            continue
        text = h.get("text", "")
        if h.get("level", "strong") in ("light", "strong") and 40 <= len(text) <= 300 \
                and text not in out and h.get("raw") != exclude_raw:
            out.append(text)
        if len(out) >= n:
            break
    return out


def _beep(freq: int) -> None:
    threading.Thread(target=winsound.Beep, args=(freq, 50), daemon=True).start()


class App:
    def __init__(self):
        self.cfg, key = config.load()
        log.info("loading SenseVoice ...")
        self.asr = SenseVoice(self.cfg.model_dir, self.cfg.language, self.cfg.asr_threads)
        self.rec = Recorder(self.cfg.sample_rate)
        self.polisher = None
        self.startup_note = ""
        local = config.is_local_url(self.cfg.polish_base_url)
        if key or local:
            self.polisher = Polisher(key, self.cfg.polish_base_url, self.cfg.polish_model,
                                     self.cfg.polish_timeout_s if not local else
                                     max(self.cfg.polish_timeout_s, 30))
            threading.Thread(target=self.polisher.warmup, daemon=True).start()
            log.info("polish via %s (%s)", self.cfg.polish_base_url, "local" if local else "cloud")
        elif self.cfg.polish:
            self.startup_note = "\n未配置 API key：只输出识别原文，不做 AI 润色（见 README）。"
            log.warning("no API key found; pasting raw transcripts")
        names = {"ctrl": ["ctrl_l", "ctrl_r", "ctrl"], "alt": ["alt_l", "alt_r", "alt_gr"]}
        self.hotkeys = {getattr(keyboard.Key, n) for n in names.get(self.cfg.hotkey, [self.cfg.hotkey])}
        self.hotkey_label = {"ctrl": "Ctrl（左右都行）", "ctrl_r": "右 Ctrl"}.get(self.cfg.hotkey,
                                                                              self.cfg.hotkey)
        self.recording = False
        self.cancelled = False
        self.active_key = None
        self.live: LiveTranscriber | None = None
        self._worker_thread: threading.Thread | None = None
        self.overlay = None
        if self.cfg.overlay:
            try:
                self.overlay = Overlay(lambda: self.rec.level)
            except Exception:  # noqa: BLE001
                log.exception("overlay failed to start; continuing without it")
        self._ignore_keys_until = 0.0
        self._take = 0          # counts Ctrl holds, so a late timer can't touch a newer one
        self._ui_shown = False
        self.t_start = 0.0
        self.last_text = ""
        self.jobs: queue.Queue = queue.Queue()
        self.tray = pystray.Icon("budazi", IDLE, f"不打字：按住 {self.hotkey_label} 说话",
                                 self._menu())

    # ---------- tray ----------
    def _menu(self):
        return pystray.Menu(
            pystray.MenuItem("AI 润色", self._toggle_polish, checked=lambda _: self.cfg.polish),
            pystray.MenuItem("  轻度（去口头禅、改口误）", lambda: self._set_level("light"),
                             checked=lambda _: self.cfg.polish_level == "light", radio=True),
            pystray.MenuItem("  重度（再合并重复、理顺语序）", lambda: self._set_level("strong"),
                             checked=lambda _: self.cfg.polish_level == "strong", radio=True),
            pystray.MenuItem("  精炼（删铺垫、先说重点，约一半长度）", lambda: self._set_level("concise"),
                             checked=lambda _: self.cfg.polish_level == "concise", radio=True),
            pystray.MenuItem("  梳理（补上跳掉的逻辑、调顺序，保留你的文风）",
                             lambda: self._set_level("restructure"),
                             checked=lambda _: self.cfg.polish_level == "restructure", radio=True),
            pystray.MenuItem("重新粘贴上一条", lambda: self.jobs.put(("repaste", None))),
            pystray.MenuItem("打开历史记录", lambda: __import__("os").startfile(HISTORY)
                             if HISTORY.exists() else None),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出", self._quit),
        )

    def _on_tray_ready(self, icon):
        icon.visible = True
        try:
            icon.notify(f"已启动。按住 {self.hotkey_label} 说话，说完松开。"
                        + self.startup_note, "不打字")
        except Exception:  # noqa: BLE001
            pass
        if self.cfg.beep:
            winsound.Beep(660, 60)
            winsound.Beep(990, 80)

    def _set_level(self, level: str):
        self.cfg.polish_level = level
        log.info("polish level -> %s", level)

    def _toggle_polish(self):
        self.cfg.polish = not self.cfg.polish

    def _quit(self):
        self.jobs.put(("quit", None))
        self.tray.stop()

    def _ui(self, kind: str, *args) -> None:
        """Update the on-screen indicator (no-op if it's turned off or failed to start)."""
        if self.overlay is None:
            return
        try:
            getattr(self.overlay, {"recording": "recording", "processing": "processing",
                                   "flash": "flash", "hide": "hide"}[kind])(*args)
        except Exception:  # noqa: BLE001
            pass

    def _set_icon(self, img) -> None:
        # updating the tray can block; keep it off the keyboard-hook thread
        threading.Thread(target=setattr, args=(self.tray, "icon", img), daemon=True).start()

    def _cancel(self, why: str) -> None:
        if self.recording and not self.cancelled:
            log.info("cancelled: %s", why)
            self.cancelled = True
            if self._ui_shown:  # it's a shortcut after all: just get out of the way
                self._ui("hide")
                self._set_icon(IDLE)

    def _show_recording_ui(self, take: int) -> None:
        """Runs ui_delay_ms after Ctrl goes down, only if it's still a plain Ctrl hold."""
        if self.recording and not self.cancelled and take == self._take:
            self._ui_shown = True
            self._ui("recording")
            self._set_icon(REC)
            if self.cfg.beep:
                _beep(880)

    # ---------- hotkey (must return fast: it runs inside the OS keyboard hook) ----------
    def _on_press(self, key):
        if time.perf_counter() < self._ignore_keys_until:
            return  # synthetic Ctrl+V from our own paste
        if key in self.hotkeys:
            if not self.recording:  # ignore auto-repeat while held
                self.recording, self.cancelled, self.active_key = True, False, key
                self.t_start = time.perf_counter()
                # audio starts right away (nothing is lost), but the indicator only shows
                # after ui_delay_ms, so quick Ctrl+C / Ctrl+V don't flash it
                self.rec.start()
                self.live = LiveTranscriber(self.asr, self.rec, self.cfg.sample_rate, _is_noise)
                self._take += 1
                self._ui_shown = False
                t = threading.Timer(self.cfg.ui_delay_ms / 1000, self._show_recording_ui,
                                    args=(self._take,))
                t.daemon = True
                t.start()
        elif self.recording:
            # another key while holding -> user is typing a shortcut (Ctrl+C...), not dictating
            self._cancel(f"{key} pressed while holding hotkey")

    def _on_click(self, x, y, button, pressed):
        if pressed:
            self._cancel("mouse click while holding hotkey")

    def _on_scroll(self, x, y, dx, dy):
        self._cancel("mouse scroll while holding hotkey")

    def _on_release(self, key):
        if time.perf_counter() < self._ignore_keys_until:
            return
        if not self.recording or key != self.active_key:
            return
        self.recording = False
        audio = self.rec.stop()
        held_ms = (time.perf_counter() - self.t_start) * 1000
        log.info("hotkey released after %.0fms, audio %.1fs, peak %.3f", held_ms,
                 len(audio) / self.cfg.sample_rate, float(abs(audio).max()) if len(audio) else 0)
        live, self.live = self.live, None
        if self.cancelled or held_ms < self.cfg.min_hold_ms:
            live.cancel()
            self._set_icon(IDLE)
            self._ui("hide")   # shortcuts and taps end silently
            return
        if self.cfg.beep:
            _beep(660)
        self._ui("processing", "识别中")
        self._set_icon(BUSY)
        self._ensure_worker()
        self.jobs.put(("dictate", (audio, foreground_exe(), live)))

    # ---------- worker ----------
    def _worker(self):
        # This thread must never die: one bad job (or a tray-icon hiccup) used to kill it,
        # after which every recording just piled up unprocessed.
        while True:
            try:
                kind, arg = self.jobs.get()
                if kind == "quit":
                    return
                if kind == "repaste" and self.last_text:
                    time.sleep(0.2)
                    self._paste(self.last_text, foreground_exe())
                elif kind == "dictate":
                    self._dictate(*arg)
            except BaseException:  # noqa: BLE001
                log.exception("job failed")
                self._ui("flash", "出错了，详情见 budazi.log", RED, 2.5)
            finally:
                try:
                    self._set_icon(IDLE)
                except BaseException:  # noqa: BLE001
                    pass

    def _ensure_worker(self):
        if self._worker_thread is None or not self._worker_thread.is_alive():
            if self._worker_thread is not None:
                log.error("worker thread had died; restarting it")
            self._worker_thread = threading.Thread(target=self._worker, daemon=True, name="worker")
            self._worker_thread.start()

    def _paste(self, text: str, exe: str):
        # our own Ctrl+V goes through the keyboard hook too; ignore it there
        self._ignore_keys_until = time.perf_counter() + 5
        try:
            paste_text(text, self.cfg.restore_clipboard, exe)
        finally:  # hook events for our keystrokes can arrive a moment later
            self._ignore_keys_until = time.perf_counter() + 0.15

    def _save_take(self, audio) -> str | None:
        """Keep the last N recordings in recordings/ for debugging recognition."""
        if self.cfg.keep_recordings <= 0:
            return None
        import soundfile as sf
        d = config.ROOT / "recordings"
        d.mkdir(exist_ok=True)
        path = d / f"{datetime.now():%Y%m%d-%H%M%S}.wav"
        sf.write(path, audio, self.cfg.sample_rate)
        for old in sorted(d.glob("*.wav"))[:-self.cfg.keep_recordings]:
            old.unlink(missing_ok=True)
        return path.name

    def _dictate(self, audio, exe: str, live: LiveTranscriber | None = None):
        t0 = time.perf_counter()
        try:
            wav = self._save_take(audio)
        except Exception:  # noqa: BLE001
            wav = None
        if live is not None:
            raw, t_asr, pieces = live.finish(audio)
            if pieces > 1:
                log.info("transcribed in %d pieces while recording", pieces)
        else:
            raw, t_asr = self.asr.transcribe(audio, self.cfg.sample_rate)
        if _is_noise(raw):
            log.info("(no speech: %r)", raw)
            self._ui("flash", "没听到说话", GREY, 1.2)
            return
        level_name = {"light": "轻度", "strong": "重度", "concise": "精炼",
                      "restructure": "梳理"}.get(self.cfg.polish_level, "")
        if self.cfg.polish and self.polisher:
            self._ui("processing", f"整理中（{level_name}）")
        text, t_llm, err, model_used = raw, 0.0, None, None
        if self.cfg.polish and self.polisher and len(raw) >= self.cfg.skip_polish_under_chars:
            style = self.cfg.app_styles.get(exe)
            level = self.cfg.polish_level
            models = [self.cfg.polish_model]
            if level in self.cfg.level_models:            # e.g. restructure always uses Kimi
                models.insert(0, self.cfg.level_models[level])
            elif (len(raw) >= self.cfg.long_min_chars and self.cfg.long_model
                    and level in self.cfg.long_model_levels):
                models.insert(0, self.cfg.long_model)  # fall back to the fast model
            voice = load_voice_samples(HISTORY, 3) if level == "restructure" else None
            for m in models:
                try:
                    text, t_llm = self.polisher.polish(raw, self.cfg.dictionary, style,
                                                       model=m, level=level, voice_samples=voice)
                    text, err, model_used = text or raw, None, m
                    break
                except Exception as e:  # noqa: BLE001  never lose what the user said
                    err = f"{m.split('/')[-1]}: {type(e).__name__}: {e}"
                    log.warning("polish failed (%s)", err)
                    text = raw
        self._paste(text, exe)
        self.last_text = text
        if err:
            self._ui("flash", "润色失败，已输入原文", AMBER, 2.0)
        else:
            self._ui("flash", f"已输入 {len(text)} 字", GREEN, 0.9)
        total = time.perf_counter() - t0
        short = model_used.split("/")[-1] if model_used else "raw"
        log.info("[%s] asr %.0fms llm %.0fms (%s) total %.0fms | %s -> %s",
                 exe, t_asr * 1000, t_llm * 1000, short, total * 1000, raw, text)
        with HISTORY.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "time": datetime.now().isoformat(timespec="seconds"), "app": exe,
                "audio_s": round(len(audio) / self.cfg.sample_rate, 2),
                "raw": raw, "text": text, "asr_ms": round(t_asr * 1000),
                "llm_ms": round(t_llm * 1000), "model": short, "wav": wav,
                "level": self.cfg.polish_level if model_used else "raw",
                "total_ms": round(total * 1000), "error": err,
            }, ensure_ascii=False) + "\n")

    def run(self):
        self._ensure_worker()
        listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
        listener.start()
        from pynput import mouse
        mouse.Listener(on_click=self._on_click, on_scroll=self._on_scroll, daemon=True).start()
        log.info("ready: hold %s and speak", self.cfg.hotkey)
        self.tray.run(setup=self._on_tray_ready)
        listener.stop()
        self.rec.close()


def _message_box(text: str, title: str = "不打字", icon: int = 0x40) -> None:
    import ctypes
    ctypes.windll.user32.MessageBoxW(None, text, title, icon | 0x40000)  # topmost


def _single_instance() -> bool:
    """Hold a named mutex for the process lifetime; False if another copy has it."""
    import ctypes
    k32 = ctypes.windll.kernel32
    globals()["_MUTEX"] = k32.CreateMutexW(None, False, "Local\\BudaziDictation")
    return k32.GetLastError() != 183  # ERROR_ALREADY_EXISTS


def main():
    if not _single_instance():
        _message_box("不打字 已经在运行了。\n\n图标在任务栏右下角（可能收在 ^ 里），右键可以退出。")
        return
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(),
                  logging.FileHandler(config.ROOT / "budazi.log", encoding="utf-8")])
    logging.getLogger("httpx").setLevel(logging.WARNING)
    # pythonw has no stderr: send uncaught errors from any thread to the log file
    import sys
    threading.excepthook = lambda a: log.error(
        "uncaught error in thread %s", a.thread.name if a.thread else "?",
        exc_info=(a.exc_type, a.exc_value, a.exc_traceback))
    sys.excepthook = lambda t, v, tb: log.error("uncaught error", exc_info=(t, v, tb))
    try:
        import faulthandler
        globals()["_FAULT_LOG"] = open(config.ROOT / "budazi.crash.log", "a", encoding="utf-8")
        faulthandler.enable(globals()["_FAULT_LOG"], all_threads=True)
    except Exception:  # noqa: BLE001
        pass
    try:
        App().run()
    except Exception as e:  # noqa: BLE001  pythonw has no console, so show startup errors
        log.exception("startup failed")
        _message_box(f"不打字 启动失败：\n{type(e).__name__}: {e}\n\n详情见 budazi.log", icon=0x10)


if __name__ == "__main__":
    main()
