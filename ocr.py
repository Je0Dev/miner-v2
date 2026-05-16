"""OCR functions for Game Sentence Miner v2."""
import hashlib, re, time, json
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
_OCR_CACHE = {}
CACHE_MAX_SIZE = 500

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

def _image_hash(path: Path) -> str:
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()

def _get_cached_result(cache_key: str) -> str | None:
    if cache_key in _OCR_CACHE:
        entry = _OCR_CACHE[cache_key]
        if time.time() - entry["time"] < 3600:  # 1 hour cache
            return entry["text"]
        del _OCR_CACHE[cache_key]
    return None

def _cache_result(cache_key: str, text: str):
    if len(_OCR_CACHE) >= CACHE_MAX_SIZE:
        oldest = min(_OCR_CACHE, key=lambda k: _OCR_CACHE[k]["time"])
        del _OCR_CACHE[oldest]
    _OCR_CACHE[cache_key] = {"text": text, "time": time.time()}

def _upscale_for_small_text(img: Image.Image, lang: str) -> Image.Image:
    """Upscale image for better small text OCR."""
    script = LANG_REGISTRY.get(lang, {}).get("script", "latin")
    w, h = img.size
    if script == "cjk":
        if w < 1000 or h < 300:
            img = img.resize((w * 3, h * 3), Image.LANCZOS)
    elif script in ("greek", "cyrillic"):
        if w < 800 or h < 200:
            img = img.resize((w * 2, h * 2), Image.LANCZOS)
    else:
        if w < 600 or h < 150:
            img = img.resize((w * 2, h * 2), Image.LANCZOS)
    return img

def _enhance_for_dense_text(img: Image.Image) -> Image.Image:
    """Extra enhancement for dense UI text."""
    arr = np.array(img)
    avg = np.mean(arr)
    if avg < 100: img = ImageOps.invert(img)
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.0)
    img = img.filter(ImageFilter.SHARPEN)
    img = img.filter(ImageFilter.SHARPEN)
    return img

def preprocess_image(image_path: Path, lang: str = "zh") -> Image.Image:
    img = Image.open(image_path).convert("L")
    img = _upscale_for_small_text(img, lang)
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
    img = _upscale_for_small_text(img, lang)
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

_CJK_RE = re.compile(r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af]')
_COPYRIGHT_RE = re.compile(r'[©®™℗℠]')
_UI_SYMBOLS_RE = re.compile(r'[\u2460-\u24ff\u2600-\u26ff\u2700-\u27bf\u3000-\u303f\uff00-\uffef\u2000-\u206f\u20a0-\u20cf\u2100-\u214f\u2190-\u21ff\u2200-\u22ff\u2300-\u23ff\u25a0-\u25ff\u2e80-\u2eff\u3100-\u312f\u3200-\u32ff]')
_CIRCLED_RE = re.compile(r'[\u2460-\u24ff\u3200-\u32ff]')
_DINGBATS_RE = re.compile(r'[\u2700-\u27bf]')
_MISC_SYMBOLS_RE = re.compile(r'[\u2600-\u26ff]')

def _filter_garbage(text: str, lang: str = "zh") -> str:
    if not text: return ""
    # Remove UI symbols: circled numbers, dingbats, misc symbols, arrows, math, etc.
    text = _CIRCLED_RE.sub('', text)
    text = _DINGBATS_RE.sub('', text)
    text = _MISC_SYMBOLS_RE.sub('', text)
    text = _UI_SYMBOLS_RE.sub('', text)
    text = _COPYRIGHT_RE.sub('', text)
    script = LANG_REGISTRY.get(lang, {}).get("script", "latin")
    if script == "cjk":
        text = re.sub(r'(?<!\d)\d{1,3}(?!\d)', '', text)
        text = re.sub(r'(?<![A-Za-z])[A-Za-z](?![A-Za-z])', '', text)
        text = re.sub(r'\b([A-Za-z])\s+\1\b', '', text)
        text = re.sub(r'[「」【】〖〗《》〈〉\[\]{}()|\\/_~`@#$%^&*+=]', '', text)
        text = re.sub(r'([。，！？])\1+', r'\1', text)
        cjk_chars = _CJK_RE.findall(text)
        non_cjk = len(text.replace(' ', '')) - len(cjk_chars)
        if len(cjk_chars) > 0 and non_cjk > len(cjk_chars) * 0.4:
            return ""
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

def _ocr_with_fallback(img, t_lang: str, lang: str, psm_modes: list) -> str:
    """Try multiple PSM modes with graceful fallback."""
    for psm in psm_modes:
        try:
            text = pytesseract.image_to_string(img, config=f"--oem 3 --psm {psm} -l {t_lang}").strip()
            if text:
                filtered = _filter_garbage(_ensure_utf8(text), lang)
                if filtered: return filtered
        except Exception as e:
            log.warning(f"OCR PSM {psm} failed: {e}")
    return ""

def ocr_image(image_path: Path, lang: str = "zh") -> str:
    prewarm_tesseract(LANG_REGISTRY.get(lang, {}).get("tess", lang))
    t_lang = LANG_REGISTRY.get(lang, {}).get("tess", lang)
    cache_key = f"{_image_hash(image_path)}:{lang}"
    cached = _get_cached_result(cache_key)
    if cached: return cached
    # Try preprocessed first
    try:
        img = preprocess_image(image_path, lang)
        result = _ocr_with_fallback(img, t_lang, lang, [6, 3, 5])
        if result:
            _cache_result(cache_key, result)
            return result
    except Exception as e:
        log.warning(f"OCR preprocessed failed: {e}")
    # Try enhanced for dense text
    try:
        img = Image.open(image_path).convert("L")
        img = _upscale_for_small_text(img, lang)
        img = _enhance_for_dense_text(img)
        result = _ocr_with_fallback(img, t_lang, lang, [6, 3, 5])
        if result:
            _cache_result(cache_key, result)
            return result
    except Exception as e:
        log.warning(f"OCR enhanced failed: {e}")
    # Raw fallback
    try:
        img = Image.open(image_path).convert("L")
        img = _upscale_for_small_text(img, lang)
        result = _ocr_with_fallback(img, t_lang, lang, [6, 3, 5])
        if result:
            _cache_result(cache_key, result)
            return result
    except Exception as e:
        log.error(f"OCR failed completely: {e}")
    return ""

def ocr_long_text(image_path: Path, lang: str = "zh") -> str:
    prewarm_tesseract(LANG_REGISTRY.get(lang, {}).get("tess", lang))
    t_lang = LANG_REGISTRY.get(lang, {}).get("tess", lang)
    cache_key = f"long:{_image_hash(image_path)}:{lang}"
    cached = _get_cached_result(cache_key)
    if cached: return cached
    try:
        img = preprocess_image_long(image_path, lang)
        result = _ocr_with_fallback(img, t_lang, lang, [3, 5])
        if result:
            _cache_result(cache_key, result)
            return result
    except Exception as e:
        log.warning(f"OCR long preprocessed failed: {e}")
    try:
        img = Image.open(image_path).convert("L")
        img = _upscale_for_small_text(img, lang)
        result = _ocr_with_fallback(img, t_lang, lang, [3, 5])
        if result:
            _cache_result(cache_key, result)
            return result
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
            img = _upscale_for_small_text(img, lang)
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
