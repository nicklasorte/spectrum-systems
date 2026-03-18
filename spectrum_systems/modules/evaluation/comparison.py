"""
Comparison — spectrum_systems/modules/evaluation/comparison.py

Structural and semantic comparison of expected vs actual pipeline outputs.

Design principles
-----------------
- Structural comparison uses exact set matching (missing / extra / exact).
- Semantic comparison uses token overlap and substring containment to tolerate
  phrasing differences.
- Both comparisons return precision, recall, and F1 score.
- No external dependencies beyond the Python standard library.

Public API
----------
ComparisonResult
    Container for precision, recall, F1, and per-item details.

compare_structural(expected, actual) -> ComparisonResult
compare_semantic(expected, actual, threshold) -> ComparisonResult
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class ComparisonResult:
    """Result of a structural or semantic comparison.

    Attributes
    ----------
    precision:
        True positives / (true positives + false positives).  Fraction of
        actual items that are also in expected.
    recall:
        True positives / (true positives + false negatives).  Fraction of
        expected items that were found in actual.
    f1_score:
        Harmonic mean of precision and recall.
    matched:
        List of (expected_item, actual_item) pairs that matched.
    missing:
        Expected items not found in actual.
    extra:
        Actual items not found in expected.
    """

    precision: float
    recall: float
    f1_score: float
    matched: List[Any] = field(default_factory=list)
    missing: List[Any] = field(default_factory=list)
    extra: List[Any] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def compare_structural(
    expected: List[Any],
    actual: List[Any],
) -> ComparisonResult:
    """Compare two lists using exact matching.

    Treats each item as a JSON-serialisable value.  Uses set semantics: order
    does not matter, duplicates are collapsed.

    Parameters
    ----------
    expected:
        Ground-truth list from the golden case.
    actual:
        Pipeline-produced list.

    Returns
    -------
    ComparisonResult
    """
    expected_keys = {_item_key(item) for item in expected}
    actual_keys = {_item_key(item) for item in actual}

    matched_keys = expected_keys & actual_keys
    missing_keys = expected_keys - actual_keys
    extra_keys = actual_keys - expected_keys

    # Rebuild human-readable lists
    key_to_expected = {_item_key(item): item for item in expected}
    key_to_actual = {_item_key(item): item for item in actual}

    matched = [(key_to_expected[k], key_to_actual[k]) for k in sorted(matched_keys)]
    missing = [key_to_expected[k] for k in sorted(missing_keys)]
    extra = [key_to_actual[k] for k in sorted(extra_keys)]

    tp = len(matched_keys)
    precision = tp / len(actual_keys) if actual_keys else (1.0 if not expected_keys else 0.0)
    recall = tp / len(expected_keys) if expected_keys else 1.0
    f1 = _f1(precision, recall)

    return ComparisonResult(
        precision=precision,
        recall=recall,
        f1_score=f1,
        matched=matched,
        missing=missing,
        extra=extra,
    )


def compare_semantic(
    expected: List[Any],
    actual: List[Any],
    threshold: float = 0.3,
) -> ComparisonResult:
    """Compare two lists using fuzzy semantic matching.

    Tolerates phrasing differences by computing token-overlap similarity
    between pairs of items.  Each expected item is matched to the best
    available actual item (greedy, highest similarity first).

    Parameters
    ----------
    expected:
        Ground-truth list from the golden case.
    actual:
        Pipeline-produced list.
    threshold:
        Minimum Jaccard similarity required for two items to be considered a
        match.  Defaults to ``0.3``.

    Returns
    -------
    ComparisonResult
    """
    if not expected and not actual:
        return ComparisonResult(precision=1.0, recall=1.0, f1_score=1.0)
    if not expected:
        return ComparisonResult(
            precision=0.0, recall=1.0, f1_score=0.0,
            extra=list(actual),
        )
    if not actual:
        return ComparisonResult(
            precision=1.0, recall=0.0, f1_score=0.0,
            missing=list(expected),
        )

    expected_texts = [_item_text(item) for item in expected]
    actual_texts = [_item_text(item) for item in actual]

    available = list(range(len(actual)))
    matched: List[Any] = []
    missing: List[Any] = []
    used_actual: set = set()

    for i, exp_text in enumerate(expected_texts):
        best_idx: Optional[int] = None
        best_sim = -1.0
        for j in available:
            if j in used_actual:
                continue
            sim = _jaccard_similarity(exp_text, actual_texts[j])
            if sim > best_sim:
                best_sim = sim
                best_idx = j

        if best_idx is not None and best_sim >= threshold:
            matched.append((expected[i], actual[best_idx]))
            used_actual.add(best_idx)
        else:
            missing.append(expected[i])

    extra = [actual[j] for j in range(len(actual)) if j not in used_actual]

    tp = len(matched)
    precision = tp / len(actual) if actual else 1.0
    recall = tp / len(expected) if expected else 1.0
    f1 = _f1(precision, recall)

    return ComparisonResult(
        precision=precision,
        recall=recall,
        f1_score=f1,
        matched=matched,
        missing=missing,
        extra=extra,
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

_STOP_WORDS = frozenset({
    "a", "an", "the", "and", "or", "of", "to", "in", "is", "are",
    "was", "were", "that", "this", "it", "its", "for", "on", "at",
    "by", "with", "from", "as", "be", "been", "being", "have", "has",
    "had", "do", "does", "did", "will", "would", "could", "should",
})


def _tokenize(text: str) -> frozenset:
    raw = re.findall(r"[a-zA-Z0-9]+", text.lower())
    return frozenset(t for t in raw if t not in _STOP_WORDS and len(t) > 1)


def _item_text(item: Any) -> str:
    """Convert an item (str, dict, or other) to a text representation."""
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        # Use the most descriptive text field available
        for key in ("text", "description", "title", "content", "summary", "decision"):
            if key in item and isinstance(item[key], str):
                return item[key]
        # Fallback: JSON-encode the dict
        import json
        try:
            return json.dumps(item, sort_keys=True)
        except (TypeError, ValueError):
            return str(item)
    return str(item)


def _item_key(item: Any) -> str:
    """Produce a stable string key for set-based exact comparison."""
    import json
    if isinstance(item, str):
        return item.strip().lower()
    try:
        return json.dumps(item, sort_keys=True)
    except (TypeError, ValueError):
        return str(item)


def _jaccard_similarity(a: str, b: str) -> float:
    tokens_a = _tokenize(a)
    tokens_b = _tokenize(b)
    if not tokens_a and not tokens_b:
        return 1.0
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


def _f1(precision: float, recall: float) -> float:
    denom = precision + recall
    return (2 * precision * recall / denom) if denom > 0 else 0.0
