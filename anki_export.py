"""Anki CSV export for Game Sentence Miner v2.

Generates properly formatted CSV for direct Anki import.
Fields: Sentence, Translation, Pinyin, Audio, Source, Timestamp
"""
import csv, json
from pathlib import Path
from config import MINING_DIR, SENTENCES_FILE
from text import get_pinyin
from log import log

ANKI_CSV = MINING_DIR / "anki_export.csv"
ANKI_FIELDS = ["Sentence", "Translation", "Pinyin", "Audio", "Source", "Timestamp"]


def export_to_anki_csv(anki_csv_path: Path = ANKI_CSV) -> int:
    """Export all mined sentences to Anki-compatible CSV.
    
    Returns number of entries exported.
    """
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
    
    if not entries:
        return 0
    
    exported = 0
    with open(anki_csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=ANKI_FIELDS, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        
        for entry in entries:
            sentence = entry.get("sentence", "").strip()
            if not sentence:
                continue
            
            translation = entry.get("translation", "").strip()
            source = entry.get("source", "").strip()
            timestamp = entry.get("timestamp", "").strip()
            audio_path = entry.get("audio", "").strip()
            
            # Generate pinyin if not present
            pinyin = entry.get("pinyin", "").strip()
            if not pinyin:
                pinyin = get_pinyin(sentence)
            
            # Format audio path for Anki (relative to collection.media)
            audio_tag = ""
            if audio_path and Path(audio_path).exists():
                audio_file = Path(audio_path).name
                audio_tag = f"[sound:{audio_file}]"
            
            row = {
                "Sentence": sentence,
                "Translation": translation,
                "Pinyin": pinyin,
                "Audio": audio_tag,
                "Source": source,
                "Timestamp": timestamp,
            }
            writer.writerow(row)
            exported += 1
    
    log.info(f"Exported {exported} entries to {anki_csv_path}")
    return exported


def append_to_anki_csv(entry: dict, anki_csv_path: Path = ANKI_CSV) -> bool:
    """Append a single entry to the Anki CSV file."""
    sentence = entry.get("sentence", "").strip()
    if not sentence:
        return False
    
    # Create file with header if it doesn't exist
    if not anki_csv_path.exists():
        with open(anki_csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=ANKI_FIELDS, quoting=csv.QUOTE_ALL)
            writer.writeheader()
    
    pinyin = entry.get("pinyin", "").strip()
    if not pinyin:
        pinyin = get_pinyin(sentence)
    
    audio_path = entry.get("audio", "").strip()
    audio_tag = ""
    if audio_path and Path(audio_path).exists():
        audio_file = Path(audio_path).name
        audio_tag = f"[sound:{audio_file}]"
    
    row = {
        "Sentence": sentence,
        "Translation": entry.get("translation", ""),
        "Pinyin": pinyin,
        "Audio": audio_tag,
        "Source": entry.get("source", ""),
        "Timestamp": entry.get("timestamp", ""),
    }
    
    with open(anki_csv_path, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=ANKI_FIELDS, quoting=csv.QUOTE_ALL)
        writer.writerow(row)
    
    return True
