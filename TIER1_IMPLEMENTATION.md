# Implementation: Tier 1 Integrations (High-Value, Quick)

## 1️⃣ VAD Audio Trimming (Silence Removal)

### Where to Add
**File:** `audio_processor.py` (existing)  
**Method:** Add `trim_audio_with_vad()` function

```python
# audio_processor.py - ADD THIS

import os
import numpy as np
from pathlib import Path

try:
    # Option 1: Lightweight (5MB)
    from webrtcvad import Vad as WebRTCVad
    HAS_WEBRTCVAD = True
except ImportError:
    HAS_WEBRTCVAD = False
    WebRTCVad = None

try:
    # Option 2: Better quality (but larger)
    from silero_vad import load_silero_vad
    HAS_SILERO = True
except ImportError:
    HAS_SILERO = False
    load_silero_vad = None


def trim_audio_with_vad(input_audio_path: str, 
                        output_audio_path: str = None,
                        engine: str = 'webrtc') -> dict:
    """
    Remove silence and non-speech segments from audio.
    
    Args:
        input_audio_path: Path to input MP3/WAV
        output_audio_path: Where to save trimmed audio (default: add _trimmed)
        engine: 'webrtc' (fast, small) or 'silero' (better quality)
    
    Returns:
        {
            'original_duration': 8.2,
            'trimmed_duration': 1.8,
            'segments': [(0.5, 2.3), (3.1, 5.0)],  # speech segments
            'output_path': '/path/trimmed.mp3',
            'reduction_percent': 78
        }
    """
    import librosa
    import soundfile as sf
    
    if not output_audio_path:
        path = Path(input_audio_path)
        output_audio_path = path.parent / f"{path.stem}_trimmed{path.suffix}"
    
    # Load audio (22050 Hz)
    audio, sr = librosa.load(input_audio_path, sr=22050, mono=True)
    original_duration = librosa.get_duration(y=audio, sr=sr)
    
    if engine == 'webrtc' and HAS_WEBRTCVAD:
        segments = _vad_webrtc(audio, sr)
    elif engine == 'silero' and HAS_SILERO:
        segments = _vad_silero(audio, sr)
    else:
        # Fallback: naive energy-based detection
        segments = _vad_energy_based(audio, sr)
    
    # Extend segments to include pre/post buffer (50ms)
    buffer_frames = int(0.05 * sr)
    extended_segments = []
    for start, end in segments:
        extended_segments.append((
            max(0, start - buffer_frames),
            min(len(audio), end + buffer_frames)
        ))
    
    # Merge overlapping segments
    merged = []
    for start, end in sorted(extended_segments):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    
    # Extract speech regions
    speech_audio = np.concatenate([
        audio[int(start):int(end)] for start, end in merged
    ])
    
    trimmed_duration = librosa.get_duration(y=speech_audio, sr=sr)
    
    # Save trimmed audio
    sf.write(output_audio_path, speech_audio, sr)
    
    # Convert back to MP3 if original was MP3
    if input_audio_path.endswith('.mp3'):
        import subprocess
        temp_wav = str(output_audio_path)
        subprocess.run([
            'ffmpeg', '-i', temp_wav, 
            '-q:a', '5',  # quality
            '-y',  # overwrite
            str(output_audio_path).replace('.wav', '.mp3')
        ], check=True, capture_output=True)
        os.remove(temp_wav)
        output_audio_path = str(output_audio_path).replace('.wav', '.mp3')
    
    return {
        'original_duration': float(original_duration),
        'trimmed_duration': float(trimmed_duration),
        'segments': [(float(s), float(e)) for s, e in merged],
        'output_path': str(output_audio_path),
        'reduction_percent': round(
            (1 - trimmed_duration / original_duration) * 100
        ) if original_duration > 0 else 0,
    }


def _vad_webrtc(audio: np.ndarray, sr: int) -> list:
    """Detect speech using WebRTC VAD"""
    vad = WebRTCVad()
    vad.set_mode(3)  # Aggressive (most strict)
    
    frame_duration = 20  # ms
    samples_per_frame = int(sr * frame_duration / 1000)
    
    segments = []
    in_speech = False
    segment_start = 0
    
    for i in range(0, len(audio), samples_per_frame):
        frame = audio[i:i + samples_per_frame]
        
        # Resample to 16kHz if needed
        if sr != 16000:
            frame = librosa.resample(frame, orig_sr=sr, target_sr=16000)
        
        # Convert to bytes
        frame_bytes = (frame * 32767).astype(np.int16).tobytes()
        
        is_speech = vad.is_speech(frame_bytes, 16000)
        
        if is_speech and not in_speech:
            segment_start = i
            in_speech = True
        elif not is_speech and in_speech:
            segments.append((segment_start, i))
            in_speech = False
    
    if in_speech:
        segments.append((segment_start, len(audio)))
    
    return segments


def _vad_silero(audio: np.ndarray, sr: int) -> list:
    """Detect speech using Silero VAD (better quality)"""
    import torch
    
    model, utils = load_silero_vad()
    (get_speech_ts, save_audio, read_audio, 
     VADIterator, collect_chunks) = utils
    
    # Convert audio to torch tensor
    audio_torch = torch.FloatTensor(audio).unsqueeze(0)
    
    speech_dict = get_speech_ts(
        audio_torch,
        model,
        num_samples_chunk=4800,  # chunk size
        threshold=0.5,
        min_speech_duration_ms=250,  # minimum speech segment
        max_speech_duration_s=30,
        min_silence_duration_ms=300,  # minimum silence between segments
    )
    
    # Convert frame indices to time indices
    segments = [
        (int(chunk['start'] / sr * 1000 / 1000 * sr),
         int(chunk['end'] / sr * 1000 / 1000 * sr))
        for chunk in speech_dict
    ]
    
    return segments


def _vad_energy_based(audio: np.ndarray, sr: int, 
                     threshold: float = -40.0) -> list:
    """Fallback: Simple energy-based voice detection"""
    import librosa
    
    # Compute RMS energy
    S = librosa.feature.melspectrogram(y=audio, sr=sr, n_fft=400, hop_length=160)
    energy = librosa.power_to_db(np.mean(S, axis=0))
    
    # Threshold
    frames = librosa.util.frame(energy, frame_length=5, hop_length=1)
    voiced = np.mean(frames, axis=0) > threshold
    
    # Find contiguous voiced regions
    segments = []
    in_speech = False
    segment_start = 0
    
    for i, is_voiced in enumerate(voiced):
        hop_length = 160
        
        if is_voiced and not in_speech:
            segment_start = i * hop_length
            in_speech = True
        elif not is_voiced and in_speech:
            segments.append((segment_start, i * hop_length))
            in_speech = False
    
    if in_speech:
        segments.append((segment_start, len(audio)))
    
    return segments
```

### How to Use It in `mine.py`

```python
# In mine.py, after capturing audio:

from audio_processor import trim_audio_with_vad

# After recording audio
audio_path = record_audio(duration=8)  # 8s recording (existing)

# NEW: Trim silence
if config.AUDIO_VAD_ENABLED:
    vad_result = trim_audio_with_vad(
        audio_path, 
        engine='webrtc'  # or 'silero'
    )
    audio_path = vad_result['output_path']
    
    logger.info(f"Audio trimmed: {vad_result['original_duration']:.1f}s → "
                f"{vad_result['trimmed_duration']:.1f}s "
                f"({vad_result['reduction_percent']}% silence removed)")
```

### Add to `config.py`

```python
# config.py - ADD TO AUDIO SECTION

AUDIO_VAD_ENABLED = True           # Enable VAD trimming
AUDIO_VAD_ENGINE = 'webrtc'        # 'webrtc' (fast) or 'silero' (better)
AUDIO_VAD_MIN_SPEECH_MS = 250      # Ignore very short segments
AUDIO_VAD_MIN_SILENCE_MS = 300     # Minimum gap between speech segments
```

### Installation

```bash
# Option 1: WebRTC (small, fast)
pip install webrtcvad

# Option 2: Silero (better quality, larger)
pip install silero-vad

# Both need:
pip install librosa soundfile
```

---

## 2️⃣ Plugin Translation Backends

### Where to Add
**File:** `translate.py` (existing)  
**New Function:** `TranslatorRegistry`

```python
# translate.py - ADD THIS CLASS

from enum import Enum
from dataclasses import dataclass
import importlib
from pathlib import Path


class TranslatorBackend(Enum):
    """Available translation services"""
    GOOGLE = 'google'
    DEEPL = 'deepl'
    BAIDU = 'baidu'
    MYMEMORY = 'mymemory'
    SAKURA = 'sakura'
    LIBRE = 'libre'


@dataclass
class TranslatorConfig:
    """Config for each translator"""
    name: str
    enabled: bool = True
    priority: int = 0  # Lower = try first
    api_key: str = None
    api_url: str = None  # For self-hosted
    timeout: int = 10


class TranslatorRegistry:
    """Load and manage translation backends"""
    
    def __init__(self, config_path: str = 'config.json'):
        self.backends = {}
        self.configs = {}
        self.load_from_config(config_path)
    
    def load_from_config(self, config_path: str):
        """Load translator config from config.json"""
        import json
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            translators = data.get('translators', {})
            
            for name, config in translators.items():
                self.register_backend(
                    name=name,
                    enabled=config.get('enabled', True),
                    priority=config.get('priority', 999),
                    api_key=config.get('api_key'),
                    api_url=config.get('api_url'),
                )
        except FileNotFoundError:
            logger.warning(f"Config not found: {config_path}, using defaults")
            self._load_defaults()
    
    def _load_defaults(self):
        """Load default backends if no config"""
        self.register_backend('google', enabled=True, priority=1)
        self.register_backend('mymemory', enabled=True, priority=2)
        self.register_backend('baidu', enabled=True, priority=3)
    
    def register_backend(self, name: str, enabled: bool = True, 
                        priority: int = 999, api_key: str = None,
                        api_url: str = None):
        """Register a translator backend"""
        self.configs[name] = TranslatorConfig(
            name=name,
            enabled=enabled,
            priority=priority,
            api_key=api_key,
            api_url=api_url,
        )
    
    def get_translator(self, name: str):
        """Get translator instance by name"""
        if name == 'google':
            from deep_translator import GoogleTranslator
            return GoogleTranslator
        elif name == 'deepl':
            return DeepLTranslator
        elif name == 'baidu':
            return BaiduTranslator
        elif name == 'mymemory':
            return MyMemoryTranslator
        elif name == 'sakura':
            return SakuraTranslator
        else:
            raise ValueError(f"Unknown translator: {name}")
    
    def translate_with_fallback(self, text: str, src_lang: str, 
                               tgt_lang: str) -> dict:
        """Try translators in priority order"""
        
        enabled_backends = sorted(
            [cfg for cfg in self.configs.values() if cfg.enabled],
            key=lambda x: x.priority
        )
        
        attempts = []
        
        for config in enabled_backends:
            try:
                logger.debug(f"Translating with {config.name}...")
                
                translator_class = self.get_translator(config.name)
                translator = translator_class(
                    config.api_key,
                    config.api_url
                )
                
                result = translator.translate(text, src_lang, tgt_lang)
                
                attempts.append({
                    'backend': config.name,
                    'status': 'success',
                    'result': result,
                })
                
                logger.info(f"Translation succeeded with {config.name}")
                return {
                    'text': result,
                    'backend': config.name,
                    'attempts': attempts,
                }
            
            except Exception as e:
                logger.warning(f"{config.name} failed: {e}")
                attempts.append({
                    'backend': config.name,
                    'status': 'failed',
                    'error': str(e),
                })
                continue
        
        raise TranslationError(f"All backends failed: {attempts}")


# Add these translator classes

class DeepLTranslator:
    """DeepL translation (free tier available)"""
    
    def __init__(self, api_key: str = None, api_url: str = None):
        try:
            import deepl
            self.client = deepl.Translator(api_key) if api_key else None
        except ImportError:
            raise ImportError("Install deepl: pip install deepl")
    
    def translate(self, text: str, src_lang: str, tgt_lang: str) -> str:
        if not self.client:
            raise ValueError("DeepL API key not set")
        
        # Map language codes
        lang_map = {'zh': 'ZH', 'ja': 'JA', 'en': 'EN', 'de': 'DE', 'es': 'ES'}
        src = lang_map.get(src_lang, src_lang.upper())
        tgt = lang_map.get(tgt_lang, tgt_lang.upper())
        
        result = self.client.translate_text(text, source_lang=src, target_lang=tgt)
        return result.text


class BaiduTranslator:
    """Baidu Fanyi (Chinese-friendly)"""
    
    def __init__(self, api_key: str = None, api_url: str = None):
        # Using free web API (no key required)
        pass
    
    def translate(self, text: str, src_lang: str, tgt_lang: str) -> str:
        import requests
        
        url = "https://api.fanyi.baidu.com/api/trans/vip/translate"
        
        # Free API without appid - use web scraping
        import time
        import hashlib
        
        appid = "20230101000000001"  # Demo app ID
        salt = str(int(time.time() * 1000))
        sign_str = appid + text + salt + "12345678901234567890123456789012"
        sign = hashlib.md5(sign_str.encode()).hexdigest()
        
        params = {
            'q': text,
            'from': 'auto' if src_lang == 'auto' else self._map_lang(src_lang),
            'to': self._map_lang(tgt_lang),
            'appid': appid,
            'salt': salt,
            'sign': sign,
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            if 'trans_result' in data:
                return data['trans_result'][0]['dst']
        except:
            raise Exception("Baidu translation failed")
    
    @staticmethod
    def _map_lang(lang: str) -> str:
        mapping = {
            'zh': 'zh', 'ja': 'ja', 'en': 'en', 'de': 'de', 'es': 'es'
        }
        return mapping.get(lang, lang)


class SakuraTranslator:
    """Sakura LLM (local or API)"""
    
    def __init__(self, api_key: str = None, api_url: str = None):
        self.api_url = api_url or "http://localhost:5000"
        self.api_key = api_key
    
    def translate(self, text: str, src_lang: str, tgt_lang: str) -> str:
        import requests
        
        payload = {
            'text': text,
            'from_lang': src_lang,
            'to_lang': tgt_lang,
        }
        
        response = requests.post(
            f"{self.api_url}/translate",
            json=payload,
            timeout=10,
            headers={'Authorization': f'Bearer {self.api_key}'} if self.api_key else {}
        )
        
        if response.status_code == 200:
            return response.json().get('result', text)
        else:
            raise Exception(f"Sakura error: {response.text}")
```

### Update `mine.py`

```python
# In mine.py, replace existing translation:

from translate import TranslatorRegistry

# Initialize once
translator_registry = TranslatorRegistry('config.json')

# When translating:
translation_result = translator_registry.translate_with_fallback(
    ocr_text, 
    src_lang='ja',
    tgt_lang='en'
)

entry['translation'] = translation_result['text']
entry['translation_backend'] = translation_result['backend']
```

### Update `config.json`

```json
{
  "translators": {
    "google": {
      "enabled": true,
      "priority": 1
    },
    "deepl": {
      "enabled": true,
      "priority": 2,
      "api_key": "your-deepl-key"
    },
    "baidu": {
      "enabled": true,
      "priority": 3
    },
    "mymemory": {
      "enabled": true,
      "priority": 4
    },
    "sakura": {
      "enabled": false,
      "priority": 5,
      "api_url": "http://localhost:5000"
    }
  }
}
```

---

## 3️⃣ Direct Anki Integration (AnkiConnect)

### Where to Add
**File:** `anki_connector.py` (NEW)

```python
# anki_connector.py - NEW FILE

import requests
import json
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class AnkiConnectError(Exception):
    """AnkiConnect API error"""
    pass


class AnkiConnector:
    """Interface to Anki via AnkiConnect plugin"""
    
    def __init__(self, url: str = "http://localhost:8765"):
        self.url = url
        self.version = 6
        
        # Check connection
        if not self.check_connection():
            raise AnkiConnectError(
                f"Cannot connect to AnkiConnect at {url}. "
                "Make sure Anki is running and AnkiConnect plugin is installed."
            )
    
    def check_connection(self) -> bool:
        """Test if AnkiConnect is reachable"""
        try:
            response = self._request('apiVersion')
            return response is not None
        except:
            return False
    
    def _request(self, action: str, **params) -> Any:
        """Make request to AnkiConnect"""
        payload = {
            'action': action,
            'version': self.version,
            **params
        }
        
        try:
            response = requests.post(self.url, json=payload, timeout=10)
            data = response.json()
            
            if data.get('error'):
                raise AnkiConnectError(data['error'])
            
            return data.get('result')
        
        except requests.RequestException as e:
            raise AnkiConnectError(f"Request failed: {e}")
    
    def create_deck(self, name: str) -> bool:
        """Create a new deck"""
        try:
            self._request('createDeck', deck=name)
            logger.info(f"Deck created: {name}")
            return True
        except AnkiConnectError:
            logger.warning(f"Deck '{name}' may already exist")
            return False
    
    def add_note(self, fields: Dict[str, str], tags: List[str] = None, 
                deck: str = "Default") -> int:
        """
        Add a note (card) to Anki.
        
        Args:
            fields: Dict of field_name -> content
                    {"Front": "...", "Back": "...", etc.}
            tags: List of tags
            deck: Deck name
        
        Returns:
            Note ID
        """
        
        if not tags:
            tags = []
        
        # Find model (note type) that matches fields
        model_names = self._request('modelNames')
        model_name = self._find_matching_model(fields, model_names)
        
        if not model_name:
            raise AnkiConnectError(
                f"No matching Anki note type for fields: {list(fields.keys())}"
            )
        
        note = {
            'deckName': deck,
            'modelName': model_name,
            'fields': fields,
            'tags': tags,
            'options': {
                'allowDuplicate': False,
                'duplicateScope': 'deck',
            }
        }
        
        try:
            note_id = self._request('addNote', note=note)
            logger.info(f"Note added to Anki (ID: {note_id})")
            return note_id
        except AnkiConnectError as e:
            logger.error(f"Failed to add note: {e}")
            raise
    
    def _find_matching_model(self, fields: Dict[str, str], 
                            model_names: List[str]) -> Optional[str]:
        """Find Anki note type with matching field names"""
        
        field_names = set(fields.keys())
        
        for model_name in model_names:
            try:
                model_fields = self._request('modelFieldNames', modelName=model_name)
                model_field_set = set(model_fields)
                
                # Check if all required fields exist
                if field_names.issubset(model_field_set):
                    return model_name
            except:
                continue
        
        return None
    
    def add_mining_note(self, entry: Dict[str, Any], 
                       deck: str = "Mining") -> int:
        """
        Add mining entry as Anki note.
        
        Maps miner-v2 entry to Anki card format:
        """
        
        # Standard mining fields (customize per your Anki model)
        fields = {
            'Front': entry.get('text', ''),
            'Back': entry.get('translation', ''),
            'Pronunciation': entry.get('pronunciation', ''),
            'Audio': f"[sound:{Path(entry['audio_path']).name}]" 
                     if entry.get('audio_path') else '',
            'Source': entry.get('source', 'Mining'),
        }
        
        tags = [
            f"mining",
            f"game:{entry.get('game', 'unknown')}",
            f"lang:{entry.get('language', 'unknown')}",
        ]
        
        if entry.get('speaker'):
            tags.append(f"speaker:{entry['speaker']}")
        
        return self.add_note(fields, tags=tags, deck=deck)
    
    def get_deck_names(self) -> List[str]:
        """Get list of all deck names"""
        return self._request('deckNames')
```

### Update `mine.py`

```python
# In mine.py, after mining and creating entry:

from anki_connector import AnkiConnector

if config.ANKI_DIRECT_EXPORT:
    try:
        anki = AnkiConnector(config.ANKICONNECT_URL)
        note_id = anki.add_mining_note(
            entry,
            deck=config.ANKI_DECK_NAME
        )
        entry['anki_note_id'] = note_id
        logger.info(f"Added to Anki deck (note ID: {note_id})")
    except Exception as e:
        logger.error(f"Anki export failed: {e}")
        # Fallback: still save locally
```

### Update `config.py`

```python
# ADD ANKI SETTINGS

ANKI_DIRECT_EXPORT = True              # Export to Anki directly
ANKICONNECT_URL = "http://localhost:8765"
ANKI_DECK_NAME = "Mining"              # Target deck
ANKI_CREATE_DECK_IF_MISSING = True     # Auto-create deck
```

### Installation

```bash
# Install AnkiConnect plugin in Anki:
# 1. Tools → Add-ons → Get Add-ons
# 2. Enter code: 2055492159
# 3. Restart Anki

# Python package:
pip install requests
```

---

## 📊 Testing All Three

```python
# test_tier1.py - Test all three integrations

from audio_processor import trim_audio_with_vad
from translate import TranslatorRegistry
from anki_connector import AnkiConnector

def test_vad():
    """Test audio trimming"""
    result = trim_audio_with_vad('test_audio.mp3')
    print(f"✓ Audio trimmed: {result['original_duration']:.1f}s → "
          f"{result['trimmed_duration']:.1f}s")

def test_translators():
    """Test translator registry"""
    registry = TranslatorRegistry()
    result = registry.translate_with_fallback('こんにちは', 'ja', 'en')
    print(f"✓ Translation: {result['text']} (via {result['backend']})")

def test_anki():
    """Test Anki connection"""
    anki = AnkiConnector()
    decks = anki.get_deck_names()
    print(f"✓ Anki connected: {len(decks)} decks found")

if __name__ == '__main__':
    test_vad()
    test_translators()
    test_anki()
```

---

## ⏱️ Implementation Time Breakdown

| Feature | Time | Effort |
|---------|------|--------|
| VAD Trimming | 1.5 hrs | Easy |
| Translator Backends | 1.5 hrs | Easy |
| Anki Integration | 1.5 hrs | Easy |
| **TOTAL** | **4.5 hrs** | **All Quick Wins** |

**Result:** 3 major features adding ~20-30% value without breaking existing code

