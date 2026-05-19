"""Configurable text replacement pipeline - ported from GameSentenceMiner."""
from __future__ import annotations
import re, json
from pathlib import Path
from config import MINING_DIR
from log import log

REPLACEMENT_RULES_FILE = MINING_DIR / "text_replacements.json"
HTML_TAG_WILDCARD_PATTERNS = {"<.*>", "<.+>"}

def load_rules() -> list[dict]:
    if REPLACEMENT_RULES_FILE.exists():
        try:
            return json.loads(REPLACEMENT_RULES_FILE.read_text())
        except Exception: pass
    return []

def save_rules(rules: list[dict]):
    REPLACEMENT_RULES_FILE.write_text(json.dumps(rules, ensure_ascii=False, indent=2))

def add_rule(find: str, replace: str = "", mode: str = "plain",
             case_sensitive: bool = False, whole_word: bool = False,
             enabled: bool = True) -> dict:
    rules = load_rules()
    rule = {"find": find, "replace": replace, "mode": mode,
            "case_sensitive": case_sensitive, "whole_word": whole_word,
            "enabled": enabled}
    rules.append(rule)
    save_rules(rules)
    return rule

def remove_rule(index: int) -> bool:
    rules = load_rules()
    if 0 <= index < len(rules):
        rules.pop(index)
        save_rules(rules)
        return True
    return False

def _apply_rule(text: str, rule: dict) -> str:
    find = rule.get("find", "")
    if not find: return text
    mode = (rule.get("mode", "plain") or "").strip().lower()
    replacement = "" if rule.get("replace") is None else rule["replace"]
    if mode in ("regex", "regex_replace"):
        pattern = find
        if replacement == "" and pattern.replace(" ", "") in HTML_TAG_WILDCARD_PATTERNS:
            pattern = r"<[^>]*>"
        if rule.get("whole_word"):
            pattern = r"\b" + pattern + r"\b"
        flags = 0 if rule.get("case_sensitive") else re.IGNORECASE
        try:
            return re.sub(pattern, replacement, text, flags=flags)
        except re.error as exc:
            log.warning(f"Invalid regex in replacement rule '{find}': {exc}")
            return text
    if rule.get("case_sensitive") and not rule.get("whole_word"):
        return text.replace(find, replacement)
    pattern = re.escape(find)
    if rule.get("whole_word"):
        pattern = r"\b" + pattern + r"\b"
    flags = 0 if rule.get("case_sensitive") else re.IGNORECASE
    return re.sub(pattern, lambda _: replacement, text, flags=flags)

def apply_text_processing(text: str) -> str:
    """Apply all enabled text replacement rules to text."""
    if not text: return text
    rules = load_rules()
    for rule in rules:
        if rule.get("enabled", True):
            text = _apply_rule(text, rule)
    return text
