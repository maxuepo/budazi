"""A small floating pill at the bottom of the screen that shows what budazi is doing.

- recording: red dot, scrolling microphone level meter, elapsed seconds
- processing: amber dot + "整理中（重度）…"
- done / cancelled / nothing heard: a short message, then it hides

Built as a raw Win32 layered window (not Tk): Tk activates its windows when it maps
them, which steals focus from the app you're dictating into. This window is created
with WS_EX_NOACTIVATE | WS_EX_TRANSPARENT, so it never takes focus and mouse clicks go
straight through it. Frames are drawn with PIL and pushed with UpdateLayeredWindow.
"""
from __future__ import annotations

import ctypes
import queue
import threading
import time
from ctypes import wintypes

import numpy as np
from PIL import Image, ImageDraw, ImageFont

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

WS_POPUP = 0x80000000
WS_EX_LAYERED, WS_EX_TRANSPARENT, WS_EX_TOOLWINDOW = 0x80000, 0x20, 0x80
WS_EX_NOACTIVATE, WS_EX_TOPMOST = 0x8000000, 0x8
SW_HIDE, SW_SHOWNOACTIVATE = 0, 4
HWND_TOPMOST = -1
SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE = 0x1, 0x2, 0x10
SPI_GETWORKAREA = 0x30
ULW_ALPHA, AC_SRC_ALPHA = 2, 1
PM_REMOVE = 1

BG = (31, 35, 41, 245)
FG = (242, 244, 247, 255)
RED, AMBER, GREEN, GREY = "#ff4d4f", "#f5a524", "#3fb950", "#9aa4b2"
N_BARS = 16

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.DefWindowProcW.restype = LRESULT
user32.CreateWindowExW.restype = wintypes.HWND
user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                                   ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                   wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, wintypes.UINT]
# 64-bit handles: declare every signature, or ctypes truncates handles to 32-bit ints
kernel32.GetModuleHandleW.restype = wintypes.HMODULE
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
user32.GetDC.restype = wintypes.HDC
user32.GetDC.argtypes = [wintypes.HWND]
user32.RegisterClassExW.restype = wintypes.ATOM
user32.PeekMessageW.argtypes = [ctypes.c_void_p, wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT]
user32.TranslateMessage.argtypes = [ctypes.c_void_p]
user32.DispatchMessageW.argtypes = [ctypes.c_void_p]
user32.DispatchMessageW.restype = LRESULT
user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.UpdateLayeredWindow.argtypes = [wintypes.HWND, wintypes.HDC, ctypes.c_void_p, ctypes.c_void_p,
                                       wintypes.HDC, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p,
                                       wintypes.DWORD]
gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.DeleteDC.argtypes = [wintypes.HDC]
gdi32.CreateDIBSection.restype = wintypes.HBITMAP
gdi32.CreateDIBSection.argtypes = [wintypes.HDC, ctypes.c_void_p, wintypes.UINT,
                                   ctypes.POINTER(ctypes.c_void_p), wintypes.HANDLE, wintypes.DWORD]
gdi32.SelectObject.restype = wintypes.HGDIOBJ
gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("style", wintypes.UINT), ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON),
                ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR),
                ("hIconSm", wintypes.HICON)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD),
                ("biCompression", wintypes.DWORD), ("biSizeImage", wintypes.DWORD),
                ("biXPelsPerMeter", wintypes.LONG), ("biYPelsPerMeter", wintypes.LONG),
                ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [("BlendOp", ctypes.c_ubyte), ("BlendFlags", ctypes.c_ubyte),
                ("SourceConstantAlpha", ctypes.c_ubyte), ("AlphaFormat", ctypes.c_ubyte)]


def _work_area() -> tuple[int, int, int, int]:
    r = wintypes.RECT()
    user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(r), 0)
    return r.left, r.top, r.right, r.bottom


def _font(size: int):
    for name in ("msyh.ttc", "msyhbd.ttc", "simhei.ttf", "segoeui.ttf"):
        try:
            return ImageFont.truetype(f"C:/Windows/Fonts/{name}", size)
        except OSError:
            continue
    return ImageFont.load_default()


class Overlay:
    def __init__(self, level_fn=lambda: 0.0):
        self.level_fn = level_fn
        self.q: queue.Queue = queue.Queue()
        self.mode, self.label, self.t0, self.hide_at = "hidden", "", 0.0, 0.0
        self.levels = [0.0] * N_BARS
        self.hwnd = None
        self._ready = threading.Event()
        self._error: BaseException | None = None
        threading.Thread(target=self._run, daemon=True, name="overlay").start()
        self._ready.wait(5)
        if self._error:
            raise self._error

    # ---- thread-safe API ----
    def recording(self):
        self.q.put(("recording", None))

    def processing(self, label: str = "整理中…"):
        self.q.put(("processing", label))

    def flash(self, text: str, color: str = GREEN, seconds: float = 1.0):
        self.q.put(("flash", (text, color, seconds)))

    def hide(self):
        self.q.put(("hide", None))

    # ---- overlay thread ----
    def _run(self):
        try:
            self._create()
        except BaseException as e:  # noqa: BLE001
            self._error = e
            self._ready.set()
            return
        self._ready.set()
        msg = wintypes.MSG()
        while True:
            while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            try:
                self._tick()
            except Exception:  # noqa: BLE001  never let the UI loop die
                pass
            time.sleep(0.033)

    def _create(self):
        try:  # this thread only: render at real pixels on high-DPI screens
            user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))  # PER_MONITOR_AWARE_V2
        except Exception:  # noqa: BLE001
            pass
        dpi = user32.GetDpiForSystem() if hasattr(user32, "GetDpiForSystem") else 96
        self.s = s = dpi / 96.0
        self.w, self.h = int(260 * s), int(46 * s)
        self.font = _font(int(15 * s))
        hinst = kernel32.GetModuleHandleW(None)
        self._wndproc = WNDPROC(lambda h, m, w, l: user32.DefWindowProcW(h, m, w, l))
        wc = WNDCLASSEXW(cbSize=ctypes.sizeof(WNDCLASSEXW), lpfnWndProc=self._wndproc,
                         hInstance=hinst, lpszClassName="BudaziOverlay")
        user32.RegisterClassExW(ctypes.byref(wc))
        left, top, right, bottom = _work_area()
        self.x = left + (right - left - self.w) // 2
        self.y = bottom - self.h - int(28 * s)
        self.hwnd = user32.CreateWindowExW(
            WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE | WS_EX_TOPMOST,
            "BudaziOverlay", "budazi", WS_POPUP, self.x, self.y, self.w, self.h,
            None, None, hinst, None)
        if not self.hwnd:
            raise OSError(f"CreateWindowExW failed: {ctypes.get_last_error()}")

    # drawing ------------------------------------------------------------
    def _frame(self) -> Image.Image:
        s, w, h = self.s, self.w, self.h
        k = 2  # supersample for smooth edges
        img = Image.new("RGBA", (w * k, h * k), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((0, 0, w * k - 1, h * k - 1), radius=h * k // 2, fill=BG)
        mid = h * k // 2

        def dot(color):
            r = int(6 * s * k)
            cx = int(24 * s * k)
            d.ellipse((cx - r, mid - r, cx + r, mid + r), fill=color)

        now = time.perf_counter()
        if self.mode == "recording":
            on = int((now - self.t0) * 2) % 2 == 0
            dot(RED if on else "#a8383a")
            x0 = int(108 * s * k)
            for i, lvl in enumerate(self.levels):
                bh = max(3 * s * k, lvl * 28 * s * k)
                x = x0 + int(i * 6 * s * k)
                d.rounded_rectangle((x, mid - bh / 2, x + 3.5 * s * k, mid + bh / 2),
                                    radius=int(1.7 * s * k), fill=RED)
        elif self.mode == "processing":
            dot(AMBER)
        elif self.mode == "flash":
            dot(self.label[1])
        img = img.resize((w, h), Image.LANCZOS)
        d = ImageDraw.Draw(img)
        tx, my = int(40 * s), h // 2
        if self.mode == "recording":
            d.text((tx, my), "录音中", font=self.font, fill=FG, anchor="lm")
            d.text((w - int(18 * s), my), f"{int(now - self.t0)}s", font=self.font,
                   fill=GREY, anchor="rm")
        elif self.mode == "processing":
            dots = "•" * (1 + int((now - self.t0) * 3) % 3)
            d.text((tx, my), f"{self.label} {dots}", font=self.font, fill=FG, anchor="lm")
        elif self.mode == "flash":
            d.text((tx, my), self.label[0], font=self.font, fill=FG, anchor="lm")
        return img

    def _push(self, img: Image.Image):
        w, h = img.size
        a = np.asarray(img, dtype=np.uint16)
        alpha = a[..., 3:4]
        bgra = np.empty((h, w, 4), dtype=np.uint8)
        bgra[..., 0] = (a[..., 2] * alpha[..., 0] // 255)   # premultiplied B
        bgra[..., 1] = (a[..., 1] * alpha[..., 0] // 255)
        bgra[..., 2] = (a[..., 0] * alpha[..., 0] // 255)
        bgra[..., 3] = alpha[..., 0]
        screen = user32.GetDC(None)
        mem = gdi32.CreateCompatibleDC(screen)
        bmi = BITMAPINFOHEADER(biSize=ctypes.sizeof(BITMAPINFOHEADER), biWidth=w, biHeight=-h,
                               biPlanes=1, biBitCount=32, biCompression=0)
        bits = ctypes.c_void_p()
        hbmp = gdi32.CreateDIBSection(mem, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0)
        ctypes.memmove(bits, bgra.tobytes(), w * h * 4)
        old = gdi32.SelectObject(mem, hbmp)
        pt_dst, pt_src = wintypes.POINT(self.x, self.y), wintypes.POINT(0, 0)
        size = wintypes.SIZE(w, h)
        blend = BLENDFUNCTION(0, 0, 255, AC_SRC_ALPHA)
        user32.UpdateLayeredWindow(self.hwnd, screen, ctypes.byref(pt_dst), ctypes.byref(size), mem,
                                   ctypes.byref(pt_src), 0, ctypes.byref(blend), ULW_ALPHA)
        gdi32.SelectObject(mem, old)
        gdi32.DeleteObject(hbmp)
        gdi32.DeleteDC(mem)
        user32.ReleaseDC(None, screen)

    def _show(self):
        user32.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)
        user32.SetWindowPos(self.hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                            SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE)

    def _hide(self):
        self.mode = "hidden"
        user32.ShowWindow(self.hwnd, SW_HIDE)

    def _tick(self):
        changed = False
        while True:
            try:
                kind, arg = self.q.get_nowait()
            except queue.Empty:
                break
            now = time.perf_counter()
            if kind == "hide":
                self._hide()
                continue
            if kind == "recording":
                self.mode, self.t0, self.levels = "recording", now, [0.0] * N_BARS
            elif kind == "processing":
                self.mode, self.t0, self.label = "processing", now, arg
            elif kind == "flash":
                text, color, secs = arg
                self.mode, self.label, self.hide_at = "flash", (text, color), now + secs
            changed = True
        if self.mode == "flash" and time.perf_counter() > self.hide_at:
            self._hide()
        if self.mode == "hidden":
            return
        if self.mode == "recording":
            # scrolling level meter, newest on the right; sqrt so quiet speech still moves
            self.levels = self.levels[1:] + [min(1.0, (max(self.level_fn(), 0.0) ** 0.5) * 4.5)]
        self._push(self._frame())
        if changed:
            self._show()
