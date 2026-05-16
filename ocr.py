"""OCR functions for Game Sentence Miner v2.

Handles Tesseract OCR with preprocessing and caching.
Optimized for game text including borderless window mode (smaller text).
"""
import hashlib
from pathlib import Path
try:
    import pytesseract
    from PIL import Image, ImageEnhance, ImageFilter
except ImportError:
    print("ERROR: pip install pytesseract pillow"); import sys; sys.exit(1)
from config import OCR_LANGS
from log import log

_tesseract_ready = False


def prewarm_tesseract(lang: str = "chi_sim"):
    """Load Tesseract models at startup."""
    global _tesseract_ready
    if _tesseract_ready:
        return
    try:
        img = Image.new("L", (100, 30), 255)
        pytesseract.image_to_string(img, config=f"--oem 3 --psm 6 -l {lang}")
        _tesseract_ready = True
        log.info(f"Tesseract pre-warmed ({lang})")
    except Exception as e:
        log.warning(f"Tesseract pre-warm failed: {e}")


def _image_hash(path: Path) -> str:
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def preprocess_image(image_path: Path) -> Image.Image:
    """Preprocess image for better OCR accuracy.

    Optimized for game text including borderless window mode:
    1. Convert to grayscale
    2. Increase contrast (1.5x)
    3. Sharpen to enhance small text
    4. Binarize with lower threshold (128) for smaller text
    """
    img = Image.open(image_path).convert("L")
    # Increase contrast for better text visibility
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.5)
    # Sharpen to enhance small text edges
    img = img.filter(ImageFilter.SHARPEN)
    # Binarize with lower threshold for smaller text
    return img.point(lambda p: 255 if p > 128 else 0)


def _ensure_utf8(text: str) -> str:
    """Ensure text is properly decoded UTF-8."""
    if not text:
        return ""
    try:
        text.encode('utf-8')
        if all(ord(c) < 128 or (0x4e00 <= ord(c) <= 0x9fff) or
               (0x3040 <= ord(c) <= 0x30ff) or (0x3000 <= ord(c) <= 0x303f) or
               (0xff00 <= ord(c) <= 0xffef) for c in text.strip()):
            return text
    except Exception:
        pass
    try:
        return text.encode('latin-1').decode('utf-8')
    except Exception:
        return text


def ocr_image(image_path: Path, lang: str = "zh", use_confidence: bool = True) -> str:
    """Extract text from image using Tesseract OCR.

    Uses PSM 6 (uniform block of text) for game text.
    For borderless window mode with smaller text, PSM 3 (fully automatic)
    is used as fallback if PSM 6 returns empty.
    """
    prewarm_tesseract(OCR_LANGS.get(lang, lang))
    t_lang = OCR_LANGS.get(lang, lang)
    try:
        img = preprocess_image(image_path)
        # Try PSM 6 first (uniform block of text)
        config = f"--oem 3 --psm 6 -l {t_lang}"
        text = pytesseract.image_to_string(img, config=config).strip()
        # If empty, try PSM 3 (fully automatic) for smaller text
        if not text:
            config = f"--oem 3 --psm 3 -l {t_lang}"
            text = pytesseract.image_to_string(img, config=config).strip()
        return _ensure_utf8(text)
    except Exception as e:
        log.error(f"OCR failed: {e}")
        return ""


def ocr_image_with_boxes(image_path: Path, lang: str = "zh") -> dict:
    """Extract text with bounding boxes for proximity merging."""
    prewarm_tesseract(OCR_LANGS.get(lang, lang))
    t_lang = OCR_LANGS.get(lang, lang)
    try:
        img = preprocess_image(image_path)
        config = f"--oem 3 --psm 6 -l {t_lang}"
        data = pytesseract.image_to_data(img, config=config, output_type=pytesseract.Output.DICT)
        if "text" in data:
            data["text"] = [_ensure_utf8(t) for t in data["text"]]
        return data
    except Exception as e:
        log.error(f"OCR with boxes failed: {e}")
        return {}
