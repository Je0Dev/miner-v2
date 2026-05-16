#!/bin/bash
# Yomitan Hover Overlay wrapper
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-python3}"
OCR_LANG="${1:-chi_sim}"

# Kill existing instance
pkill -f "yomitan-hover" 2>/dev/null || true
sleep 0.2

exec $PYTHON "$SCRIPT_DIR/yomitan-hover.py" "$OCR_LANG"
