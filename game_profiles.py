#!/usr/bin/env python3
"""Per-Game Configuration Profiles - Auto-detect game and apply correct settings."""
import json, subprocess, re
from pathlib import Path
from config import MINING_DIR, LANG_REGISTRY

PROFILES_FILE = MINING_DIR / "game_profiles.json"

DEFAULT_PROFILE = {
    "ocr_lang": "zh",
    "translate_to": "en",
    "audio_duration": 5,
    "long_text": False,
    "zone": None,
    "zones": [],
    "ocr_region": None,
    "auto_hide_sec": 15,
    "parallel_translate": False,
    "mssim_enabled": True,
    "notes": ""
}

def _detect_active_window() -> dict | None:
    """Detect the currently active/focused window."""
    try:
        out = subprocess.run(["hyprctl", "activewindow", "-j"],
                            capture_output=True, text=True, timeout=2)
        if out.returncode == 0:
            return json.loads(out.stdout)
    except Exception: pass
    return None

def _get_window_class(window: dict) -> str:
    """Get normalized window class for profile matching."""
    return (window.get("class", "") or window.get("title", "")).lower().strip()

def load_profiles() -> dict:
    """Load all game profiles."""
    if PROFILES_FILE.exists():
        try:
            return json.loads(PROFILES_FILE.read_text())
        except Exception: pass
    return {}

def save_profiles(profiles: dict):
    """Save all game profiles."""
    PROFILES_FILE.write_text(json.dumps(profiles, ensure_ascii=False, indent=2))

def get_profile(window_class: str = None) -> dict:
    """Get profile for current or specified window."""
    profiles = load_profiles()
    if window_class is None:
        window = _detect_active_window()
        if not window:
            return DEFAULT_PROFILE.copy()
        window_class = _get_window_class(window)

    # Exact match first
    if window_class in profiles:
        profile = profiles[window_class]
        return {**DEFAULT_PROFILE, **profile}

    # Partial match
    for key, profile in profiles.items():
        if key in window_class or window_class in key:
            return {**DEFAULT_PROFILE, **profile}

    return DEFAULT_PROFILE.copy()

def create_profile(window_class: str = None, **kwargs) -> dict:
    """Create or update a profile for a game."""
    if window_class is None:
        window = _detect_active_window()
        if not window:
            return DEFAULT_PROFILE.copy()
        window_class = _get_window_class(window)

    profiles = load_profiles()
    profile = {**DEFAULT_PROFILE, **kwargs}
    profiles[window_class] = profile
    save_profiles(profiles)
    return profile

def delete_profile(window_class: str) -> bool:
    """Delete a game profile."""
    profiles = load_profiles()
    if window_class in profiles:
        del profiles[window_class]
        save_profiles(profiles)
        return True
    return False

def list_profiles() -> list[dict]:
    """List all game profiles."""
    profiles = load_profiles()
    result = []
    for cls, profile in profiles.items():
        result.append({"window_class": cls, **profile})
    return result

def auto_detect_and_apply() -> dict:
    """Auto-detect current game and return its profile."""
    window = _detect_active_window()
    if not window:
        return DEFAULT_PROFILE.copy()

    window_class = _get_window_class(window)
    profile = get_profile(window_class)

    # If no profile exists, create one with defaults
    if window_class not in load_profiles():
        create_profile(window_class, notes=f"Auto-created for {window.get('title', window_class)}")

    return profile

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", action="store_true", help="List profiles")
    parser.add_argument("--create", action="store_true", help="Create profile for current window")
    parser.add_argument("--delete", metavar="CLASS", help="Delete profile")
    parser.add_argument("--set", nargs=2, metavar=("KEY", "VALUE"), action="append", help="Set profile value")
    parser.add_argument("--detect", action="store_true", help="Detect current window")
    args = parser.parse_args()

    if args.list:
        for p in list_profiles():
            print(f"  {p['window_class']}: lang={p['ocr_lang']}, zone={p.get('zone', 'none')}")
    elif args.create:
        profile = create_profile()
        print(f"Profile created: {list(load_profiles().keys())[-1]}")
    elif args.delete:
        if delete_profile(args.delete):
            print(f"Deleted profile: {args.delete}")
        else:
            print(f"Profile not found: {args.delete}")
    elif args.set:
        window = _detect_active_window()
        if not window:
            print("No active window detected")
            exit(1)
        wc = _get_window_class(window)
        kwargs = {k: v for k, v in args.set}
        profile = create_profile(wc, **kwargs)
        print(f"Updated profile for {wc}: {kwargs}")
    elif args.detect:
        window = _detect_active_window()
        if window:
            print(f"Window: {window.get('title', 'N/A')}")
            print(f"Class: {_get_window_class(window)}")
            profile = get_profile()
            print(f"Profile: {profile}")
        else:
            print("No active window")
