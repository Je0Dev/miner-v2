"""Text processing: filtering, deduplication, sentence splitting, pinyin."""
import re
import json
from pathlib import Path
from config import MIN_TEXT_LENGTH, MAX_TEXT_LENGTH, MINING_DIR, SENTENCES_FILE
from log import log

# Sentence boundary patterns for CJK + Western
SENTENCE_BREAKS = re.compile(r'([。！？!?；;\n\r]+)')
CJK_CHARS = re.compile(r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]')
UNICODE_ESCAPE_RE = re.compile(r'\\u([0-9a-fA-F]{4})')


def sanitize_unicode(text: str) -> str:
    """Fix mojibake and convert unicode escape sequences to proper characters."""
    if not text:
        return ""
    # Convert literal \\uXXXX sequences
    def _replace_escape(m):
        return chr(int(m.group(1), 16))
    text = UNICODE_ESCAPE_RE.sub(_replace_escape, text)
    # Fix mojibake (UTF-8 bytes decoded as Latin-1)
    if any(0x80 <= ord(c) <= 0xFF for c in text):
        try:
            fixed = text.encode('latin-1', errors='ignore').decode('utf-8', errors='replace')
            if CJK_CHARS.findall(fixed) and len(CJK_CHARS.findall(fixed)) > len(CJK_CHARS.findall(text)):
                text = fixed
        except Exception:
            pass
    return text


def clean_text(text: str) -> str:
    """Clean and normalize OCR text."""
    text = sanitize_unicode(text)
    text = re.sub(r'[^\S\n]+', ' ', text)
    text = text.strip()
    return text


def is_valid_text(text: str) -> bool:
    """Check if text meets minimum/length requirements."""
    if not text or len(text) < MIN_TEXT_LENGTH or len(text) > MAX_TEXT_LENGTH:
        return False
    if text in ("[No text detected]", "OCR failed", ""):
        return False
    return True


def split_sentences(text: str) -> list[str]:
    """Split text into sentences using CJK and Western punctuation."""
    parts = SENTENCE_BREAKS.split(text)
    sentences = []
    current = ""
    for part in parts:
        if SENTENCE_BREAKS.match(part):
            current += part
            cleaned = clean_text(current)
            if is_valid_text(cleaned):
                sentences.append(cleaned)
            current = ""
        else:
            current += part
    cleaned = clean_text(current)
    if is_valid_text(cleaned):
        sentences.append(cleaned)
    return sentences if sentences else [clean_text(text)] if is_valid_text(clean_text(text)) else []


def text_similarity(a: str, b: str) -> float:
    """Calculate Jaccard similarity between two strings."""
    if not a or not b:
        return 0.0
    set_a, set_b = set(a), set(b)
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def is_duplicate(new_text: str, history: list[str], threshold: float = 0.85) -> bool:
    """Check if new text is too similar to any entry in history."""
    for old in history:
        if text_similarity(new_text, old) > threshold:
            return True
    return False


def load_history(max_entries: int = 500) -> list[str]:
    """Load recent sentence history from JSON file."""
    path = MINING_DIR / SENTENCES_FILE
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            entries = json.load(f)
        return [e.get("sentence", "") for e in entries[-max_entries:] if e.get("sentence")]
    except Exception:
        return []


def get_pinyin(text: str) -> str:
    """Convert Chinese text to pinyin with tone marks."""
    try:
        from pypinyin import pinyin, Style
        result = pinyin(text, style=Style.TONE3)
        return " ".join([item[0] for item in result])
    except Exception:
        return ""


def format_with_pinyin(text: str) -> str:
    """Return text with pinyin annotation: 你好 (ni3 hao3)"""
    if not text or not CJK_CHARS.search(text):
        return text
    py = get_pinyin(text)
    if py:
        return f"{text} ({py})"
    return text
