"""Smart duplicate detection with OCR variation handling."""
import re
from config import MINING_DIR, SENTENCES_FILE
from log import log

def normalize_for_comparison(text: str) -> str:
    """Normalize text for duplicate comparison."""
    if not text: return ""
    # Remove spaces between CJK characters
    text = re.sub(r'([\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af])\s+', r'\1', text)
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip().lower()
    # Remove punctuation
    text = re.sub(r'[^\w\s]', '', text)
    return text

def levenshtein_distance(s1: str, s2: str) -> int:
    """Calculate Levenshtein distance between two strings."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (c1 != c2)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row
    return prev_row[-1]

def is_similar(text1: str, text2: str, threshold: float = 0.85) -> bool:
    """Check if two texts are similar (handles OCR variations)."""
    n1, n2 = normalize_for_comparison(text1), normalize_for_comparison(text2)
    if not n1 or not n2: return False
    if n1 == n2: return True
    # Levenshtein similarity
    dist = levenshtein_distance(n1, n2)
    max_len = max(len(n1), len(n2))
    similarity = 1 - (dist / max_len)
    return similarity >= threshold

def is_duplicate_smart(new_text: str, history: list = None, threshold: float = 0.85) -> bool:
    """Check if text is duplicate against history with OCR variation tolerance."""
    if history is None:
        history = load_history_smart()
    for old in history:
        if is_similar(new_text, old, threshold):
            log.info(f"Duplicate detected: {new_text[:30]}")
            return True
    return False

def load_history_smart(max_entries: int = 500) -> list:
    """Load recent sentence history."""
    path = MINING_DIR / SENTENCES_FILE
    if not path.exists(): return []
    try:
        import json
        with open(path, "r", encoding="utf-8") as f:
            entries = json.load(f)
        return [e.get("sentence", "") for e in entries[-max_entries:] if e.get("sentence")]
    except Exception:
        return []
