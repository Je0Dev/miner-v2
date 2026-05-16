"""Anki CSV export for Game Sentence Miner v2 - multi-language support."""
import csv, json
from pathlib import Path
from config import MINING_DIR, SENTENCES_FILE, LANG_REGISTRY
from text import get_pronunciation
from log import log

ANKI_CSV = MINING_DIR / "anki_export.csv"
ANKI_FIELDS = ["Sentence", "Translation", "Pronunciation", "Audio", "Source", "Timestamp", "Language"]

def export_to_anki_csv(anki_csv_path: Path = ANKI_CSV) -> int:
    sentences_json = MINING_DIR / SENTENCES_FILE
    if not sentences_json.exists():
        log.warning("No sentences.json found")
        return 0
    try:
        with open(sentences_json, "r", encoding="utf-8") as f:
            entries = json.load(f)
    except Exception as e:
        log.error(f"Failed to load sentences: {e}")
        return 0
    if not entries: return 0
    exported = 0
    with open(anki_csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=ANKI_FIELDS, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        for entry in entries:
            sentence = entry.get("sentence", "").strip()
            if not sentence: continue
            translation = entry.get("translation", "").strip()
            source = entry.get("source", "").strip()
            timestamp = entry.get("timestamp", "").strip()
            audio_path = entry.get("audio", "").strip()
            lang = entry.get("lang", "zh")
            pron = entry.get("pronunciation", "").strip()
            if not pron: pron = get_pronunciation(sentence, lang)
            audio_tag = ""
            if audio_path and Path(audio_path).exists():
                audio_tag = f"[sound:{Path(audio_path).name}]"
            writer.writerow({"Sentence": sentence, "Translation": translation,
                "Pronunciation": pron, "Audio": audio_tag, "Source": source,
                "Timestamp": timestamp, "Language": LANG_REGISTRY.get(lang, {}).get("name", lang)})
            exported += 1
    log.info(f"Exported {exported} entries to {anki_csv_path}")
    return exported

def append_to_anki_csv(entry: dict, anki_csv_path: Path = ANKI_CSV) -> bool:
    sentence = entry.get("sentence", "").strip()
    if not sentence: return False
    if not anki_csv_path.exists():
        with open(anki_csv_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=ANKI_FIELDS, quoting=csv.QUOTE_ALL)
            writer.writeheader()
    lang = entry.get("lang", "zh")
    pron = entry.get("pronunciation", "").strip()
    if not pron: pron = get_pronunciation(sentence, lang)
    audio_path = entry.get("audio", "").strip()
    audio_tag = ""
    if audio_path and Path(audio_path).exists():
        audio_tag = f"[sound:{Path(audio_path).name}]"
    row = {"Sentence": sentence, "Translation": entry.get("translation", ""),
        "Pronunciation": pron, "Audio": audio_tag, "Source": entry.get("source", ""),
        "Timestamp": entry.get("timestamp", ""),
        "Language": LANG_REGISTRY.get(lang, {}).get("name", lang)}
    with open(anki_csv_path, "a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=ANKI_FIELDS, quoting=csv.QUOTE_ALL)
        writer.writerow(row)
    return True
