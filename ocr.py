"""OCR functions for Game Sentence Miner v2."""
import hashlib, re
from pathlib import Path
try:
    import pytesseract
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps
    import numpy as np
    from scipy.ndimage import grey_closing
except ImportError:
    print("ERROR: pip install pytesseract pillow numpy scipy"); import sys; sys.exit(1)
from config import LANG_REGISTRY
from log import log

_tesseract_ready = False

def prewarm_tesseract(lang: str = "chi_sim"):
    global _tesseract_ready
    if _tesseract_ready: return
    try:
        img = Image.new("L", (100, 30), 255)
        pytesseract.image_to_string(img, config=f"--oem 3 --psm 6 -l {lang}")
        _tesseract_ready = True
        log.info(f"Tesseract pre-warmed ({lang})")
    except Exception as e:
        log.warning(f"Tesseract pre-warm failed: {e}")

def preprocess_image(image_path: Path, lang: str = "zh") -> Image.Image:
    img = Image.open(image_path).convert("L")
    arr = np.array(img)
    avg = np.mean(arr)
    if avg < 100: img = ImageOps.invert(img)
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.5)
    img = img.filter(ImageFilter.SHARPEN)
    arr = np.array(img)
    h, w = arr.shape
    ks = max(5, min(h, w) // 10)
    if ks % 2 == 0: ks += 1
    bg = grey_closing(arr, size=(ks, ks))
    result = 255 - (bg - arr)
    result = (result > 128).astype(np.uint8) * 255
    return Image.fromarray(result)

def preprocess_image_long(image_path: Path, lang: str = "zh") -> Image.Image:
    img = Image.open(image_path).convert("L")
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.3)
    img = img.filter(ImageFilter.MedianFilter(size=3))
    arr = np.array(img)
    h, w = arr.shape
    ks = max(7, min(h, w) // 8)
    if ks % 2 == 0: ks += 1
    bg = grey_closing(arr, size=(ks, ks))
    result = 255 - (bg - arr)
    result = (result > 128).astype(np.uint8) * 255
    return Image.fromarray(result)

def _ensure_utf8(text: str) -> str:
    if not text: return ""
    try:
        text.encode('utf-8')
        return text
    except Exception: pass
    try: return text.encode('latin-1').decode('utf-8')
    except Exception: return text

def _filter_garbage(text: str, lang: str = "zh") -> str:
    if not text: return ""
    script = LANG_REGISTRY.get(lang, {}).get("script", "latin")
    if script == "cjk":
        # Remove standalone digits and digit pairs
        text = re.sub(r'(?<!\d)\d{1,3}(?!\d)', '', text)
        # Remove standalone Latin letters not part of valid words
        text = re.sub(r'(?<![A-Za-z])[A-Za-z](?![A-Za-z])', '', text)
        text = re.sub(r'\b([A-Za-z])\s+\1\b', '', text)
        # Remove common OCR artifacts and UI symbols
        text = re.sub(r'[「」【】〖〗《》〈〉\[\]{}()|\\/_~`@#$%^&*+=]', '', text)
        # Remove repeated punctuation
        text = re.sub(r'([。，！？])\1+', r'\1', text)
    elif script == "latin":
        text = re.sub(r'(?<!\d)\d{1,2}(?!\d)', '', text)
        text = re.sub(r'\b([A-Za-z])\s+\1\b', '', text)
    elif script == "greek":
        text = re.sub(r'(?<!\d)\d{1,3}(?!\d)', '', text)
        text = re.sub(r'[^\u0370-\u03FF\u0020-\u007F]', '', text)
    elif script == "cyrillic":
        text = re.sub(r'(?<!\d)\d{1,3}(?!\d)', '', text)
        text = re.sub(r'[^\u0400-\u04FF\u0020-\u007F]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text if text and not text.isspace() else ""

def ocr_image(image_path: Path, lang: str = "zh") -> str:
    prewarm_tesseract(LANG_REGISTRY.get(lang, {}).get("tess", lang))
    t_lang = LANG_REGISTRY.get(lang, {}).get("tess", lang)
    for psm in [6, 3, 5]:
        try:
            img = preprocess_image(image_path, lang)
            text = pytesseract.image_to_string(img, config=f"--oem 3 --psm {psm} -l {t_lang}").strip()
            if text:
                filtered = _filter_garbage(_ensure_utf8(text), lang)
                if filtered: return filtered
        except Exception as e:
            log.warning(f"OCR PSM {psm} failed: {e}")
    try:
        img = Image.open(image_path).convert("L")
        for psm in [6, 3, 5]:
            text = pytesseract.image_to_string(img, config=f"--oem 3 --psm {psm} -l {t_lang}").strip()
            if text:
                filtered = _filter_garbage(_ensure_utf8(text), lang)
                if filtered: return filtered
    except Exception as e:
        log.error(f"OCR failed completely: {e}")
    return ""

def ocr_long_text(image_path: Path, lang: str = "zh") -> str:
    prewarm_tesseract(LANG_REGISTRY.get(lang, {}).get("tess", lang))
    t_lang = LANG_REGISTRY.get(lang, {}).get("tess", lang)
    for psm in [3, 5]:
        try:
            img = preprocess_image_long(image_path, lang)
            text = pytesseract.image_to_string(img, config=f"--oem 3 --psm {psm} -l {t_lang}").strip()
            if text:
                filtered = _filter_garbage(_ensure_utf8(text), lang)
                if filtered: return filtered
        except Exception as e:
            log.warning(f"OCR long PSM {psm} failed: {e}")
    try:
        img = Image.open(image_path).convert("L")
        for psm in [3, 5]:
            text = pytesseract.image_to_string(img, config=f"--oem 3 --psm {psm} -l {t_lang}").strip()
            if text:
                filtered = _filter_garbage(_ensure_utf8(text), lang)
                if filtered: return filtered
    except Exception as e:
        log.error(f"OCR long text failed: {e}")
    return ""

def ocr_vertical_text(image_path: Path, lang: str = "zh") -> str:
    prewarm_tesseract(LANG_REGISTRY.get(lang, {}).get("tess", lang))
    t_lang = LANG_REGISTRY.get(lang, {}).get("tess", lang)
    results = []
    try:
        img = preprocess_image(image_path, lang)
        text = pytesseract.image_to_string(img, config=f"--oem 3 --psm 5 -l {t_lang}").strip()
        if text: results.append(_filter_garbage(_ensure_utf8(text), lang))
    except Exception as e:
        log.warning(f"Vertical PSM 5 failed: {e}")
    for rot in [90, 270, 180]:
        try:
            img = Image.open(image_path).convert("L").rotate(rot, expand=True)
            arr = np.array(img)
            if np.mean(arr) < 100: img = ImageOps.invert(img)
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.5).filter(ImageFilter.SHARPEN)
            arr = np.array(img)
            h, w = arr.shape
            ks = max(5, min(h, w) // 10)
            if ks % 2 == 0: ks += 1
            bg = grey_closing(arr, size=(ks, ks))
            result = 255 - (bg - arr)
            result = (result > 128).astype(np.uint8) * 255
            img = Image.fromarray(result)
            for psm in [6, 3]:
                text = pytesseract.image_to_string(img, config=f"--oem 3 --psm {psm} -l {t_lang}").strip()
                if text: results.append(_filter_garbage(_ensure_utf8(text), lang))
        except Exception as e:
            log.warning(f"Rotation {rot} failed: {e}")
    valid = [r for r in results if r and len(r) > 1]
    return max(valid, key=len) if valid else ""
