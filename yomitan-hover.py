#!/usr/bin/env python3
"""Yomitan Hover Overlay - Small draggable window that OCRs continuously (multi-language)."""
import sys, time, subprocess, os, threading, unicodedata
from pathlib import Path
try:
    import tkinter as tk
except ImportError:
    print("ERROR: python-tkinter required"); sys.exit(1)
sys.path.insert(0, str(Path(__file__).parent))
from ocr import ocr_image, prewarm_tesseract
from translate import copy_to_clipboard, notify
from text import clean_text
from config import LANG_REGISTRY
from log import log

TEMP_DIR = f"{os.environ.get('XDG_RUNTIME_DIR', '/tmp')}/yomitan-hover"
os.makedirs(TEMP_DIR, exist_ok=True)
PID_FILE = f"{TEMP_DIR}/hover.pid"
if os.path.exists(PID_FILE):
    try:
        with open(PID_FILE) as f: old_pid = int(f.read().strip())
        os.kill(old_pid, 9)
    except Exception: pass
    os.remove(PID_FILE)
with open(PID_FILE, "w") as f: f.write(str(os.getpid()))

OCR_LANG_SHORT = sys.argv[1] if len(sys.argv) > 1 else "zh"
if OCR_LANG_SHORT in LANG_REGISTRY:
    OCR_LANG_TESS = LANG_REGISTRY[OCR_LANG_SHORT]["tess"]
else:
    OCR_LANG_TESS = OCR_LANG_SHORT
    OCR_LANG_SHORT = "zh"
CAPTURE_COUNT = 0
LAST_TEXT = ""
prewarm_tesseract(OCR_LANG_TESS)

root = tk.Tk()
root.title("Yomitan Hover")
root.geometry("250x80+200+200")
root.attributes("-topmost", True)
root.attributes("-alpha", 0.90)
root.configure(bg="#1a1a2e")
status_var = tk.StringVar(value=f"Yomitan Hover ({OCR_LANG_SHORT.upper()})\nDrag over text")
label = tk.Label(root, textvariable=status_var, bg="#1a1a2e", fg="#ffdd57",
                 font=("Sans", 10), justify=tk.CENTER)
label.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
drag_data = {"x": 0, "y": 0}
def on_press(event): drag_data["x"] = event.x; drag_data["y"] = event.y
def on_drag(event):
    x = root.winfo_x() + event.x - drag_data["x"]
    y = root.winfo_y() + event.y - drag_data["y"]
    root.geometry(f"+{x}+{y}")
root.bind("<Button-1>", on_press)
root.bind("<B1-Motion>", on_drag)

def _clean_unicode(text: str) -> str:
    text = unicodedata.normalize('NFC', text)
    text = text.replace('\ufffd', '').replace('\u200b', '')
    text = text.replace('\xa0', ' ').strip()
    return text

def ocr_loop():
    global CAPTURE_COUNT, LAST_TEXT
    time.sleep(1)
    while True:
        try:
            x, y, w, h = root.winfo_x(), root.winfo_y(), root.winfo_width(), root.winfo_height()
            if w < 10 or h < 10:
                time.sleep(2); continue
            img_path = f"{TEMP_DIR}/hover.png"
            geom = f"{x},{y} {w}x{h}"
            subprocess.run(["grim", "-g", geom, img_path], capture_output=True, check=True, timeout=3)
            text = _clean_unicode(clean_text(ocr_image(Path(img_path), OCR_LANG_SHORT)))
            if text and len(text) > 1 and text != LAST_TEXT:
                LAST_TEXT = text
                CAPTURE_COUNT += 1
                copy_to_clipboard(text)
                log.info(f"Hover #{CAPTURE_COUNT}: {text[:60]}")
                root.after(0, lambda t=text: status_var.set(f"#{CAPTURE_COUNT}\n{t[:50]}"))
            time.sleep(2)
        except Exception as e:
            log.warning(f"Hover error: {e}")
            time.sleep(2)

threading.Thread(target=ocr_loop, daemon=True).start()
notify("Yomitan Hover", f"Active - Drag over text ({OCR_LANG_SHORT.upper()})", timeout=3000)
root.mainloop()
