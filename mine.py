"""Main mining logic - capture, OCR, translate, save, notify."""
import time
from datetime import datetime
from pathlib import Path
from config import MINING_DIR, AUDIO_DIR, IMAGES_DIR, VIDEO_DIR
from text import clean_text, is_valid_text, is_duplicate, load_history, format_with_pinyin
from ocr import ocr_image
from translate import translate_text, copy_to_clipboard, record_audio, notify
from log import log


def mine_sentence(ocr_lang="zh", translate_to="en", audio_duration=5, source_name="Game",
                  auto_clipboard=True, use_vad=True, push_anki=True) -> dict | None:
    """Execute one complete mining cycle.

    Workflow:
    1. User selects region (slurp)
    2. Capture screenshot + OCR
    3. Translate text
    4. IMMEDIATE notification with text + translation + pinyin
    5. Auto-copy to clipboard for Yomitan
    6. Record audio
    7. Save to session folder + Anki
    8. Confirmation notification
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    sd = MINING_DIR / ts
    sd.mkdir(parents=True, exist_ok=True)
    for d in [AUDIO_DIR, IMAGES_DIR, VIDEO_DIR]:
        (sd / d).mkdir(exist_ok=True)

    log.info(f"Mining: {ocr_lang}->{translate_to}")

    # Step 1: Capture region
    img_path = sd / IMAGES_DIR / "capture.png"
    log.info("Select text region...")
    notify("Mining", "Select text region...", timeout=3000)
    geom = capture_region(img_path)
    if not geom:
        notify("Mining", "Capture cancelled", timeout=3000)
        return None

    # Step 2: OCR
    log.info(f"OCRing region: {geom}")
    text = clean_text(ocr_image(img_path, ocr_lang))
    if not text or len(text) < 2:
        notify("Mining", "No text detected", timeout=3000)
        return None

    log.info(f"OCR result: {text[:60]}")

    # Step 3: Translate
    tr = translate_text(text, src=ocr_lang, dest=translate_to)
    log.info(f"Translation: {tr[:60]}")

    # Step 4: Pinyin (for Chinese)
    py = format_with_pinyin(text) if ocr_lang == "zh" else text

    # Step 5: IMMEDIATE notification with text + translation + pinyin
    body = f"Text: {text[:100]}"
    if py != text:
        body += f"\nPinyin: {py[:100]}"
    if tr:
        body += f"\nTranslation: {tr[:100]}"
    notify("Sentence Captured", body, timeout=12000)

    # Step 6: Auto-copy to clipboard for Yomitan
    if auto_clipboard:
        copy_to_clipboard(text)

    # Step 7: Record audio
    af_path = sd / f"{AUDIO_DIR}/audio_{ts}.mp3"
    log.info(f"Recording {audio_duration}s audio...")
    notify("Mining", f"Recording {audio_duration}s audio...", timeout=3000)
    audio_ok = record_audio(af_path, audio_duration)
    af = f"{AUDIO_DIR}/audio_{ts}.mp3" if audio_ok else ""

    # Step 8: Save entry
    entry = {
        "sentence": text,
        "translation": tr,
        "audio": af,
        "pinyin": py if py != text else "",
        "source": source_name,
        "timestamp": ts,
        "screenshot": f"{IMAGES_DIR}/capture.png",
    }

    # Save to session JSON
    with open(sd / "entry.json", "w", encoding="utf-8") as f:
        import json
        json.dump(entry, f, ensure_ascii=False, indent=2)

    # Append to master sentences.json
    sentences_json = MINING_DIR / "sentences.json"
    all_entries = []
    if sentences_json.exists():
        try:
            with open(sentences_json, "r", encoding="utf-8") as f:
                all_entries = json.load(f)
        except Exception:
            all_entries = []
    all_entries.append(entry)
    with open(sentences_json, "w", encoding="utf-8") as f:
        json.dump(all_entries, f, ensure_ascii=False, indent=2)

    # Append to history
    with open(MINING_DIR / "history_sentences.txt", "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {text} | {tr}\n")

    # Step 9: Confirmation notification
    confirm_body = f"Text: {text[:60]}\nTranslation: {tr[:60]}\nAudio: {'Yes' if audio_ok else 'No'}\nSaved: {sd.name}"
    notify("Sentence Mined", confirm_body, timeout=10000)

    log.info(f"Mining complete: {sd}")
    return entry


# Import capture here to avoid circular imports
from capture import capture_region
