"""Screen capture functions - slurp, grim, geometry parsing."""
import subprocess, json, time
from pathlib import Path
from log import log

MAX_RETRIES = 3


def get_display_scale():
    """Get display scale factor from Hyprland."""
    try:
        result = subprocess.run(["hyprctl", "monitors", "-j"],
            capture_output=True, text=True, check=True)
        for m in json.loads(result.stdout):
            if m.get("focused"):
                return float(m.get("scale", 1.0))
    except Exception:
        pass
    return 1.0


def parse_slurp_geom(geom_str: str) -> tuple | None:
    """Parse slurp geometry string."""
    try:
        if "," in geom_str:
            return tuple(map(int, geom_str.split(",")))
        geom_str = geom_str.replace(" ", "")
        if "x" in geom_str and "+" in geom_str:
            wh, rest = geom_str.split("+", 1)
            w, h = map(int, wh.split("x"))
            parts = rest.split("+")
            return int(parts[0]), int(parts[1]) if len(parts) > 1 else 0, w, h
        if "x" in geom_str:
            w, h = map(int, geom_str.split("x"))
            return 0, 0, w, h
    except Exception:
        pass
    return None


def capture_region(output_path: Path, geom: str = None) -> str | None:
    """Capture screen region with slurp + grim. Retries on cancel."""
    scale = get_display_scale()
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            if not geom:
                result = subprocess.run(
                    ["slurp", "-d", "-b", "333333cc", "-c", "ff0000ff", "-s", "ff000044", "-w", "3"],
                    capture_output=True, text=True, timeout=30
                )
                if result.returncode != 0 or not result.stdout.strip():
                    if attempt < MAX_RETRIES:
                        log.info(f"Capture cancelled, retrying ({attempt}/{MAX_RETRIES})")
                        time.sleep(0.3)
                        continue
                    return None
                geom = result.stdout.strip()
            parsed = parse_slurp_geom(geom)
            if not parsed:
                return None
            x, y, w, h = parsed
            sx, sy = int(x * scale), int(y * scale)
            sw, sh = int(w * scale), int(h * scale)
            subprocess.run(["grim", "-g", f"{sx},{sy},{sw},{sh}", str(output_path)], check=True)
            log.info(f"Captured region: {geom}")
            return geom
        except subprocess.CalledProcessError as e:
            log.error(f"Capture failed (attempt {attempt}): {e}")
            if attempt < MAX_RETRIES:
                time.sleep(0.3)
                continue
            return None
    return None


def capture_screenshot(output_path: Path, geom: str = None) -> bool:
    """Capture screenshot, optionally cropped."""
    try:
        if geom:
            scale = get_display_scale()
            parsed = parse_slurp_geom(geom)
            if parsed:
                x, y, w, h = parsed
                sx, sy = int(x * scale), int(y * scale)
                sw, sh = int(w * scale), int(h * scale)
                subprocess.run(["grim", "-g", f"{sx},{sy},{sw},{sh}", str(output_path)],
                    check=True, capture_output=True)
                return True
        subprocess.run(["grim", str(output_path)], check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        log.error(f"Screenshot failed: {e}")
        return False
