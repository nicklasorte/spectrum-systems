"""
interpret.py — INTERPRET stage of the Working Paper Engine pipeline.

Responsibilities:
  - Map ObservedItems into structured concern buckets.
  - Generate initial gap candidates.
  - Map concerns to report sections.
  - Identify contradictions and missing required elements.

Design constraints:
  - Fully deterministic; no LLM calls.
  - Returns only InterpretedConcern objects; no mutations of input.
  - Gap candidates are marked is_gap_candidate=True for later promotion.
"""
from __future__ import annotations

import re
from typing import Dict, List, Set, Tuple

from .models import (
    ConcernBucket,
    InterpretedConcern,
    ObservedItem,
    SectionID,
    SourceType,
)

# ---------------------------------------------------------------------------
# Tag → bucket mapping
# ---------------------------------------------------------------------------

_TAG_TO_BUCKET: Dict[str, ConcernBucket] = {
    "assumption": ConcernBucket.ASSUMPTIONS,
    "constraint": ConcernBucket.CONSTRAINTS,
    "open_issue": ConcernBucket.MISSING_ELEMENTS,
    "uncertainty": ConcernBucket.ASSUMPTIONS,
    "methodology": ConcernBucket.METHODOLOGY,
    "decision": ConcernBucket.AGENCY_CONCERNS,
    "fact": ConcernBucket.DATA,
}

# Bucket → section mappings (primary section reference)
_BUCKET_TO_SECTIONS: Dict[ConcernBucket, List[SectionID]] = {
    ConcernBucket.METHODOLOGY: [SectionID.S3],
    ConcernBucket.DATA: [SectionID.S5],
    ConcernBucket.ASSUMPTIONS: [SectionID.S4],
    ConcernBucket.CONSTRAINTS: [SectionID.S4, SectionID.S3],
    ConcernBucket.AGENCY_CONCERNS: [SectionID.S2, SectionID.S7],
    ConcernBucket.CONTRADICTIONS: [SectionID.S6, SectionID.S7],
    ConcernBucket.MISSING_ELEMENTS: [SectionID.S5, SectionID.S6],
}

# Keywords that strongly indicate a gap
_GAP_KEYWORDS: Tuple[str, ...] = (
    "missing", "not available", "no data", "not yet",
    "gap", "need additional", "undefined", "tbd",
    "to be determined", "open question", "open issue",
    "not validated", "unvalidated", "pending", "unclear",
)

# Patterns that suggest contradictions across observed items
_CONTRADICTION_PATTERNS: Tuple[Tuple[str, str], ...] = (
    (r"\b(\d+)\s*km\b", r"\b(\d+)\s*km\b"),          # conflicting distances
    (r"\b(\d+)\s*dBm\b", r"\b(\d+)\s*dBm\b"),         # conflicting power values
    (r"\b(\d+)\s*MHz\b", r"\b(\d+)\s*MHz\b"),          # conflicting frequencies
)

# Required methodology keywords — absence signals a missing-element concern
_REQUIRED_METHOD_KEYWORDS: Tuple[str, ...] = (
    "propagation model", "link budget", "interference", "path loss",
)


def _is_gap_candidate(item: ObservedItem) -> bool:
    lower = item.text.lower()
    return any(kw in lower for kw in _GAP_KEYWORDS) or item.tag == "open_issue"


def _bucket_for_item(item: ObservedItem) -> ConcernBucket:
    return _TAG_TO_BUCKET.get(item.tag, ConcernBucket.DATA)


def _sections_for_bucket(bucket: ConcernBucket) -> List[SectionID]:
    return list(_BUCKET_TO_SECTIONS.get(bucket, [SectionID.S5]))


def _detect_contradictions(items: List[ObservedItem]) -> List[InterpretedConcern]:
    """
    Simple contradiction detection: find pairs of items from different
    sources that reference conflicting numeric values for the same unit.
    """
    concerns: List[InterpretedConcern] = []
    # Map from pattern → list of (matched_value, item)
    pattern_entries: Dict[str, List[Tuple[str, ObservedItem]]] = {}

    for pattern, _ in _CONTRADICTION_PATTERNS:
        for item in items:
            matches = re.findall(pattern, item.text)
            for match in matches:
                pattern_entries.setdefault(pattern, []).append((match, item))

    seen_pairs: Set[Tuple[str, str]] = set()
    idx = 0
    for pattern, entries in pattern_entries.items():
        if len(entries) < 2:
            continue
        # Check if entries contain different values from different sources
        unique_values = {v for v, _ in entries}
        if len(unique_values) < 2:
            continue
        for i, (val_a, item_a) in enumerate(entries):
            for val_b, item_b in entries[i + 1:]:
                if val_a == val_b:
                    continue
                pair_key = (item_a.item_id, item_b.item_id)
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)
                idx += 1
                concerns.append(
                    InterpretedConcern(
                        concern_id=f"CON-{idx:04d}",
                        bucket=ConcernBucket.CONTRADICTIONS,
                        description=(
                            f"Conflicting values detected: '{val_a}' vs '{val_b}' "
                            f"in sources {item_a.source_artifact_id!r} and "
                            f"{item_b.source_artifact_id!r}."
                        ),
                        source_item_ids=[item_a.item_id, item_b.item_id],
                        section_refs=[SectionID.S6, SectionID.S7],
                        is_gap_candidate=True,
                        confidence=0.7,
                    )
                )
    return concerns


def _detect_missing_methods(items: List[ObservedItem]) -> List[InterpretedConcern]:
    """Flag required methodology topics not found in any observed item."""
    all_text = " ".join(item.text.lower() for item in items)
    concerns: List[InterpretedConcern] = []
    for i, kw in enumerate(_REQUIRED_METHOD_KEYWORDS, start=1):
        if kw not in all_text:
            concerns.append(
                InterpretedConcern(
                    concern_id=f"MISS-{i:04d}",
                    bucket=ConcernBucket.MISSING_ELEMENTS,
                    description=f"No reference to '{kw}' found in any source. This may indicate a missing methodology element.",
                    source_item_ids=[],
                    section_refs=[SectionID.S3, SectionID.S5],
                    is_gap_candidate=True,
                    confidence=0.8,
                )
            )
    return concerns


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def interpret(observed: List[ObservedItem]) -> List[InterpretedConcern]:
    """
    INTERPRET stage: map observed items into structured concern buckets.

    Returns a flat list of InterpretedConcern instances.
    """
    concerns: List[InterpretedConcern] = []

    for idx, item in enumerate(observed, start=1):
        bucket = _bucket_for_item(item)
        sections = _sections_for_bucket(bucket)
        is_gap = _is_gap_candidate(item)
        concerns.append(
            InterpretedConcern(
                concern_id=f"INT-{idx:04d}",
                bucket=bucket,
                description=item.text,
                source_item_ids=[item.item_id],
                section_refs=sections,
                is_gap_candidate=is_gap,
                confidence=item.confidence,
            )
        )

    # Cross-item contradiction detection
    concerns.extend(_detect_contradictions(observed))

    # Missing required methodology checks
    concerns.extend(_detect_missing_methods(observed))

    return concerns
