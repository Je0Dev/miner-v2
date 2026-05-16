"""Batch processing - process multiple screenshots at once."""
import json
from pathlib import Path
from config import MINING_DIR, IMAGES_DIR
from ocr import ocr_image
from translate import translate_text
from text import get_pronunciation
from log import log

def batch_process(image_dir: Path, lang: str = "zh", translate_to: str = "en") -> list:
    """Process all images in directory."""
    results = []
    images = sorted(image_dir.glob("*.png")) + sorted(image_dir.glob("*.jpg"))
    log.info(f"Batch processing {len(images)} images")
    for i, img_path in enumerate(images):
        log.info(f"Processing {i+1}/{len(images)}: {img_path.name}")
        text = ocr_image(img_path, lang)
        if not text or len(text) < 2:
            log.warning(f"No text in {img_path.name}")
            continue
        tr = translate_text(text, src=lang, dest=translate_to)
        pron = get_pronunciation(text, lang)
        entry = {
            "sentence": text, "translation": tr,
            "pronunciation": pron, "lang": lang,
            "source": f"batch:{img_path.name}",
            "timestamp": "", "screenshot": str(img_path),
        }
        results.append(entry)
    # Save results
    sentences_json = MINING_DIR / "sentences.json"
    all_entries = []
    if sentences_json.exists():
        try:
            with open(sentences_json, "r", encoding="utf-8") as f:
                all_entries = json.load(f)
        except Exception: pass
    all_entries.extend(results)
    with open(sentences_json, "w", encoding="utf-8") as f:
        json.dump(all_entries, f, ensure_ascii=False, indent=2)
    log.info(f"Batch complete: {len(results)} sentences extracted")
    return results
