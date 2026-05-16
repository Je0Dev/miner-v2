"""Auto text region detection using edge detection."""
import subprocess, json, numpy as np
from PIL import Image, ImageFilter
from pathlib import Path
from log import log

def detect_text_regions(image_path: Path, min_area: int = 5000) -> list:
    """Detect potential text regions using edge density analysis."""
    try:
        img = Image.open(image_path).convert("L")
        arr = np.array(img)
        h, w = arr.shape
        # Edge detection
        edges = np.abs(np.diff(arr, axis=1))
        edge_density = np.mean(edges > 30, axis=1)
        # Find rows with high edge density (likely text)
        threshold = np.mean(edge_density) * 1.5
        text_rows = np.where(edge_density > threshold)[0]
        if len(text_rows) == 0:
            return []
        # Group consecutive rows into regions
        regions = []
        start = text_rows[0]
        for i in range(1, len(text_rows)):
            if text_rows[i] - text_rows[i-1] > 10:
                regions.append((start, text_rows[i-1]))
                start = text_rows[i]
        regions.append((start, text_rows[-1]))
        # Filter by minimum area
        result = []
        for y1, y2 in regions:
            height = y2 - y1
            if height * w >= min_area:
                result.append({"x": 0, "y": y1, "w": w, "h": height})
        log.info(f"Detected {len(result)} text regions")
        return result
    except Exception as e:
        log.error(f"Text detection failed: {e}")
        return []

def auto_capture(output_path: Path) -> bool:
    """Auto-detect and capture text regions."""
    try:
        # Full screenshot first
        subprocess.run(["grim", str(output_path)], check=True, capture_output=True)
        regions = detect_text_regions(output_path)
        if regions:
            log.info(f"Auto-detected regions: {len(regions)}")
            return True
        return False
    except Exception as e:
        log.error(f"Auto capture failed: {e}")
        return False
