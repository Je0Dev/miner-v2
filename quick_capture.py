#!/usr/bin/env python3
"""Quick Capture - Instant full-screen or zone-based capture for fast NPC dialogue."""
import sys, time, subprocess, os, json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from config import MINING_DIR, AUDIO_DIR, IMAGES_DIR, LANG_REGISTRY
from ocr import ocr_image, ocr_long_text
from translate import translate_text, copy_to_clipboard, record_audio, notify
from text import clean_text, get_pronunciation, filter_garbage, is_duplicate, load_history
from text import normalize_repeating_chars, remove_line_duplicates
from text_replace import apply_text_processing
from zones import get_zone, list_zones
from universal_log import log_capture
from stats import record_mining
from log import log

ANKI_CSV = MINING_DIR / "anki_export.csv"
SERVER_URL = "http://127.0.0.1:5002/api/add"

def send_to_server(entry: dict):
    try:
        import urllib.request
        data = json.dumps({"original": entry.get("sentence", ""), "lang": entry.get("lang", "zh"),
            "translation": entry.get("translation", ""), "pronunciation": entry.get("pronunciation", ""),
            "source": entry.get("source", "Game"), "mode": "quick"}).encode()
        req = urllib.request.Request(SERVER_URL, data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=2)
    except Exception: pass

def quick_capture(ocr_lang="zh", translate_to="en", source_name="Game",
                  auto_clipboard=True, zone_name=None, long_text=False) -> dict | None:
    """Instant capture without region selection - for fast NPC dialogue."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    sd = MINING_DIR / f"quick_{ts}"
    sd.mkdir(parents=True, exist_ok=True)
    for d in [AUDIO_DIR, IMAGES_DIR]:
        (sd / d).mkdir(exist_ok=True)
    
    log.info(f"Quick capture: {ocr_lang}->{translate_to}")
    img_path = sd / IMAGES_DIR / "capture.png"
    
    # Determine capture geometry
    geom = None
    if zone_name:
        zone = get_zone(zone_name)
        if zone:
            geom = zone["geom"]
            ocr_lang = zone.get("lang", ocr_lang)
            log.info(f"Using zone: {zone_name}")
    
    # Capture screen
    try:
        if geom:
            subprocess.run(["grim", "-g", geom, str(img_path)], check=True, timeout=5)
        else:
            # Full screen capture
            subprocess.run(["grim", str(img_path)], check=True, timeout=5)
    except Exception as e:
        notify("Quick Capture", f"Capture failed: {e}", timeout=2000)
        return None
    
    # OCR
    if long_text:
        text = clean_text(ocr_long_text(img_path, ocr_lang))
    else:
        text = clean_text(ocr_image(img_path, ocr_lang))
    # Apply garbage filtering and text processing
    text = filter_garbage(text, ocr_lang)
    text = normalize_repeating_chars(text)
    text = remove_line_duplicates(text)
    text = apply_text_processing(text)
    
    if not text or len(text) < 2:
        notify("Quick Capture", "No text detected", timeout=2000)
        return None
    
    # Duplicate check
    history = load_history()
    if is_duplicate(text, history):
        notify("Quick Capture", "Duplicate detected", timeout=2000)
        return None
    
    log.info(f"OCR: {text[:60]}")
    
    # Translate
    tr = translate_text(text, src=ocr_lang, dest=translate_to)
    pron = get_pronunciation(text, ocr_lang)
    
    # Show notification immediately
    body = f"Text: {text[:100]}"
    if pron: body += f"\n{pron[:100]}"
    if tr: body += f"\nTranslation: {tr[:100]}"
    notify("Quick Capture", body, timeout=8000)
    
    if auto_clipboard:
        copy_to_clipboard(text)
    
    # Save entry
    words = []
    try:
        import jieba
        for w in jieba.lcut(text):
            w = w.strip()
            if w: words.append({"word": w, "pinyin": get_pronunciation(w, ocr_lang)})
    except Exception: pass
    
    entry = {
        "sentence": text, "translation": tr, "audio": "",
        "pronunciation": pron, "lang": ocr_lang,
        "source": source_name, "timestamp": ts,
        "screenshot": f"{IMAGES_DIR}/capture.png",
        "mode": "quick", "words": words, "tags": [], "character": ""
    }
    
    log_capture(sentence=text, translation=tr, pronunciation=pron,
                source=source_name, lang=ocr_lang)
    
    with open(sd / "entry.json", "w", encoding="utf-8") as f:
        json.dump(entry, f, ensure_ascii=False, indent=2)
    
    # Append to sentences.json
    sentences_json = MINING_DIR / "sentences.json"
    all_entries = []
    if sentences_json.exists():
        try:
            with open(sentences_json, "r", encoding="utf-8") as f:
                all_entries = json.load(f)
        except Exception: pass
    all_entries.append(entry)
    with open(sentences_json, "w", encoding="utf-8") as f:
        json.dump(all_entries, f, ensure_ascii=False, indent=2)
    
    # Record stats
    record_mining(ocr_lang, success=True, ocr_confidence=0, translation_ok=bool(tr))
    
    # Send to sentence server
    send_to_server(entry)
    
    log.info(f"Quick capture complete: {sd}")
    return entry

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("-l", "--lang", default="zh", choices=LANG_REGISTRY.keys())
    parser.add_argument("-t", "--translate-to", default="en")
    parser.add_argument("-s", "--source", default="Game")
    parser.add_argument("--zone", help="Use saved zone")
    parser.add_argument("--long-text", action="store_true")
    args = parser.parse_args()
    
    quick_capture(ocr_lang=args.lang, translate_to=args.translate_to,
                  source_name=args.source, zone_name=args.zone,
                  long_text=args.long_text)
