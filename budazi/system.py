"""Pick the platform layer: Windows (winput.py) or macOS (macinput.py)."""
import sys

IS_WINDOWS = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"

if IS_WINDOWS:
    from .winput import (TRAY_HINT, foreground_exe, message_box, open_path, paste_text,  # noqa: F401
                         play_tone, single_instance)
elif IS_MAC:
    from .macinput import (TRAY_HINT, foreground_exe, message_box, open_path,  # noqa: F401
                           paste_text, play_tone, single_instance)
else:
    raise RuntimeError("不打字 only supports Windows and macOS")
