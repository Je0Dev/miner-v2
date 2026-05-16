"""Configuration constants for Game Sentence Miner v2."""
import os
from pathlib import Path

# Tesseract data directory (local fallback if system data missing)
LOCAL_TESSDATA = Path(__file__).parent / "tessdata"
if LOCAL_TESSDATA.exists():
    os.environ["TESSDATA_PREFIX"] = str(LOCAL_TESSDATA)

MINING_DIR = Path(__file__).parent / "mining"
ANKI_EXPORT_FILE = "anki_export.csv"
SENTENCES_FILE = "sentences.json"
AUDIO_DIR = "audio"
IMAGES_DIR = "images"
VIDEO_DIR = "video"
ZONES_FILE = "zones.json"
CONFIG_FILE = "config.json"
DB_FILE = "miner.db"

# Language registry: code -> {tesseract, google, name, script, has_romaji}
LANG_REGISTRY = {
    "zh": {"tess": "chi_sim", "google": "zh-CN", "name": "Chinese", "script": "cjk", "romaji": "pinyin"},
    "ja": {"tess": "jpn", "google": "ja", "name": "Japanese", "script": "cjk", "romaji": "romaji"},
    "ko": {"tess": "kor", "google": "ko", "name": "Korean", "script": "cjk", "romaji": "romanization"},
    "de": {"tess": "deu", "google": "de", "name": "German", "script": "latin", "romaji": None},
    "es": {"tess": "spa", "google": "es", "name": "Spanish", "script": "latin", "romaji": None},
    "el": {"tess": "ell", "google": "el", "name": "Greek", "script": "greek", "romaji": "transliteration"},
    "fr": {"tess": "fra", "google": "fr", "name": "French", "script": "latin", "romaji": None},
    "pl": {"tess": "pol", "google": "pl", "name": "Polish", "script": "latin", "romaji": None},
    "ru": {"tess": "rus", "google": "ru", "name": "Russian", "script": "cyrillic", "romaji": "transliteration"},
    "en": {"tess": "eng", "google": "en", "name": "English", "script": "latin", "romaji": None},
}

# Backward compatibility
OCR_LANGS = {k: v["tess"] for k, v in LANG_REGISTRY.items()}
GOOGLE_LANG_CODES = {k: v["google"] for k, v in LANG_REGISTRY.items()}

TRANSLATION_LANGS = {"en": "English"}
REPLAY_BUFFER_SIZE = 20
REPLAY_WINDOW_SECONDS = 120
ANKICONNECT_URL = "http://localhost:8765"
MIN_TEXT_LENGTH = 2
MAX_TEXT_LENGTH = 500
VAD_ENABLED = True
VAD_AGGRESSIVENESS = 2
VAD_PADDING_MS = 200
RECORDING_ENABLED = False
RECORDING_DURATION = 5
RECORDING_FPS = 10
RECORDING_MAX_SEGMENTS = 10
LIVE_OCR_INTERVAL = 2.0
LIVE_OCR_AUTO_HIDE = 10

MINING_DIR.mkdir(parents=True, exist_ok=True)
