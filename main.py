#!/usr/bin/env python3
"""Game Sentence Miner v2 - CLI entry point."""
import sys, argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import LANG_REGISTRY
from log import log

def main():
    parser = argparse.ArgumentParser(description="Game Sentence Miner v2")
    parser.add_argument("-l", "--lang", choices=LANG_REGISTRY.keys(), default="zh",
                        help="OCR language (zh, ja, ko, de, es, el, fr, pl, ru, en)")
    parser.add_argument("-t", "--translate-to", default="en", help="Translate to (default: en)")
    parser.add_argument("-a", "--audio-duration", type=int, default=5, help="Audio duration (seconds)")
    parser.add_argument("-s", "--source", default="Game", help="Source name")
    parser.add_argument("--live", action="store_true", help="Launch live OCR overlay")
    parser.add_argument("--no-clipboard", action="store_true", help="Don't copy to clipboard")
    parser.add_argument("--no-vad", action="store_true", help="Disable VAD audio trimming")
    parser.add_argument("--long-text", action="store_true", help="Use OCR optimized for long dialogue")
    args = parser.parse_args()

    if args.live:
        from overlay import LiveOCROverlay
        LiveOCROverlay(ocr_lang=args.lang, translate_to=args.translate_to,
                       source_name=args.source).run()
    else:
        from mine import mine_sentence
        mine_sentence(ocr_lang=args.lang, translate_to=args.translate_to,
                      audio_duration=args.audio_duration, source_name=args.source,
                      auto_clipboard=not args.no_clipboard, use_vad=not args.no_vad,
                      long_text=args.long_text)

if __name__ == "__main__":
    main()
