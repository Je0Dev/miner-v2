"""Logging configuration for Game Sentence Miner v2."""
import logging
from pathlib import Path
from config import MINING_DIR

LOG_FILE = MINING_DIR / "miner.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

log = logging.getLogger("miner")
