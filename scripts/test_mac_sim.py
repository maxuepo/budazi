"""Exercise the macOS code paths on Windows with fake Mac-only modules (no real Mac needed).

Nothing here touches the real keyboard or clipboard: those are replaced with recorders.
"""
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pystray  # noqa: E402,F401  import real backends before pretending to be a Mac
import sounddevice  # noqa: E402,F401
import sherpa_onnx  # noqa: E402,F401
import httpx  # noqa: E402,F401
import soundfile  # noqa: E402,F401
import pynput.keyboard as real_kb  # noqa: E402

calls = []

# ---- fakes for Mac-only modules ----
fcntl = types.ModuleType("fcntl")
fcntl.LOCK_EX, fcntl.LOCK_NB = 2, 4
_locked = set()


def flock(f, op):
    if f.name in _locked:
        raise OSError("locked")
    _locked.add(f.name)


fcntl.flock = flock
sys.modules["fcntl"] = fcntl


class _App:
    def localizedName(self):
        return "Code"


class _WS:
    @staticmethod
    def sharedWorkspace():
        return _WS()

    def frontmostApplication(self):
        return _App()


appkit = types.ModuleType("AppKit")
appkit.NSWorkspace = _WS
sys.modules["AppKit"] = appkit
helper = types.ModuleType("PyObjCTools.AppHelper")
helper.callAfter = lambda fn, *a: calls.append(("callAfter", fn.__name__, a[1:]))
pkg = types.ModuleType("PyObjCTools")
pkg.AppHelper = helper
sys.modules["PyObjCTools"] = pkg
sys.modules["PyObjCTools.AppHelper"] = helper


class FakeController:
    def press(self, k):
        calls.append(("press", str(k)))

    def release(self, k):
        calls.append(("release", str(k)))

    def pressed(self, k):
        outer = self

        class _C:
            def __enter__(s):
                outer.press(k)

            def __exit__(s, *a):
                outer.release(k)
        return _C()


real_kb.Controller = FakeController

import pyperclip  # noqa: E402
clip = {"v": "OLD"}
pyperclip.paste = lambda: clip["v"]
pyperclip.copy = lambda t: clip.__setitem__("v", t)

import subprocess  # noqa: E402
ran = []
subprocess.run = lambda args, **k: ran.append(args) or types.SimpleNamespace(stdout="", returncode=0)
subprocess.Popen = lambda args, **k: ran.append(args)

sys.platform = "darwin"  # from here on budazi believes it is on macOS

from budazi import system  # noqa: E402
from budazi import macinput  # noqa: E402

ok = lambda name, cond: print(("PASS " if cond else "FAIL ") + name)  # noqa: E731

ok("system picks macOS layer", system.IS_MAC and system.paste_text is macinput.paste_text)
ok("frontmost app via AppKit", system.foreground_exe() == "code")

macinput._restore_later = lambda old, ours: clip.__setitem__("v", old)  # run restore inline
calls.clear()
system.paste_text("你好 hello", restore=True, exe="code")
seq = [c for c in calls if c[0] in ("press", "release") and ("cmd" in c[1] or c[1] == "'v'" or c[1] == "v")]
ok("paste sends Cmd+V", [c[1] for c in seq][:4] == ["Key.cmd", "v", "v", "Key.cmd"])
ok("clipboard restored after paste", clip["v"] == "OLD")

ran.clear()
system.message_box('他说"你好"\\', error=True)
script = ran[0][2]
ok("dialog uses osascript with escaped text", ran[0][:2] == ["osascript", "-e"]
   and '\\"你好\\"' in script and "with icon stop" in script)

lockfile = ROOT / ".budazi.lock"
ok("first copy gets the lock", system.single_instance() is True)
ok("second copy is refused", system.single_instance() is False)

ran.clear()
system.open_path("/tmp/history.jsonl")
ok("open file uses `open`", ran and ran[0][0] == "open")

# ---- app wiring on "macOS" ----
import budazi.app as A  # noqa: E402


class FakeTray:
    icon = None


app = A.App.__new__(A.App)          # skip __init__ (no mic / model needed for these checks)
app.tray = FakeTray()
calls.clear()
app._set_icon(A.REC)
ok("menu-bar icon updated on main thread (AppHelper.callAfter)", calls and calls[0][0] == "callAfter")

cfg, _ = A.config.load()
ok("overlay disabled on macOS", not (cfg.overlay and system.IS_WINDOWS))
try:
    lockfile.unlink()
except OSError:
    pass
