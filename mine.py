"""Main mining logic - capture, OCR, translate, save, notify."""
import json, csv
import time
from datetime import datetime
from pathlib import Path
from config import MINING_DIR, AUDIO_DIR, IMAGES_DIR, VIDEO_DIR, LANG_REGISTRY
from text import clean_text, is_valid_text, is_duplicate, load_history, format_with_pronunciation, get_pronunciation
from ocr import ocr_image, ocr_long_text
from translate import translate_text, copy_to_clipboard, record_audio, notify
from capture import capture_region
from universal_log import log_capture
from log import log

ANKI_CSV = MINING_DIR / "anki_export.csv"
ANKI_FIELDS = ["Sentence", "Translation", "Pronunciation", "Audio", "Source", "Timestamp", "Language"]

def mine_sentence(ocr_lang="zh", translate_to="en", audio_duration=5, source_name="Game",
                  auto_clipboard=True, use_vad=True, push_anki=True, long_text=False) -> dict | None:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    sd = MINING_DIR / ts
    sd.mkdir(parents=True, exist_ok=True)
    for d in [AUDIO_DIR, IMAGES_DIR, VIDEO_DIR]:
        (sd / d).mkdir(exist_ok=True)
    log.info(f"Mining: {ocr_lang}->{translate_to}")
    img_path = sd / IMAGES_DIR / "capture.png"
    log.info("Select text region...")
    geom = capture_region(img_path)
    if not geom:
        notify("Mining", "Capture cancelled", timeout=2000)
        return None
    log.info(f"OCRing region: {geom}")
    if long_text:
        text = clean_text(ocr_long_text(img_path, ocr_lang))
    else:
        text = clean_text(ocr_image(img_path, ocr_lang))
    if not text or len(text) < 2:
        notify("Mining", "No text detected", timeout=3000)
        return None
    log.info(f"OCR result: {text[:60]}")
    tr = translate_text(text, src=ocr_lang, dest=translate_to)
    log.info(f"Translation: {tr[:60]}")
    pron = get_pronunciation(text, ocr_lang)
    pron_display = f"{text}\n{pron}" if pron else text
    body = f"Text: {text[:100]}"
    if pron: body += f"\n{LANG_REGISTRY.get(ocr_lang, {}).get('romaji', 'Pron')}: {pron[:100]}"
    if tr: body += f"\nTranslation: {tr[:100]}"
    notify("Sentence Captured", body, timeout=12000)
    if auto_clipboard: copy_to_clipboard(text)
    af_path = sd / f"{AUDIO_DIR}/audio_{ts}.mp3"
    log.info(f"Recording {audio_duration}s audio...")
    notify("Mining", f"Recording {audio_duration}s audio...", timeout=3000)
    audio_ok = record_audio(af_path, audio_duration)
    af = f"{AUDIO_DIR}/audio_{ts}.mp3" if audio_ok else ""
    entry = {
        "sentence": text, "translation": tr, "audio": af,
        "pronunciation": pron, "lang": ocr_lang,
        "source": source_name, "timestamp": ts,
        "screenshot": f"{IMAGES_DIR}/capture.png",
    }
    log_capture(sentence=text, translation=tr, pronunciation=pron,
                source=source_name, lang=ocr_lang, audio=af)
    with open(sd / "entry.json", "w", encoding="utf-8") as f:
        json.dump(entry, f, ensure_ascii=False, indent=2)
    sentences_json = MINING_DIR / "sentences.json"
    all_entries = []
    if sentences_json.exists():
        try:
            with open(sentences_json, "r", encoding="utf-8") as f:
                all_entries = json.load(f)
        except Exception: all_entries = []
    all_entries.append(entry)
    with open(sentences_json, "w", encoding="utf-8") as f:
        json.dump(all_entries, f, ensure_ascii=False, indent=2)
    with open(MINING_DIR / "history_sentences.txt", "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {text} | {tr}\n")
    _append_to_anki_csv(entry)
    confirm_body = f"Text: {text[:60]}\nTranslation: {tr[:60]}\nAudio: {'Yes' if audio_ok else 'No'}\nSaved: {sd.name}"
    notify("Sentence Mined", confirm_body, timeout=10000)
    log.info(f"Mining complete: {sd}")
    return entry

def _append_to_anki_csv(entry: dict):
    sentence = entry.get("sentence", "").strip()
    if not sentence: return
    if not ANKI_CSV.exists():
        with open(ANKI_CSV, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=ANKI_FIELDS, quoting=csv.QUOTE_ALL)
            writer.writeheader()
    lang = entry.get("lang", "zh")
    pron = entry.get("pronunciation", "").strip()
    if not pron: pron = get_pronunciation(sentence, lang)
    audio_path = entry.get("audio", "").strip()
    audio_tag = ""
    if audio_path and Path(audio_path).exists():
        audio_tag = f"[sound:{Path(audio_path).name}]"
    row = {
        "Sentence": sentence, "Translation": entry.get("translation", ""),
        "Pronunciation": pron, "Audio": audio_tag, "Source": entry.get("source", ""),
        "Timestamp": entry.get("timestamp", ""),
        "Language": LANG_REGISTRY.get(lang, {}).get("name", lang),
    }
    with open(ANKI_CSV, "a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=ANKI_FIELDS, quoting=csv.QUOTE_ALL)
        writer.writerow(row)
