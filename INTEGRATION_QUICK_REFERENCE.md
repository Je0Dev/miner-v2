# Quick Reference: Feature Integration at a Glance

## 🎯 3 Tier 1 Features (Week 1)

### 1️⃣ VAD Audio Trimming
```
Problem: 8s recordings full of silence/music
Solution: Auto-trim to 1-2s pure dialogue
Time:    2 hours
Value:   High (better cards, smaller files)
File:    audio_processor.py (add functions)
From:    GameSentenceMiner/vad.py
```

### 2️⃣ Plugin Translators
```
Problem: Only Google Translate (single point of failure)
Solution: Try DeepL, Sakura, Baidu, etc. in order
Time:    2 hours
Value:   High (better quality, no API failures)
File:    translate.py (add TranslatorRegistry class)
From:    LunaTranslator/translator/*.py (50+ backends)
```

### 3️⃣ Direct Anki Export
```
Problem: Export to CSV then manually import to Anki
Solution: Add cards directly via AnkiConnect API
Time:    2 hours
Value:   High (faster workflow, automatic)
File:    anki_connector.py (new file)
From:    GameSentenceMiner/anki.py
```

---

## 📊 Impact

```
BEFORE                          AFTER
────────────────────────────────────────────────────────
60-90s per entry          →     30-45s per entry (-50%)
Raw 8s audio              →     1-2s trimmed audio
Google only               →     10+ translators
CSV import to Anki        →     Auto-export
✗ No context              →     ✓ Game name + screenshot
✗ No progress tracking    →     ✓ Daily stats
```

---

## ⏱️ Implementation Timeline

```
HOUR    TASK
────────────────────────────────────
0-0.5   Read FEATURE_INTEGRATION_GUIDE.md
0.5-1   Read TIER1_IMPLEMENTATION.md
1-2     Modify config.py + mine.py
2-4     Copy anki_connector.py code
4-5     Copy VAD functions to audio_processor.py
5-6     Copy TranslatorRegistry to translate.py
6-6.5   pip install (webrtcvad, librosa, etc.)
6.5-7   Test integrations
7+      Mine and verify!
```

---

## 📝 Files to Touch

```
MODIFY (3 files):
├─ config.py             (+15 lines)
├─ mine.py              (+10 lines)
└─ translate.py         (+10 lines)

CREATE (1 file):
└─ anki_connector.py     (250 lines, copy from doc)

ENHANCE (2 files):
├─ audio_processor.py    (+200 lines, copy from doc)
└─ translate.py         (+300 lines, copy from doc)

TOTAL EDITS: ~30 lines of actual changes
NEW CODE:  ~750 lines (mostly copy-paste from docs)
```

---

## 🔗 Integration Points

### **VAD → audio_processor.py + mine.py**
```python
# In mine.py after recording audio:
if config.AUDIO_VAD_ENABLED:
    result = trim_audio_with_vad(audio_path)
    audio_path = result['output_path']
```

### **Translators → translate.py + mine.py**
```python
# In translate.py:
registry = TranslatorRegistry('config.json')

# In mine.py:
result = registry.translate_with_fallback(text, 'ja', 'en')
entry['translation'] = result['text']
entry['translation_backend'] = result['backend']
```

### **Anki → anki_connector.py + mine.py**
```python
# In mine.py after creating entry:
if config.ANKI_DIRECT_EXPORT:
    anki = AnkiConnector(config.ANKICONNECT_URL)
    note_id = anki.add_mining_note(entry, config.ANKI_DECK_NAME)
    entry['anki_note_id'] = note_id
```

---

## 📦 Dependencies

```bash
pip install webrtcvad   # 5 MB  (VAD - lightweight)
pip install librosa     # 10 MB (already have)
pip install soundfile   # 1 MB  (audio I/O)
pip install deepl       # 1 MB  (translator)
pip install requests    # Already have
```

**Total:** 4 small packages, ~20 MB, ~2 min install time

---

## ✅ Verification

```bash
# Test 1: VAD
python3 -c "from audio_processor import trim_audio_with_vad; print('✓')"

# Test 2: Translators
python3 -c "from translate import TranslatorRegistry; print('✓')"

# Test 3: Anki
python3 -c "from anki_connector import AnkiConnector; print('✓')"

# Test 4: Full mining
bash mine.sh -l ja -t en

# Test 5: Verify output
python3 -c "
import json
with open('mining/sentences.json') as f:
    e = json.load(f)[-1]
    print(f'Audio: {e.get(\"audio_duration\")}s')
    print(f'Backend: {e.get(\"translation_backend\")}')
    print(f'Anki ID: {e.get(\"anki_note_id\")}')
"
```

---

## 📚 Document Map

```
START HERE
    ↓
README_INTEGRATIONS.md  (this overview)
    ↓
FEATURE_INTEGRATION_GUIDE.md  (what features exist)
    ↓
TIER1_IMPLEMENTATION.md  (copy-paste code)
    ↓
INTEGRATION_MAP.md  (where code goes)
    ↓
Mine and verify!
```

---

## 🎮 Example Before/After

### **BEFORE (Today)**
```bash
$ bash mine.sh -l ja -t en
[Select region: dialogue box]
[OCR: 「こんにちは」]
[Google Translate: "Hello"]
[Record 8s audio with background music]
[Save JSON, generate CSV]
[Manually import CSV to Anki]
⏱ TIME: ~90 seconds
🎵 AUDIO: 8 seconds (noisy)
```

### **AFTER (After Implementation)**
```bash
$ bash mine.sh -l ja -t en
[Select region: dialogue box]
[OCR: 「こんにちは」]
[Try DeepL: "Hello" ✓ (better quality)]
[Record 8s audio]
[VAD auto-trim → 1.2s pure dialogue ✓]
[Save JSON, generate CSV, add to Anki ✓]
📲 NOTIFICATION: "Card added to Anki Mining deck"
⏱ TIME: ~45 seconds (50% faster!)
🎵 AUDIO: 1.2 seconds (clean, perfect for Anki)
```

---

## 🚀 Go-to-Market Plan

**Phase 1 (This Week):** Implement VAD + Translators + AnkiConnect  
**Phase 2 (Next Week):** Add stats + game context + OCR registry  
**Phase 3 (Later):** AI translation + zone auto-detect + advanced features  

**Current Status:** Ready to implement Phase 1  
**Estimated Effort:** 6-8 hours total  
**Expected Benefit:** 30-50% improvement in speed + quality

---

## 💬 Questions Before Starting?

**Q: Can I just do VAD?**  
A: Yes! Features are independent.

**Q: Does this break CSV export?**  
A: No, CSV generation continues as backup.

**Q: Need Anki to be running?**  
A: Only if ANKI_DIRECT_EXPORT=True. Can disable.

**Q: How do I revert if something breaks?**  
A: Just delete new files, remove imports. ~30 seconds.

---

## 🎯 Next Step

**→ Read [FEATURE_INTEGRATION_GUIDE.md](FEATURE_INTEGRATION_GUIDE.md)**

Pick one feature, implement it, test it. You've got this! 🚀

