#!/usr/bin/env python3
"""Yomitan Hover Overlay - Semi-transparent window that OCRs the area it covers."""
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
SERVER_URL = "http://127.0.0.1:5002/api/add"

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
    SCRIPT_TYPE = LANG_REGISTRY[OCR_LANG_SHORT]["script"]
else:
    OCR_LANG_TESS = OCR_LANG_SHORT
    OCR_LANG_SHORT = "zh"
    SCRIPT_TYPE = "cjk"

VALID_CHARS = {
    "cjk": re.compile(r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af]'),
    "latin": re.compile(r'[\u0041-\u007a\u00c0-\u024f]'),
    "greek": re.compile(r'[\u0370-\u03ff]'),
    "cyrillic": re.compile(r'[\u0400-\u04ff]'),
}
CHAR_PATTERN = VALID_CHARS.get(SCRIPT_TYPE, VALID_CHARS["cjk"])

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

def send_to_server(original, lang, translation="", pronunciation=""):
    try:
        import urllib.request
        data = json.dumps({"original": original, "lang": lang,
            "translation": translation, "pronunciation": pronunciation, "source": "Hover"}).encode()
        req = urllib.request.Request(SERVER_URL, data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=2)
    except Exception: pass

def clean_for_display(text: str) -> str:
    if not text: return ""
    text = text.replace('\ufffd', '').replace('\u200b', '').replace('\ufeff', '')
    text = ''.join(c for c in text if unicodedata.category(c)[0] != 'C' or c in '\n\t')
    # Remove UI symbols, circled numbers, dingbats, math, arrows
    text = re.sub(r'[\u2460-\u24ff\u2600-\u26ff\u2700-\u27bf\u3000-\u303f\uff00-\uffef\u2000-\u206f\u20a0-\u20cf\u2100-\u214f\u2190-\u21ff\u2200-\u22ff\u2300-\u23ff\u25a0-\u25ff\u2e80-\u2eff\u3100-\u312f\u3200-\u32ff]', '', text)
    text = re.sub(r'[©®™℗℠]', '', text)
    chars = CHAR_PATTERN.findall(text)
    punct = re.findall(r'[。！？.!?、，,;:…—\-\'"()\[\]]', text)
    text = ''.join(chars + punct)
    return re.sub(r'\s+', ' ', text).strip()

def clean_english(text: str) -> str:
    if not text: return ""
    return ''.join(c for c in text if ord(c) < 128 or c == ' ')

# Create semi-transparent overlay - labels visible, background see-through
root = tk.Tk()
root.title("Yomitan Hover")
root.geometry("300x45+200+200")
root.minsize(150, 30)
root.maxsize(800, 150)
root.attributes("-topmost", True)
root.attributes("-alpha", 0.85)  # Semi-transparent - see game text through it
root.configure(bg="#000000")
root.resizable(True, True)

# Make window background transparent but keep labels opaque
root.wm_attributes("-transparentcolor", "#000000")

orig_var = tk.StringVar(value="")
trans_var = tk.StringVar(value=f"Hover ({OCR_LANG_SHORT.upper()})")

# Labels with visible background so text is readable
orig_label = tk.Label(root, textvariable=orig_var, bg="#1a1a2e", fg="#00ff88",
                      font=("Sans", 10), justify=tk.LEFT, anchor=tk.W, padx=4, pady=2)
orig_label.pack(fill=tk.X, padx=2, pady=(2, 0))

trans_label = tk.Label(root, textvariable=trans_var, bg="#1a1a2e", fg="#ffdd57",
                       font=("Sans", 11, "bold"), justify=tk.LEFT, anchor=tk.W, padx=4, pady=2)
trans_label.pack(fill=tk.X, padx=2, pady=(0, 2))

# Draggable
drag_data = {"x": 0, "y": 0}
def on_press(event):
    drag_data["x"] = event.x; drag_data["y"] = event.y
    root.lift()
def on_drag(event):
    x = root.winfo_x() + event.x - drag_data["x"]
    y = root.winfo_y() + event.y - drag_data["y"]
    root.geometry(f"+{x}+{y}")
    root.lift()
root.bind("<Button-1>", on_press)
root.bind("<B1-Motion>", on_drag)
root.bind("<Enter>", lambda e: root.lift())

def capture_and_ocr():
    """Hide window briefly, capture, OCR, show again."""
    root.withdraw()
    time.sleep(0.08)
    try:
        x, y, w, h = root.winfo_x(), root.winfo_y(), root.winfo_width(), root.winfo_height()
        img_path = f"{TEMP_DIR}/hover.png"
        geom = f"{x},{y} {w}x{h}"
        subprocess.run(["grim", "-g", geom, img_path], capture_output=True, check=True, timeout=3)
    except Exception:
        root.deiconify()
        return None
    root.deiconify()
    if not os.path.exists(img_path):
        return None
    raw_text = ocr_image(Path(img_path), OCR_LANG_SHORT)
    return clean_for_display(clean_text(raw_text))

def ocr_loop():
    global CAPTURE_COUNT, LAST_TEXT
    stable_count = 0
    time.sleep(0.5)
    while True:
        try:
            text = capture_and_ocr()
            if not text:
                time.sleep(0.5); continue
            valid_count = len(CHAR_PATTERN.findall(text))
            if valid_count < 2 or len(text) < 2:
                time.sleep(0.5); continue
            if text != LAST_TEXT:
                LAST_TEXT = text
                stable_count = 0
                time.sleep(0.3); continue
            stable_count += 1
            if stable_count >= 2:
                CAPTURE_COUNT += 1
                root.after(0, lambda t=text[:80]: orig_var.set(t))
                tr = translate_text(text, src=OCR_LANG_SHORT, dest="en")
                pron = get_pronunciation(text, OCR_LANG_SHORT)
                tr_clean = clean_english(tr)
                pron_clean = clean_english(pron)
                display = tr_clean[:100] if tr_clean else "(no translation)"
                if pron_clean: display += f" | {pron_clean[:30]}"
                root.after(0, lambda d=display: trans_var.set(d))
                entry = {"timestamp": datetime.now().isoformat(), "lang": OCR_LANG_SHORT,
                         "original": text, "translation": tr_clean, "pronunciation": pron_clean}
                save_clipboard_entry(entry)
                send_to_server(text, OCR_LANG_SHORT, tr_clean, pron_clean)
                copy_to_clipboard(text)
                log.info(f"Hover #{CAPTURE_COUNT}: {text[:60]} -> {tr_clean[:60]}")
                stable_count = 0
            time.sleep(0.5)
        except Exception as e:
            log.warning(f"Hover error: {e}")
            time.sleep(0.5)

threading.Thread(target=ocr_loop, daemon=True).start()
notify("Yomitan Hover", f"Active ({OCR_LANG_SHORT.upper()})", timeout=2000)
root.mainloop()
