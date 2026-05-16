"""Performance monitoring - track OCR accuracy, translation quality."""
import json, time
from pathlib import Path
from config import MINING_DIR
from log import log

STATS_FILE = MINING_DIR / "stats.json"

def load_stats() -> dict:
    """Load performance stats."""
    if not STATS_FILE.exists():
        return {"sessions": 0, "total_mined": 0, "ocr_failures": 0,
                "translation_failures": 0, "avg_confidence": 0, "by_lang": {}}
    try:
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"sessions": 0, "total_mined": 0, "ocr_failures": 0,
                "translation_failures": 0, "avg_confidence": 0, "by_lang": {}}

def save_stats(stats: dict):
    """Save performance stats."""
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

def record_mining(lang: str, success: bool, ocr_confidence: float = 0,
                  translation_ok: bool = True):
    """Record a mining session result."""
    stats = load_stats()
    stats["total_mined"] += 1
    if not success: stats["ocr_failures"] += 1
    if not translation_ok: stats["translation_failures"] += 1
    if ocr_confidence > 0:
        n = stats.get("confidence_count", 0) + 1
        stats["avg_confidence"] = (stats["avg_confidence"] * (n-1) + ocr_confidence) / n
        stats["confidence_count"] = n
    if lang not in stats["by_lang"]:
        stats["by_lang"][lang] = {"count": 0, "failures": 0}
    stats["by_lang"][lang]["count"] += 1
    if not success: stats["by_lang"][lang]["failures"] += 1
    save_stats(stats)

def format_stats_report(stats: dict = None) -> str:
    """Format stats as readable report."""
    if stats is None: stats = load_stats()
    lines = ["Mining Statistics:", "=" * 40]
    lines.append(f"  Total mined: {stats['total_mined']}")
    lines.append(f"  OCR failures: {stats['ocr_failures']}")
    lines.append(f"  Translation failures: {stats['translation_failures']}")
    lines.append(f"  Avg OCR confidence: {stats['avg_confidence']:.1f}%")
    lines.append("\nBy Language:")
    for lang, data in stats.get("by_lang", {}).items():
        fail_rate = data["failures"] / data["count"] * 100 if data["count"] > 0 else 0
        lines.append(f"  {lang}: {data['count']} mined, {fail_rate:.1f}% fail rate")
    return "\n".join(lines)
