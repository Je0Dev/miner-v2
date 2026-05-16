#!/bin/bash
# Game Sentence Miner v2 wrapper
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-python3}"

OCR_LANG="zh"; TRANSLATE_TO="en"; AUDIO_DURATION=5
LIVE=false; LONG_TEXT=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -l) OCR_LANG="$2"; shift 2 ;;
        -t) TRANSLATE_TO="$2"; shift 2 ;;
        -a) AUDIO_DURATION="$2"; shift 2 ;;
        --live) LIVE=true; shift ;;
        --long-text) LONG_TEXT=true; shift ;;
        -h) echo "Usage: $0 [-l LANG] [-t LANG] [-a SEC] [--live] [--long-text]"; exit 0 ;;
        *) echo "Unknown: $1"; exit 1 ;;
    esac
done

for cmd in grim slurp tesseract ffmpeg wl-copy; do
    command -v "$cmd" &>/dev/null || { echo "ERROR: $cmd required"; exit 1; }
done

CMD="$PYTHON \"$SCRIPT_DIR/main.py\" -l $OCR_LANG -t $TRANSLATE_TO -a $AUDIO_DURATION"
[ "$LIVE" = true ] && CMD="$CMD --live"
[ "$LONG_TEXT" = true ] && CMD="$CMD --long-text"
eval $CMD
