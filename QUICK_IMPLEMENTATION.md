# Quick Implementation Guide - Miner-v2 Improvements

## 1️⃣ Speaker Detection (30 min implementation)

### Add to `text.py`:

```python
import re
from typing import Optional

def extract_speaker_and_dialogue(text: str, lang: str) -> dict:
    """
    Extract speaker attribution from game dialogue.
    
    Patterns for common game formats:
    - Japanese: 「dialogue」with speaker before/after colon
    - Chinese: Similar bracket patterns
    - English: "Speaker: dialogue" format
    
    Returns:
        {
            'speaker': 'character_name' or None,
            'dialogue': 'cleaned_text',
            'has_speaker': bool,
            'confidence': 0.0-1.0
        }
    """
    
    patterns = {
        'ja': [
            # Pattern: Name：「dialogue」
            (r'^(.+?)[:：]\s*[「『](.+?)[」』]', 0.95),
            # Pattern: 「dialogue」(Name)
            (r'^[「『](.+?)[」』]\s*\((.+?)\)', 0.90),
            # Pattern: Name: dialogue (no brackets)
            (r'^(.+?)[:：]\s*([^\n]+?)(?:\n|$)', 0.75),
        ],
        'zh': [
            # Chinese patterns similar to Japanese
            (r'^(.+?)[:：]\s*[「『](.+?)[」』]', 0.95),
            (r'^[「『](.+?)[」』]\s*[（(](.+?)[）)]', 0.90),
            (r'^(.+?)[:：]\s*([^\n]+?)(?:\n|$)', 0.75),
        ],
        'en': [
            # Pattern: "Speaker: dialogue"
            (r'^"?([A-Z][a-z]+)"?:\s*["\']?(.+?)["\']?$', 0.90),
            # Pattern: Speaker: dialogue
            (r'^([A-Z][a-z]+):\s*(.+?)$', 0.85),
            # Narration patterns (no speaker)
            (r'^(?:The|A|An|It|He|She|They)\s+', 0.0),  # narrator text, conf=0
        ],
    }
    
    text = text.strip()
    if not text:
        return {'speaker': None, 'dialogue': '', 'has_speaker': False, 'confidence': 0.0}
    
    # Get patterns for language, fallback to English
    lang_patterns = patterns.get(lang, patterns['en'])
    
    for pattern, confidence in lang_patterns:
        match = re.match(pattern, text, re.IGNORECASE)
        if match:
            groups = match.groups()
            if len(groups) == 2:
                speaker, dialogue = groups
                return {
                    'speaker': speaker.strip(),
                    'dialogue': dialogue.strip(),
                    'has_speaker': True,
                    'confidence': confidence,
                    'pattern_type': 'attributed_dialogue'
                }
            elif len(groups) == 1 and confidence == 0.0:
                # Narration pattern matched
                return {
                    'speaker': None,
                    'dialogue': text,
                    'has_speaker': False,
                    'confidence': 0.8,
                    'pattern_type': 'narration'
                }
    
    # No speaker pattern found - treat as pure dialogue
    return {
        'speaker': None,
        'dialogue': text,
        'has_speaker': False,
        'confidence': 0.0,
        'pattern_type': 'unattributed_dialogue'
    }


def format_with_speaker(text: str, speaker: Optional[str], lang: str) -> str:
    """Format text with speaker for display"""
    if not speaker:
        return text
    
    if lang in ('ja', 'zh'):
        return f"{speaker}：{text}"
    else:
        return f"{speaker}: {text}"
```

### Update `anki_export.py` to include speaker:

```python
def export_to_csv(entries: list[dict], output_path: str):
    """Export with speaker field"""
    
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'Sentence',           # Original text
            'SpeakerSentence',    # Speaker: Sentence
            'Translation',
            'Pronunciation',
            'Audio',
            'Source',
            'Timestamp',
            'Language',
            'WordBreakdown',
        ])
        
        writer.writeheader()
        for entry in entries:
            speaker = entry.get('speaker', '')
            sentence = entry.get('text', '')
            speaker_sentence = f"{speaker}: {sentence}" if speaker else sentence
            
            writer.writerow({
                'Sentence': sentence,
                'SpeakerSentence': speaker_sentence,
                'Translation': entry.get('translation', ''),
                'Pronunciation': entry.get('pronunciation', ''),
                'Audio': entry.get('audio_path', ''),
                'Source': entry.get('source', ''),
                'Timestamp': entry.get('timestamp', ''),
                'Language': entry.get('language', ''),
                'WordBreakdown': entry.get('word_breakdown', ''),
            })
```

---

## 2️⃣ Fuzzy Duplicate Detection (20 min)

### Add to `text.py`:

```python
from difflib import SequenceMatcher
from typing import List

def is_duplicate_fuzzy(text: str, history: List[str], threshold: float = 0.85) -> bool:
    """
    Check if text is a fuzzy duplicate using sequence matching.
    
    Args:
        text: New text to check
        history: List of previous texts (last 30 most recent)
        threshold: Similarity threshold (0.85 = 85% match)
    
    Returns:
        True if text is similar to any recent entry, False otherwise
    """
    
    if not text or len(text) < 2:
        return False
    
    # Only check recent history for performance
    recent_history = history[-30:] if len(history) > 30 else history
    
    for prev_text in recent_history:
        if not prev_text or len(prev_text) < 2:
            continue
        
        # Calculate similarity ratio
        ratio = SequenceMatcher(None, text.lower(), prev_text.lower()).ratio()
        
        if ratio > threshold:
            # Also check: is one a substring of the other?
            if text.lower() in prev_text.lower() or prev_text.lower() in text.lower():
                return True
            
            # Check length difference (avoid short text false positives)
            if abs(len(text) - len(prev_text)) / max(len(text), len(prev_text)) < 0.3:
                return True
    
    return False


def load_history_for_dedup(history_file: str = 'mining/history_sentences.txt') -> List[str]:
    """Load recent sentences from history file"""
    try:
        with open(history_file, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]
            return lines[-500:]  # Last 500 for memory efficiency
    except FileNotFoundError:
        return []
```

### Update `mine.py` to use it:

```python
# In the mining pipeline, after OCR:

history = load_history_for_dedup()

if is_duplicate_fuzzy(ocr_text, history, threshold=0.80):
    log.info(f"Skipping duplicate: {ocr_text[:50]}...")
    continue  # Skip this entry
```

---

## 3️⃣ Multi-OCR Fallback System (45 min)

### Add to `ocr.py`:

```python
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class OCREngine(Enum):
    TESSERACT = 'tesseract'
    EASYOCR = 'easyocr'
    PADDLE = 'paddle'


class MultiOCREngine:
    """Try multiple OCR engines with fallback"""
    
    def __init__(self):
        self.engines = []
        self.confidence_threshold = 0.75
        
        # Always add Tesseract (already implemented)
        self.engines.append({
            'name': OCREngine.TESSERACT,
            'func': self._ocr_tesseract,
            'priority': 1,  # Try first
        })
        
        # Add EasyOCR if available (better for CJK + stylized fonts)
        try:
            import easyocr
            self.easyocr = easyocr
            self.engines.append({
                'name': OCREngine.EASYOCR,
                'func': self._ocr_easyocr,
                'priority': 2,
            })
            logger.info("EasyOCR available - will use as fallback")
        except ImportError:
            logger.warning("EasyOCR not installed - skipping fallback")
        
        # Add PaddleOCR if available (lightweight, good accuracy)
        try:
            from paddleocr import PaddleOCR
            self.paddleocr = PaddleOCR(use_angle_cls=True, lang='ch')
            self.engines.append({
                'name': OCREngine.PADDLE,
                'func': self._ocr_paddle,
                'priority': 3,
            })
            logger.info("PaddleOCR available - will use as fallback")
        except ImportError:
            logger.warning("PaddleOCR not installed - skipping fallback")
        
        # Sort by priority
        self.engines.sort(key=lambda x: x['priority'])
    
    def extract_text(self, image, lang: str, enable_fallback: bool = True) -> dict:
        """
        Extract text trying multiple OCR engines.
        
        Returns:
            {
                'text': 'extracted text',
                'confidence': 0.0-1.0,
                'engine': 'tesseract|easyocr|paddle',
                'attempts': ['engine1 failed: reason', 'engine2 succeeded']
            }
        """
        
        results = []
        attempts = []
        
        for engine_config in self.engines:
            engine_name = engine_config['name'].value
            try:
                logger.debug(f"Attempting OCR with {engine_name}")
                
                result = engine_config['func'](image, lang)
                text = result.get('text', '').strip()
                confidence = result.get('confidence', 0.5)
                
                results.append({
                    'text': text,
                    'confidence': confidence,
                    'engine': engine_name,
                    'raw_result': result,
                })
                
                attempts.append(f"{engine_name}: OK (conf={confidence:.2f})")
                
                # If confidence is good enough, return immediately
                if confidence >= self.confidence_threshold and text:
                    logger.info(f"Good result from {engine_name} (conf={confidence:.2f})")
                    return {
                        'text': text,
                        'confidence': confidence,
                        'engine': engine_name,
                        'attempts': attempts,
                    }
                
                # If not enabling fallback, return first successful result
                if not enable_fallback:
                    return {
                        'text': text,
                        'confidence': confidence,
                        'engine': engine_name,
                        'attempts': attempts,
                    }
            
            except Exception as e:
                logger.warning(f"{engine_name} failed: {str(e)}")
                attempts.append(f"{engine_name}: FAILED ({str(e)[:50]})")
                continue
        
        # Return best result from all attempts
        if results:
            best = max(results, key=lambda r: r['confidence'])
            logger.info(f"Using best result from {best['engine']} (conf={best['confidence']:.2f})")
            return {
                'text': best['text'],
                'confidence': best['confidence'],
                'engine': best['engine'],
                'attempts': attempts,
            }
        
        # All engines failed
        logger.error("All OCR engines failed")
        return {
            'text': '',
            'confidence': 0.0,
            'engine': 'failed',
            'attempts': attempts,
        }
    
    def _ocr_tesseract(self, image, lang: str) -> dict:
        """Use existing Tesseract implementation"""
        # Call the existing ocr_text_tesseract function
        text = ocr_text_tesseract(image, lang)
        return {'text': text, 'confidence': 0.7}  # Tesseract doesn't give confidence
    
    def _ocr_easyocr(self, image, lang: str) -> dict:
        """Use EasyOCR for fallback"""
        try:
            lang_code = self._map_lang_to_easyocr(lang)
            reader = self.easyocr.Reader([lang_code], gpu=False)
            
            results = reader.readtext(image)
            
            if not results:
                return {'text': '', 'confidence': 0.0}
            
            # EasyOCR returns [(bbox, text, confidence), ...]
            texts = [text for (_, text, conf) in results]
            confidences = [conf for (_, _, conf) in results]
            
            full_text = ' '.join(texts)
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            
            return {
                'text': full_text,
                'confidence': avg_confidence,
            }
        except Exception as e:
            raise Exception(f"EasyOCR error: {str(e)}")
    
    def _ocr_paddle(self, image, lang: str) -> dict:
        """Use PaddleOCR for fallback"""
        try:
            result = self.paddleocr.ocr(image, cls=True)
            
            if not result or not result[0]:
                return {'text': '', 'confidence': 0.0}
            
            # PaddleOCR returns [[[x, y], ...], text, confidence]
            texts = [text for line in result for (text, conf) in line]
            confidences = [conf for line in result for (text, conf) in line]
            
            full_text = ' '.join(texts)
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            
            return {
                'text': full_text,
                'confidence': avg_confidence,
            }
        except Exception as e:
            raise Exception(f"PaddleOCR error: {str(e)}")
    
    @staticmethod
    def _map_lang_to_easyocr(lang: str) -> str:
        """Map miner language codes to EasyOCR codes"""
        mapping = {
            'zh': 'ch_sim',
            'ja': 'ja',
            'ko': 'ko',
            'en': 'en',
            'de': 'de',
            'es': 'es',
            'fr': 'fr',
            'ru': 'ru',
            'el': 'el',
            'pl': 'pl',
        }
        return mapping.get(lang, 'en')
```

### Update `mine.py` to use:

```python
# At module level:
ocr_engine = MultiOCREngine()

# In mining pipeline (replace existing OCR call):
ocr_result = ocr_engine.extract_text(image, language)
text = ocr_result['text']
ocr_confidence = ocr_result['confidence']
ocr_engine_used = ocr_result['engine']

# Log the attempts
logger.info(f"OCR attempts: {', '.join(ocr_result['attempts'])}")

# Store confidence for later review
entry['ocr_confidence'] = ocr_confidence
entry['ocr_engine'] = ocr_engine_used
```

---

## 4️⃣ Translation API Fallbacks (30 min)

### Add to `translate.py`:

```python
import logging
from typing import Optional
import time

logger = logging.getLogger(__name__)

class TranslationService:
    """Base class for translation services"""
    
    def translate(self, text: str, src_lang: str, tgt_lang: str) -> str:
        raise NotImplementedError
    
    def get_name(self) -> str:
        raise NotImplementedError


class GoogleTranslateService(TranslationService):
    """Existing Google Translate"""
    
    def __init__(self):
        from deep_translator import GoogleTranslator
        self.translator = GoogleTranslator
    
    def translate(self, text: str, src_lang: str, tgt_lang: str) -> str:
        translator = self.translator(source_language=src_lang, target_language=tgt_lang)
        return translator.translate(text)
    
    def get_name(self) -> str:
        return "Google Translate"


class MyMemoryService(TranslationService):
    """Free backup service (no API key required)"""
    
    def translate(self, text: str, src_lang: str, tgt_lang: str) -> str:
        import requests
        
        url = "https://api.mymemory.translated.net/get"
        params = {
            'q': text,
            'langpair': f'{src_lang}|{tgt_lang}',
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if data['responseStatus'] == 200:
                return data['responseData']['translatedText']
            else:
                raise Exception(f"MyMemory error: {data.get('responseDetails', 'Unknown')}")
        except Exception as e:
            raise Exception(f"MyMemory service error: {str(e)}")
    
    def get_name(self) -> str:
        return "MyMemory"


class LibreTranslateService(TranslationService):
    """Self-hostable translation service"""
    
    def __init__(self, api_url: str = "http://localhost:5000"):
        self.api_url = api_url
    
    def translate(self, text: str, src_lang: str, tgt_lang: str) -> str:
        import requests
        
        payload = {
            'q': text,
            'source': src_lang,
            'target': tgt_lang,
        }
        
        try:
            response = requests.post(
                f"{self.api_url}/translate",
                json=payload,
                timeout=10
            )
            data = response.json()
            return data.get('translatedText', '')
        except Exception as e:
            raise Exception(f"LibreTranslate service error: {str(e)}")
    
    def get_name(self) -> str:
        return "LibreTranslate"


class ResilientTranslator:
    """Translate with fallback services"""
    
    def __init__(self, primary_service: Optional[str] = 'google'):
        self.services: list[TranslationService] = []
        self.cache = {}
        
        # Add services in priority order
        if primary_service == 'google':
            self.services.append(GoogleTranslateService())
        
        # Always add free fallbacks
        self.services.append(MyMemoryService())
        
        # Try to add local LibreTranslate if available
        try:
            libre = LibreTranslateService()
            # Quick test
            libre.translate("test", "en", "en")
            self.services.append(libre)
            logger.info("LibreTranslate available at localhost:5000")
        except:
            logger.debug("LibreTranslate not available")
    
    def translate(self, text: str, src_lang: str, tgt_lang: str,
                  max_retries: int = 2) -> str:
        """
        Translate text using fallback services.
        
        Args:
            text: Text to translate
            src_lang: Source language code ('ja', 'zh', etc.)
            tgt_lang: Target language code
            max_retries: Max retries per service
        
        Returns:
            Translated text
        """
        
        # Check cache first
        cache_key = f"{src_lang}|{tgt_lang}|{text[:50]}"
        if cache_key in self.cache:
            logger.debug(f"Cache hit: {text[:30]}...")
            return self.cache[cache_key]
        
        last_error = None
        
        for service in self.services:
            for attempt in range(max_retries):
                try:
                    logger.debug(
                        f"Translating with {service.get_name()} "
                        f"(attempt {attempt + 1}/{max_retries})"
                    )
                    
                    result = service.translate(text, src_lang, tgt_lang)
                    
                    # Cache result
                    self.cache[cache_key] = result
                    if len(self.cache) > 1000:
                        # Clear old entries
                        self.cache = dict(list(self.cache.items())[-500:])
                    
                    logger.info(f"{service.get_name()} succeeded")
                    return result
                
                except Exception as e:
                    logger.warning(
                        f"{service.get_name()} failed (attempt {attempt + 1}/{max_retries}): {str(e)}"
                    )
                    last_error = e
                    
                    # Exponential backoff
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt
                        logger.debug(f"Waiting {wait_time}s before retry...")
                        time.sleep(wait_time)
                    
                    continue
        
        # All services failed
        logger.error(f"All translation services failed. Last error: {last_error}")
        raise Exception(f"Translation failed for: {text[:50]}... ({last_error})")


# Replace existing translator
_resilient_translator = None

def get_translator() -> ResilientTranslator:
    global _resilient_translator
    if _resilient_translator is None:
        _resilient_translator = ResilientTranslator()
    return _resilient_translator
```

### Update existing translate calls:

```python
# Old code:
# translator = GoogleTranslator(source_language=lang, target_language=target_lang)
# translation = translator.translate(text)

# New code:
translator = get_translator()
try:
    translation = translator.translate(text, lang, target_lang)
except Exception as e:
    logger.error(f"Translation failed: {e}")
    # Continue without translation (graceful degradation)
    translation = None
```

---

## Installation Commands

To support these improvements, install:

```bash
# OCR fallbacks
pip install easyocr paddleocr

# Fuzzy matching
pip install fuzzywuzzy python-Levenshtein

# Better HTTP for translation fallbacks
pip install requests

# If not already installed
pip install pillow numpy scipy
```

---

## Testing These Improvements

```python
# Quick test file: test_improvements.py

from text import extract_speaker_and_dialogue, is_duplicate_fuzzy, load_history_for_dedup
from ocr import MultiOCREngine
from translate import ResilientTranslator

# Test 1: Speaker detection
text_ja = "太郎：「こんにちは」"
result = extract_speaker_and_dialogue(text_ja, 'ja')
print(f"Speaker: {result['speaker']}, Dialogue: {result['dialogue']}")

# Test 2: Fuzzy dedup
history = ['Hello world', 'How are you', 'Testing 123']
is_dup = is_duplicate_fuzzy('Hello world!', history)
print(f"Is duplicate: {is_dup}")

# Test 3: Multi-OCR
ocr = MultiOCREngine()
from PIL import Image
img = Image.open('test.png')
result = ocr.extract_text(img, 'ja')
print(f"OCR: {result['text']} (engine: {result['engine']})")

# Test 4: Translation fallback
translator = ResilientTranslator()
trans = translator.translate('こんにちは', 'ja', 'en')
print(f"Translation: {trans}")
```

---

## Next Steps

1. **Start with Phase 1** (all quick wins): ~2-3 hours implementation
2. **Test on real mining data** from `mining/` folder
3. **Measure improvements**: Compare OCR accuracy, duplicate rate, translation success
4. **Iterate** on Phase 2 features based on results

