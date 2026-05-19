"""Performance monitoring - track OCR accuracy, translation quality per language."""
import json, time
from pathlib import Path
from config import MINING_DIR, LANG_REGISTRY
from log import log

STATS_FILE = MINING_DIR / "stats.json"

def load_stats() -> dict:
    """Load performance stats."""
    if not STATS_FILE.exists():
        return {"sessions": 0, "total_mined": 0, "ocr_failures": 0,
                "translation_failures": 0, "avg_confidence": 0,
                "by_lang": {}}
    try:
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"sessions": 0, "total_mined": 0, "ocr_failures": 0,
                "translation_failures": 0, "avg_confidence": 0,
                "by_lang": {}}

def save_stats(stats: dict):
    """Save performance stats."""
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

def record_mining(lang: str, success: bool, ocr_confidence: float = 0,
                  translation_ok: bool = True, mode: str = "normal"):
    """Record a mining session result."""
    stats = load_stats()
    stats["total_mined"] += 1
    if not success: stats["ocr_failures"] += 1
    if not translation_ok: stats["translation_failures"] += 1
    if ocr_confidence > 0:
        n = stats.get("confidence_count", 0) + 1
        stats["avg_confidence"] = (stats["avg_confidence"] * (n-1) + ocr_confidence) / n
        stats["confidence_count"] = n
    
    # Initialize language stats if not exists
    if lang not in stats["by_lang"]:
        stats["by_lang"][lang] = {
            "count": 0, "failures": 0, "translation_failures": 0,
            "quick_captures": 0, "normal_captures": 0,
            "last_used": "", "avg_confidence": 0
        }
    
    lang_stats = stats["by_lang"][lang]
    # Ensure new fields exist (for backward compatibility)
    lang_stats.setdefault("quick_captures", 0)
    lang_stats.setdefault("normal_captures", 0)
    lang_stats.setdefault("translation_failures", 0)
    lang_stats.setdefault("avg_confidence", 0)
    
    lang_stats["count"] += 1
    if not success: lang_stats["failures"] += 1
    if not translation_ok: lang_stats["translation_failures"] += 1
    if mode == "quick": lang_stats["quick_captures"] += 1
    else: lang_stats["normal_captures"] += 1
    lang_stats["last_used"] = time.strftime("%Y-%m-%d %H:%M:%S")
    
    save_stats(stats)

def format_stats_report(stats: dict = None) -> str:
    """Format stats as readable report."""
    if stats is None: stats = load_stats()
    lines = ["Mining Statistics:", "=" * 50]
    lines.append(f"  Total mined: {stats['total_mined']}")
    lines.append(f"  OCR failures: {stats['ocr_failures']}")
    lines.append(f"  Translation failures: {stats['translation_failures']}")
    conf = stats.get('avg_confidence', 0)
    lines.append(f"  Avg OCR confidence: {conf:.1f}%")
    lines.append("\nBy Language:")
    lines.append(f"  {'Lang':<6} {'Total':>6} {'Fail':>5} {'TransFail':>10} {'Quick':>6} {'Last Used':>20}")
    lines.append("  " + "-" * 55)
    for lang, data in stats.get("by_lang", {}).items():
        name = LANG_REGISTRY.get(lang, {}).get("name", lang)[:4]
        fail_rate = data["failures"]
        trans_fail = data["translation_failures"]
        quick = data.get("quick_captures", 0)
        last = data.get("last_used", "")[:19]
        lines.append(f"  {name:<6} {data['count']:>6} {fail_rate:>5} {trans_fail:>10} {quick:>6} {last:>20}")
    return "\n".join(lines)

if __name__ == "__main__":
    print(format_stats_report())
