"""OCR functions for Game Sentence Miner v2.

Handles Tesseract OCR with preprocessing and caching.
Optimized for game text including borderless window mode (smaller text).
"""
import hashlib, re
from pathlib import Path
try:
    import pytesseract
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps
    import numpy as np
    from scipy.ndimage import grey_closing
except ImportError:
    print("ERROR: pip install pytesseract pillow numpy scipy"); import sys; sys.exit(1)
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


def _detect_and_mask_images(img: Image.Image) -> Image.Image:
    """Detect and mask non-text regions (images/icons) in the capture.
    
    Uses edge density and color variance to find image regions,
    then masks them with white to prevent OCR interference.
    """
    arr = np.array(img)
    h, w = arr.shape
    
    # Split into horizontal strips to find image regions
    strip_h = max(h // 10, 10)
    masked_arr = arr.copy()
    
    for y in range(0, h, strip_h):
        strip = arr[y:y+strip_h, :]
        # High variance = likely image region
        variance = np.var(strip)
        # High edge density = likely image
        edges = np.abs(np.diff(strip, axis=1))
        edge_density = np.mean(edges > 30)
        
        if variance > 800 and edge_density > 0.3:
            # Mask this strip as white (ignore for OCR)
            masked_arr[y:y+strip_h, :] = 255
    
    return Image.fromarray(masked_arr)


def preprocess_image(image_path: Path) -> Image.Image:
    """Preprocess image for better OCR accuracy.

    Optimized for game text including borderless window mode:
    1. Convert to grayscale
    2. Auto-invert if text is light on dark background
    3. Increase contrast (1.5x)
    4. Sharpen to enhance small text
    5. Adaptive binarization using morphological operations
    """
    img = Image.open(image_path).convert("L")
    # Auto-invert if dark background (common in games)
    pixels = list(img.getdata())
    avg_brightness = sum(pixels) / len(pixels)
    if avg_brightness < 100:
        img = ImageOps.invert(img)
    # Increase contrast for better text visibility
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.5)
    # Sharpen to enhance small text edges
    img = img.filter(ImageFilter.SHARPEN)
    # Adaptive binarization using morphological top-hat transform
    # This removes background variations while preserving text
    arr = np.array(img)
    # Create structuring element (larger than text, smaller than background changes)
    h, w = arr.shape
    kernel_size = max(5, min(h, w) // 10)
    if kernel_size % 2 == 0:
        kernel_size += 1
    # Apply morphological closing to get background estimate
    background = grey_closing(arr, size=(kernel_size, kernel_size))
    # Subtract background from original (top-hat transform)
    result = background - arr
    # Invert so text is white on black (for Tesseract)
    result = 255 - result
    # Threshold
    result = (result > 128).astype(np.uint8) * 255
    return Image.fromarray(result)


def preprocess_image_long(image_path: Path) -> Image.Image:
    """Preprocess image optimized for long text/dialogue.

    For larger regions with multiple lines of text:
    1. Convert to grayscale
    2. Moderate contrast (1.3x) to preserve text gradients
    3. Denoise to reduce background artifacts
    4. Adaptive binarization with morphological operations
    """
    img = Image.open(image_path).convert("L")
    # Moderate contrast for long text
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.3)
    # Reduce noise
    img = img.filter(ImageFilter.MedianFilter(size=3))
    # Adaptive binarization using morphological operations
    arr = np.array(img)
    h, w = arr.shape
    kernel_size = max(7, min(h, w) // 8)
    if kernel_size % 2 == 0:
        kernel_size += 1
    background = grey_closing(arr, size=(kernel_size, kernel_size))
    result = background - arr
    result = 255 - result
    result = (result > 128).astype(np.uint8) * 255
    return Image.fromarray(result)


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


def _filter_garbage(text: str, lang: str = "zh") -> str:
    """Filter out OCR garbage like lone 'E' symbols and non-CJK noise."""
    if not text:
        return ""
    # Remove lone Latin characters that are likely OCR errors for CJK
    if lang in ("zh", "ja", "ko"):
        # Remove standalone Latin letters not part of valid words
        text = re.sub(r'(?<![A-Za-z])[A-Za-z](?![A-Za-z])', '', text)
        # Remove repeated single letters like "E E E"
        text = re.sub(r'\b([A-Za-z])\s+\1\b', '', text)
    # Clean up multiple spaces
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def ocr_image(image_path: Path, lang: str = "zh", use_confidence: bool = True) -> str:
    """Extract text from image using Tesseract OCR.

    Tries multiple approaches:
    1. PSM 6 (uniform block) - horizontal text
    2. PSM 3 (fully automatic) - mixed layouts
    3. PSM 5 (vertical text) - vertical Y-axis text
    4. Fallback without preprocessing
    """
    prewarm_tesseract(OCR_LANGS.get(lang, lang))
    t_lang = OCR_LANGS.get(lang, lang)
    
    # Try with preprocessing first
    try:
        img = preprocess_image(image_path)
        
        # Try PSM 6 first (uniform block of text)
        config = f"--oem 3 --psm 6 -l {t_lang}"
        text = pytesseract.image_to_string(img, config=config).strip()
        
        # If empty, try PSM 3 (fully automatic)
        if not text:
            config = f"--oem 3 --psm 3 -l {t_lang}"
            text = pytesseract.image_to_string(img, config=config).strip()
        
        # If still empty, try PSM 5 (vertical text)
        if not text:
            config = f"--oem 3 --psm 5 -l {t_lang}"
            text = pytesseract.image_to_string(img, config=config).strip()
        
        if text:
            text = _ensure_utf8(text)
            return _filter_garbage(text, lang)
    except Exception as e:
        log.warning(f"OCR with preprocessing failed: {e}")
    
    # Fallback: try without preprocessing
    try:
        img = Image.open(image_path).convert("L")
        
        # Try PSM 6
        config = f"--oem 3 --psm 6 -l {t_lang}"
        text = pytesseract.image_to_string(img, config=config).strip()
        
        # Try PSM 3
        if not text:
            config = f"--oem 3 --psm 3 -l {t_lang}"
            text = pytesseract.image_to_string(img, config=config).strip()
        
        # Try PSM 5 (vertical text)
        if not text:
            config = f"--oem 3 --psm 5 -l {t_lang}"
            text = pytesseract.image_to_string(img, config=config).strip()
        
        if text:
            text = _ensure_utf8(text)
            return _filter_garbage(text, lang)
    except Exception as e:
        log.error(f"OCR failed completely: {e}")
    
    return ""


def ocr_long_text(image_path: Path, lang: str = "zh") -> str:
    """Extract text from image optimized for long dialogue/story text.

    Tries multiple approaches:
    1. PSM 3 (fully automatic) - multi-line horizontal
    2. PSM 5 (vertical text) - Y-axis vertical text
    3. Fallback without preprocessing
    """
    prewarm_tesseract(OCR_LANGS.get(lang, lang))
    t_lang = OCR_LANGS.get(lang, lang)
    
    # Try with preprocessing first
    try:
        img = preprocess_image_long(image_path)
        
        # Try PSM 3 (fully automatic)
        config = f"--oem 3 --psm 3 -l {t_lang}"
        text = pytesseract.image_to_string(img, config=config).strip()
        
        # Try PSM 5 (vertical text)
        if not text:
            config = f"--oem 3 --psm 5 -l {t_lang}"
            text = pytesseract.image_to_string(img, config=config).strip()
        
        if text:
            text = _ensure_utf8(text)
            return _filter_garbage(text, lang)
    except Exception as e:
        log.warning(f"OCR long text with preprocessing failed: {e}")
    
    # Fallback: try without preprocessing
    try:
        img = Image.open(image_path).convert("L")
        
        # Try PSM 3
        config = f"--oem 3 --psm 3 -l {t_lang}"
        text = pytesseract.image_to_string(img, config=config).strip()
        
        # Try PSM 5 (vertical text)
        if not text:
            config = f"--oem 3 --psm 5 -l {t_lang}"
            text = pytesseract.image_to_string(img, config=config).strip()
        
        if text:
            text = _ensure_utf8(text)
            return _filter_garbage(text, lang)
    except Exception as e:
        log.error(f"OCR long text failed completely: {e}")
    
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


def ocr_vertical_text(image_path: Path, lang: str = "zh") -> str:
    """Extract vertical (Y-axis) text from image.
    
    Uses PSM 5 (assume a single uniform block of vertically aligned text).
    Also tries rotating the image 90 degrees as a fallback.
    """
    prewarm_tesseract(OCR_LANGS.get(lang, lang))
    t_lang = OCR_LANGS.get(lang, lang)
    
    # Try PSM 5 (vertical text)
    try:
        img = preprocess_image(image_path)
        config = f"--oem 3 --psm 5 -l {t_lang}"
        text = pytesseract.image_to_string(img, config=config).strip()
        if text:
            text = _ensure_utf8(text)
            return _filter_garbage(text, lang)
    except Exception as e:
        log.warning(f"Vertical OCR failed: {e}")
    
    # Fallback: rotate 90 degrees and try horizontal OCR
    try:
        img = Image.open(image_path).convert("L").rotate(90, expand=True)
        img.save('/tmp/rotated_ocr.png')
        text = ocr_image(Path('/tmp/rotated_ocr.png'), lang)
        if text:
            return text
    except Exception as e:
        log.warning(f"Rotated OCR fallback failed: {e}")
    
    return ""
