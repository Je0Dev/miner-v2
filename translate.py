"""Translation, audio recording, clipboard, and notifications."""
import subprocess, threading, time, re, unicodedata
from pathlib import Path
from log import log
from config import LANG_REGISTRY, GOOGLE_LANG_CODES

CJK_RE = re.compile(r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]')
GREEK_RE = re.compile(r'[\u0370-\u03FF]')
CYRILLIC_RE = re.compile(r'[\u0400-\u04FF]')
HANGUL_RE = re.compile(r'[\uac00-\ud7af\u1100-\u11ff]')
LATIN_ACCENT_RE = re.compile(r'[\u00c0-\u024f]')
CJK_PUNCT = re.compile(r'[。！？、；：""''（）【】《》〈〉]')
COMMON_PUNCT = re.compile(r'[.,!?;:\'"()\[\]{}\-—–]')

def _clean_translation(text: str) -> str:
    """Clean translation output: normalize Unicode, remove weird chars."""
    if not text: return ""
    text = unicodedata.normalize('NFC', text)
    text = text.replace('\ufffd', '').replace('\u200b', '').replace('\ufeff', '')
    text = text.replace('\xa0', ' ').strip()
    return text

def _clean_for_translation(text: str, lang: str) -> str:
    """Clean text BEFORE translation: remove garbage, keep only valid content."""
    if not text: return ""
    script = LANG_REGISTRY.get(lang, {}).get("script", "latin")
    if script == "cjk":
        if lang == "ko":
            # Korean: keep Hangul characters and punctuation
            valid = HANGUL_RE.findall(text) + COMMON_PUNCT.findall(text)
            cleaned = ''.join(valid)
            if len(cleaned) < len(text) * 0.5:
                return ""
            return cleaned
        # Chinese/Japanese: keep CJK characters and CJK punctuation
        valid = CJK_RE.findall(text) + CJK_PUNCT.findall(text)
        cleaned = ''.join(valid)
        if len(cleaned) < len(text) * 0.5:
            return ""
        return cleaned
    elif script == "greek":
        valid = GREEK_RE.findall(text) + COMMON_PUNCT.findall(text)
        cleaned = ''.join(valid)
        if len(cleaned) < len(text) * 0.5:
            return ""
        return cleaned
    elif script == "cyrillic":
        valid = CYRILLIC_RE.findall(text) + COMMON_PUNCT.findall(text)
        cleaned = ''.join(valid)
        if len(cleaned) < len(text) * 0.5:
            return ""
        return cleaned
    else:
        # Latin: keep letters, accents, and punctuation
        valid = re.findall(r'[\w\u00c0-\u024f.,!?;:\'"()\[\]{}\-—–\s]', text)
        return ''.join(valid).strip()

def _is_valid_for_translation(text: str, lang: str = "zh") -> bool:
    if not text or len(text.strip()) < 2: return False
    script = LANG_REGISTRY.get(lang, {}).get("script", "latin")
    if script == "cjk":
        if lang == "ko":
            hangul = HANGUL_RE.findall(text)
            if len(hangul) < 2: return False
            total = len(text.replace(' ', ''))
            if total > 0 and len(hangul) / total < 0.6: return False
            return True
        cjk_chars = CJK_RE.findall(text)
        if len(cjk_chars) < 2: return False
        total = len(text.replace(' ', ''))
        if total > 0 and len(cjk_chars) / total < 0.6: return False
        return True
    elif script == "greek":
        greek = GREEK_RE.findall(text)
        if len(greek) < 2: return False
        total = len(text.replace(' ', ''))
        if total > 0 and len(greek) / total < 0.6: return False
        return True
    elif script == "cyrillic":
        cyr = CYRILLIC_RE.findall(text)
        if len(cyr) < 2: return False
        total = len(text.replace(' ', ''))
        if total > 0 and len(cyr) / total < 0.6: return False
        return True
    elif script == "latin":
        if LATIN_ACCENT_RE.search(text) or len(text.split()) >= 2: return True
        words = text.split()
        if len(words) > 8 and all(len(w) <= 2 for w in words): return False
        if all(len(w) == 1 and w.isalpha() for w in words): return False
        if len(words) >= 2 and all(len(w) >= 2 for w in words): return True
        return len(text.strip()) >= 3
    return False

def translate_text(text: str, src: str = "zh", dest: str = "en") -> str:
    # Clean text first to remove garbage
    cleaned = _clean_for_translation(text, src)
    if not _is_valid_for_translation(cleaned, src): return ""
    try:
        from deep_translator import GoogleTranslator
        t = GoogleTranslator(source=GOOGLE_LANG_CODES.get(src, src),
                             target=GOOGLE_LANG_CODES.get(dest, dest))
        result = t.translate(cleaned)
        return _clean_translation(result.strip()) if result else ""
    except Exception as e:
        log.error(f"Translation failed: {e}")
        return ""

def _find_best_audio_source() -> str | None:
    try:
        result = subprocess.run(["pactl", "list", "short", "sources"],
                                capture_output=True, text=True, timeout=5)
        sources = result.stdout.splitlines()
        monitors = [s for s in sources if "monitor" in s]
        if monitors:
            for m in monitors:
                parts = m.split("\t")
                if len(parts) > 1 and "null" not in parts[1].lower():
                    return parts[1]
            return monitors[0].split("\t")[1]
        return None
    except Exception:
        return None

def _test_audio_source(source: str) -> bool:
    """Test if audio source is actually working."""
    try:
        result = subprocess.run(["ffmpeg", "-y", "-f", "pulse", "-i", source,
                                 "-t", "1", "-acodec", "pcm_s16le", "-f", "null", "-"],
                                capture_output=True, timeout=3)
        return result.returncode == 0
    except Exception:
        return False

def record_audio(output_path: Path, duration: int = 5, source: str = None) -> bool:
    """Record audio from desktop/game. Returns False gracefully if no audio available."""
    if source is None:
        source = _find_best_audio_source()
    if source is None:
        log.warning("No audio source found, skipping recording")
        return False
    if not _test_audio_source(source):
        log.warning(f"Audio source {source} not working, skipping recording")
        return False
    log.info(f"Recording audio from: {source}")
    cmd = ["ffmpeg", "-y", "-f", "pulse", "-i", source, "-t", str(duration),
           "-acodec", "libmp3lame", "-q:a", "2", "-loglevel", "error", str(output_path)]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for i in range(duration, 0, -1): time.sleep(1)
        proc.wait(timeout=duration + 5)
        exists = output_path.exists()
        log.info(f"Audio recording: {'success' if exists else 'failed'}")
        return exists
    except Exception as e:
        log.error(f"Audio recording failed: {e}")
        return False

def copy_to_clipboard(text: str):
    try:
        subprocess.run(["wl-copy"], input=text, text=True, check=True, capture_output=True)
        log.info(f"Copied to clipboard: {text[:50]}")
    except Exception as e:
        log.error(f"Clipboard copy failed: {e}")

def notify(title: str, body: str, timeout: int = 8000):
    try:
        subprocess.run(["notify-send", "-t", str(timeout), "--", title, body],
                       capture_output=True, text=True, timeout=3)
        log.info(f"Notification: [{title}] {body[:80]}")
    except Exception as e:
        log.error(f"Notification failed: {e}")
