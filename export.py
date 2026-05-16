"""Export improvements - Anki, JSON, Excel, audio playback."""
import csv, json, io
from pathlib import Path
from config import MINING_DIR, LANG_REGISTRY
from text import get_pronunciation
from log import log

def export_json(output_path: Path = None) -> Path:
    """Export all sentences as JSON."""
    if output_path is None:
        output_path = MINING_DIR / "export.json"
    sentences_json = MINING_DIR / "sentences.json"
    if not sentences_json.exists():
        log.warning("No sentences to export")
        return None
    with open(sentences_json, "r", encoding="utf-8") as f:
        data = json.load(f)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    log.info(f"Exported JSON: {output_path}")
    return output_path

def export_excel(output_path: Path = None) -> Path:
    """Export as Excel-compatible CSV with proper formatting."""
    if output_path is None:
        output_path = MINING_DIR / "export.xlsx.csv"
    sentences_json = MINING_DIR / "sentences.json"
    if not sentences_json.exists(): return None
    with open(sentences_json, "r", encoding="utf-8") as f:
        entries = json.load(f)
    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow(["Language", "Sentence", "Pronunciation", "Translation",
                         "Source", "Timestamp", "Audio"])
        for e in entries:
            lang = e.get("lang", "zh")
            pron = e.get("pronunciation", "") or get_pronunciation(e.get("sentence", ""), lang)
            audio = e.get("audio", "")
            writer.writerow([LANG_REGISTRY.get(lang, {}).get("name", lang),
                e.get("sentence", ""), pron, e.get("translation", ""),
                e.get("source", ""), e.get("timestamp", ""), audio])
    log.info(f"Exported Excel CSV: {output_path}")
    return output_path

def get_audio_files() -> list:
    """List all audio files with metadata."""
    audio_dir = MINING_DIR / "audio"
    if not audio_dir.exists(): return []
    return sorted(audio_dir.glob("*.mp3"))
