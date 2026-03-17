"""
Gap Detection Module — spectrum_systems/modules/gap_detection.py

Architecture boundary
---------------------
This module owns all Prompt P gap detection and signal reconciliation logic
for the Slide Intelligence Layer.  ``slide_intelligence.py`` acts as the
orchestrator/caller; it should not re-implement any of the logic housed here.

Canonical outputs
-----------------
All gap-related outputs use the *canonical gap object* shape::

    {
        "gap_id":            str,
        "gap_type":          str,    # see GAP_TYPES below
        "description":       str,
        "severity":          str,    # "high" | "medium" | "low"
        "source_slide_id":   str | None,
        "related_claim_ids": list[str],
        "evidence":          str | None,  # optional lightweight provenance
    }

All follow-up outputs use the *canonical follow-up object* shape::

    {
        "followup_id":    str,
        "type":           str,   # "discuss" | "add_evidence" | "clarify_alignment"
        "text":           str,
        "source_type":    str,   # "slide" | "transcript" | "gap"
        "source_id":      str,
        "target_section": str | None,
        "severity":       str | None,
    }

Public API
----------
- ``detect_slide_gaps(...)``                — intra-slide gap detection (Prompt P rules)
- ``compute_slide_transcript_gaps(...)``    — reconciliation gap analysis
- ``merge_slide_transcript_outputs(...)``   — slide/transcript merge
- ``detect_cross_slide_contradictions(...)``— cross-slide contradiction detection

Design constraints
------------------
- Fully deterministic; no LLM calls, no embeddings, no network access.
- Prefer false negatives over false positives in contradiction detection.
- Preserve current behaviour from P-fix-1/P-fix-2A unless intentionally
  superseded by new contradiction detection or structured follow-ups.
"""
from __future__ import annotations

import re
import uuid
from typing import Any

# ---------------------------------------------------------------------------
# Canonical gap types
# ---------------------------------------------------------------------------

#: Set of all valid ``gap_type`` strings.
GAP_TYPES: frozenset[str] = frozenset({
    "missing_propagation_model",
    "missing_assumption",
    "missing_criteria",
    "missing_method",
    "missing_basis",
    "contradiction",
    "reconciliation_gap",
})

# ---------------------------------------------------------------------------
# Stopwords and token-extraction helpers
# (Kept here to avoid importing back into slide_intelligence to prevent circular deps)
# ---------------------------------------------------------------------------

_STOPWORDS: frozenset[str] = frozenset({
    "a", "an", "the", "and", "or", "but", "nor", "so", "yet", "for",
    "in", "on", "at", "by", "to", "of", "up", "as", "is", "are", "was",
    "were", "be", "been", "being", "have", "has", "had", "do", "does",
    "did", "will", "would", "shall", "should", "may", "might", "must",
    "can", "could", "not", "no", "nor", "from", "with", "about", "into",
    "than", "then", "that", "this", "these", "those", "it", "its",
    "we", "our", "us", "i", "my", "me", "he", "she", "they", "them",
    "his", "her", "their", "who", "which", "what", "when", "where",
    "how", "all", "any", "each", "both", "few", "more", "most", "other",
    "some", "such", "if", "while", "although", "because", "since",
    "during", "after", "before", "also", "just", "only", "even", "also",
    "very", "too", "here", "there", "per", "via", "over", "under",
    "new", "use", "used", "using",
})

_MIN_SUPPORT_TOKENS = 2
_ALIGNMENT_THRESHOLD = 0.15

# Placeholder slide ID used when a match is found via direct text overlap.
_SLIDE_DIRECT_MATCH_ID = "slide_direct_match"


def _extract_tokens(text: str) -> set[str]:
    """Return lowercase, non-stopword word-tokens of ≥3 chars from *text*.

    Reused across all reconciliation logic for consistent token extraction.
    Deterministic and regex-based; no external dependencies.
    """
    raw = re.findall(r"\b[a-z]{3,}\b", text.lower())
    return {t for t in raw if t not in _STOPWORDS}


# ---------------------------------------------------------------------------
# Deck-level assumption index
# (Extracted from slide_intelligence.py to live here as part of the Prompt P
# subsystem boundary)
# ---------------------------------------------------------------------------

def build_deck_assumption_index(slide_units: list[dict]) -> dict:
    """Build a lightweight index of propagation/method keywords present anywhere
    in the slide deck.  Used by :func:`detect_slide_gaps` to avoid firing
    Rule 1 on a result slide simply because *that slide* does not mention the
    model while another slide in the same deck already does.

    Returns a dict with boolean flags::

        {
            "has_propagation_model": bool,
            "has_method_context":    bool,
        }
    """
    propagation_kws = {
        "propagation model", "path loss model", "itm", "longley-rice", "p.452",
        "p.1546", "p.528", "okumura", "hata", "cost 231", "ray tracing",
        "ray-tracing", "monte carlo", "terrain model", "clutter model",
    }
    method_kws = {
        "methodology", "method", "approach", "simulation", "analysis",
        "monte carlo", "computed", "modeled", "calculated",
    }
    has_propagation = False
    has_method = False
    for unit in slide_units:
        text = (
            (unit.get("title") or "")
            + " "
            + (unit.get("notes") or "")
            + " "
            + (unit.get("raw_text") or "")
            + " "
            + " ".join(unit.get("bullets") or [])
        ).lower()
        if not has_propagation and any(kw in text for kw in propagation_kws):
            has_propagation = True
        if not has_method and any(kw in text for kw in method_kws):
            has_method = True
        if has_propagation and has_method:
            break
    return {
        "has_propagation_model": has_propagation,
        "has_method_context": has_method,
    }


# ---------------------------------------------------------------------------
# Canonical gap object helpers
# ---------------------------------------------------------------------------

def _make_gap(
    gap_id: str,
    gap_type: str,
    description: str,
    severity: str,
    source_slide_id: str | None,
    related_claim_ids: list[str],
    evidence: str | None = None,
) -> dict:
    """Construct a canonical gap object.

    Parameters
    ----------
    gap_id:
        Unique identifier for the gap (e.g. ``"GAP-SLIDE-001-001"``).
    gap_type:
        One of :data:`GAP_TYPES`.
    description:
        Human-readable description of the gap.
    severity:
        ``"high"`` | ``"medium"`` | ``"low"``.
    source_slide_id:
        Slide that produced the gap, or ``None`` for cross-deck / meeting gaps.
    related_claim_ids:
        Claim IDs linked to this gap.
    evidence:
        Optional lightweight provenance string.
    """
    return {
        "gap_id": gap_id,
        "gap_type": gap_type,
        "description": description,
        "severity": severity,
        "source_slide_id": source_slide_id,
        "related_claim_ids": related_claim_ids,
        "evidence": evidence,
    }


# ---------------------------------------------------------------------------
# Canonical follow-up object helpers
# ---------------------------------------------------------------------------

def _make_followup(
    followup_id: str,
    followup_type: str,
    text: str,
    source_type: str,
    source_id: str,
    target_section: str | None = None,
    severity: str | None = None,
) -> dict:
    """Construct a canonical follow-up object."""
    return {
        "followup_id": followup_id,
        "type": followup_type,
        "text": text,
        "source_type": source_type,
        "source_id": source_id,
        "target_section": target_section,
        "severity": severity,
    }


# ---------------------------------------------------------------------------
# A. Intra-slide gap detection  (Prompt P rules)
# ---------------------------------------------------------------------------

def detect_slide_gaps(
    slide_unit: dict,
    claims: list[dict],
    assumptions: list[dict],
    *,
    deck_assumption_index: dict | None = None,
) -> list[dict]:
    """Detect negative-space gaps in a single slide unit's technical content.

    Implements the five Prompt P rules:

    1. Interference claim without a stated propagation model (deck-aware).
    2. Technical conclusion without any supporting assumptions.
    3. Mitigation claim without quantitative criteria or conditions.
    4. Result-like statement without a stated analysis method.
    5. Recommendation without an explicit basis or rationale.

    Parameters
    ----------
    slide_unit:
        A dict produced by :func:`~slide_intelligence.extract_slide_units`.
    claims:
        Output of :func:`~slide_intelligence.extract_claims` for this slide.
    assumptions:
        Output of :func:`~slide_intelligence.extract_assumptions` for this slide.
    deck_assumption_index:
        Optional dict from :func:`build_deck_assumption_index`.  When provided,
        Rule 1 uses deck-level context to avoid false positives.

    Returns
    -------
    list[dict]
        List of canonical gap objects.
    """
    slide_id: str = slide_unit.get("slide_id", "unknown")
    full_text: str = (
        (slide_unit.get("raw_text") or "")
        + " "
        + " ".join(slide_unit.get("bullets") or [])
    ).lower()

    gaps: list[dict] = []
    assumption_types = {a["type"] for a in assumptions}

    def _add(gap_type: str, description: str, severity: str, related: list[str]) -> None:
        gid = f"GAP-{slide_id}-{len(gaps) + 1:03d}"
        gaps.append(_make_gap(gid, gap_type, description, severity, slide_id, related))

    # Rule 1 — interference claim without propagation model (deck-aware)
    has_interference_claim = any(
        re.search(r"interfere|coexist|compatibility|harmful", c["claim_text"], re.IGNORECASE)
        for c in claims
    )
    has_propagation_assumption = "propagation_model" in assumption_types
    has_propagation_text = any(
        kw in full_text
        for kw in ["propagation model", "path loss model", "itm", "longley-rice", "p.452"]
    )
    deck_has_propagation = (
        deck_assumption_index is not None
        and deck_assumption_index.get("has_propagation_model", False)
    )
    if (
        has_interference_claim
        and not has_propagation_assumption
        and not has_propagation_text
        and not deck_has_propagation
    ):
        related = [
            c["claim_id"] for c in claims
            if re.search(r"interfere|coexist|compatibility", c["claim_text"], re.IGNORECASE)
        ]
        _add(
            "missing_propagation_model",
            "Interference claim present without stated propagation model.",
            "high",
            related,
        )

    # Rule 2 — technical conclusion without supporting assumptions
    has_conclusion = any(
        re.search(r"shows|demonstrates|confirms|result|finding", c["claim_text"], re.IGNORECASE)
        for c in claims
    )
    if has_conclusion and not assumptions:
        _add(
            "missing_assumption",
            "Technical conclusion present without supporting assumptions.",
            "medium",
            [c["claim_id"] for c in claims],
        )

    # Rule 3 — mitigation claim without criteria
    has_mitigation_claim = any(
        re.search(r"mitigat|guard band|filter|power control", c["claim_text"], re.IGNORECASE)
        for c in claims
    )
    has_mitigation_criteria = any(
        kw in full_text
        for kw in ["dB", "dbm", "mhz", "km", "percent", "%", "threshold"]
    )
    if has_mitigation_claim and not has_mitigation_criteria:
        related = [
            c["claim_id"] for c in claims
            if re.search(r"mitigat|guard band|filter", c["claim_text"], re.IGNORECASE)
        ]
        _add(
            "missing_criteria",
            "Mitigation claim stated without quantitative criteria or conditions.",
            "medium",
            related,
        )

    # Rule 4 — result without method
    has_result = any(
        re.search(r"result|calculated|computed|modeled|simulated", c["claim_text"], re.IGNORECASE)
        for c in claims
    )
    has_method = any(
        kw in full_text
        for kw in ["methodology", "method", "approach", "simulation", "analysis", "monte carlo"]
    )
    if has_result and not has_method:
        related = [
            c["claim_id"] for c in claims
            if re.search(r"result|calculated|computed|modeled|simulated", c["claim_text"], re.IGNORECASE)
        ]
        _add(
            "missing_method",
            "Result-like statement present without stated analysis method.",
            "medium",
            related,
        )

    # Rule 5 — recommendation without basis
    recommendation_re = re.compile(r"recommend|propose|should\s+be|suggest", re.IGNORECASE)
    has_recommendation = any(
        recommendation_re.search(c["claim_text"]) for c in claims
    ) or recommendation_re.search(full_text) is not None
    has_basis = any(
        kw in full_text
        for kw in ["based on", "because", "since", "given", "per the", "due to"]
    )
    if has_recommendation and not has_basis:
        related = [
            c["claim_id"] for c in claims
            if recommendation_re.search(c["claim_text"])
        ]
        _add(
            "missing_basis",
            "Recommendation stated without an explicit basis or rationale.",
            "low",
            related,
        )

    return gaps


# ---------------------------------------------------------------------------
# B. Cross-slide contradiction detection
# ---------------------------------------------------------------------------

# Polarity pairs: if slide A contains the positive pattern and slide B contains
# the negative pattern (or vice versa) for the same topic/entity, it is a
# polarity contradiction.
_POLARITY_PAIRS: list[tuple[re.Pattern, re.Pattern]] = [
    (
        re.compile(r"\bmay interfere\b|\bwill interfere\b|\bcauses interference\b", re.IGNORECASE),
        re.compile(r"\bdoes not interfere\b|\bwill not cause\b|\bno interference\b", re.IGNORECASE),
    ),
    (
        re.compile(r"\bcannot coexist\b|\bincompatible\b", re.IGNORECASE),
        re.compile(r"\bcan coexist\b|\bcompatible\b", re.IGNORECASE),
    ),
]

# Numeric extraction: captures value + unit from claim text.
_NUMERIC_RE = re.compile(
    r"(-?\d+(?:\.\d+)?)\s*(km|m|MHz|GHz|kHz|dBm|dBW|dB|dBi|W|%)",
    re.IGNORECASE,
)

# Topic/entity overlap keywords used for conservative matching.
_TOPIC_KEYWORDS: list[str] = [
    "interference", "separation", "exclusion zone", "exclusion", "guard band",
    "coexistence", "compatibility", "propagation", "path loss",
    "radar", "5g", "gnss", "satellite", "transmitter", "receiver",
    "zone", "distance", "range", "power",
]


def _claim_topic_tokens(claim_text: str) -> set[str]:
    """Extract topic-relevant tokens from a claim for overlap comparison."""
    tokens = _extract_tokens(claim_text)
    # Add topic keyword matches for richer overlap
    lower = claim_text.lower()
    for kw in _TOPIC_KEYWORDS:
        if kw in lower:
            tokens.add(kw.replace(" ", "_"))
    # Include measurement units as topic tokens so numeric claims about
    # the same unit (e.g. "km" in both "exclusion zone 5 km" and
    # "separation 3 km") count as shared evidence.
    for _, unit in _extract_numerics(claim_text):
        tokens.add(unit)
    return tokens


def _extract_numerics(text: str) -> list[tuple[float, str]]:
    """Return list of (value, unit) pairs found in *text*."""
    results = []
    for m in _NUMERIC_RE.finditer(text):
        try:
            val = float(m.group(1))
            unit = m.group(2).lower()
            results.append((val, unit))
        except ValueError:
            pass
    return results


def _topics_overlap(claim_a: str, claim_b: str) -> bool:
    """Return True if the two claims share ≥2 topic-relevant tokens."""
    tokens_a = _claim_topic_tokens(claim_a)
    tokens_b = _claim_topic_tokens(claim_b)
    return len(tokens_a & tokens_b) >= 2


def detect_cross_slide_contradictions(
    slide_units: list[dict],
    all_claims: list[dict],
) -> list[dict]:
    """Detect contradictory claims across slides in the same deck.

    Uses deterministic keyword and numeric matching.  No LLM, no embeddings.

    Detects two contradiction classes:

    1. **Quantitative conflict** — same topic/entity pair asserts different
       numeric values with the same unit (e.g. separation 5 km vs 3 km).
    2. **Polarity conflict** — one slide asserts interference / incompatibility
       while another asserts the opposite.

    Conservative matching: only emits a contradiction gap when topic/entity
    overlap between the two claims is reasonably strong (≥2 shared tokens).

    Parameters
    ----------
    slide_units:
        All slide units from :func:`~slide_intelligence.extract_slide_units`.
        Used for context; the contradiction detection works on *all_claims*.
    all_claims:
        All extracted claims from the entire deck (concatenation of per-slide
        :func:`~slide_intelligence.extract_claims` outputs).

    Returns
    -------
    list[dict]
        List of canonical gap objects with ``gap_type = "contradiction"``.
        Each gap includes an ``evidence`` field linking the conflicting claims.
    """
    gaps: list[dict] = []
    gap_counter = 0

    # Build a mapping from slide_id → slide unit for caution-flag wiring
    _slide_by_id: dict[str, dict] = {u["slide_id"]: u for u in slide_units}

    # Seen pairs to avoid duplicate gap entries
    _seen_pairs: set[frozenset] = set()

    def _add_contradiction(
        claim_a: dict,
        claim_b: dict,
        description: str,
        severity: str,
    ) -> None:
        nonlocal gap_counter
        pair_key = frozenset({claim_a["claim_id"], claim_b["claim_id"]})
        if pair_key in _seen_pairs:
            return
        _seen_pairs.add(pair_key)
        gap_counter += 1
        gid = f"CONTRA-{gap_counter:03d}"
        evidence = (
            f"Claim {claim_a['claim_id']} on slide {claim_a['source_slide_id']!r}: "
            f"{claim_a['claim_text']!r}; "
            f"Claim {claim_b['claim_id']} on slide {claim_b['source_slide_id']!r}: "
            f"{claim_b['claim_text']!r}"
        )
        gaps.append(_make_gap(
            gid,
            "contradiction",
            description,
            severity,
            claim_a["source_slide_id"],  # primary slide
            [claim_a["claim_id"], claim_b["claim_id"]],
            evidence=evidence,
        ))

    # --- Pass 1: polarity contradictions ---
    for i, claim_a in enumerate(all_claims):
        for claim_b in all_claims[i + 1:]:
            # Skip claims from the same slide
            if claim_a["source_slide_id"] == claim_b["source_slide_id"]:
                continue
            # Require topic overlap before checking polarity
            if not _topics_overlap(claim_a["claim_text"], claim_b["claim_text"]):
                continue
            for pos_pat, neg_pat in _POLARITY_PAIRS:
                a_pos = bool(pos_pat.search(claim_a["claim_text"]))
                b_neg = bool(neg_pat.search(claim_b["claim_text"]))
                a_neg = bool(neg_pat.search(claim_a["claim_text"]))
                b_pos = bool(pos_pat.search(claim_b["claim_text"]))
                if (a_pos and b_neg) or (a_neg and b_pos):
                    _add_contradiction(
                        claim_a,
                        claim_b,
                        (
                            f"Polarity conflict between slides "
                            f"{claim_a['source_slide_id']!r} and "
                            f"{claim_b['source_slide_id']!r}: "
                            f"opposite interference/compatibility assertions on same topic."
                        ),
                        "high",
                    )
                    break  # one polarity check per pair is enough

    # --- Pass 2: quantitative contradictions (same unit, different value) ---
    for i, claim_a in enumerate(all_claims):
        nums_a = _extract_numerics(claim_a["claim_text"])
        if not nums_a:
            continue
        for claim_b in all_claims[i + 1:]:
            if claim_a["source_slide_id"] == claim_b["source_slide_id"]:
                continue
            if not _topics_overlap(claim_a["claim_text"], claim_b["claim_text"]):
                continue
            nums_b = _extract_numerics(claim_b["claim_text"])
            if not nums_b:
                continue
            # Find same-unit pairs with different values
            for val_a, unit_a in nums_a:
                for val_b, unit_b in nums_b:
                    if unit_a == unit_b and val_a != val_b:
                        # Conservative: only flag when the difference is ≥10%
                        if max(abs(val_a), abs(val_b)) > 0:
                            pct_diff = abs(val_a - val_b) / max(abs(val_a), abs(val_b))
                            if pct_diff >= 0.10:
                                _add_contradiction(
                                    claim_a,
                                    claim_b,
                                    (
                                        f"Quantitative conflict between slides "
                                        f"{claim_a['source_slide_id']!r} and "
                                        f"{claim_b['source_slide_id']!r}: "
                                        f"conflicting {unit_a} values "
                                        f"({val_a} vs {val_b}) on same topic."
                                    ),
                                    "high",
                                )
                            break
                else:
                    continue
                break  # one numeric conflict per pair is enough

    return gaps


# ---------------------------------------------------------------------------
# C. Slide / transcript merge  (previously in slide_intelligence.py)
# ---------------------------------------------------------------------------

def merge_slide_transcript_outputs(
    transcript_structured: dict,
    slide_signals: dict,
    alignment_map: list[dict],
) -> dict:
    """Merge slide-extracted signals with structured transcript output.

    For each decision, action item, and open question in
    ``transcript_structured``, determine whether a matching slide provides
    evidence.  Adds ``slide_support`` (bool) and ``source_slide_ids`` (list)
    to each item.

    Also identifies:

    - ``slide_only_content`` — bullets/claims from slides with no match in
      the transcript.
    - ``discussion_only_content`` — items from the transcript with no slide
      backing.

    Parameters
    ----------
    transcript_structured:
        Structured extraction dict (decisions, action_items, open_questions).
    slide_signals:
        Output of :func:`~slide_intelligence.extract_slide_signals`.
    alignment_map:
        Output of :func:`~slide_intelligence.align_slides_to_transcript`.

    Returns
    -------
    dict
        Enriched record with all original fields plus slide support metadata.
    """

    def _text_of(item: dict | str) -> str:
        if isinstance(item, str):
            return item.lower()
        for key in ("description", "text", "content", "summary", "body"):
            if key in item:
                return str(item[key]).lower()
        return str(item).lower()

    # Build a set of all slide signal texts (lowercased) for quick lookup
    slide_texts: list[str] = []
    for key in ("claims", "assumptions", "proposals", "metrics", "open_questions"):
        slide_texts.extend(s.lower() for s in slide_signals.get(key, []))

    # Map of slide_id → matched segment texts
    alignment_lookup: dict[str, list[str]] = {
        entry["slide_id"]: [s.lower() for s in entry.get("matched_segments", [])]
        for entry in alignment_map
    }

    def _has_slide_support(item_text: str) -> tuple[bool, list[str]]:
        """Return (has_support, list_of_matching_slide_ids).

        Support requires at least ``_MIN_SUPPORT_TOKENS`` shared meaningful
        (non-stopword) tokens between the transcript item and the slide/segment
        text.
        """
        item_tokens = _extract_tokens(item_text)
        supporting_slides: list[str] = []
        for slide_id, seg_texts in alignment_lookup.items():
            seg_combined = " ".join(seg_texts)
            seg_tokens = _extract_tokens(seg_combined)
            if len(item_tokens & seg_tokens) >= _MIN_SUPPORT_TOKENS:
                supporting_slides.append(slide_id)
        if not supporting_slides:
            for st in slide_texts:
                st_tokens = _extract_tokens(st)
                if len(item_tokens & st_tokens) >= _MIN_SUPPORT_TOKENS:
                    supporting_slides.append(_SLIDE_DIRECT_MATCH_ID)
                    break
        return (len(supporting_slides) > 0, supporting_slides)

    def _enrich_list(items: list) -> list:
        enriched = []
        for item in items:
            item_copy = dict(item) if isinstance(item, dict) else {"text": item}
            support, slide_ids = _has_slide_support(_text_of(item_copy))
            item_copy["slide_support"] = support
            item_copy["source_slide_ids"] = list(set(slide_ids))
            enriched.append(item_copy)
        return enriched

    enriched = dict(transcript_structured)
    enriched["decisions"] = _enrich_list(transcript_structured.get("decisions", []))
    enriched["action_items"] = _enrich_list(transcript_structured.get("action_items", []))
    enriched["open_questions"] = _enrich_list(transcript_structured.get("open_questions", []))

    # Identify slide-only content
    all_transcript_text = " ".join(
        _text_of(item)
        for key in ("decisions", "action_items", "open_questions")
        for item in transcript_structured.get(key, [])
    )
    transcript_sig_tokens = _extract_tokens(all_transcript_text)

    slide_only: list[str] = []
    _slide_only_seen: set[str] = set()
    for sig_key in ("claims", "proposals", "open_questions", "metrics"):
        for text in slide_signals.get(sig_key, []):
            sig_tokens = _extract_tokens(text)
            if (
                len(sig_tokens & transcript_sig_tokens) < _MIN_SUPPORT_TOKENS
                and text not in _slide_only_seen
            ):
                slide_only.append(text)
                _slide_only_seen.add(text)

    # Identify discussion-only content
    discussion_only: list[str] = []
    for key in ("decisions", "action_items", "open_questions"):
        for item in transcript_structured.get(key, []):
            support, _ = _has_slide_support(_text_of(item))
            if not support:
                discussion_only.append(_text_of(item))

    enriched["slide_only_content"] = slide_only
    enriched["discussion_only_content"] = discussion_only

    return enriched


# ---------------------------------------------------------------------------
# D. Slide-transcript gap analysis with structured follow-ups
# ---------------------------------------------------------------------------

def compute_slide_transcript_gaps(
    enriched_record: dict,
    *,
    slides_present: bool = False,
) -> dict:
    """Compute the gap analysis between slide content and meeting discussion.

    Produces structured follow-up objects rather than plain strings.

    Parameters
    ----------
    enriched_record:
        Output of :func:`merge_slide_transcript_outputs`.
    slides_present:
        Set to ``True`` when a slide deck was supplied as input.  When
        ``True`` and all four output arrays are empty the result includes
        ``reconciliation_status = "inert_review_required"`` so that
        downstream consumers can surface the condition instead of silently
        passing.

    Returns
    -------
    dict
        Keys:
        ``unpresented_discussions``, ``undiscussed_slides``,
        ``weak_alignment_areas``, ``recommended_followups`` (list of canonical
        follow-up objects), ``reconciliation_status``.
    """
    unpresented = list(enriched_record.get("discussion_only_content", []))
    undiscussed = list(enriched_record.get("slide_only_content", []))

    # Weak alignment: items with slide_support=False (or missing key)
    weak_areas: list[str] = []
    for key in ("decisions", "action_items", "open_questions"):
        for item in enriched_record.get(key, []):
            if isinstance(item, dict) and not item.get("slide_support", False):
                text = item.get("description") or item.get("text") or str(item)
                if text and text not in weak_areas:
                    weak_areas.append(text)

    # Build structured follow-up objects
    followups: list[dict] = []
    fup_counter = 0

    def _next_fid() -> str:
        nonlocal fup_counter
        fup_counter += 1
        return f"FUP-{fup_counter:03d}"

    for text in undiscussed[:5]:
        snippet = text[:80].rstrip()
        followups.append(_make_followup(
            _next_fid(),
            "discuss",
            f"Discuss in next meeting: {snippet}",
            "slide",
            snippet[:40],
        ))
    for text in unpresented[:5]:
        snippet = text[:80].rstrip()
        followups.append(_make_followup(
            _next_fid(),
            "add_evidence",
            f"Add slide evidence for: {snippet}",
            "transcript",
            snippet[:40],
        ))
    for text in weak_areas[:3]:
        snippet = text[:80].rstrip()
        followups.append(_make_followup(
            _next_fid(),
            "clarify_alignment",
            f"Clarify alignment for: {snippet}",
            "gap",
            snippet[:40],
        ))

    # Inert reconciliation detection
    all_empty = (
        not unpresented and not undiscussed and not weak_areas and not followups
    )
    if slides_present and all_empty:
        reconciliation_status = "inert_review_required"
    else:
        reconciliation_status = "ok"

    return {
        "unpresented_discussions": unpresented,
        "undiscussed_slides": undiscussed,
        "weak_alignment_areas": weak_areas,
        "recommended_followups": followups,
        "reconciliation_status": reconciliation_status,
    }
