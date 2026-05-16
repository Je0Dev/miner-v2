#!/usr/bin/env python3
"""Test script to verify all miner-v2 components work."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

def test_notifications():
    """Test desktop notifications."""
    from translate import notify
    notify("Miner Test", "Notifications are working!", timeout=3000)
    print("[OK] Notifications work")

def test_clipboard():
    """Test clipboard copy/paste."""
    from translate import copy_to_clipboard
    import subprocess
    copy_to_clipboard("Test from miner-v2")
    result = subprocess.run(["wl-paste"], capture_output=True, text=True)
    assert result.stdout.strip() == "Test from miner-v2", f"Clipboard mismatch: {result.stdout}"
    print("[OK] Clipboard works")

def test_ocr():
    """Test OCR with a generated image."""
    from PIL import Image, ImageDraw
    from ocr import ocr_image
    img = Image.new('L', (200, 50), 255)
    draw = ImageDraw.Draw(img)
    draw.text((10, 10), 'Hello World', fill=0)
    img.save('/tmp/test_ocr.png')
    text = ocr_image(Path('/tmp/test_ocr.png'), 'en')
    assert len(text) > 0, "OCR returned empty text"
    print(f"[OK] OCR works: '{text}'")

def test_translation():
    """Test translation."""
    from translate import translate_text
    tr = translate_text("你好", src="zh", dest="en")
    assert len(tr) > 0, "Translation returned empty"
    print(f"[OK] Translation works: '你好' -> '{tr}'")

def test_capture():
    """Test capture module imports and scale detection."""
    from capture import get_display_scale, parse_slurp_geom
    scale = get_display_scale()
    print(f"[OK] Capture module works (scale={scale})")
    geom = parse_slurp_geom("100,100,200,50")
    assert geom == (100, 100, 200, 50), f"Parse failed: {geom}"
    print(f"[OK] Geometry parsing works")

def test_text_processing():
    """Test text processing functions."""
    from text import clean_text, format_with_pinyin, sanitize_unicode
    assert clean_text("  hello  ") == "hello"
    assert clean_text("hello   world") == "hello world"
    py = format_with_pinyin("你好")
    assert "ni" in py.lower(), f"Pinyin failed: {py}"
    print(f"[OK] Text processing works (pinyin: {py})")

def test_mine_imports():
    """Test mine module imports."""
    from mine import mine_sentence
    assert callable(mine_sentence), "mine_sentence not callable"
    print("[OK] mine_sentence imports correctly")

def test_overlay_imports():
    """Test overlay module imports."""
    from overlay import LiveOCROverlay
    assert hasattr(LiveOCROverlay, '__init__'), "LiveOCROverlay not a class"
    print("[OK] LiveOCROverlay imports correctly")

def main():
    print("=" * 50)
    print("Game Sentence Miner v2 - Component Tests")
    print("=" * 50)
    
    tests = [
        test_notifications,
        test_clipboard,
        test_ocr,
        test_translation,
        test_capture,
        test_text_processing,
        test_mine_imports,
        test_overlay_imports,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"[FAIL] {test.__name__}: {e}")
            failed += 1
    
    print("=" * 50)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 50)
    
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
