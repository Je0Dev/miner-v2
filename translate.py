"""Translation, audio recording, clipboard, and notifications."""
import subprocess, threading, time, re
from pathlib import Path
from log import log

# CJK character patterns for validation
CJK_RE = re.compile(r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]')


def _is_valid_for_translation(text: str) -> bool:
    """Check if text is worth translating (not garbage/UI elements)."""
    if not text or len(text.strip()) < 2:
        return False
    # Accept if it has CJK characters (primary indicator of valid text)
    if CJK_RE.search(text):
        return True
    # Reject text that's mostly single Latin letters (OCR garbage)
    latin_only = re.sub(r'[^A-Za-z\s]', '', text)
    if len(latin_only) > len(text) * 0.7:
        return False
    # Reject text with too many special characters
    special_chars = re.findall(r'[^\w\s\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]', text)
    if len(special_chars) > len(text) * 0.3:
        return False
    return True


def translate_text(text: str, src: str = "zh", dest: str = "en") -> str:
    """Translate text using Google Translate. Only translates to English by default."""
    if not _is_valid_for_translation(text):
        return ""
    try:
        from deep_translator import GoogleTranslator
        from config import GOOGLE_LANG_CODES
        t = GoogleTranslator(source=GOOGLE_LANG_CODES.get(src, src),
                             target=GOOGLE_LANG_CODES.get(dest, dest))
        result = t.translate(text)
        return result.strip() if result else ""
    except Exception as e:
        log.error(f"Translation failed: {e}")
        return ""


def _find_best_audio_source() -> str:
    """Find the best audio source for game audio capture."""
    try:
        result = subprocess.run(["pactl", "list", "short", "sources"],
                                capture_output=True, text=True)
        sources = result.stdout.splitlines()
        # Prefer monitor sources (capture desktop/game audio)
        monitors = [s for s in sources if "monitor" in s]
        if monitors:
            # Try to find a non-null monitor first
            for m in monitors:
                parts = m.split("\t")
                if len(parts) > 1 and "null" not in parts[1].lower():
                    return parts[1]
            return monitors[0].split("\t")[1]
        # Fallback to default
        return "alsa_output.pci-0000_00_1b.0.analog-stereo.monitor"
    except Exception:
        return "alsa_output.pci-0000_00_1b.0.analog-stereo.monitor"


def record_audio(output_path: Path, duration: int = 5, source: str = None) -> bool:
    """Record audio from desktop/game. Captures exactly what you hear."""
    if source is None:
        source = _find_best_audio_source()
    log.info(f"Recording audio from: {source}")
    cmd = ["ffmpeg", "-y", "-f", "pulse", "-i", source, "-t", str(duration),
           "-acodec", "libmp3lame", "-q:a", "2", "-loglevel", "error", str(output_path)]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for i in range(duration, 0, -1):
            time.sleep(1)
        proc.wait()
        exists = output_path.exists()
        log.info(f"Audio recording: {'success' if exists else 'failed'}")
        return exists
    except Exception as e:
        log.error(f"Audio recording failed: {e}")
        return False


def copy_to_clipboard(text: str):
    """Copy text to Wayland clipboard."""
    try:
        subprocess.run(["wl-copy"], input=text, text=True, check=True, capture_output=True)
        log.info(f"Copied to clipboard: {text[:50]}")
    except Exception as e:
        log.error(f"Clipboard copy failed: {e}")


def notify(title: str, body: str, timeout: int = 8000):
    """Send desktop notification."""
    try:
        subprocess.run(["notify-send", "-t", str(timeout), "--", title, body],
                       capture_output=True, text=True, timeout=3)
        log.info(f"Notification: [{title}] {body[:80]}")
    except Exception as e:
        log.error(f"Notification failed: {e}")
