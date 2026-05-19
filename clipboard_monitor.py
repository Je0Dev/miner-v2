#!/usr/bin/env python3
"""Clipboard Monitor - Event-based clipboard watcher for Yomitan integration."""
import sys, time, json, subprocess, threading
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from config import MINING_DIR, LANG_REGISTRY
from text import clean_text, filter_garbage, get_pronunciation
from translate import translate_text, notify
from log import log

CLIPBOARD_FILE = MINING_DIR / "yomitan_clipboard.json"
SERVER_URL = "http://127.0.0.1:5002/api/add"

def get_clipboard() -> str:
    try:
        return subprocess.run(["wl-paste"], capture_output=True, text=True, timeout=2).stdout.strip()
    except Exception: return ""

def send_to_server(original, lang="zh", translation="", pronunciation=""):
    try:
        import urllib.request
        data = json.dumps({"original": original, "lang": lang,
            "translation": translation, "pronunciation": pronunciation, "source": "Clipboard"}).encode()
        req = urllib.request.Request(SERVER_URL, data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=2)
    except Exception: pass

def save_entry(entry: dict):
    history = []
    if CLIPBOARD_FILE.exists():
        try:
            history = json.loads(CLIPBOARD_FILE.read_text())
        except Exception: pass
    history.append(entry)
    if len(history) > 500: history = history[-500:]
    CLIPBOARD_FILE.write_text(json.dumps(history, ensure_ascii=False, indent=2))

def auto_detect_lang(text: str) -> str:
    """Auto-detect language from text content."""
    import re
    cjk = re.findall(r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]', text)
    hangul = re.findall(r'[\uac00-\ud7af]', text)
    greek = re.findall(r'[\u0370-\u03ff]', text)
    cyrillic = re.findall(r'[\u0400-\u04ff]', text)
    if cjk:
        return "ja" if re.findall(r'[\u3040-\u309f\u30a0-\u30ff]', text) else "zh"
    if hangul: return "ko"
    if greek: return "el"
    if cyrillic: return "ru"
    return "en"

def monitor_clipboard(interval=0.5, lang=None, auto_save=True):
    """Watch clipboard for changes and auto-process."""
    last = ""
    count = 0
    log.info(f"Clipboard monitor started (lang={lang or 'auto'})")
    notify("Clipboard Monitor", "Watching clipboard", timeout=2000)
    while True:
        try:
            current = get_clipboard()
            if current and current != last and len(current) >= 2:
                text = clean_text(current)
                text = filter_garbage(text, lang or auto_detect_lang(text))
                if text and len(text) >= 2:
                    detected_lang = lang or auto_detect_lang(text)
                    tr = translate_text(text, src=detected_lang, dest="en")
                    pron = get_pronunciation(text, detected_lang)
                    count += 1
                    entry = {"timestamp": datetime.now().isoformat(), "lang": detected_lang,
                             "original": text, "translation": tr, "pronunciation": pron, "source": "Clipboard"}
                    if auto_save:
                        save_entry(entry)
                        send_to_server(text, detected_lang, tr, pron)
                    log.info(f"Clipboard #{count}: {text[:60]} -> {tr[:60]}")
                    last = current
            time.sleep(interval)
        except Exception as e:
            log.warning(f"Clipboard error: {e}")
            time.sleep(interval)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("-l", "--lang", choices=LANG_REGISTRY.keys(), help="Force language")
    parser.add_argument("-i", "--interval", type=float, default=0.5, help="Check interval")
    parser.add_argument("--no-save", action="store_true", help="Don't save entries")
    args = parser.parse_args()
    monitor_clipboard(interval=args.interval, lang=args.lang, auto_save=not args.no_save)
