# Game Sentence Miner v2

Complete rewrite combining the best of LunaTranslator and GameSentenceMiner.

## Quick Start

```bash
# Quick capture - select region, OCR, translate, save
./mine.sh -l zh -t en

# Live OCR overlay - draggable box over text
./mine.sh --live -l zh -t en

# Yomitan hover - small window, drag over text
./yomitan-hover.sh chi_sim
```

## Workflow

### Quick Capture (SUPER+X)
1. Press SUPER+X
2. Select text region with slurp (red selection box)
3. OCR extracts text
4. Translation appears in notification (top-left)
5. Text copied to clipboard for Yomitan
6. Audio recorded (5s)
7. Saved to ~/Downloads/Mining/YYYYMMDD_HHMMSS/

### Live OCR (SUPER+O)
1. Press SUPER+O
2. Click "Select Region" -> slurp selection box
3. Click "Start Live" -> auto-OCRs every 2s
4. Text + translation + pinyin shown in window
5. Auto-copied to clipboard for Yomitan
6. Click "Mine" to save with audio

### Yomitan Hover (SUPER+Y)
1. Press SUPER+Y
2. Small window appears (250x60px)
3. Drag window over game text
4. OCRs every 2s, copies to clipboard
5. Yomitan shows definition automatically

## Keybindings

| Key | Action |
|-----|--------|
| SUPER+X | Quick Capture (Chinese) |
| SUPER+SHIFT+X | Quick Capture (Japanese) |
| SUPER+ALT+X | Quick Capture (German) |
| SUPER+O | Live OCR Overlay (Chinese) |
| SUPER+SHIFT+O | Live OCR Overlay (Japanese) |
| SUPER+Y | Yomitan Hover (Chinese) |
| SUPER+SHIFT+Y | Yomitan Hover (Japanese) |
| SUPER+CTRL+X | Kill All |

## Output

~/Downloads/Mining/
- sentences.json - All mined sentences
- history_sentences.txt - Human-readable history
- anki_export.csv - Anki import file
- miner.log - Activity log
- YYYYMMDD_HHMMSS/ - Session folders
  - entry.json - Entry metadata
  - audio/audio_*.mp3 - Audio recordings
  - images/capture.png - OCR source image

## Dependencies

- grim, slurp (screenshots)
- tesseract + language data (OCR)
- ffmpeg (audio recording)
- wl-clipboard (clipboard)
- pipewire/pulseaudio (audio)
- deep-translator (translation)
- pytesseract, pillow (OCR)
- pypinyin (Chinese pinyin)
