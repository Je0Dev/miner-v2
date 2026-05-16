"""Health check system - verify all dependencies before mining."""
import subprocess, shutil
from pathlib import Path
from log import log

def check_command(cmd: str) -> bool:
    """Check if command exists."""
    return shutil.which(cmd) is not None

def check_tesseract() -> bool:
    """Check Tesseract is working."""
    try:
        result = subprocess.run(["tesseract", "--version"], capture_output=True, text=True)
        return result.returncode == 0
    except Exception:
        return False

def check_audio() -> dict:
    """Check audio system status."""
    try:
        result = subprocess.run(["pactl", "list", "short", "sources"],
                                capture_output=True, text=True, timeout=5)
        sources = result.stdout.splitlines()
        monitors = [s for s in sources if "monitor" in s]
        return {"available": len(monitors) > 0, "sources": monitors}
    except Exception as e:
        return {"available": False, "error": str(e)}

def run_health_check() -> dict:
    """Run full health check."""
    checks = {
        "grim": check_command("grim"),
        "slurp": check_command("slurp"),
        "ffmpeg": check_command("ffmpeg"),
        "wl-copy": check_command("wl-copy"),
        "tesseract": check_tesseract(),
        "audio": check_audio(),
        "mining_dir": Path(__file__).parent.joinpath("mining").exists(),
    }
    checks["all_ok"] = all([
        checks["grim"], checks["slurp"], checks["ffmpeg"],
        checks["wl-copy"], checks["tesseract"], checks["mining_dir"]
    ])
    return checks

def format_health_report(checks: dict) -> str:
    """Format health check results."""
    lines = ["Health Check Results:", "=" * 40]
    for key, value in checks.items():
        if key == "audio":
            status = "OK" if value.get("available") else "NO SOURCES"
            lines.append(f"  Audio: {status}")
        elif key == "all_ok":
            status = "PASS" if value else "FAIL"
            lines.append(f"\nOverall: {status}")
        else:
            status = "OK" if value else "MISSING"
            lines.append(f"  {key}: {status}")
    return "\n".join(lines)
