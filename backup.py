"""Auto-backup and recovery for mining data."""
import json, shutil, time
from pathlib import Path
from config import MINING_DIR
from log import log

BACKUP_DIR = MINING_DIR / "backups"
MAX_BACKUPS = 10

def create_backup() -> bool:
    """Create timestamped backup of mining data."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"backup_{ts}"
    backup_path.mkdir(exist_ok=True)
    try:
        # Backup key files
        for f in ["sentences.json", "anki_export.csv", "universal_log.txt"]:
            src = MINING_DIR / f
            if src.exists():
                shutil.copy2(src, backup_path / f)
        log.info(f"Backup created: {backup_path}")
        # Clean old backups
        cleanup_old_backups()
        return True
    except Exception as e:
        log.error(f"Backup failed: {e}")
        return False

def cleanup_old_backups():
    """Remove old backups beyond MAX_BACKUPS."""
    backups = sorted(BACKUP_DIR.glob("backup_*"))
    while len(backups) > MAX_BACKUPS:
        oldest = backups.pop(0)
        shutil.rmtree(oldest)
        log.info(f"Removed old backup: {oldest}")

def recover_from_backup(backup_path: Path = None) -> bool:
    """Recover mining data from backup."""
    if backup_path is None:
        backups = sorted(BACKUP_DIR.glob("backup_*"))
        if not backups:
            log.error("No backups available")
            return False
        backup_path = backups[-1]
    try:
        for f in backup_path.iterdir():
            if f.is_file():
                shutil.copy2(f, MINING_DIR / f.name)
        log.info(f"Recovered from: {backup_path}")
        return True
    except Exception as e:
        log.error(f"Recovery failed: {e}")
        return False

def list_backups() -> list:
    """List available backups."""
    return sorted(BACKUP_DIR.glob("backup_*"), reverse=True)
