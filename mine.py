"""Main mining logic - capture, OCR, translate, save, notify."""
import json, csv, time
from datetime import datetime
from pathlib import Path
from config import MINING_DIR, AUDIO_DIR, IMAGES_DIR, VIDEO_DIR, LANG_REGISTRY
from text import clean_text, is_valid_text, is_duplicate, load_history, format_with_pronunciation, get_pronunciation
from ocr import ocr_image, ocr_long_text
from translate import translate_text, copy_to_clipboard, record_audio, notify
from capture import capture_region
from zones import get_zone, list_zones
from universal_log import log_capture
from log import log

ANKI_CSV = MINING_DIR / "anki_export.csv"
ANKI_FIELDS = ["Sentence", "Translation", "Pronunciation", "Audio", "Source", "Timestamp", "Language"]

def _safe_ocr(image_path: Path, lang: str, long_text: bool) -> str:
    """OCR with graceful error recovery."""
    try:
        if long_text:
            return clean_text(ocr_long_text(image_path, lang))
        return clean_text(ocr_image(image_path, lang))
    except Exception as e:
        log.error(f"OCR error: {e}")
        return ""

def _safe_translate(text: str, src: str, dest: str) -> str:
    """Translate with graceful error recovery."""
    try:
        return translate_text(text, src=src, dest=dest)
    except Exception as e:
        log.error(f"Translation error: {e}")
        return ""

def mine_sentence(ocr_lang="zh", translate_to="en", audio_duration=5, source_name="Game",
                  auto_clipboard=True, use_vad=True, push_anki=True, long_text=False,
                  zone_name: str = None) -> dict | None:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    sd = MINING_DIR / ts
    sd.mkdir(parents=True, exist_ok=True)
    for d in [AUDIO_DIR, IMAGES_DIR, VIDEO_DIR]:
        (sd / d).mkdir(exist_ok=True)
    log.info(f"Mining: {ocr_lang}->{translate_to}")
    img_path = sd / IMAGES_DIR / "capture.png"
    log.info("Select text region...")
    geom = None
    if zone_name:
        zone = get_zone(zone_name)
        if zone:
            geom = zone["geom"]
            ocr_lang = zone.get("lang", ocr_lang)
            log.info(f"Using zone: {zone_name}")
    geom = capture_region(img_path, geom)
    if not geom:
        notify("Mining", "Capture cancelled", timeout=2000)
        return None
    text = _safe_ocr(img_path, ocr_lang, long_text)
    if not text or len(text) < 2:
        notify("Mining", "No text detected", timeout=2000)
        return None
    log.info(f"OCR result: {text[:60]}")
    tr = _safe_translate(text, ocr_lang, translate_to)
    log.info(f"Translation: {tr[:60]}")
    pron = get_pronunciation(text, ocr_lang)
    body = f"Text: {text[:100]}"
    if pron: body += f"\n{LANG_REGISTRY.get(ocr_lang, {}).get('romaji', 'Pron')}: {pron[:100]}"
    if tr: body += f"\nTranslation: {tr[:100]}"
    notify("Sentence Captured", body, timeout=12000)
    if auto_clipboard: copy_to_clipboard(text)
    af_path = sd / f"{AUDIO_DIR}/audio_{ts}.mp3"
    log.info(f"Recording {audio_duration}s audio...")
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

def mine_multi_region(ocr_lang="zh", translate_to="en", audio_duration=5, source_name="Game",
                      auto_clipboard=True, long_text=False, zones: list[str] = None) -> dict | None:
    """Capture and OCR multiple regions, combine results."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    sd = MINING_DIR / ts
    sd.mkdir(parents=True, exist_ok=True)
    for d in [AUDIO_DIR, IMAGES_DIR, VIDEO_DIR]:
        (sd / d).mkdir(exist_ok=True)
    all_text = []
    if zones:
        for i, zone_name in enumerate(zones):
            zone = get_zone(zone_name)
            if not zone:
                log.warning(f"Zone not found: {zone_name}")
                continue
            img_path = sd / IMAGES_DIR / f"capture_{i}.png"
            geom = capture_region(img_path, zone["geom"])
            if not geom: continue
            text = _safe_ocr(img_path, ocr_lang, long_text)
            if text and len(text) >= 2:
                all_text.append(text)
    else:
        img_path = sd / IMAGES_DIR / "capture.png"
        geom = capture_region(img_path)
        if not geom:
            notify("Mining", "Capture cancelled", timeout=2000)
            return None
        text = _safe_ocr(img_path, ocr_lang, long_text)
        if text and len(text) >= 2:
            all_text.append(text)
    if not all_text:
        notify("Mining", "No text detected", timeout=2000)
        return None
    combined = "\n".join(all_text)
    tr = _safe_translate(combined, ocr_lang, translate_to)
    pron = get_pronunciation(combined, ocr_lang)
    body = f"Text: {combined[:100]}"
    if pron: body += f"\n{LANG_REGISTRY.get(ocr_lang, {}).get('romaji', 'Pron')}: {pron[:100]}"
    if tr: body += f"\nTranslation: {tr[:100]}"
    notify("Sentence Captured", body, timeout=12000)
    if auto_clipboard: copy_to_clipboard(combined)
    af_path = sd / f"{AUDIO_DIR}/audio_{ts}.mp3"
    audio_ok = record_audio(af_path, audio_duration)
    af = f"{AUDIO_DIR}/audio_{ts}.mp3" if audio_ok else ""
    entry = {
        "sentence": combined, "translation": tr, "audio": af,
        "pronunciation": pron, "lang": ocr_lang,
        "source": source_name, "timestamp": ts,
        "screenshot": f"{IMAGES_DIR}/capture.png",
    }
    log_capture(sentence=combined, translation=tr, pronunciation=pron,
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
        f.write(f"[{ts}] {combined} | {tr}\n")
    _append_to_anki_csv(entry)
    notify("Sentence Mined", f"Text: {combined[:60]}\nSaved: {sd.name}", timeout=10000)
    log.info(f"Multi-region mining complete: {sd}")
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
