"""OCR text comparison utilities - ported from GameSentenceMiner."""
from __future__ import annotations
from dataclasses import dataclass
from difflib import SequenceMatcher
import regex
from rapidfuzz import fuzz

punctuation_regex = regex.compile(r"[\p{P}\p{S}\p{Z}]")

@dataclass(frozen=True)
class OCRCompareSettings:
    """Tunable heuristics for OCR text comparison."""
    evolving_prefix_threshold: int = 85
    anchored_truncation_min_threshold: int = 70
    anchored_truncation_strict_threshold: int = 75
    anchored_truncation_base_margin: int = 15
    anchored_truncation_min_length: int = 8
    anchored_truncation_min_ratio_percent: int = 25
    chunk_subset_min_length: int = 5
    matching_block_short_candidate_limit: int = 4
    matching_block_small_candidate_min_size: int = 1
    matching_block_default_min_size: int = 2
    chunk_coverage_floor_percent: int = 80
    chunk_coverage_ceiling_percent: int = 95
    chunk_coverage_threshold_offset: int = 5
    chunk_longest_block_min: int = 2
    chunk_longest_block_divisor: int = 4

def _resolve_settings(settings: OCRCompareSettings | None) -> OCRCompareSettings:
    return settings or OCRCompareSettings()

def normalize_for_comparison(text: str) -> str:
    """Strip all non-letter/non-digit Unicode characters and collapse whitespace."""
    return punctuation_regex.sub("", str(text))

def is_evolving_text(shorter: str, longer: str, prefix_threshold: int | None = None,
                     settings: OCRCompareSettings | None = None) -> bool:
    """Return True when shorter looks like a prefix of longer (text evolution)."""
    if not shorter or not longer or len(shorter) > len(longer):
        return False
    n = len(shorter)
    active_settings = _resolve_settings(settings)
    resolved_threshold = active_settings.evolving_prefix_threshold if prefix_threshold is None else prefix_threshold
    return fuzz.ratio(shorter, longer[:n]) >= resolved_threshold

def _normalize_candidate(text: str) -> str:
    value = str(text).strip()
    if not value: return ""
    normalized = normalize_for_comparison(value)
    return normalized or value

def _compare_flat_strings(prev_text: str, new_text: str, threshold: int,
                          settings: OCRCompareSettings | None = None) -> bool:
    """Compare two strings with punctuation stripping and anchored truncation checks."""
    active_settings = _resolve_settings(settings)
    norm_prev = _normalize_candidate(prev_text)
    norm_new = _normalize_candidate(new_text)
    if not norm_prev or not norm_new: return False
    similarity = fuzz.ratio(norm_prev, norm_new)
    if similarity >= threshold: return True
    # Handle truncated OCR variants via anchored prefix/suffix comparison
    shorter_len = min(len(norm_prev), len(norm_new))
    longer_len = max(len(norm_prev), len(norm_new))
    min_ratio = max(0.0, active_settings.anchored_truncation_min_ratio_percent / 100.0)
    if (threshold >= active_settings.anchored_truncation_min_threshold
        and shorter_len >= max(1, active_settings.anchored_truncation_min_length)
        and (shorter_len / longer_len) >= min_ratio):
        if threshold >= active_settings.anchored_truncation_strict_threshold and similarity < (
            threshold - active_settings.anchored_truncation_base_margin):
            return False
        shorter_str = norm_prev if len(norm_prev) <= len(norm_new) else norm_new
        longer_str = norm_new if len(norm_prev) <= len(norm_new) else norm_prev
        n = len(shorter_str)
        anchored = max(fuzz.ratio(shorter_str, longer_str[:n]), fuzz.ratio(shorter_str, longer_str[-n:]))
        return anchored >= threshold
    return False

def _normalize_chunks(chunks: list) -> list[str]:
    normalized: list[str] = []
    for chunk in chunks:
        if chunk is None: continue
        candidate = _normalize_candidate(chunk)
        if candidate: normalized.append(candidate)
    return normalized

def _matching_block_stats(reference: str, candidate: str,
                          settings: OCRCompareSettings | None = None) -> tuple[float, int]:
    """Return candidate coverage and longest contiguous match inside reference."""
    if not reference or not candidate: return 0.0, 0
    active_settings = _resolve_settings(settings)
    matcher = SequenceMatcher(None, reference, candidate, autojunk=False)
    min_block_size = (max(1, active_settings.matching_block_small_candidate_min_size)
                      if len(candidate) <= active_settings.matching_block_short_candidate_limit
                      else max(1, active_settings.matching_block_default_min_size))
    covered = 0; longest = 0
    for _, _, size in matcher.get_matching_blocks():
        if size > longest: longest = size
        if size >= min_block_size: covered += size
    return covered / len(candidate), longest

def _chunk_is_covered_by_previous(prev_flat: str, prev_chunks: list[str], new_chunk: str,
                                   threshold: int, settings: OCRCompareSettings | None = None) -> bool:
    """True when new_chunk adds no meaningful content beyond prior OCR."""
    if not prev_flat or not new_chunk: return False
    active_settings = _resolve_settings(settings)
    if new_chunk in prev_flat: return True
    if any(_compare_flat_strings(prev_chunk, new_chunk, threshold) for prev_chunk in prev_chunks):
        return True
    if len(new_chunk) < max(1, active_settings.chunk_subset_min_length): return False
    coverage, longest_block = _matching_block_stats(prev_flat, new_chunk, active_settings)
    coverage_floor = active_settings.chunk_coverage_floor_percent / 100.0
    coverage_ceiling = active_settings.chunk_coverage_ceiling_percent / 100.0
    required_coverage = max(coverage_floor, min(coverage_ceiling,
        (threshold - active_settings.chunk_coverage_threshold_offset) / 100.0))
    required_block = max(active_settings.chunk_longest_block_min,
                         len(new_chunk) // max(1, active_settings.chunk_longest_block_divisor))
    return coverage >= required_coverage and longest_block >= required_block

def _chunks_are_fully_covered(prev_chunks: list, new_chunks: list, threshold: int,
                               settings: OCRCompareSettings | None = None) -> bool:
    active_settings = _resolve_settings(settings)
    norm_prev_chunks = _normalize_chunks(prev_chunks)
    norm_new_chunks = _normalize_chunks(new_chunks)
    if not norm_prev_chunks or not norm_new_chunks: return False
    prev_flat = "".join(norm_prev_chunks)
    return all(_chunk_is_covered_by_previous(prev_flat, norm_prev_chunks, nc, threshold, active_settings)
               for nc in norm_new_chunks)

def compare_ocr_results(prev_text: str | list | None, new_text: str | list | None,
                        threshold: int = 90, settings: OCRCompareSettings | None = None) -> bool:
    """Return True when prev_text and new_text are similar enough.
    Supports str and list[str] inputs. Uses rapidfuzz + regex for Unicode-aware comparison."""
    if not prev_text or not new_text: return False
    active_settings = _resolve_settings(settings)
    prev_chunks = prev_text if isinstance(prev_text, list) else None
    new_chunks = new_text if isinstance(new_text, list) else None
    if isinstance(prev_text, list):
        prev_text = "".join(str(item) for item in prev_text if item is not None)
    if isinstance(new_text, list):
        new_text = "".join(str(item) for item in new_text if item is not None)
    prev_text = str(prev_text).strip()
    new_text = str(new_text).strip()
    if not prev_text or not new_text: return False
    if prev_chunks is not None and new_chunks is not None:
        return _chunks_are_fully_covered(prev_chunks, new_chunks, threshold, active_settings)
    return _compare_flat_strings(prev_text, new_text, threshold, active_settings)
