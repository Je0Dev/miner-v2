#!/usr/bin/env python3
"""Yomitan Hover Overlay - Small draggable window that OCRs continuously.

Creates a small transparent window that the user drags over game text.
It OCRs every 2 seconds and copies results to clipboard for Yomitan.

Usage:
    ./yomitan-hover.sh chi_sim   # Chinese
    ./yomitan-hover.sh jpn       # Japanese
"""
import sys, time, subprocess, os, threading
from pathlib import Path

try:
    import tkinter as tk
except ImportError:
    print("ERROR: python-tkinter required"); sys.exit(1)

sys.path.insert(0, str(Path(__file__).parent))
from ocr import ocr_image, prewarm_tesseract
from translate import copy_to_clipboard, notify
from text import clean_text
from config import OCR_LANGS
from log import log

TEMP_DIR = f"{os.environ.get('XDG_RUNTIME_DIR', '/tmp')}/yomitan-hover"
os.makedirs(TEMP_DIR, exist_ok=True)
PID_FILE = f"{TEMP_DIR}/hover.pid"

# Kill existing instance
if os.path.exists(PID_FILE):
    try:
        with open(PID_FILE) as f:
            old_pid = int(f.read().strip())
        os.kill(old_pid, 9)
    except Exception:
        pass
    os.remove(PID_FILE)

with open(PID_FILE, "w") as f:
    f.write(str(os.getpid()))

OCR_LANG_SHORT = sys.argv[1] if len(sys.argv) > 1 else "zh"
OCR_LANG_TESS = OCR_LANGS.get(OCR_LANG_SHORT, OCR_LANG_SHORT)
CAPTURE_COUNT = 0
LAST_TEXT = ""

# Prewarm Tesseract
prewarm_tesseract(OCR_LANG_TESS)

# Create small floating window
root = tk.Tk()
root.title("Yomitan Hover")
root.geometry("250x80+200+200")
root.attributes("-topmost", True)
root.attributes("-alpha", 0.90)
root.configure(bg="#1a1a2e")
# Don't use overrideredirect - breaks Wayland/Hyprland interaction

# UI elements
status_var = tk.StringVar(value=f"Yomitan Hover ({OCR_LANG_SHORT.upper()})\nDrag over text")
label = tk.Label(root, textvariable=status_var, bg="#1a1a2e", fg="#ffdd57",
                 font=("Sans", 10), justify=tk.CENTER)
label.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

# Make window draggable
drag_data = {"x": 0, "y": 0}
def on_press(event):
    drag_data["x"] = event.x
    drag_data["y"] = event.y
def on_drag(event):
    x = root.winfo_x() + event.x - drag_data["x"]
    y = root.winfo_y() + event.y - drag_data["y"]
    root.geometry(f"+{x}+{y}")

root.bind("<Button-1>", on_press)
root.bind("<B1-Motion>", on_drag)

def ocr_loop():
    """Continuously OCR the region beneath the window."""
    global CAPTURE_COUNT, LAST_TEXT
    time.sleep(1)
    while True:
        try:
            x = root.winfo_x()
            y = root.winfo_y()
            w = root.winfo_width()
            h = root.winfo_height()
            if w < 10 or h < 10:
                time.sleep(2)
                continue
            img_path = f"{TEMP_DIR}/hover.png"
            geom = f"{x},{y} {w}x{h}"
            subprocess.run(["grim", "-g", geom, img_path],
                           capture_output=True, check=True, timeout=3)
            text = clean_text(ocr_image(Path(img_path), OCR_LANG_SHORT))
            if text and len(text) > 1 and text != LAST_TEXT:
                LAST_TEXT = text
                CAPTURE_COUNT += 1
                copy_to_clipboard(text)
                log.info(f"Yomitan #{CAPTURE_COUNT}: {text[:60]}")
                root.after(0, lambda t=text: status_var.set(
                    f"#{CAPTURE_COUNT}\n{t[:50]}"))
                notify(f"Yomitan #{CAPTURE_COUNT}", text[:80], timeout=2000)
            time.sleep(2)
        except Exception as e:
            log.warning(f"Yomitan hover error: {e}")
            time.sleep(2)

threading.Thread(target=ocr_loop, daemon=True).start()
notify("Yomitan Hover", f"Active - Drag over text ({OCR_LANG_SHORT.upper()})", timeout=3000)
root.mainloop()
