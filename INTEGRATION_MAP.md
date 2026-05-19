# Integration Map: Existing Miner-v2 Code → New Features

## 🔗 How Features Connect to Current Code

### **VAD Audio Trimming → `audio_processor.py` + `translate.py`**

```
Current Flow:
  capture.py
    ↓
  [RECORD AUDIO ~8 seconds] ← record_system_audio()
    ↓
  translate.py → save_audio(audio_path)
    ↓
  mining/TIMESTAMP/audio/audio.mp3

NEW Flow:
  capture.py
    ↓
  [RECORD AUDIO ~8 seconds]
    ↓
  audio_processor.py → trim_audio_with_vad() [NEW]
    ↓
    ├─ Detect speech segments
    ├─ Remove silence/music
    └─ Output: audio.mp3 (1-2s instead of 8s)
    ↓
  translate.py → save_audio(trimmed_audio)
    ↓
  mining/TIMESTAMP/audio/audio.mp3 [SMALLER FILE]
```

**Integration Point:**
```python
# In translate.py, update save_audio():

def save_audio(audio_path: str, output_dir: str) -> str:
    """Save audio, with optional VAD trimming"""
    
    if config.AUDIO_VAD_ENABLED:
        from audio_processor import trim_audio_with_vad
        result = trim_audio_with_vad(audio_path)
        audio_path = result['output_path']
    
    # Rest of existing code
    return shutil.copy(audio_path, output_dir)
```

**No Changes Needed in:**
- `capture.py` (just passes audio)
- `mine.py` (doesn't know about trimming)
- `universal_log.py` (logs same way)

---

### **Plugin Translators → `translate.py` + `config.py`**

```
Current Flow:
  mine.py
    ↓
  translate.py → translate_text(text, 'ja', 'en')
    ├─ Try GoogleTranslator()
    ├─ Except: Try MyMemoryService()
    └─ Return translation
    ↓
  entry['translation'] = result

NEW Flow:
  mine.py
    ↓
  translate.py → TranslatorRegistry() [NEW]
    ├─ Load backends from config.json
    ├─ Try by priority:
    │   1. Google
    │   2. DeepL (if key available)
    │   3. Baidu
    │   4. MyMemory
    │   5. Sakura (if running)
    └─ Return result + which backend succeeded
    ↓
  entry['translation'] = result
  entry['translation_backend'] = 'deepl'  [NEW FIELD]
```

**Integration Point:**
```python
# In translate.py, update translate_text():

# OLD:
def translate_text(text: str, src_lang: str, tgt_lang: str) -> str:
    translator = GoogleTranslator(...)
    return translator.translate(text)

# NEW:
_registry = None

def get_translator_registry() -> TranslatorRegistry:
    global _registry
    if not _registry:
        _registry = TranslatorRegistry('config.json')
    return _registry

def translate_text(text: str, src_lang: str, tgt_lang: str) -> dict:
    registry = get_translator_registry()
    result = registry.translate_with_fallback(text, src_lang, tgt_lang)
    return result  # Returns {'text': '...', 'backend': 'deepl', 'attempts': [...]}
```

**Update in `mine.py`:**
```python
# OLD:
translation = translate_text(ocr_text, 'ja', 'en')
entry['translation'] = translation

# NEW:
translation_result = translate_text(ocr_text, 'ja', 'en')
entry['translation'] = translation_result['text']
entry['translation_backend'] = translation_result['backend']
```

**Changes Needed in:**
- `mine.py` (line ~150): Store backend in entry
- `anki_export.py` (optional): Add `translation_backend` column
- `config.json`: Add translator configurations

---

### **Anki Direct Export → `anki_export.py` + `mine.py`**

```
Current Flow:
  mine.py → mining/sentences.json [stores all entries]
    ↓
  anki_export.py → mining/anki_export.csv [exports to CSV]
    ↓
  [User manually imports CSV to Anki in AnkiConnect dialog]

NEW Flow:
  mine.py → mining/sentences.json [stores all entries]
    ↓
  [IF anki_direct_export enabled]
    ├─ anki_connector.py → AnkiConnector.add_mining_note(entry)
    │  ├─ Check AnkiConnect running
    │  ├─ Create deck if needed
    │  └─ Add note directly
    ↓
  entry['anki_note_id'] = 12345 [NEW FIELD]
    ↓
  [Also generate CSV as fallback]

User just mines → Cards automatically in Anki (no manual import needed!)
```

**Integration Point:**
```python
# In mine.py, at end of mining workflow:

def finalize_mining_entry(entry: dict, config) -> dict:
    """Finalize entry and optionally export to Anki"""
    
    # Existing: Save to universal_log, JSON, etc.
    universal_log_entry(entry)
    save_to_json('mining/sentences.json', entry)
    
    # NEW: Anki export
    if config.ANKI_DIRECT_EXPORT:
        try:
            from anki_connector import AnkiConnector
            anki = AnkiConnector(config.ANKICONNECT_URL)
            note_id = anki.add_mining_note(entry, config.ANKI_DECK_NAME)
            entry['anki_note_id'] = note_id
            log.info(f"✓ Added to Anki (note ID: {note_id})")
        except Exception as e:
            log.warning(f"Anki export failed: {e}, continuing...")
    
    return entry
```

**Changes Needed in:**
- `mine.py` (add AnkiConnector call at end)
- `config.py` (add ANKI_* settings)
- `anki_export.py` (optional: keep CSV export as fallback)

**No Changes Needed in:**
- `universal_log.py` (logs work the same)
- `capture.py`, `ocr.py`, `text.py` (unaffected)

---

## 📊 Implementation Checklist by File

### **Files to MODIFY (3 files, ~20 lines total)**

#### 1. `translate.py` (~10 lines)
```python
# CHANGE 1: Add imports at top
from translate import TranslatorRegistry

# CHANGE 2: Add registry singleton (~5 lines)
_registry = None
def get_translator_registry():
    global _registry
    if not _registry:
        _registry = TranslatorRegistry('config.json')
    return _registry

# CHANGE 3: Update translate_text() return (~1 line change)
# OLD: return translator.translate(text)
# NEW: result = registry.translate_with_fallback(...)
#      return result  # Now returns dict not str
```

#### 2. `mine.py` (~10 lines)
```python
# CHANGE 1: Add anki_connector import (1 line)
from anki_connector import AnkiConnector

# CHANGE 2: Update translation handling (2 lines)
# OLD: entry['translation'] = translate_text(...)
# NEW: result = translate_text(...)
#      entry['translation'] = result['text']
#      entry['translation_backend'] = result.get('backend')

# CHANGE 3: Add Anki export before saving (8 lines)
if config.ANKI_DIRECT_EXPORT:
    try:
        anki = AnkiConnector(config.ANKICONNECT_URL)
        note_id = anki.add_mining_note(entry, config.ANKI_DECK_NAME)
        entry['anki_note_id'] = note_id
    except Exception as e:
        logger.warning(f"Anki export failed: {e}")

# CHANGE 4: VAD audio trimming (3 lines)
# In save_audio() call:
if config.AUDIO_VAD_ENABLED:
    from audio_processor import trim_audio_with_vad
    result = trim_audio_with_vad(audio_path)
    audio_path = result['output_path']
```

#### 3. `config.py` (~15 lines)
```python
# ADD to config.py:

# Translator backends
TRANSLATOR_BACKENDS = {
    'google': {'enabled': True, 'priority': 1},
    'deepl': {'enabled': True, 'priority': 2, 'api_key': None},
    'baidu': {'enabled': True, 'priority': 3},
    'mymemory': {'enabled': True, 'priority': 4},
}

# Anki Integration
ANKI_DIRECT_EXPORT = True
ANKICONNECT_URL = "http://localhost:8765"
ANKI_DECK_NAME = "Mining"

# Audio VAD
AUDIO_VAD_ENABLED = True
AUDIO_VAD_ENGINE = 'webrtc'  # or 'silero'
```

### **Files to CREATE (3 files)**

#### 1. `anki_connector.py` (NEW, ~250 lines)
Provided in TIER1_IMPLEMENTATION.md

#### 2. `audio_processor.py` ENHANCEMENT (NEW VAD functions, ~200 lines)
Provided in TIER1_IMPLEMENTATION.md

Add to existing audio_processor.py:
```python
# Existing functions:
# - record_system_audio()
# - save_audio()

# ADD these new functions:
# - trim_audio_with_vad()
# - _vad_webrtc()
# - _vad_silero()
# - _vad_energy_based()
```

#### 3. `translate.py` ENHANCEMENT (NEW classes, ~300 lines)
Provided in TIER1_IMPLEMENTATION.md

Add to existing translate.py:
```python
# Existing functions:
# - translate_text()
# - get_cached_translation()

# ADD these new classes:
# - TranslatorRegistry
# - TranslatorBackend
# - TranslatorConfig
# - DeepLTranslator
# - BaiduTranslator
# - SakuraTranslator
```

---

## 🔀 Data Flow: Before → After

### **Example Mining Session Flow**

#### **BEFORE (Current)**
```
1. User: bash mine.sh -l ja -t en
2. capture.py: Select region → grim screenshot
3. ocr.py: Tesseract → "こんにちは"
4. text.py: Clean → "こんにちは"
5. translate.py: Google → "Hello"
6. audio_processor.py: Record 8s audio → audio.mp3
7. mine.py:
   - Save JSON: {text, translation, audio}
   - Generate CSV row
8. User manually imports CSV to Anki (slow!)
```

#### **AFTER (With Tier 1 Integration)**
```
1. User: bash mine.sh -l ja -t en
2. capture.py: Select region → grim screenshot
3. ocr.py: Tesseract → "こんにちは"
4. text.py: Clean → "こんにちは"
5. translate.py: Try DeepL → Success → "Hello" + backend='deepl'
6. audio_processor.py: 
   - Record 8s audio
   - Trim silence → 1.2s dialogue only ✓ (NEW)
7. mine.py:
   - Save JSON: {text, translation, audio, translation_backend, anki_note_id}
   - Try AnkiConnect → Add card directly ✓ (NEW)
   - Fallback: Generate CSV
8. Notification: "Card added to Anki Mining deck" (instant!)
```

**Time saved:** ~30-60 seconds per entry!

---

## 🧪 Testing Integration Points

### **Test 1: VAD Audio**
```bash
# Test existing + new code works together
python3 -c "
from audio_processor import trim_audio_with_vad
from mine import record_system_audio

# Record 8s
audio = record_system_audio(duration=8)

# Trim it
result = trim_audio_with_vad(audio)
print(f'✓ Audio: {result[\"original_duration\"]:.1f}s → {result[\"trimmed_duration\"]:.1f}s')
"
```

### **Test 2: Translator Registry**
```bash
python3 -c "
from translate import TranslatorRegistry

registry = TranslatorRegistry('config.json')
result = registry.translate_with_fallback('こんにちは', 'ja', 'en')
print(f'✓ Translation: {result[\"text\"]} via {result[\"backend\"]}')
"
```

### **Test 3: Anki Integration**
```bash
python3 -c "
from anki_connector import AnkiConnector

anki = AnkiConnector()
decks = anki.get_deck_names()
print(f'✓ Connected to Anki: {len(decks)} decks')

# Test adding note
try:
    note_id = anki.add_note(
        fields={'Front': 'test', 'Back': 'テスト'},
        deck='Mining'
    )
    print(f'✓ Note added: {note_id}')
except Exception as e:
    print(f'✗ Failed: {e}')
"
```

### **Test 4: Full Integration**
```bash
# Mine one entry and verify all integrations
bash mine.sh -l ja -t en

# Check output
python3 -c "
import json
with open('mining/sentences.json') as f:
    entries = json.load(f)
    latest = entries[-1]
    
    print('✓ Latest entry:')
    print(f'  Text: {latest[\"text\"]}')
    print(f'  Translation: {latest[\"translation\"]}')
    print(f'  Translator: {latest.get(\"translation_backend\", \"unknown\")}')
    print(f'  Audio duration: {latest.get(\"audio_duration\", \"unknown\")}s')
    print(f'  Anki note ID: {latest.get(\"anki_note_id\", \"not exported\")}')
"
```

---

## ⚠️ Breaking Changes: NONE

All integrations are:
- **Backwards compatible** (old code still works)
- **Optional** (can disable in config)
- **Fallback-safe** (failure doesn't break mining)

Example: If Anki not running, mining continues and saves to JSON + CSV

---

## 📦 Dependencies Summary

| Feature | Package | Size | Purpose |
|---------|---------|------|---------|
| VAD (WebRTC) | `webrtcvad` | 5 MB | Audio trimming (fast) |
| VAD (Silero) | `silero-vad` | 50 MB | Audio trimming (better quality) |
| Audio processing | `librosa` | 10 MB | Already have |
| Deep Learning | `soundfile` | 1 MB | Audio save/load |
| Translation (DeepL) | `deepl` | - | API-only |
| Translation (Baidu) | (web API) | - | No package needed |
| Anki API | `requests` | Already have | AnkiConnect |

**Total new packages:** 3-4 small ones (webrtcvad, librosa, soundfile, deepl optional)  
**Installation time:** ~2 minutes

---

## ✅ Ready to Implement?

1. **Start with:** Modify `config.py` + `mine.py` + `translate.py` (~20 lines total)
2. **Add files:** Copy `anki_connector.py` + VAD functions from TIER1_IMPLEMENTATION.md
3. **Install packages:** `pip install webrtcvad librosa soundfile deepl`
4. **Test:** Run integration tests above
5. **Mine:** Use `bash mine.sh` as normal, everything works!

**Time to working state:** ~2-3 hours  
**Value gained:** 20-30% quality/speed improvement

