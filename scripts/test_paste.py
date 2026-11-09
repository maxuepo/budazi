"""Open a small Tk window, paste into it with winput.paste_text, report what arrived.

Safe: aborts without pasting if the test window didn't get focus, and puts the
user's own clipboard back at the end.
"""
import sys
import threading
import time
import tkinter as tk

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
import pyperclip
from budazi.winput import foreground_exe, paste_text

user_clip = pyperclip.paste()
root = tk.Tk()
root.title("budazi paste test")
root.attributes("-topmost", True)
box = tk.Text(root, width=40, height=4)
box.pack()
result = {}


def run():
    time.sleep(0.8)
    root.after(0, lambda: (root.focus_force(), box.focus_set()))
    time.sleep(0.4)
    result["exe"] = foreground_exe()
    if result["exe"] not in ("python.exe", "pythonw.exe"):
        result["text"] = "(skipped: test window not focused)"
    else:
        pyperclip.copy("ORIGINAL-CLIPBOARD")
        paste_text("粘贴测试 paste OK ✓", restore=True, exe=result["exe"])
        time.sleep(0.4)
        result["text"] = box.get("1.0", "end").strip()
        time.sleep(1.0)  # clipboard is restored in the background after 0.8s
        result["clip"] = pyperclip.paste() == "ORIGINAL-CLIPBOARD"
    pyperclip.copy(user_clip)
    root.after(0, root.destroy)


threading.Thread(target=run, daemon=True).start()
root.mainloop()
print("foreground:", result.get("exe"))
print("pasted text:", repr(result.get("text")))
print("clipboard restored:", result.get("clip"))
