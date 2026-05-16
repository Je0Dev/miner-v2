#!/bin/bash
# Yomitan Hover Overlay wrapper
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-python3}"
OCR_LANG="${1:-chi_sim}"

# Map Tesseract codes to short codes
case "$OCR_LANG" in
    chi_sim|zh) LANG_CODE="zh" ;;
    jpn|ja) LANG_CODE="ja" ;;
    kor|ko) LANG_CODE="ko" ;;
    deu|de) LANG_CODE="de" ;;
    spa|es) LANG_CODE="es" ;;
    ell|el) LANG_CODE="el" ;;
    fra|fr) LANG_CODE="fr" ;;
    pol|pl) LANG_CODE="pl" ;;
    rus|ru) LANG_CODE="ru" ;;
    eng|en) LANG_CODE="en" ;;
    *) LANG_CODE="zh" ;;
esac

pkill -f "yomitan-hover" 2>/dev/null || true
sleep 0.2

exec $PYTHON "$SCRIPT_DIR/yomitan-hover.py" "$LANG_CODE"
