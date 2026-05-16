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

OCR_LANG = sys.argv[1] if len(sys.argv) > 1 else "chi_sim"
CAPTURE_COUNT = 0
LAST_TEXT = ""

def ocr_region(x, y, w, h, lang):
    """Capture and OCR a region at given coordinates."""
    img = f"{TEMP_DIR}/hover.png"
    geom = f"{x},{y} {w}x{h}"
    try:
        subprocess.run(["grim", "-g", geom, img], capture_output=True, check=True, timeout=3)
        result = subprocess.run(["tesseract", img, "-", "-l", lang],
                                capture_output=True, text=True, timeout=5)
        text = result.stdout.strip()
        text = " ".join(text.split())
        return text
    except Exception:
        return ""

def notify(title, body, timeout=2000):
    try:
        subprocess.run(["notify-send", "-t", str(timeout), "--", title, body], capture_output=True)
    except Exception:
        pass

def copy_to_clipboard(text):
    try:
        subprocess.run(["wl-copy"], input=text, text=True, capture_output=True, timeout=2)
    except Exception:
        pass

# Create small floating window
root = tk.Tk()
root.title("Yomitan Hover")
root.geometry("250x60+200+200")
# Don't use -type splash as it can make window non-interactive
root.attributes("-topmost", True)
root.attributes("-alpha", 0.85)
root.configure(bg="#1a1a2e")
root.overrideredirect(True)

# UI elements
label = tk.Label(root, text=f"Yomitan Hover ({OCR_LANG})\nDrag over text to OCR",
                 bg="#1a1a2e", fg="#ffdd57", font=("Sans", 9), justify=tk.CENTER)
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
    time.sleep(1)  # Give window time to appear
    while True:
        try:
            x = root.winfo_x()
            y = root.winfo_y()
            w = root.winfo_width()
            h = root.winfo_height()
            text = ocr_region(x, y, w, h, OCR_LANG)
            if text and len(text) > 1 and text != LAST_TEXT:
                LAST_TEXT = text
                CAPTURE_COUNT += 1
                copy_to_clipboard(text)
                root.after(0, lambda t=text: label.config(
                    text=f"#{CAPTURE_COUNT}\n{t[:50]}", fg="#88ff88"))
                notify(f"Yomitan #{CAPTURE_COUNT}", text[:100], timeout=2000)
            time.sleep(2)
        except Exception:
            time.sleep(2)

# Start OCR loop in background
threading.Thread(target=ocr_loop, daemon=True).start()

notify("Yomitan Hover", f"Active - Drag window over text ({OCR_LANG})", timeout=3000)
root.mainloop()
