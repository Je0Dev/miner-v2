"""Multi-Engine Parallel Translation - Google + LibreTranslate + MyMemory ranked display."""
import threading, json, subprocess, time
from pathlib import Path
from log import log
from config import GOOGLE_LANG_CODES

_translation_cache = {}

def translate_google(text: str, src: str, dest: str) -> str:
    """Translate using Google Translate (deep-translator)."""
    try:
        from deep_translator import GoogleTranslator
        t = GoogleTranslator(source=GOOGLE_LANG_CODES.get(src, src),
                             target=GOOGLE_LANG_CODES.get(dest, dest))
        result = t.translate(text)
        return result.strip() if result else ""
    except Exception as e:
        log.warning(f"Google Translate failed: {e}")
        return ""

def translate_libre(text: str, src: str, dest: str) -> str:
    """Translate using LibreTranslate (self-hosted or public)."""
    try:
        cmd = ["curl", "-s", "-X", "POST", "http://localhost:5000/translate",
               "-H", "Content-Type: application/json",
               "-d", json.dumps({"q": text, "source": src, "target": dest})]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return data.get("translatedText", "").strip()
    except Exception as e:
        log.warning(f"LibreTranslate failed: {e}")
    return ""

def translate_mymemory(text: str, src: str, dest: str) -> str:
    """Translate using MyMemory API (free, no auth)."""
    try:
        import urllib.request
        pair = f"{src}|{dest}"
        url = f"https://api.mymemory.translated.net/get?q={urllib.request.quote(text)}&langpair={pair}"
        req = urllib.request.Request(url)
        resp = urllib.request.urlopen(req, timeout=5)
        data = json.loads(resp.read())
        return data.get("responseData", {}).get("translatedText", "").strip()
    except Exception as e:
        log.warning(f"MyMemory failed: {e}")
    return ""

def translate_parallel(text: str, src: str, dest: str, engines=None) -> dict:
    """Run multiple translation engines in parallel, return ranked results."""
    if engines is None:
        engines = ["google", "libre", "mymemory"]

    results = {}
    threads = {}

    def _run(name, func):
        results[name] = func(text, src, dest)

    engine_map = {"google": translate_google, "libre": translate_libre, "mymemory": translate_mymemory}

    for name in engines:
        if name in engine_map:
            t = threading.Thread(target=_run, args=(name, engine_map[name]), daemon=True)
            threads[name] = t
            t.start()

    # Wait up to 8 seconds for all engines
    for name, t in threads.items():
        t.join(timeout=8)

    # Rank results by length similarity to source and presence
    ranked = []
    src_len = len(text)
    for name, result in results.items():
        if result and len(result) > 2:
            # Score: prefer results close to 1.5x source length (typical translation ratio)
            ratio = len(result) / max(src_len, 1)
            score = 1.0 - abs(ratio - 1.5) / 2.0
            ranked.append({"engine": name, "text": result, "score": max(0, score)})

    ranked.sort(key=lambda x: x["score"], reverse=True)
    return {"results": ranked, "best": ranked[0]["text"] if ranked else "",
            "all": {r["engine"]: r["text"] for r in ranked}}

def translate_text(text: str, src: str = "zh", dest: str = "en", parallel=False) -> str:
    """Translate text. If parallel=True, uses multi-engine; otherwise Google only."""
    cache_key = f"{'p' if parallel else 's'}:{src}:{dest}:{text}"
    if cache_key in _translation_cache:
        return _translation_cache[cache_key]

    if parallel:
        result = translate_parallel(text, src, dest)
        best = result["best"]
        if best:
            _translation_cache[cache_key] = best
            if len(_translation_cache) > 1000:
                keys = list(_translation_cache.keys())
                for k in keys[:500]:
                    del _translation_cache[k]
        return best
    else:
        return translate_google(text, src, dest)
