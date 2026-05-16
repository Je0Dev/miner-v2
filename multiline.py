"""Multi-line text buffer for combining consecutive dialogue lines.

Used in live OCR mode to combine multiple consecutive captures into
a single long text (e.g., dialogue boxes that appear line by line).

From GameSentenceMiner's approach: keeps recent OCR text with timestamps
and combines them when they appear within a time window.
"""
import time
import threading
from collections import deque
from text import clean_text, is_valid_text
from log import log


class MultiLineBuffer:
    """Keeps recent OCR text to combine consecutive dialogue lines."""

    def __init__(self, max_lines: int = 20, window_sec: int = 30):
        self.max_lines = max_lines
        self.window_sec = window_sec
        self.buffer = deque(maxlen=max_lines)
        self._lock = threading.Lock()

    def add(self, text: str, timestamp: float | None = None):
        """Add text to buffer with timestamp."""
        ts = timestamp or time.time()
        cleaned = clean_text(text)
        if not is_valid_text(cleaned):
            return
        with self._lock:
            # Skip duplicates
            for entry in self.buffer:
                if entry["text"] == cleaned:
                    return
            self.buffer.append({"text": cleaned, "time": ts})

    def get_combined(self, max_age_sec: int = 15) -> str:
        """Combine recent lines into a single string."""
        cutoff = time.time() - max_age_sec
        with self._lock:
            recent = [e["text"] for e in self.buffer if e["time"] >= cutoff]
        if not recent:
            return ""
        return "\n".join(recent)

    def get_recent(self, count: int = 5) -> list[dict]:
        """Get recent entries."""
        with self._lock:
            return list(self.buffer)[-count:]

    def clear(self):
        with self._lock:
            self.buffer.clear()

    def get_latest(self) -> str:
        """Get most recent text."""
        with self._lock:
            return self.buffer[-1]["text"] if self.buffer else ""

    def get_all_text(self) -> str:
        """Get all buffered text combined."""
        with self._lock:
            return "\n".join(e["text"] for e in self.buffer)
