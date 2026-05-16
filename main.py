#!/usr/bin/env python3
"""Game Sentence Miner v2 - CLI entry point."""
import sys, argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import LANG_REGISTRY
from zones import list_zones, save_zone, delete_zone
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
    parser.add_argument("--zone", help="Use saved zone for capture")
    parser.add_argument("--save-zone", metavar="NAME", help="Save current selection as zone")
    parser.add_argument("--list-zones", action="store_true", help="List saved zones")
    parser.add_argument("--delete-zone", metavar="NAME", help="Delete a saved zone")
    parser.add_argument("--multi-region", nargs="+", metavar="ZONE", help="Capture multiple zones")
    args = parser.parse_args()

    if args.list_zones:
        zones = list_zones()
        if zones:
            print("Saved zones:")
            for z in zones: print(f"  {z}")
        else:
            print("No zones saved")
        return

    if args.save_zone:
        from capture import capture_region
        from pathlib import Path
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name
        geom = capture_region(Path(tmp_path))
        if geom:
            save_zone(args.save_zone, geom, args.lang)
            print(f"Zone '{args.save_zone}' saved")
        return

    if args.delete_zone:
        if delete_zone(args.delete_zone):
            print(f"Zone '{args.delete_zone}' deleted")
        else:
            print(f"Zone '{args.delete_zone}' not found")
        return

    if args.live:
        from overlay import LiveOCROverlay
        LiveOCROverlay(ocr_lang=args.lang, translate_to=args.translate_to,
                       source_name=args.source).run()
    elif args.multi_region:
        from mine import mine_multi_region
        mine_multi_region(ocr_lang=args.lang, translate_to=args.translate_to,
                          audio_duration=args.audio_duration, source_name=args.source,
                          auto_clipboard=not args.no_clipboard, long_text=args.long_text,
                          zones=args.multi_region)
    else:
        from mine import mine_sentence
        mine_sentence(ocr_lang=args.lang, translate_to=args.translate_to,
                      audio_duration=args.audio_duration, source_name=args.source,
                      auto_clipboard=not args.no_clipboard, use_vad=not args.no_vad,
                      long_text=args.long_text, zone_name=args.zone)

if __name__ == "__main__":
    main()
