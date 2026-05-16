"""Translation provider fallback: Google → LibreTranslate."""
import subprocess, json
from config import GOOGLE_LANG_CODES
from log import log

def translate_libretranslate(text: str, src: str, dest: str) -> str:
    """Translate using LibreTranslate (self-hosted or public)."""
    try:
        cmd = ["curl", "-s", "-X", "POST", "http://localhost:5000/translate",
               "-H", "Content-Type: application/json",
               "-d", json.dumps({"q": text, "source": src, "target": dest})]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return data.get("translatedText", "").strip()
    except Exception as e:
        log.warning(f"LibreTranslate failed: {e}")
    return ""

def translate_with_fallback(text: str, src: str, dest: str) -> str:
    """Try Google first, fallback to LibreTranslate."""
    # Try Google Translate
    try:
        from deep_translator import GoogleTranslator
        t = GoogleTranslator(source=GOOGLE_LANG_CODES.get(src, src),
                             target=GOOGLE_LANG_CODES.get(dest, dest))
        result = t.translate(text)
        if result and result.strip():
            return result.strip()
    except Exception as e:
        log.warning(f"Google Translate failed: {e}")
    # Fallback to LibreTranslate
    result = translate_libretranslate(text, src, dest)
    if result:
        log.info(f"LibreTranslate fallback succeeded")
        return result
    log.error("All translation providers failed")
    return ""
