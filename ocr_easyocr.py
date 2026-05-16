"""EasyOCR fallback for when Tesseract fails."""
try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False
from pathlib import Path
from config import LANG_REGISTRY
from log import log

_readers = {}

def _get_easyocr_reader(lang: str):
    """Get or create EasyOCR reader for language."""
    if lang in _readers: return _readers[lang]
    lang_map = {"zh": ["ch_sim", "en"], "ja": ["ja", "en"], "ko": ["ko", "en"],
                "de": ["de", "en"], "es": ["es", "en"], "el": ["el", "en"],
                "fr": ["fr", "en"], "pl": ["pl", "en"], "ru": ["ru", "en"], "en": ["en"]}
    langs = lang_map.get(lang, ["en"])
    try:
        _readers[lang] = easyocr.Reader(langs, gpu=False, verbose=False)
        log.info(f"EasyOCR loaded: {langs}")
    except Exception as e:
        log.error(f"EasyOCR failed to load: {e}")
        return None
    return _readers[lang]

def ocr_easyocr(image_path: Path, lang: str = "zh") -> str:
    """OCR using EasyOCR as fallback."""
    if not EASYOCR_AVAILABLE:
        log.warning("EasyOCR not installed: pip install easyocr")
        return ""
    reader = _get_easyocr_reader(lang)
    if not reader: return ""
    try:
        results = reader.readtext(str(image_path), detail=0)
        text = " ".join(results).strip()
        log.info(f"EasyOCR result: {text[:60]}")
        return text
    except Exception as e:
        log.error(f"EasyOCR failed: {e}")
        return ""
