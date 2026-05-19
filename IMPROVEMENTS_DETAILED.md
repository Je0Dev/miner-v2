# Miner-v2: Comprehensive Improvement Roadmap

## 🎯 Priority 1: Sentence Extraction & Quality

### 1.1 **Dialogue Segmentation & Speaker Attribution**
**Problem**: Captures raw text without identifying who's speaking
**Impact**: Mining unusable dialogue sequences, hard to create context-aware cards

**Solutions**:

#### A. Heuristic-Based Speaker Detection (No ML)
```python
# Add to text.py
def extract_speaker_attribution(text: str, lang: str) -> dict:
    """
    Detect speaker patterns without ML:
    - Japanese: 「...」 or 『...』 brackets (speaker: before/after)
    - Chinese: 「」 、 markers; dialogue markers
    - English: "Speaker: dialogue" or newline patterns
    """
    patterns = {
        'ja': [
            r'(.+?)[:：][\s]*「(.+?)」',  # Name: 「dialogue」
            r'(.+?)[:：][\s]*『(.+?)』',  # Name: 『dialogue』
        ],
        'zh': [
            r'(.+?)[:：][\s]*「(.+?)」',  # Chinese speaker pattern
            r'(.+?)[:：][\s]*『(.+?)』',
        ],
        'en': [
            r'(\w+):\s*["\'](.+?)["\']',  # Name: "dialogue"
            r'(\w+):\s*(.+?)(?=\n|\.|$)',  # Name: dialogue (newline/period)
        ],
    }
    # Returns: [{'speaker': 'Name', 'dialogue': 'text', 'pattern': 'type'}, ...]
```

**Implementation**:
- Add speaker detection function to `text.py`
- Update `mine.py` to structure output as `{speaker, dialogue, context}`
- Add `speaker` field to Anki export
- Test on common VN/game dialogue patterns

#### B. Multiline Buffering Enhancement (Already Partially Implemented)
**Current**: `overlay.py` has `MultiLineBuffer` class
**Improve**:
- Add speaker consistency checking (same speaker = combine lines)
- Add punctuation-aware flushing (flush on sentence-ending punctuation)
- Store 3-5 line context history for deduplication

**Code Location**: `overlay.py` → enhance `MultiLineBuffer` class

---

### 1.2 **Context Preservation & Filtering**
**Problem**: No way to distinguish setup lines vs. useful learning content

**Solutions**:

#### A. Content-Type Classification
```python
# Add to text.py
def classify_dialogue_type(text: str, lang: str) -> str:
    """
    Classify dialogue type:
    - 'greeting': common phrases (hello, goodbye, etc.)
    - 'menu': UI text (Save, Load, Options)
    - 'narrative': long descriptive text
    - 'dialogue': conversational content (KEEP)
    - 'system': system messages
    """
    # Returns: 'dialogue' | 'greeting' | 'menu' | etc.
```

#### B. Repetition Filtering
- Track last N sentences globally (not just per-session)
- Use fuzzy string matching (difflib or `fuzzywuzzy`) for semantic duplication
- Allow user-configurable sensitivity (0-100%)

**Implementation**:
```python
# In text.py
from difflib import SequenceMatcher

def is_duplicate_fuzzy(text, history, threshold=0.85):
    for prev in history[-20:]:  # Check last 20
        if SequenceMatcher(None, text, prev).ratio() > threshold:
            return True
    return False
```

---

### 1.3 **Batch Validation & Quality Metrics**
**Problem**: No way to audit mining quality; garbage in → garbage out

**Solutions**:

```python
# Add new file: quality_metrics.py
class MiningQualityAnalyzer:
    def analyze_batch(self, entries: list[dict]) -> dict:
        """Score mining session quality"""
        return {
            'total_entries': len(entries),
            'unique_entries': len(set(e['text'] for e in entries)),
            'avg_length': statistics.mean([len(e['text']) for e in entries]),
            'has_translation': sum(1 for e in entries if e.get('translation')),
            'has_audio': sum(1 for e in entries if e.get('audio_path')),
            'quality_score': self.calculate_quality_score(entries),
            'warnings': [  # List problematic entries
                'duplicate at indices [5, 12]',
                'untranslated at index 7',
                'very short text at index 2',
            ]
        }
    
    def calculate_quality_score(self, entries):
        """0-100 score based on:
        - Uniqueness (20%)
        - Translation coverage (20%)
        - Text quality (30%)
        - Length distribution (15%)
        - Audio availability (15%)
        """
```

**Integration**:
- Run after each mining session
- Display as notification/dashboard
- Export quality report with CSV

---

## 🎯 Priority 2: OCR & Text Extraction Accuracy

### 2.1 **Multi-OCR Fallback System**
**Problem**: Tesseract alone is ~70-85% accurate; no backup when it fails

**Solution**: Implement OCR engine fallback chain
```python
# Modify ocr.py
class OCREngine:
    def __init__(self):
        self.engines = [
            TesseractOCR(preset='game_optimized'),
            EasyOCREngine(),  # Better for CJK/stylized fonts
            GoogleVisionAPI(),  # Last resort (API cost)
        ]
    
    def extract_text(self, image, lang):
        results = []
        for engine in self.engines:
            try:
                result = engine.extract(image, lang)
                confidence = engine.confidence_score(result)
                results.append({'engine': engine.name, 'text': result, 'conf': confidence})
                if confidence > 0.85:  # Good enough
                    return results[0]
            except Exception as e:
                log.warning(f"{engine.name} failed: {e}")
                continue
        
        # Return best result from all attempts
        return max(results, key=lambda r: r['conf'])
```

**Implementation Priority**:
1. **EasyOCR** (free, better CJK): pip install easyocr
2. **Tesseract + Game Presets** (existing, optimize)
3. **PaddleOCR** (lightweight, good for games): pip install paddleocr

**New Module**: `ocr_easyocr.py` (already exists!) & `ocr_paddle.py`

### 2.2 **Game-Specific Preprocessing Profiles**
**Problem**: Same preprocessing for all games fails on stylized fonts

**Solution**: Add game detection + preprocessing profiles
```python
# New file: game_profiles.py
GAME_PROFILES = {
    'generic': {
        'upscale': 2.5,
        'contrast': 1.8,
        'sharpen': 1.2,
        'bg_subtract': True,
    },
    'visual_novel_otaku': {  # Stylized VN fonts
        'upscale': 3.0,
        'contrast': 2.0,
        'sharpen': 1.5,
        'bg_subtract': True,
        'ocr_engines': ['easyocr', 'paddle', 'tesseract'],
    },
    'pixel_art': {  # Retro fonts
        'upscale': 4.0,
        'contrast': 1.5,
        'sharpen': 2.0,
        'bg_subtract': False,
    },
    'realistic': {  # Modern 3D games
        'upscale': 2.0,
        'contrast': 1.5,
        'sharpen': 0.8,
        'bg_subtract': True,
    },
}

def detect_game_style(image) -> str:
    """Detect game engine/style from screenshot"""
    # Count distinct colors, check pixel patterns, etc.
    # Return profile key
```

**UX**: Add to zone definition:
```json
{
  "zones": [{
    "name": "dialogue_box",
    "rect": [100, 500, 800, 650],
    "game_profile": "visual_novel_otaku",
    "language": "ja"
  }]
}
```

---

### 2.3 **Confidence Scoring & Filtering**
**Problem**: No way to know which OCR results are trustworthy

**Solution**:
```python
# Add to ocr.py
class OCRResult:
    text: str
    confidence: float  # 0-1
    engine: str
    preprocessed_image_stats: dict  # for debugging
    
    def is_reliable(self, threshold=0.75):
        """Filter unreliable results"""
        return self.confidence >= threshold

# In mine.py: skip low-confidence OCR results
```

**Display in Anki/log**: Show confidence in card back for manual review

---

## 🎯 Priority 3: Audio Handling

### 3.1 **Audio Source Separation**
**Problem**: Captures all system audio (music, SFX, dialogue mix) = unusable

**Solution**: Detect and isolate dialogue audio
```python
# New file: audio_processor.py
class AudioProcessor:
    def extract_dialogue_audio(self, full_recording: str, start_time: float, 
                              duration: float = 5.0) -> str:
        """
        Extract dialogue from recording:
        1. Frequency analysis: dialogue is ~300-3000 Hz (music below)
        2. Voice activity detection: identify speech vs. silence
        3. Denoise: remove background music
        """
        # Using librosa + scipy
        
        # Step 1: High-pass filter (remove low frequencies)
        audio = librosa.load(full_recording)
        filtered = librosa.effects.hpss(audio)[0]  # Harmonic/Percussive source sep
        
        # Step 2: Voice activity detection
        mfcc = librosa.feature.mfcc(filtered, sr=22050)
        
        # Step 3: Extract window around mining time
        sr = 22050
        start_sample = int(start_time * sr)
        duration_samples = int(duration * sr)
        dialogue_audio = filtered[start_sample:start_sample + duration_samples]
        
        # Step 4: Normalize + encode
        return encode_mp3(dialogue_audio)
```

**Dependencies**: `librosa`, `soundfile`, `ffmpeg`

**Integration**: Update `translate.py` to use `AudioProcessor` before saving

### 3.2 **Configurable Audio Duration & Format**
**Current**: Fixed 15s + 5s capture times
**Improve**:
- Make audio duration configurable per zone
- Add silence detection (trim audio if game is quiet)
- Support WAV + MP3 (user preference)

```python
# In config.py, add:
AUDIO_CONFIG = {
    'enabled': True,
    'duration_seconds': 8.0,
    'format': 'mp3',  # or 'wav'
    'sample_rate': 22050,
    'enable_voice_isolation': True,
    'trim_silence': True,
}
```

---

## 🎯 Priority 4: Workflow & UX Improvements

### 4.1 **Smart Zone Detection & Auto-Setup**
**Problem**: Manual zone creation is tedious; no way to find text regions automatically

**Solution**: Add zone detection wizard
```python
# New file: zone_detector.py
class ZoneDetector:
    def find_text_regions(self, screenshot_path: str) -> list[dict]:
        """
        Auto-detect text boxes in screenshot:
        1. Tesseract detects layout (text regions)
        2. Find rectangular clusters of text
        3. Group by position (dialogue boxes, menus, etc.)
        """
        # Returns: [{'rect': (x, y, w, h), 'type': 'dialogue|menu|subtitle', 'text': 'preview'}, ...]
    
    def suggest_zones(self, game_name: str, screenshots: list[str]) -> list[dict]:
        """
        User provides 3-5 screenshots, system suggests zone setup:
        - Finds consistent text locations across screenshots
        - Groups by type
        - Builds zones.json template
        """
```

**UX Flow**:
```
$ python3 main.py --detect-zones "Elden Ring"
> Provide 3-5 screenshots of normal gameplay...
> [Analyzing screenshots...]
> Found:
>   - Dialogue box: (640, 500, 600, 150)
>   - NPC name: (650, 470, 400, 30)
>   - Quest log: (1000, 200, 300, 600)
> Save zones.json? [Y/n]
```

---

### 4.2 **Batch Mining with Session Management**
**Problem**: No way to organize mining by session/context

**Solution**: Add session/campaign management
```python
# Extend mining/ folder structure:
mining/
  ├── zones.json
  ├── campaigns/
  │   ├── elden_ring_pt1/
  │   │   ├── config.json      # Settings for this campaign
  │   │   ├── sessions/
  │   │   │   ├── 20260516_093000/
  │   │   │   └── 20260516_140000/
  │   │   └── exported/         # Finalized cards
  │   └── japanese_reading/
  └── history_sentences.txt     # Global dedup

# In main.py:
python3 main.py --campaign "elden_ring_pt1" --start-mining -l ja -t en
```

**Benefits**:
- Organize mining by game/context
- Per-campaign settings
- Easy to review/curate before exporting to Anki

---

### 4.3 **Anki Integration Improvements**
**Current**: Exports static CSV
**Improve**:

```python
# Extend anki_export.py
class AnkiExporter:
    def export_direct(self, entries, deck_name='Mining'):
        """Direct AnkiConnect export (if Anki running)"""
        # pip install anki-connect-api
        
    def create_filtered_deck(self, entries):
        """Create filtered deck for review-before-add workflow"""
        
    def export_media(self, entries):
        """Export with audio/images embedded"""
        
    def export_with_metadata(self, entries):
        """CSV with OCR confidence, source, context"""
```

**New Fields in Anki**:
- Pronunciation (existing)
- Speaker (new)
- OCR Confidence (new)
- Audio Duration (new)
- Source Game (improved)
- Sentence Context (new - prev/next line)
- Mining Mode (quick/live/hover)

---

## 🎯 Priority 5: Error Handling & Robustness

### 5.1 **Retry Logic & API Fallbacks**
**Problem**: Single API failure = mining session fails

**Solution**: Robust retry with exponential backoff
```python
# New file: resilience.py
class ResilientTranslator:
    def __init__(self):
        self.services = [
            GoogleTranslateAPI(),
            MyMemoryAPI(),           # Free, no key required
            LibreTranslateAPI(),      # Can self-host
        ]
    
    async def translate_with_fallback(self, text, src_lang, tgt_lang):
        """Try each service with retry logic"""
        for service in self.services:
            try:
                result = await self.retry_with_backoff(
                    lambda: service.translate(text, src_lang, tgt_lang),
                    max_retries=3,
                    backoff_factor=2.0
                )
                return result
            except Exception as e:
                log.warning(f"{service.name} failed: {e}, trying next...")
        
        log.error("All translation services failed")
        raise TranslationError(text)
```

### 5.2 **Graceful Degradation**
**If translation fails**: Still save OCR + audio (useful for review)
**If audio fails**: Still save text + translation
**If OCR fails**: Ask user to confirm text manually

---

## 🎯 Priority 6: Developer Experience

### 6.1 **Add Health Check & Diagnostics**
**Current**: `--health` flag exists
**Improve**:
```python
# Extend health.py
def run_diagnostics():
    checks = {
        'tesseract_installed': check_tesseract(),
        'easyocr_available': check_easyocr(),
        'paddle_ocr_available': check_paddle(),
        'audio_system': check_audio(),
        'translation_api': check_translation_api(),
        'cache_stats': get_cache_stats(),
        'mining_dir_writable': check_write_access(),
        'gpu_available': check_gpu(),
    }
    
    # Return detailed report + suggestions
    return {
        'status': 'healthy' if all(checks.values()) else 'degraded',
        'details': checks,
        'recommendations': [...]
    }
```

### 6.2 **Logging & Observability**
**Improve**: Add structured logging with levels
```python
# In log.py
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('mining/miner.log'),
        logging.StreamHandler(),
    ]
)

# Per-module loggers:
logger = logging.getLogger(__name__)
logger.debug('OCR attempt 2/3 for image %s', image_path)
```

---

## 📊 Implementation Priority Matrix

```
High Impact + Quick Win:
  ✅ 1.1A Speaker detection (heuristic)
  ✅ 1.2B Fuzzy duplicate filtering
  ✅ 2.1 Multi-OCR fallback (EasyOCR)
  ✅ 5.1 Translation fallbacks

High Impact + Medium Effort:
  🔧 2.2 Game-specific profiles
  🔧 3.1 Audio source separation
  🔧 4.1 Zone auto-detection
  🔧 5.2 Graceful degradation

Nice to Have / Long Term:
  ⏳ 1.3 Quality metrics dashboard
  ⏳ 4.2 Campaign management
  ⏳ 4.3 Anki integration improvements
  ⏳ 6.1 Comprehensive health checks
```

---

## 🚀 Quick Start Implementation Checklist

### Phase 1 (Week 1): Core Improvements
- [ ] Add speaker detection to `text.py`
- [ ] Implement fuzzy deduplication in `text.py`
- [ ] Add EasyOCR support in `ocr.py` with fallback logic
- [ ] Add translation API fallbacks in `translate.py`
- [ ] Update Anki export to include speaker field

### Phase 2 (Week 2): Advanced Features
- [ ] Create `audio_processor.py` for voice isolation
- [ ] Add game profile system in `game_profiles.py`
- [ ] Implement confidence scoring in OCR
- [ ] Add session/campaign structure

### Phase 3 (Week 3): Polish
- [ ] Add quality metrics analyzer
- [ ] Implement zone auto-detection
- [ ] Improve health check system
- [ ] Add comprehensive logging

---

## 📝 Testing Strategy

For each improvement:
1. Add unit tests in `tests/` directory
2. Test on real game screenshots (include in `test_images/`)
3. Validate with actual Anki exports
4. Benchmark performance (OCR time, API latency)
5. Collect user feedback

---

## 🎮 Games to Test Against

Based on mining history, optimize for:
- VNs with stylized fonts (EasyOCR focus)
- Action RPGs with dynamic text (zone detection)
- JRPGs with dialogue systems (speaker detection)
- Mobile games (small text upscaling)

---

## 📚 Recommended Dependencies to Add

```bash
# OCR improvements
pip install easyocr paddleocr

# Audio processing
pip install librosa soundfile

# Fuzzy matching
pip install fuzzywuzzy python-Levenshtein

# Advanced NLP (future)
pip install spacy transformers

# Async improvements
pip install aiohttp

# Logging
pip install python-json-logger

# Testing
pip install pytest pytest-asyncio pytest-cov
```

