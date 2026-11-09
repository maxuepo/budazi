"""macOS platform layer: same functions as winput.py.

Needs (System Settings → Privacy & Security), granted to the app that runs Python
(Terminal / iTerm, or the venv's python for a LaunchAgent):
  - Microphone          to record
  - Input Monitoring    to see the hotkey being held
  - Accessibility       to send Cmd+V
"""
from __future__ import annotations

import fcntl
import os
import subprocess
import threading
import time

import pyperclip
from pynput.keyboard import Controller, Key

_kb = Controller()


def foreground_exe() -> str:
    """Lower-case name of the frontmost app, e.g. 'code', 'terminal', 'wechat'."""
    try:
        from AppKit import NSWorkspace  # pyobjc, installed on macOS
        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        return (app.localizedName() or "").lower() if app else ""
    except Exception:  # noqa: BLE001  fall back to AppleScript (slower, ~0.1 s)
        try:
            out = subprocess.run(
                ["osascript", "-e", 'tell application "System Events" to get name of '
                 'first application process whose frontmost is true'],
                capture_output=True, text=True, timeout=1)
            return out.stdout.strip().lower()
        except Exception:  # noqa: BLE001
            return ""


def paste_text(text: str, restore: bool = True, exe: str = "") -> None:
    try:
        old = pyperclip.paste() if restore else None
    except pyperclip.PyperclipException:
        old = None
    pyperclip.copy(text)
    time.sleep(0.05)
    # the hotkey (Control/Option) was just released, but make sure it isn't logically down
    for k in (Key.ctrl, Key.ctrl_r, Key.alt, Key.alt_r, Key.shift):
        try:
            _kb.release(k)
        except Exception:  # noqa: BLE001
            pass
    with _kb.pressed(Key.cmd):
        _kb.press("v")
        _kb.release("v")
    if restore and old is not None:
        threading.Thread(target=_restore_later, args=(old, text), daemon=True).start()


def _restore_later(old: str, ours: str) -> None:
    time.sleep(0.8)
    try:
        if pyperclip.paste() == ours:  # don't clobber something the user copied meanwhile
            pyperclip.copy(old)
    except pyperclip.PyperclipException:
        pass


# ---- sounds, dialogs, single instance, opening files ----

_SOUNDS = {"start": ["Tink"], "stop": ["Pop"], "ready": ["Glass"]}


def play_tone(kind: str) -> None:
    for name in _SOUNDS.get(kind, []):
        path = f"/System/Library/Sounds/{name}.aiff"
        if os.path.exists(path):
            subprocess.Popen(["afplay", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _applescript_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def message_box(text: str, title: str = "不打字", error: bool = False) -> None:
    icon = "stop" if error else "note"
    script = (f"display dialog {_applescript_str(text)} with title {_applescript_str(title)} "
              f'buttons {{"OK"}} default button "OK" with icon {icon}')
    try:
        subprocess.run(["osascript", "-e", script], timeout=120, capture_output=True)
    except Exception:  # noqa: BLE001
        pass


def single_instance() -> bool:
    """Hold an exclusive lock on a file for the process lifetime."""
    from . import config
    f = open(config.ROOT / ".budazi.lock", "w")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.close()
        return False
    globals()["_LOCK"] = f
    return True


def open_path(path) -> None:
    subprocess.Popen(["open", str(path)])


TRAY_HINT = "图标在屏幕顶部菜单栏右侧，点击可以退出。"
