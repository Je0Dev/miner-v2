# Miner-v2: Feature Integration from LunaTranslator & GameSentenceMiner

## 🎯 What to Add & Where

### **Tier 1: High-Value, Quick Integration (Week 1)**

#### 1.1 **Voice Activity Detection (VAD) - Auto-trim Audio**
**Source:** GameSentenceMiner/vad.py
**Solves:** Audio clips full of silence, music, or background noise

**Integration Point:** `audio_processor.py` (NEW)
```python
# Add to existing audio capture workflow
from silero_vad import load_silero_vad  # or other VAD

def trim_audio_to_speech(audio_path: str) -> str:
    """Remove silence from captured audio, keep only dialogue"""
    # Detect speech segments
    # Export only dialogue parts (0.5s-8s windows)
    # Return trimmed MP3
```

**Code Size:** ~80 lines  
**Dependencies:** `silero-vad` (5 MB) OR `webrtcvad` (small)  
**Location in miner-v2:** Replace raw audio saving with VAD-trimmed version  
**Anki Field:** Keep duration, show in card (e.g., "1.2s dialogue vs 8s raw")

---

#### 1.2 **Plugin Translation Backends (LunaTranslator Style)**
**Source:** LunaTranslator/translator/*.py (50+ backends)
**Solves:** Single translation service limitation

**Integration Point:** Extend `translate.py`
```python
# Instead of hardcoded services, load translator plugins
class TranslatorRegistry:
    def __init__(self):
        self.backends = {}
        self.load_backends_from_plugins()
    
    def get_translator(self, name: str) -> TranslatorBackend:
        """Return translator: 'google', 'deepl', 'sakura', etc."""
```

**Code Size:** ~150 lines  
**Integration:** `python3 main.py --translate-backend deepl --text "hello"`  
**Dependencies:** Just add DeepL, Sakura config (no new packages if using web APIs)

**Start With:**
- Google (existing) + MyMemory (existing)
- Add: DeepL (free tier), Baidu (CJK expert)
- Backend registration in config.py

---

#### 1.3 **Direct Anki Integration (Like GSM)**
**Source:** GameSentenceMiner/anki.py
**Solves:** Exporting to CSV then manual import is slow

**Integration Point:** New `anki_connector.py`
```python
# Connect directly to AnkiConnect (requires Anki running)
class AnkiConnector:
    def add_note(self, fields: dict, tags: list) -> int:
        """Create card directly in Anki via AnkiConnect API"""
        # Returns note ID or raises exception
    
    def create_deck(self, name: str) -> bool:
        """Auto-create mining deck"""
```

**Code Size:** ~100 lines  
**Dependencies:** `requests` (already have)  
**Setup:** User installs AnkiConnect extension (1 min)  
**UX:** `python3 main.py --anki-deck "Japanese-Mining" --add-to-anki`

---

### **Tier 2: Medium-Value Features (Week 2)**

#### 2.1 **Stats Dashboard Like GSM**
**Source:** GameSentenceMiner stats tracking  
**Shows:** Mined sentences/day, vocabulary coverage, kanji distribution

**Integration Point:** New `stats.py` (extend existing)
```python
# Existing: mine.py → universal_log.py
# Add: Track mining velocity, language frequency, sources

class MiningStats:
    def daily_summary(self) -> dict:
        """Cards today, week, month"""
    
    def language_distribution(self) -> dict:
        """% sentences per language"""
    
    def source_stats(self) -> dict:
        """Top 10 games mined from"""
```

**Display:** Terminal table or JSON export  
**Integration:** Add `python3 main.py --stats` (already exists, improve it)

---

#### 2.2 **Multi-OCR with Engine Switching (LunaTranslator Approach)**
**Source:** LunaTranslator/ocrengines/*.py  
**Improves:** Already planned in IMPROVEMENTS, but structured like Luna

**Integration Point:** `ocr.py` refactor
```python
# Instead of: try tesseract, fallback to easy
# Do: Load OCR engines from registry (Tesseract, EasyOCR, Paddle, Google Vision)

class OCRRegistry:
    engines = {
        'tesseract': TesseractOCREngine,
        'easyocr': EasyOCREngine,
        'paddle': PaddleOCREngine,
        'google': GoogleVisionEngine,  # Premium fallback
    }
```

**Config in zones.json:**
```json
{
  "zones": [{
    "name": "dialogue",
    "ocr_engine": "easyocr",  // per-zone override
    "ocr_backup": ["tesseract", "paddle"]
  }]
}
```

---

#### 2.3 **Game State Snapshot with Mining**
**Source:** GSM stores screenshots + GIF context  
**Solves:** Cards lack context (where/when in game)

**Integration Point:** Extend `mine.py`
```python
# When mining sentence, also:
# 1. Save screenshot (already doing)
# 2. Store game name from Yomitan/zone
# 3. Create card field: "Context: [game screenshot link]"

entry = {
    'text': 'dialogue',
    'game': 'Elden Ring',  # NEW
    'timestamp': '20260516_093000',
    'screenshot': 'mining/20260516_093000/screenshot.png',  # NEW
    'context': 'NPC: Melina at Roundtable Hold',  # NEW (manual or auto)
}
```

**Anki Field:** 6th field = `<img src="file:///path/screenshot.png" />`

---

### **Tier 3: Advanced Features (Week 3+)**

#### 3.1 **AI Translation (Claude/GPT) Like GSM**
**Source:** GSM/ai/service.py, contracts.py  
**Adds:** Context-aware translation, cultural notes

**Integration Point:** New `ai_translation.py`
```python
# If user has Claude/ChatGPT API key, use for better translations
class AITranslator:
    def translate_with_context(self, text: str, prev_text: str, 
                              speaker: str, game: str) -> str:
        """
        Example: Japanese: 「約束だ」
        Context: Quest complete, NPC gratitude
        Output: "It's a promise." (vs generic "a promise/vow")
        """
```

**Requires:** User API key (optional feature)  
**Config:** `config.json: {"ai_provider": "claude", "api_key": "***"}`

---

#### 3.2 **Text Hooking Integration (Like LunaTranslator)**
**Source:** LunaTranslator text hooks + GameSentenceMiner Textractor  
**Solves:** Capture text directly from game memory (not just OCR)

**Note:** Linux + Hyprland only (LunaTranslator is Windows-only)

**Possible Path:**
```python
# Use existing Yomitan clipboard approach, but auto-capture
# OR: Integrate with game's built-in clipboard (if available)
# Example: Many VNs support copy-to-clipboard natively

# Add: Monitor clipboard automatically during --live mode
class ClipboardTextMiner:
    def capture_clipboard_changes(self):
        """Watch for new text on clipboard (Yomitan integration)"""
```

**Integration:** Already done via yomitan-hover.py, extend it

---

#### 3.3 **Replay Mining - Extract Past Dialogue**
**Source:** GSM replay_handler.py  
**Allows:** Mine dialogue you missed (go back in conversation logs)

**Integration Point:** New `replay.py`
```python
# Store dialogue history in mining/history_sentences.txt
# Allow user to mark favorites/review old entries

python3 main.py --review-history --filter "game=Elden Ring"
# Shows: [1] "I'm trying..." [NPC: Melina] [00:30:45]
#        [2] "Gather the Great Runes" [NPC: Melina] [01:02:10]
#        Export selected to Anki
```

---

## 📊 Integration Priority Matrix

```
Quick Wins (2-3 hrs each):
✅ [1.1] VAD Audio Trimming           → Better audio clips
✅ [1.2] Plugin Translation Backends  → DeepL/Sakura support  
✅ [1.3] Direct Anki Integration      → Faster workflow

Medium (4-5 hrs each):
🔧 [2.1] Enhanced Stats Dashboard     → Motivation + tracking
🔧 [2.2] Engine Switching (Config)    → Flexible OCR
🔧 [2.3] Game State Snapshots         → Context for cards

Advanced (6+ hrs each):
⏳ [3.1] AI Translation Service       → Better quality
⏳ [3.2] Text Hooking / Clipboard    → Native game text
⏳ [3.3] Replay Mining                → Review & catch-up
```

---

## 🔗 Integration Points with Existing Miner-v2 Code

### **Existing Pipeline to Extend:**

```
mine.py (orchestrator)
  ├─ capture.py          [2.3] ADD: store game context
  ├─ ocr.py              [2.2] REFACTOR: plugin system
  ├─ text.py             [EXISTING: speaker, dedup]
  ├─ translate.py        [1.2] EXTEND: backend registry
  │  └─ audio_processor.py [1.1] NEW: VAD trimming
  ├─ anki_export.py      [1.3] NEW: AnkiConnector option
  ├─ stats.py            [2.1] ENHANCE: daily summary
  └─ replay.py           [3.3] NEW: history review

Config: zones.json, config.py
  [2.2] ADD: per-zone ocr_engine, translation_backend
  [1.1] ADD: vad_enabled, audio_trim_silence
  [1.3] ADD: anki_direct_export, ankiconnect_url
  [3.1] ADD: ai_translation_enabled, ai_api_key, ai_model
```

---

## 📝 Recommended Implementation Order

### **Phase 1 (Do This Week):**
```
1. Implement VAD audio trimming [1.1]
   - Integrates seamlessly with existing audio_processor.py
   - Biggest quality improvement
   - ~2 hours
   
2. Add DeepL + Sakura translator backends [1.2]
   - Extends translate.py with plugin system
   - No breaking changes
   - ~3 hours

3. Add AnkiConnect direct export [1.3]
   - Parallel with CSV export (optional)
   - Much faster workflow
   - ~2 hours
```

**Total Time: 7 hours → 3 Major UX improvements**

### **Phase 2 (Following Week):**
```
4. Refactor OCR with plugin registry [2.2]
5. Add game context snapshots [2.3]
6. Enhance stats tracking [2.1]
```

---

## 💾 Files to Create/Modify

| File | Action | Integration |
|------|--------|---|
| `audio_processor.py` | ENHANCE | VAD + silero-vad |
| `translate.py` | EXTEND | TranslatorRegistry |
| `anki_connector.py` | CREATE | AnkiConnect API |
| `ocr.py` | REFACTOR | OCRRegistry pattern |
| `mine.py` | UPDATE | Call new modules |
| `stats.py` | ENHANCE | Daily/weekly stats |
| `config.py` | EXTEND | New settings |
| `zones.json` | EXTEND | Per-zone engine config |
| `replay.py` | CREATE | History mining |

---

## 🎮 Feature Comparison After Integration

| Feature | Before | After | Source |
|---------|--------|-------|--------|
| Audio Quality | Raw (~8s) | Trimmed (~1-2s) | GSM VAD |
| Translators | Google + 2 fallback | 10+ backends selectable | Luna |
| Anki Export | CSV (manual) | Direct via AnkiConnect | GSM |
| Context | None | Screenshot + game name | GSM |
| OCR Engines | Tesseract + fallback | Configurable per zone | Luna |
| Stats | None | Daily/weekly summary | GSM |
| Card Quality | Text only | Text + context + audio | Combined |

---

## ⚡ Quick Start: Pick One

**Want immediate 20% quality boost?**
→ Implement [1.1] VAD trimming + [1.3] AnkiConnect (6 hours total)

**Want better text capture?**
→ Implement [1.2] Plugin backends + [2.2] OCR registry (6 hours total)

**Want complete workflow upgrade?**
→ Do all Phase 1 + Phase 2 (15 hours, new capabilities)

---

