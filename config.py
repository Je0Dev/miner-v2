"""Configuration constants for Game Sentence Miner v2."""
from pathlib import Path

MINING_DIR = Path.home() / "Downloads" / "Mining"
ANKI_EXPORT_FILE = "anki_export.csv"
SENTENCES_FILE = "sentences.json"
AUDIO_DIR = "audio"
IMAGES_DIR = "images"
VIDEO_DIR = "video"
ZONES_FILE = "zones.json"
CONFIG_FILE = "config.json"
DB_FILE = "miner.db"

# OCR languages: short code -> Tesseract language name
OCR_LANGS = {
    "zh": "chi_sim", "ja": "jpn", "de": "deu", "el": "ell",
    "es": "spa", "en": "eng", "fr": "fra", "ko": "kor",
    "ru": "rus", "pt": "por", "it": "ita", "vi": "vie",
    "th": "tha", "ar": "ara",
}

# Translation target languages
TRANSLATION_LANGS = {
    "en": "English", "ja": "Japanese", "de": "German", "el": "Greek",
    "es": "Spanish", "zh": "Chinese", "fr": "French", "ko": "Korean",
    "ru": "Russian", "pt": "Portuguese", "it": "Italian", "vi": "Vietnamese",
    "th": "Thai", "ar": "Arabic",
}

# Google Translate language code mapping
GOOGLE_LANG_CODES = {
    "zh": "zh-CN", "ja": "ja", "de": "de", "el": "el", "es": "es",
    "en": "en", "fr": "fr", "ko": "ko", "ru": "ru", "pt": "pt",
    "it": "it", "vi": "vi", "th": "th", "ar": "ar",
}

# Replay buffer settings
REPLAY_BUFFER_SIZE = 20
REPLAY_WINDOW_SECONDS = 120

# AnkiConnect
ANKICONNECT_URL = "http://localhost:8765"

# Text filtering
MIN_TEXT_LENGTH = 2
MAX_TEXT_LENGTH = 500

# VAD settings
VAD_ENABLED = True
VAD_AGGRESSIVENESS = 2
VAD_PADDING_MS = 200

# Screen recording
RECORDING_ENABLED = False
RECORDING_DURATION = 5
RECORDING_FPS = 10
RECORDING_MAX_SEGMENTS = 10

# Live OCR settings
LIVE_OCR_INTERVAL = 2.0  # seconds between OCR captures
LIVE_OCR_AUTO_HIDE = 10  # seconds of inactivity before auto-hide

MINING_DIR.mkdir(parents=True, exist_ok=True)
