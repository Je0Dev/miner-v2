#!/usr/bin/env python3
"""Yomitan Hover Overlay - Transparent window that OCRs text beneath it."""
import sys, time, subprocess, os, threading, unicodedata, json
from pathlib import Path
from datetime import datetime
try:
    import tkinter as tk
except ImportError:
    print("ERROR: python-tkinter required"); sys.exit(1)
sys.path.insert(0, str(Path(__file__).parent))
from ocr import ocr_image, prewarm_tesseract
from translate import copy_to_clipboard, notify, translate_text
from text import clean_text, get_pronunciation
from config import LANG_REGISTRY, MINING_DIR
from log import log

TEMP_DIR = f"{os.environ.get('XDG_RUNTIME_DIR', '/tmp')}/yomitan-hover"
os.makedirs(TEMP_DIR, exist_ok=True)
PID_FILE = f"{TEMP_DIR}/hover.pid"
CLIPBOARD_FILE = MINING_DIR / "yomitan_clipboard.json"

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

def load_clipboard_history() -> list:
    if CLIPBOARD_FILE.exists():
        try:
            with open(CLIPBOARD_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception: pass
    return []

def save_clipboard_entry(entry: dict):
    history = load_clipboard_history()
    history.append(entry)
    # Keep last 500 entries
    if len(history) > 500:
        history = history[-500:]
    with open(CLIPBOARD_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

# Create transparent floating window
root = tk.Tk()
root.title("Yomitan Hover")
root.geometry("300x40+200+200")
root.attributes("-topmost", True)
root.attributes("-alpha", 0.3)
root.configure(bg="#ffffff")
root.overrideredirect(True)

# Thin colored border
border = tk.Frame(root, bg="#00d4ff", height=3)
border.pack(fill=tk.X, side=tk.TOP)

status_var = tk.StringVar(value=f"Hover ({OCR_LANG_SHORT.upper()}) - Drag over text")
label = tk.Label(root, textvariable=status_var, bg="#000000", fg="#00ff00",
                 font=("Monospace", 9), justify=tk.LEFT, anchor=tk.W)
label.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

# Draggable
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
    text = text.replace('\ufffd', '').replace('\u200b', '').replace('\ufeff', '')
    return text.replace('\xa0', ' ').strip()

def ocr_loop():
    global CAPTURE_COUNT, LAST_TEXT
    time.sleep(1)
    while True:
        try:
            x, y, w, h = root.winfo_x(), root.winfo_y(), root.winfo_width(), root.winfo_height()
            if w < 10 or h < 10:
                time.sleep(2); continue
            # Capture area BELOW the window
            capture_y = y + h
            capture_h = max(30, h)
            img_path = f"{TEMP_DIR}/hover.png"
            geom = f"{x},{capture_y} {w}x{capture_h}"
            subprocess.run(["grim", "-g", geom, img_path], capture_output=True, check=True, timeout=3)
            text = _clean_unicode(clean_text(ocr_image(Path(img_path), OCR_LANG_SHORT)))
            if text and len(text) > 1 and text != LAST_TEXT:
                LAST_TEXT = text
                CAPTURE_COUNT += 1
                # Get translation and pronunciation
                tr = translate_text(text, src=OCR_LANG_SHORT, dest="en")
                pron = get_pronunciation(text, OCR_LANG_SHORT)
                # Build entry
                entry = {
                    "timestamp": datetime.now().isoformat(),
                    "lang": OCR_LANG_SHORT,
                    "original": text,
                    "translation": tr,
                    "pronunciation": pron,
                }
                # Save to JSON
                save_clipboard_entry(entry)
                copy_to_clipboard(text)
                log.info(f"Hover #{CAPTURE_COUNT}: {text[:60]}")
                display = text[:40] + "..." if len(text) > 40 else text
                root.after(0, lambda t=display: status_var.set(f"#{CAPTURE_COUNT}: {t}"))
            time.sleep(1.5)
        except Exception as e:
            log.warning(f"Hover error: {e}")
            time.sleep(2)

threading.Thread(target=ocr_loop, daemon=True).start()
notify("Yomitan Hover", f"Active ({OCR_LANG_SHORT.upper()}) - Scanning below window", timeout=2000)
root.mainloop()
