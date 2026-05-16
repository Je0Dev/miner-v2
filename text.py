"""Text processing: filtering, deduplication, sentence splitting, pinyin/romaji."""
import re, json, unicodedata
from pathlib import Path
from config import MIN_TEXT_LENGTH, MAX_TEXT_LENGTH, MINING_DIR, SENTENCES_FILE, LANG_REGISTRY
from log import log

SENTENCE_BREAKS = re.compile(r'([。！？!?；;\.\n\r]+)')
CJK_CHARS = re.compile(r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]')
HANGUL_CHARS = re.compile(r'[\uac00-\ud7af\u1100-\u11ff]')
GREEK_CHARS = re.compile(r'[\u0370-\u03FF]')
CYRILLIC_CHARS = re.compile(r'[\u0400-\u04FF]')
UNICODE_ESCAPE_RE = re.compile(r'\\u([0-9a-fA-F]{4})')

def sanitize_unicode(text: str) -> str:
    if not text: return ""
    def _replace_escape(m): return chr(int(m.group(1), 16))
    text = UNICODE_ESCAPE_RE.sub(_replace_escape, text)
    # Normalize to NFC (composed form)
    text = unicodedata.normalize('NFC', text)
    # Remove replacement characters, zero-width spaces, and other invisible chars
    text = text.replace('\ufffd', '')  # Replacement character
    text = text.replace('\u200b', '')  # Zero-width space
    text = text.replace('\u200c', '')  # Zero-width non-joiner
    text = text.replace('\u200d', '')  # Zero-width joiner
    text = text.replace('\ufeff', '')  # BOM
    text = text.replace('\xa0', ' ')   # Non-breaking space
    # Remove control characters except newlines and tabs
    text = ''.join(c for c in text if unicodedata.category(c)[0] != 'C' or c in '\n\r\t')
    # Fix mojibake (UTF-8 bytes decoded as Latin-1)
    if any(0x80 <= ord(c) <= 0xFF for c in text):
        try:
            fixed = text.encode('latin-1', errors='ignore').decode('utf-8', errors='replace')
            if CJK_CHARS.findall(fixed) and len(CJK_CHARS.findall(fixed)) > len(CJK_CHARS.findall(text)):
                text = fixed
        except Exception: pass
    return text

def clean_text(text: str) -> str:
    text = sanitize_unicode(text)
    # Remove ALL spaces between CJK characters (Tesseract artifact)
    cjk_re = r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af\u3000-\u303f\uff00-\uffef]'
    while re.search(f'({cjk_re})\\s+({cjk_re})', text):
        text = re.sub(f'({cjk_re})\\s+({cjk_re})', r'\1\2', text)
    text = re.sub(r'[^\S\n]+', ' ', text)
    return text.strip()

def is_valid_text(text: str) -> bool:
    if not text or len(text) < MIN_TEXT_LENGTH or len(text) > MAX_TEXT_LENGTH: return False
    if text in ("[No text detected]", "OCR failed", ""): return False
    # Reject text that looks like UI menu (too many short fragments)
    words = text.split()
    if len(words) > 10 and all(len(w) <= 2 for w in words):
        return False
    # Reject text with too many numbers/symbols mixed with CJK
    cjk_count = len(CJK_CHARS.findall(text))
    digit_count = len(re.findall(r'\d', text))
    if cjk_count > 0 and digit_count > cjk_count * 0.3:
        return False
    # Reject text with copyright/trademark symbols as primary content
    if re.match(r'^[©®™℗℠\s]+$', text):
        return False
    return True

def split_sentences(text: str) -> list[str]:
    parts = SENTENCE_BREAKS.split(text)
    sentences, current = [], ""
    for part in parts:
        if SENTENCE_BREAKS.match(part):
            current += part
            cleaned = clean_text(current)
            if is_valid_text(cleaned): sentences.append(cleaned)
            current = ""
        else: current += part
    cleaned = clean_text(current)
    if is_valid_text(cleaned): sentences.append(cleaned)
    return sentences if sentences else [clean_text(text)] if is_valid_text(clean_text(text)) else []

def text_similarity(a: str, b: str) -> float:
    if not a or not b: return 0.0
    set_a, set_b = set(a), set(b)
    if not set_a or not set_b: return 0.0
    return len(set_a & set_b) / len(set_a | set_b)

def is_duplicate(new_text: str, history: list[str], threshold: float = 0.85) -> bool:
    return any(text_similarity(new_text, old) > threshold for old in history)

def load_history(max_entries: int = 500) -> list[str]:
    path = MINING_DIR / SENTENCES_FILE
    if not path.exists(): return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            entries = json.load(f)
        return [e.get("sentence", "") for e in entries[-max_entries:] if e.get("sentence")]
    except Exception: return []

def get_pinyin(text: str, tone_marks: bool = False) -> str:
    try:
        from pypinyin import pinyin, Style
        style = Style.TONE if tone_marks else Style.TONE3
        result = pinyin(text, style=style, heteronym=False)
        return " ".join([item[0] for item in result])
    except Exception: return ""

def get_romaji(text: str, lang: str = "ja") -> str:
    if lang == "ja":
        try:
            import romkan
            return romkan.to_roma(text)
        except Exception: pass
    elif lang == "ko":
        try:
            from hangul_romanize import convert
            return convert(text)
        except Exception: pass
    return ""

def get_transliteration(text: str, lang: str = "el") -> str:
    if lang == "el":
        try:
            import trans
            return trans.greek(text)
        except Exception: pass
    elif lang == "ru":
        try:
            import trans
            return trans.russian(text)
        except Exception: pass
    return ""

def get_pronunciation(text: str, lang: str = "zh") -> str:
    info = LANG_REGISTRY.get(lang, {})
    romaji_type = info.get("romaji")
    if romaji_type == "pinyin": return get_pinyin(text)
    elif romaji_type == "romaji": return get_romaji(text, "ja")
    elif romaji_type == "romanization": return get_romaji(text, "ko")
    elif romaji_type == "transliteration": return get_transliteration(text, lang)
    return ""

def format_with_pronunciation(text: str, lang: str = "zh") -> str:
    if not text: return text
    script = LANG_REGISTRY.get(lang, {}).get("script", "latin")
    if script == "cjk" and (CJK_CHARS.search(text) or HANGUL_CHARS.search(text)):
        pron = get_pronunciation(text, lang)
        if pron: return f"{text}\n{pron}"
    elif script in ("greek", "cyrillic"):
        pron = get_pronunciation(text, lang)
        if pron: return f"{text}\n{pron}"
    return text
