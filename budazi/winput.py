"""Windows platform layer: paste at the cursor, foreground app, sounds, dialogs, single instance.

macinput.py implements the same functions for macOS; system.py picks one.
"""
from __future__ import annotations

import ctypes
import os
import threading
import time
from ctypes import wintypes

import pyperclip

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

VK_CONTROL, VK_V, VK_SHIFT = 0x11, 0x56, 0x10
KEYEVENTF_KEYUP = 0x0002
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def _key(vk: int, up: bool = False) -> None:
    user32.keybd_event(vk, 0, KEYEVENTF_KEYUP if up else 0, 0)


def foreground_exe() -> str:
    """Lower-case exe name of the focused window, e.g. 'code.exe'."""
    hwnd = user32.GetForegroundWindow()
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(len(buf))
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return os.path.basename(buf.value).lower()
        return ""
    finally:
        kernel32.CloseHandle(h)


# Terminals where Ctrl+V may not paste; Ctrl+Shift+V works in most of them.
_SHIFT_PASTE = {"windowsterminal.exe", "wezterm-gui.exe", "alacritty.exe", "mintty.exe"}


def paste_text(text: str, restore: bool = True, exe: str = "") -> None:
    try:
        old = pyperclip.paste() if restore else None
    except pyperclip.PyperclipException:
        old = None
    pyperclip.copy(text)
    time.sleep(0.03)
    # make sure no modifier from the hotkey is still logically down
    for vk in (0xA2, 0xA3, 0xA4, 0xA5, VK_SHIFT):  # L/R Ctrl, L/R Alt, Shift
        if user32.GetAsyncKeyState(vk) & 0x8000:
            _key(vk, up=True)
    use_shift = exe in _SHIFT_PASTE
    _key(VK_CONTROL)
    if use_shift:
        _key(VK_SHIFT)
    _key(VK_V)
    _key(VK_V, up=True)
    if use_shift:
        _key(VK_SHIFT, up=True)
    _key(VK_CONTROL, up=True)
    if restore and old is not None:
        threading.Thread(target=_restore_later, args=(old, text), daemon=True).start()


def _restore_later(old: str, ours: str) -> None:
    time.sleep(0.8)  # Electron/browser apps can read the clipboard late
    try:
        if pyperclip.paste() == ours:  # don't clobber something the user copied meanwhile
            pyperclip.copy(old)
    except pyperclip.PyperclipException:
        pass


# ---- sounds, dialogs, single instance, opening files ----

_TONES = {"start": [(880, 50)], "stop": [(660, 50)], "ready": [(660, 60), (990, 80)]}


def play_tone(kind: str) -> None:
    import winsound

    def run():
        for freq, ms in _TONES.get(kind, []):
            winsound.Beep(freq, ms)
    threading.Thread(target=run, daemon=True).start()


def message_box(text: str, title: str = "不打字", error: bool = False) -> None:
    user32.MessageBoxW(None, text, title, (0x10 if error else 0x40) | 0x40000)  # topmost


def single_instance() -> bool:
    """Hold a named mutex for the process lifetime; False if another copy has it."""
    globals()["_MUTEX"] = kernel32.CreateMutexW(None, False, "Local\\BudaziDictation")
    return kernel32.GetLastError() != 183  # ERROR_ALREADY_EXISTS


def open_path(path) -> None:
    os.startfile(path)


TRAY_HINT = "图标在任务栏右下角（可能收在 ^ 里），右键可以退出。"
