"""Dictionary lookups for word definitions - CC-CEDict (Chinese), JMdict (Japanese)."""
import re, json, os
from pathlib import Path
from config import MINING_DIR
from log import log

DICT_DIR = MINING_DIR / "dict"
DICT_DIR.mkdir(parents=True, exist_ok=True)
CCEDICT_FILE = DICT_DIR / "cedict_ts.u8"
JMDICT_FILE = DICT_DIR / "jmdict_cache.json"

def _download_ccedict():
    """Download CC-CEDict dictionary."""
    if CCEDICT_FILE.exists() and CCEDICT_FILE.stat().st_size > 1000:
        return True
    try:
        import urllib.request
        url = "https://www.mdbg.net/chinese/export/cedict/cedict_1_0_ts_utf-8_mdbg.txt.gz"
        import gzip
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=30)
        data = gzip.decompress(resp.read())
        CCEDICT_FILE.write_bytes(data)
        log.info(f"CC-CEDict downloaded ({CCEDICT_FILE.stat().st_size} bytes)")
        return True
    except Exception as e:
        log.warning(f"CC-CEDict download failed: {e}")
        return False

def _parse_ccedict_line(line: str) -> dict | None:
    """Parse a CC-CEDict line: 傳統 传统 [chuan2 tong3] /traditional/."""
    m = re.match(r'^(\S+)\s+(\S+)\s+\[([^\]]+)\]\s+/(.+)/', line)
    if not m: return None
    return {"traditional": m.group(1), "simplified": m.group(2),
            "pinyin": m.group(3), "definitions": m.group(4).split("/")}

_ccedict_cache = {}
_ccedict_loaded = False

def _load_ccedict():
    global _ccedict_loaded, _ccedict_cache
    if _ccedict_loaded: return
    if not CCEDICT_FILE.exists():
        _download_ccedict()
    if not CCEDICT_FILE.exists():
        _ccedict_loaded = True
        return
    try:
        with open(CCEDICT_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"): continue
                entry = _parse_ccedict_line(line)
                if entry:
                    key = entry["simplified"]
                    if key not in _ccedict_cache:
                        _ccedict_cache[key] = []
                    _ccedict_cache[key].append(entry)
                    # Also index by traditional
                    tkey = entry["traditional"]
                    if tkey != key:
                        if tkey not in _ccedict_cache:
                            _ccedict_cache[tkey] = []
                        _ccedict_cache[tkey].append(entry)
        log.info(f"CC-CEDict loaded: {len(_ccedict_cache)} entries")
    except Exception as e:
        log.warning(f"CC-CEDict load failed: {e}")
    _ccedict_loaded = True

def lookup_chinese(word: str) -> list[dict]:
    """Look up Chinese word in CC-CEDict."""
    _load_ccedict()
    return _ccedict_cache.get(word, [])

def _lookup_japanese_online(word: str) -> list[dict]:
    """Look up Japanese word via Jisho.org API."""
    try:
        import urllib.request
        url = f"https://jisho.org/api/v1/search/words?keyword={urllib.request.quote(word)}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=5)
        data = json.loads(resp.read())
        results = []
        for entry in data.get("data", [])[:3]:
            senses = entry.get("senses", [])
            defs = []
            for s in senses:
                defs.extend(s.get("english_definitions", []))
            readings = entry.get("japanese", [])
            reading = readings[0].get("reading", "") if readings else ""
            results.append({"word": word, "reading": reading, "definitions": defs[:5]})
        return results
    except Exception as e:
        log.warning(f"Jisho lookup failed: {e}")
    return []

def lookup_japanese(word: str) -> list[dict]:
    """Look up Japanese word."""
    return _lookup_japanese_online(word)

def lookup_korean(word: str) -> list[dict]:
    """Look up Korean word via Naver API."""
    try:
        import urllib.request
        url = f"https://krdict.korean.go.kr/api/search?key=demo&part=word&q={urllib.request.quote(word)}&type=search"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=5)
        data = resp.read().decode("utf-8")
        m = re.findall(r'<item>(.*?)</item>', data, re.DOTALL)
        results = []
        for item in m[:3]:
            word_m = re.search(r'<word>(.*?)</word>', item)
            def_m = re.search(r'<meaning>(.*?)</meaning>', item)
            if word_m and def_m:
                results.append({"word": word_m.group(1), "definition": def_m.group(1)})
        return results
    except Exception as e:
        log.warning(f"Korean lookup failed: {e}")
    return []

def get_definition(word: str, lang: str = "zh") -> list[str]:
    """Get definitions for a word in the given language."""
    if lang == "zh":
        entries = lookup_chinese(word)
        if entries:
            defs = []
            for e in entries:
                defs.extend(e.get("definitions", []))
            return list(dict.fromkeys(defs))[:5]
    elif lang == "ja":
        entries = lookup_japanese(word)
        if entries:
            defs = []
            for e in entries:
                defs.extend(e.get("definitions", []))
            return list(dict.fromkeys(defs))[:5]
    elif lang == "ko":
        entries = lookup_korean(word)
        if entries:
            return [e.get("definition", "") for e in entries if e.get("definition")]
    return []

def enrich_word_breakdown(text: str, lang: str = "zh") -> list[dict]:
    """Get word breakdown with definitions included."""
    from text import get_word_breakdown, get_pronunciation
    words = get_word_breakdown(text, lang)
    enriched = []
    for w in words:
        word = w.get("word", "")
        if not word: continue
        defs = get_definition(word, lang)
        entry = {"word": word}
        if lang == "zh":
            entry["pinyin"] = w.get("pinyin", "")
        elif lang == "ja":
            entry["romaji"] = w.get("romaji", "")
        entry["definitions"] = defs
        entry["definition_short"] = defs[0] if defs else ""
        enriched.append(entry)
    return enriched

def format_definition_display(text: str, lang: str = "zh") -> str:
    """Format word breakdown with definitions for display."""
    words = enrich_word_breakdown(text, lang)
    if not words: return ""
    lines = []
    for w in words:
        word = w.get("word", "")
        pron = w.get("pinyin", "") or w.get("romaji", "")
        defn = w.get("definition_short", "")
        if pron and defn:
            lines.append(f"{word} → {pron}: {defn}")
        elif pron:
            lines.append(f"{word} → {pron}")
        else:
            lines.append(word)
    return " | ".join(lines)
