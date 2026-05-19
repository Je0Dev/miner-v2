"""Main mining logic - capture, OCR, translate, save, notify."""
import json, csv, time
from datetime import datetime
from pathlib import Path
from config import MINING_DIR, AUDIO_DIR, IMAGES_DIR, VIDEO_DIR, LANG_REGISTRY
from text import (clean_text, is_valid_text, is_duplicate, load_history,
                  get_pronunciation, split_sentences, get_word_breakdown, filter_garbage,
                  normalize_repeating_chars, remove_line_duplicates)
from text_replace import apply_text_processing
from compare import compare_ocr_results
from ocr import ocr_image, ocr_long_text
from translate import translate_text, copy_to_clipboard, record_audio, notify
from capture import capture_region
from zones import get_zone, list_zones
from universal_log import log_capture
from log import log

ANKI_CSV = MINING_DIR / "anki_export.csv"
ANKI_FIELDS = ["Sentence", "Translation", "Pronunciation", "Audio", "Source", "Timestamp", "Language", "WordBreakdown"]
SERVER_URL = "http://127.0.0.1:5002/api/add"

def send_to_server(entry: dict):
    try:
        import urllib.request
        data = json.dumps({"original": entry.get("sentence", ""), "lang": entry.get("lang", "zh"),
            "translation": entry.get("translation", ""), "pronunciation": entry.get("pronunciation", ""),
            "source": entry.get("source", "Game"), "mode": "normal"}).encode()
        req = urllib.request.Request(SERVER_URL, data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=2)
    except Exception: pass

def _save_entry(entry: dict, sd: Path, ts: str):
    with open(sd / "entry.json", "w", encoding="utf-8") as f:
        json.dump(entry, f, ensure_ascii=False, indent=2)
    sj = MINING_DIR / "sentences.json"
    all_e = json.loads(sj.read_text()) if sj.exists() else []
    all_e.append(entry)
    sj.write_text(json.dumps(all_e, ensure_ascii=False, indent=2))
    with open(MINING_DIR / "history_sentences.txt", "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {entry['sentence']} | {entry.get('translation', '')}\n")

def _mine_single(text: str, ocr_lang: str, translate_to: str, source_name: str,
                 audio_duration: int, ts: str, sd: Path, af: str, split: bool = False) -> list[dict]:
    """Mine a single text block, optionally splitting into sentences."""
    sentences = split_sentences(text) if split else [text]
    entries = []
    for sent in sentences:
        if len(sent) < 2: continue
        tr = translate_text(sent, src=ocr_lang, dest=translate_to)
        pron = get_pronunciation(sent, ocr_lang)
        words = get_word_breakdown(sent, ocr_lang)
        entry = {"sentence": sent, "translation": tr, "audio": af, "pronunciation": pron,
                 "lang": ocr_lang, "source": source_name, "timestamp": ts,
                 "screenshot": f"{IMAGES_DIR}/capture.png",
                 "words": words, "tags": [], "character": ""}
        entries.append(entry)
    return entries

def mine_sentence(ocr_lang="zh", translate_to="en", audio_duration=5, source_name="Game",
                  auto_clipboard=True, push_anki=True, long_text=False,
                  zone_name: str = None, split_sentences_flag: bool = True) -> list[dict]:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    sd = MINING_DIR / ts
    sd.mkdir(parents=True, exist_ok=True)
    for d in [AUDIO_DIR, IMAGES_DIR, VIDEO_DIR]: (sd / d).mkdir(exist_ok=True)
    geom = None
    if zone_name:
        zone = get_zone(zone_name)
        if zone: geom, ocr_lang = zone["geom"], zone.get("lang", ocr_lang)
    img_path = sd / IMAGES_DIR / "capture.png"
    geom = capture_region(img_path, geom)
    if not geom:
        notify("Mining", "Capture cancelled", timeout=2000); return []
    text = clean_text(ocr_long_text(img_path, ocr_lang) if long_text else ocr_image(img_path, ocr_lang))
    text = filter_garbage(text, ocr_lang)
    text = normalize_repeating_chars(text)
    text = remove_line_duplicates(text)
    text = apply_text_processing(text)
    if not is_valid_text(text):
        notify("Mining", "No text detected", timeout=2000); return []
    # Check duplicates with GSM's advanced comparison
    history = load_history()
    if is_duplicate(text, history) or any(compare_ocr_results(text, old, threshold=85) for old in history[-50:]):
        notify("Mining", "Duplicate detected", timeout=2000); return []
    log.info(f"Mining: {text[:60]}")
    af_path = sd / f"{AUDIO_DIR}/audio_{ts}.mp3"
    audio_ok = record_audio(af_path, audio_duration)
    af = f"{AUDIO_DIR}/audio_{ts}.mp3" if audio_ok else ""
    entries = _mine_single(text, ocr_lang, translate_to, source_name, audio_duration, ts, sd, af, split_sentences_flag)
    if not entries: return []
    for entry in entries:
        _save_entry(entry, sd, ts)
        log_capture(sentence=entry["sentence"], translation=entry.get("translation", ""),
                    pronunciation=entry.get("pronunciation", ""), source=source_name,
                    lang=ocr_lang, audio=af)
        _append_to_anki_csv(entry)
        send_to_server(entry)
    if auto_clipboard: copy_to_clipboard(entries[0]["sentence"])
    body = f"Text: {entries[0]['sentence'][:60]}\nTranslation: {entries[0].get('translation', '')[:60]}\nSentences: {len(entries)}"
    notify("Sentence Mined", body, timeout=10000)
    return entries

def mine_multi_region(ocr_lang="zh", translate_to="en", audio_duration=5, source_name="Game",
                      auto_clipboard=True, long_text=False, zones: list[str] = None) -> list[dict]:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    sd = MINING_DIR / ts
    sd.mkdir(parents=True, exist_ok=True)
    for d in [AUDIO_DIR, IMAGES_DIR, VIDEO_DIR]: (sd / d).mkdir(exist_ok=True)
    all_text = []
    if zones:
        for i, zn in enumerate(zones):
            zone = get_zone(zn)
            if not zone: continue
            img_path = sd / IMAGES_DIR / f"capture_{i}.png"
            geom = capture_region(img_path, zone["geom"])
            if not geom: continue
            text = clean_text(ocr_long_text(img_path, ocr_lang) if long_text else ocr_image(img_path, ocr_lang))
            text = filter_garbage(text, ocr_lang)
            text = normalize_repeating_chars(text)
            text = apply_text_processing(text)
            if is_valid_text(text): all_text.append(text)
    else:
        img_path = sd / IMAGES_DIR / "capture.png"
        geom = capture_region(img_path)
        if not geom: notify("Mining", "Capture cancelled", timeout=2000); return []
        text = clean_text(ocr_long_text(img_path, ocr_lang) if long_text else ocr_image(img_path, ocr_lang))
        text = filter_garbage(text, ocr_lang)
        text = normalize_repeating_chars(text)
        text = apply_text_processing(text)
        if is_valid_text(text): all_text.append(text)
    if not all_text: notify("Mining", "No text detected", timeout=2000); return []
    combined = "\n".join(all_text)
    af_path = sd / f"{AUDIO_DIR}/audio_{ts}.mp3"
    audio_ok = record_audio(af_path, audio_duration)
    af = f"{AUDIO_DIR}/audio_{ts}.mp3" if audio_ok else ""
    entries = _mine_single(combined, ocr_lang, translate_to, source_name, audio_duration, ts, sd, af, True)
    for entry in entries:
        _save_entry(entry, sd, ts)
        _append_to_anki_csv(entry)
        send_to_server(entry)
    if auto_clipboard: copy_to_clipboard(entries[0]["sentence"])
    notify("Sentence Mined", f"Text: {entries[0]['sentence'][:60]}\nSaved: {sd.name}", timeout=10000)
    return entries

def _append_to_anki_csv(entry: dict):
    sentence = entry.get("sentence", "").strip()
    if not sentence: return
    if not ANKI_CSV.exists():
        with open(ANKI_CSV, "w", encoding="utf-8-sig", newline="") as f:
            csv.DictWriter(f, fieldnames=ANKI_FIELDS, quoting=csv.QUOTE_ALL).writeheader()
    lang = entry.get("lang", "zh")
    pron = entry.get("pronunciation", "") or get_pronunciation(sentence, lang)
    audio_path = entry.get("audio", "")
    audio_tag = f"[sound:{Path(audio_path).name}]" if audio_path and Path(audio_path).exists() else ""
    words = entry.get("words", [])
    word_breakdown = " | ".join(f"{w['word']}→{w.get('pinyin', w.get('romaji', ''))}" for w in words if w.get("word"))
    row = {"Sentence": sentence, "Translation": entry.get("translation", ""), "Pronunciation": pron,
           "Audio": audio_tag, "Source": entry.get("source", ""), "Timestamp": entry.get("timestamp", ""),
           "Language": LANG_REGISTRY.get(lang, {}).get("name", lang), "WordBreakdown": word_breakdown}
    with open(ANKI_CSV, "a", encoding="utf-8-sig", newline="") as f:
        csv.DictWriter(f, fieldnames=ANKI_FIELDS, quoting=csv.QUOTE_ALL).writerow(row)
