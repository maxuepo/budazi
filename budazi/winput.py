"""Windows helpers: paste text at the cursor and find the foreground app."""
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
