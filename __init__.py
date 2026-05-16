"""Game Sentence Miner v2 - Combined from LunaTranslator + GameSentenceMiner.

This is a complete rewrite combining the best features from both reference projects:

From LunaTranslator:
- Plugin-based text source architecture (clipboard/OCR/texthook)
- MSSIM image stability detection before OCR
- Multi-region OCR support with visual selectors
- Multi-engine parallel translation with ranked display
- Auto-disappear on inactivity
- Frameless translucent window
- Native clipboard listener
- Per-game configuration profiles
- Queued TTS player with auto-forward

From GameSentenceMiner:
- OBS replay buffer + VAD audio pipeline
- WebSocket multi-source text intake
- Yomitan postMessage bridge for dictionary lookups
- Word-level coordinate overlay with furigana
- Session-based file organization
- System tray + desktop notifications
- SQLite database for persistent history

From current implementation:
- Hyprland/Wayland native (grim/slurp)
- deep-translator for free translation
- Tesseract OCR with preprocessing
- AnkiConnect integration
"""
