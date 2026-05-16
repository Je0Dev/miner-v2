"""OCR confidence scoring with auto-retry."""
import pytesseract
from PIL import Image
from pathlib import Path
from config import LANG_REGISTRY
from log import log

CONFIDENCE_THRESHOLD = 60
MAX_RETRIES = 3

def get_ocr_confidence(image_path: Path, lang: str, psm: int = 6) -> dict:
    """Get OCR text with confidence scores."""
    t_lang = LANG_REGISTRY.get(lang, {}).get("tess", lang)
    try:
        img = Image.open(image_path).convert("L")
        data = pytesseract.image_to_data(img, config=f"--oem 3 --psm {psm} -l {t_lang}",
                                         output_type=pytesseract.Output.DICT)
        text_parts = []
        confidences = []
        for i, word in enumerate(data.get("text", [])):
            conf = int(data.get("conf", [0])[i])
            if word.strip() and conf > 0:
                text_parts.append(word)
                confidences.append(conf)
        text = " ".join(text_parts).strip()
        avg_conf = sum(confidences) / len(confidences) if confidences else 0
        return {"text": text, "confidence": avg_conf, "word_count": len(confidences)}
    except Exception as e:
        log.error(f"Confidence check failed: {e}")
        return {"text": "", "confidence": 0, "word_count": 0}

def ocr_with_confidence(image_path: Path, lang: str, ocr_func) -> str:
    """OCR with confidence check, retry with different PSM if low."""
    for attempt in range(MAX_RETRIES):
        psm = [6, 3, 5][attempt]
        result = get_ocr_confidence(image_path, lang, psm)
        if result["confidence"] >= CONFIDENCE_THRESHOLD and result["text"]:
            log.info(f"OCR confidence: {result['confidence']:.1f}% (PSM {psm})")
            return result["text"]
        log.warning(f"Low confidence: {result['confidence']:.1f}% (PSM {psm}), retrying...")
    # Final attempt with main OCR function
    text = ocr_func(image_path, lang)
    return text
