#!/usr/bin/env python3
"""Yomitan Hover Overlay - Resizable transparent window that OCRs and translates text."""
import sys, time, subprocess, os, threading, unicodedata, json, re
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
    if len(history) > 500:
        history = history[-500:]
    with open(CLIPBOARD_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def clean_display_text(text: str) -> str:
    """Remove ALL unicode garbage, keep only clean readable text."""
    if not text: return ""
    # Remove zero-width, BOM, replacement chars
    text = text.replace('\ufffd', '').replace('\u200b', '').replace('\ufeff', '')
    text = text.replace('\u200c', '').replace('\u200d', '').replace('\u00a0', ' ')
    # Remove ALL symbols and punctuation except basic ones
    # Keep: letters, digits, spaces, basic punctuation (.!?,;:'"-)
    cleaned = []
    for c in text:
        cat = unicodedata.category(c)
        # Keep letters (L), numbers (N), spaces (Zs), basic punctuation
        if cat.startswith('L') or cat.startswith('N') or cat == 'Zs':
            cleaned.append(c)
        elif c in '.!?,;:\'"()- ':
            cleaned.append(c)
    text = ''.join(cleaned)
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text

# Create window - keep on top, semi-transparent, resizable
root = tk.Tk()
root.title("Yomitan Hover")
root.geometry("400x80+200+200")
root.minsize(200, 40)
root.attributes("-topmost", True)
root.attributes("-alpha", 0.75)
root.configure(bg="#1a1a1a")
root.resizable(True, True)

# Top accent bar
top_bar = tk.Frame(root, bg="#00d4ff", height=2)
top_bar.pack(fill=tk.X, side=tk.TOP)

# Display variables
orig_var = tk.StringVar(value="")
trans_var = tk.StringVar(value=f"Hover ({OCR_LANG_SHORT.upper()}) - drag over text")

# Original text line
orig_label = tk.Label(root, textvariable=orig_var, bg="#1a1a1a", fg="#ffffff",
                      font=("Sans", 11), justify=tk.LEFT, anchor=tk.W)
orig_label.pack(fill=tk.X, padx=8, pady=(6, 2))

# Translation line
trans_label = tk.Label(root, textvariable=trans_var, bg="#1a1a1a", fg="#ffdd57",
                       font=("Sans", 12, "bold"), justify=tk.LEFT, anchor=tk.W)
trans_label.pack(fill=tk.X, padx=8, pady=(0, 6))

# Bottom accent bar
bottom_bar = tk.Frame(root, bg="#00d4ff", height=2)
bottom_bar.pack(fill=tk.X, side=tk.BOTTOM)

# Draggable - always raise window
drag_data = {"x": 0, "y": 0}
def on_press(event):
    drag_data["x"] = event.x
    drag_data["y"] = event.y
    root.lift()  # Bring to front
def on_drag(event):
    x = root.winfo_x() + event.x - drag_data["x"]
    y = root.winfo_y() + event.y - drag_data["y"]
    root.geometry(f"+{x}+{y}")
    root.lift()  # Keep in front while dragging
root.bind("<Button-1>", on_press)
root.bind("<B1-Motion>", on_drag)
# Also raise on any click
root.bind("<Enter>", lambda e: root.lift())

def ocr_loop():
    global CAPTURE_COUNT, LAST_TEXT
    stable_count = 0
    time.sleep(1)
    while True:
        try:
            x, y, w, h = root.winfo_x(), root.winfo_y(), root.winfo_width(), root.winfo_height()
            if w < 10 or h < 10:
                time.sleep(2); continue
            # Capture area BELOW the window (offset by window height)
            capture_y = y + h
            capture_h = max(40, h)
            img_path = f"{TEMP_DIR}/hover.png"
            geom = f"{x},{capture_y} {w}x{capture_h}"
            subprocess.run(["grim", "-g", geom, img_path], capture_output=True, check=True, timeout=3)
            raw_text = ocr_image(Path(img_path), OCR_LANG_SHORT)
            text = clean_display_text(clean_text(raw_text))
            # Only update if text is different and stable (seen 2+ times)
            if text and len(text) > 1:
                if text == LAST_TEXT:
                    stable_count += 1
                else:
                    stable_count = 0
                    LAST_TEXT = text
                    continue
                # Only process after seeing same text twice (reduces flicker)
                if stable_count >= 1:
                    CAPTURE_COUNT += 1
                    # Get translation (async to not block)
                    tr = translate_text(text, src=OCR_LANG_SHORT, dest="en")
                    pron = get_pronunciation(text, OCR_LANG_SHORT)
                    # Clean display text
                    orig_display = clean_display_text(text)
                    trans_display = clean_display_text(tr) if tr else ""
                    if pron:
                        pron_clean = clean_display_text(pron)
                        trans_display = f"{trans_display} | {pron_clean}"
                    # Update UI
                    root.after(0, lambda o=orig_display, t=trans_display: (
                        orig_var.set(o),
                        trans_var.set(t) if t else trans_var.set("")
                    ))
                    # Save entry
                    entry = {
                        "timestamp": datetime.now().isoformat(),
                        "lang": OCR_LANG_SHORT,
                        "original": text,
                        "translation": tr,
                        "pronunciation": pron,
                    }
                    save_clipboard_entry(entry)
                    copy_to_clipboard(text)
                    log.info(f"Hover #{CAPTURE_COUNT}: {text[:60]} -> {tr[:60]}")
            time.sleep(1.5)
        except Exception as e:
            log.warning(f"Hover error: {e}")
            time.sleep(2)

threading.Thread(target=ocr_loop, daemon=True).start()
notify("Yomitan Hover", f"Active ({OCR_LANG_SHORT.upper()})", timeout=2000)
root.mainloop()
