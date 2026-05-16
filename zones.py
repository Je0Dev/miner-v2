"""Zone management - save and load capture regions."""
import json
from pathlib import Path
from config import MINING_DIR, ZONES_FILE
from log import log

def save_zone(name: str, geom: str, lang: str = "zh") -> bool:
    """Save a capture zone with name, geometry, and language."""
    zones = load_zones()
    zones[name] = {"geom": geom, "lang": lang}
    try:
        with open(MINING_DIR / ZONES_FILE, "w", encoding="utf-8") as f:
            json.dump(zones, f, ensure_ascii=False, indent=2)
        log.info(f"Zone saved: {name} ({geom})")
        return True
    except Exception as e:
        log.error(f"Failed to save zone: {e}")
        return False

def load_zones() -> dict:
    """Load all saved zones."""
    path = MINING_DIR / ZONES_FILE
    if not path.exists(): return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def get_zone(name: str) -> dict | None:
    """Get a specific zone by name."""
    zones = load_zones()
    return zones.get(name)

def list_zones() -> list[str]:
    """List all saved zone names."""
    return list(load_zones().keys())

def delete_zone(name: str) -> bool:
    """Delete a saved zone."""
    zones = load_zones()
    if name in zones:
        del zones[name]
        try:
            with open(MINING_DIR / ZONES_FILE, "w", encoding="utf-8") as f:
                json.dump(zones, f, ensure_ascii=False, indent=2)
            log.info(f"Zone deleted: {name}")
            return True
        except Exception as e:
            log.error(f"Failed to delete zone: {e}")
    return False
