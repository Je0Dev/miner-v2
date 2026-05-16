"""Translation, audio recording, clipboard, and notifications."""
import subprocess, threading, time, re
from pathlib import Path
from log import log
from config import LANG_REGISTRY, GOOGLE_LANG_CODES

CJK_RE = re.compile(r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]')
GREEK_RE = re.compile(r'[\u0370-\u03FF]')
CYRILLIC_RE = re.compile(r'[\u0400-\u04FF]')
HANGUL_RE = re.compile(r'[\uac00-\ud7af\u1100-\u11ff]')
LATIN_ACCENT_RE = re.compile(r'[\u00c0-\u024f]')

def _is_valid_for_translation(text: str, lang: str = "zh") -> bool:
    if not text or len(text.strip()) < 2: return False
    script = LANG_REGISTRY.get(lang, {}).get("script", "latin")
    if script == "cjk":
        if lang == "ko" and HANGUL_RE.search(text): return True
        if CJK_RE.search(text): return True
    elif script == "greek" and GREEK_RE.search(text): return True
    elif script == "cyrillic" and CYRILLIC_RE.search(text): return True
    elif script == "latin":
        if LATIN_ACCENT_RE.search(text) or len(text.split()) >= 2: return True
    words = text.split()
    if all(len(w) == 1 and w.isalpha() for w in words): return False
    if len(words) >= 2 and all(len(w) >= 2 for w in words): return True
    return len(text.strip()) >= 3

def translate_text(text: str, src: str = "zh", dest: str = "en") -> str:
    if not _is_valid_for_translation(text, src): return ""
    try:
        from deep_translator import GoogleTranslator
        t = GoogleTranslator(source=GOOGLE_LANG_CODES.get(src, src),
                             target=GOOGLE_LANG_CODES.get(dest, dest))
        result = t.translate(text)
        return result.strip() if result else ""
    except Exception as e:
        log.error(f"Translation failed: {e}")
        return ""

def _find_best_audio_source() -> str:
    try:
        result = subprocess.run(["pactl", "list", "short", "sources"],
                                capture_output=True, text=True)
        sources = result.stdout.splitlines()
        monitors = [s for s in sources if "monitor" in s]
        if monitors:
            for m in monitors:
                parts = m.split("\t")
                if len(parts) > 1 and "null" not in parts[1].lower():
                    return parts[1]
            return monitors[0].split("\t")[1]
        return "alsa_output.pci-0000_00_1b.0.analog-stereo.monitor"
    except Exception:
        return "alsa_output.pci-0000_00_1b.0.analog-stereo.monitor"

def record_audio(output_path: Path, duration: int = 5, source: str = None) -> bool:
    if source is None: source = _find_best_audio_source()
    log.info(f"Recording audio from: {source}")
    cmd = ["ffmpeg", "-y", "-f", "pulse", "-i", source, "-t", str(duration),
           "-acodec", "libmp3lame", "-q:a", "2", "-loglevel", "error", str(output_path)]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for i in range(duration, 0, -1): time.sleep(1)
        proc.wait()
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
