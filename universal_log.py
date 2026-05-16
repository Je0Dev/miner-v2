"""Universal root log for all extracted content, translations, and pronunciation."""
import json
from datetime import datetime
from pathlib import Path
from config import MINING_DIR

UNIVERSAL_LOG = MINING_DIR / "universal_log.txt"
UNIVERSAL_JSON = MINING_DIR / "universal_log.json"

def log_capture(sentence: str, translation: str = "", pronunciation: str = "",
                source: str = "Game", lang: str = "zh", audio: str = ""):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(UNIVERSAL_LOG, "a", encoding="utf-8") as f:
        f.write(f"\n{'='*60}\n")
        f.write(f"[{ts}] {lang.upper()} -> EN | Source: {source}\n")
        f.write(f"Text: {sentence}\n")
        if pronunciation:
            f.write(f"Pronunciation: {pronunciation}\n")
        if translation:
            f.write(f"Translation: {translation}\n")
        if audio:
            f.write(f"Audio: {audio}\n")
        f.write(f"{'='*60}\n")
    entry = {
        "timestamp": ts, "lang": lang, "source": source,
        "sentence": sentence, "pronunciation": pronunciation,
        "translation": translation, "audio": audio,
    }
    entries = []
    if UNIVERSAL_JSON.exists():
        try:
            with open(UNIVERSAL_JSON, "r", encoding="utf-8") as f:
                entries = json.load(f)
        except Exception:
            entries = []
    entries.append(entry)
    with open(UNIVERSAL_JSON, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
