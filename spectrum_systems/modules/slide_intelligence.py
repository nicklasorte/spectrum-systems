"""
Slide Intelligence Module — spectrum_systems/modules/slide_intelligence.py

Treats uploaded slide decks as first-class governed technical artifacts that
feed working-paper generation, assumptions tracking, claim extraction, gap
detection, and knowledge-graph seed capabilities.

Design philosophy:
- Slides are structured intelligence, not transcript text.
- All logic is deterministic; no LLM, no network, no embeddings.
- Preserves full traceability from slide → downstream artifact.
- Supports the Observe → Interpret → Recommend golden path.

Functions (A–K):
  A. extract_slide_units
  B. score_slide_signal
  C. classify_slide_role
  D. extract_claims
  E. extract_assumptions
  F. extract_entities_and_relationships
  G. detect_gaps
  H. map_to_working_paper_section
  I. rewrite_for_working_paper
  J. compare_with_transcript_and_paper
  K. build_slide_intelligence_packet
"""

from __future__ import annotations

import json
import math
import re
import uuid
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Prompt P gap detection subsystem
# Architecture note (P-fix-2B): all Prompt P logic now lives in gap_detection.py.
# slide_intelligence.py is the orchestrator; it calls into gap_detection for
# gap detection, contradiction detection, merge/reconciliation, and follow-up
# construction.  The _STOPWORDS / _build_deck_assumption_index helpers are
# re-exported here for backward compatibility with existing test imports.
# ---------------------------------------------------------------------------
from .gap_detection import (
    build_deck_assumption_index as _build_deck_assumption_index,
    detect_slide_gaps,
    detect_cross_slide_contradictions,
    merge_slide_transcript_outputs,
    compute_slide_transcript_gaps,
    _STOPWORDS,
    _extract_tokens,
)

# ---------------------------------------------------------------------------
# Internal keyword tables
# ---------------------------------------------------------------------------

_TECH_PARAM_KEYWORDS: list[str] = [
    "MHz", "GHz", "dB", "dBm", "dBi", "dBW", "km", "m/s", "W/m",
    "EIRP", "OOBE", "PFD", "C/N", "SNR", "BER", "Eb/No",
    "bandwidth", "guard band", "separation", "threshold",
    "path loss", "propagation", "link budget", "clutter",
    "antenna gain", "beamwidth", "polarization",
    "deployment density", "receiver sensitivity",
    "modulation", "waveform", "duty cycle",
    "reliability", "availability",
]

_MODEL_KEYWORDS: list[str] = [
    "ITM", "Longley-Rice", "Okumura", "Hata", "COST 231", "3GPP",
    "IMT", "P.452", "P.1546", "P.528", "Rec. ITU",
    "Monte Carlo", "ray tracing", "ray-tracing",
    "clutter model", "terrain model", "propagation model",
    "hybrid model", "statistical model",
]

_SYSTEM_KEYWORDS: list[str] = [
    "5G NR", "5G", "LTE", "radar", "GPS", "GNSS", "satellite",
    "base station", "UE", "terminal", "sensor", "transponder",
    "AMT", "AMS", "ARNS", "radionavigation", "radiolocation",
    "fixed service", "mobile service", "aeronautical",
    "federal incumbent", "non-federal", "licensee",
]

_INTERFERENCE_KEYWORDS: list[str] = [
    "interference", "interfere", "interfering",
    "protection", "protect", "protected", "co-channel",
    "adjacent channel", "spurious", "out-of-band", "in-band",
    "compatibility", "coexistence", "harmful interference",
    "aggregate", "coordination zone",
]

_CLAIM_PATTERNS: list[str] = [
    r"may interfere",
    r"will interfere",
    r"causes interference",
    r"manageable with",
    r"requires\s+\w",
    r"supports\s+\w",
    r"protects\s+\w",
    r"demonstrates\s+\w",
    r"shows\s+\w",
    r"is sufficient",
    r"is adequate",
    r"is not expected",
    r"is expected",
    r"meets the",
    r"exceeds the",
    r"below the",
    r"above the",
    r"does not interfere",
    r"can coexist",
    r"cannot coexist",
    r"will not cause",
    r"will cause",
    r"margin of",
    r"margin is",
]

_ASSUMPTION_TYPE_MAP: dict[str, list[str]] = {
    "OOBE": ["OOBE", "out-of-band emission", "spurious emission"],
    "EIRP": ["EIRP", "effective isotropic radiated power", "radiated power"],
    "bandwidth": ["bandwidth", "channel bandwidth", "occupied bandwidth"],
    "propagation_model": [
        "propagation model", "path loss model", "ITM", "Longley-Rice",
        "Okumura", "Hata", "P.452", "P.1546", "P.528",
    ],
    "clutter_model": ["clutter", "clutter model", "terrain clutter", "foliage"],
    "receiver_threshold": [
        "receiver threshold", "sensitivity", "noise floor",
        "protection threshold", "I/N", "C/I", "C/N threshold",
    ],
    "deployment_density": [
        "deployment density", "base station density", "site density",
        "number of stations", "number of users", "user density",
    ],
    "guard_band": ["guard band", "guard-band", "frequency separation"],
    "reliability": ["reliability", "availability", "uptime", "link availability"],
    "antenna_gain": ["antenna gain", "antenna height", "antenna pattern", "beamwidth"],
}

_SECTION_ROLE_MAP: dict[str, str] = {
    "background": "Objective and Scope",
    "objective": "Objective and Scope",
    "system_description": "System Description",
    "assumptions": "Assumptions and Inputs",
    "methodology": "Methodology",
    "link_budget": "Methodology",
    "propagation": "Methodology",
    "interference": "Preliminary Findings",
    "mitigation": "Mitigation Options",
    "findings": "Preliminary Findings",
    "recommendation": "Recommended Next Steps",
    "open_issue": "Open Questions",
}

_STYLE_MODE_MAP: dict[str, str] = {
    "source_text": "narrative",
    "source_claim": "findings_text",
    "source_question": "question_prompt",
    "source_exhibit": "exhibit_note",
}

_TECH_TAG_STYLE_MAP: dict[str, str] = {
    "assumptions": "assumptions_block",
    "methodology": "methods_text",
    "link_budget": "methods_text",
    "propagation": "methods_text",
    "findings": "findings_text",
    "interference": "findings_text",
    "recommendation": "findings_text",
    "open_issue": "issue_statement",
}

# Placeholder slide ID used in merge_slide_transcript_outputs when a match
# is found via direct text overlap rather than the alignment map.
_SLIDE_DIRECT_MATCH_ID = "slide_direct_match"

# Minimum combined cosine+overlap score to count as a real alignment match.
_ALIGNMENT_THRESHOLD = 0.15


# ---------------------------------------------------------------------------
# A. Slide structuring
# ---------------------------------------------------------------------------


def extract_slide_units(slide_deck_artifact: dict) -> list[dict]:
    """
    Normalize a slide deck artifact into per-slide structured units.

    Each unit captures slide_id, slide_number, title, bullets, notes,
    raw_text, figures_present, tables_present, source_artifact_id, and
    presenting_org (when available).

    Heuristics:
    - title prefers explicit ``title`` field, else first non-empty line.
    - bullets preserve ordering from the source ``bullets`` or ``content`` list.
    - raw_text is the full per-slide text blob.
    - figures_present / tables_present are inferred from explicit flags or
      simple ``type`` / keyword indicators in the fixture structure.

    Parameters
    ----------
    slide_deck_artifact:
        A governed slide deck artifact dict.  Expected fields::

            {
              "artifact_id": str,
              "presenting_org": str | None,
              "slides": [
                {
                  "slide_number": int,
                  "title": str | None,
                  "bullets": list[str] | None,
                  "content": list[str] | None,
                  "notes": str | None,
                  "raw_text": str | None,
                  "has_figure": bool | None,
                  "has_table": bool | None,
                  "type": str | None,    # "figure" | "table" | "text" | ...
                }
              ]
            }

    Returns
    -------
    list[dict]
        Ordered list of slide unit dicts.
    """
    source_id: str = slide_deck_artifact.get("artifact_id", "unknown")
    presenting_org: str | None = slide_deck_artifact.get("presenting_org")
    raw_slides: list[dict] = slide_deck_artifact.get("slides", [])

    units: list[dict] = []
    for idx, slide in enumerate(raw_slides):
        slide_number: int = slide.get("slide_number", idx + 1)

        # --- title ---
        title: str = slide.get("title") or ""
        if not title:
            raw = slide.get("raw_text", "") or ""
            for line in raw.splitlines():
                line = line.strip()
                if line:
                    title = line
                    break

        # --- bullets ---
        bullets: list[str] = []
        raw_bullets = slide.get("bullets") or slide.get("content") or []
        if isinstance(raw_bullets, list):
            bullets = [str(b).strip() for b in raw_bullets if str(b).strip()]

        # --- notes ---
        notes: str = slide.get("notes") or ""

        # --- raw_text ---
        raw_text: str = slide.get("raw_text") or ""
        if not raw_text:
            parts: list[str] = []
            if title:
                parts.append(title)
            parts.extend(bullets)
            if notes:
                parts.append(notes)
            raw_text = "\n".join(parts)

        # --- figures / tables ---
        slide_type: str = (slide.get("type") or "").lower()
        figures_present: bool = bool(
            slide.get("has_figure")
            or slide_type in ("figure", "diagram", "chart", "image")
            or "figure" in raw_text.lower()
            or "diagram" in raw_text.lower()
            or "chart" in raw_text.lower()
        )
        tables_present: bool = bool(
            slide.get("has_table")
            or slide_type == "table"
            or "table" in raw_text.lower()
        )

        # --- slide_id ---
        slide_id: str = slide.get("slide_id") or f"{source_id}-slide-{slide_number}"

        units.append({
            "slide_id": slide_id,
            "slide_number": slide_number,
            "title": title,
            "bullets": bullets,
            "notes": notes,
            "raw_text": raw_text,
            "figures_present": figures_present,
            "tables_present": tables_present,
            "source_artifact_id": source_id,
            "presenting_org": presenting_org,
        })

    return units


# ---------------------------------------------------------------------------
# B. Signal scoring
# ---------------------------------------------------------------------------


def score_slide_signal(slide_unit: dict) -> dict:
    """
    Score a slide unit for technical signal richness.

    The signal_score (0.0–1.0) rewards content that is likely to contribute
    to a spectrum study working paper: technical parameters, model references,
    system names, interference / propagation content, and structured data
    (tables / figures).

    Parameters
    ----------
    slide_unit:
        A dict produced by :func:`extract_slide_units`.

    Returns
    -------
    dict
        ``{"signal_score": float, "reasoning": list[str]}``
    """
    text: str = (slide_unit.get("raw_text") or "").lower()
    bullets: list[str] = slide_unit.get("bullets") or []
    full_text: str = text + " " + " ".join(b.lower() for b in bullets)

    reasons: list[str] = []
    score: float = 0.0

    def _check(keywords: list[str], label: str, weight: float) -> None:
        nonlocal score
        matched = [kw for kw in keywords if kw.lower() in full_text]
        if matched:
            reasons.append(f"{label}: {', '.join(matched[:3])}")
            score += weight

    _check(_TECH_PARAM_KEYWORDS, "technical_parameters", 0.25)
    _check(_MODEL_KEYWORDS, "model_references", 0.20)
    _check(_SYSTEM_KEYWORDS, "system_names", 0.15)
    _check(_INTERFERENCE_KEYWORDS, "interference_content", 0.15)

    if slide_unit.get("tables_present"):
        reasons.append("tables_present")
        score += 0.10

    if slide_unit.get("figures_present"):
        reasons.append("figures_present")
        score += 0.05

    assumption_kws = [
        "assume", "assumed", "assumption", "given that",
        "per the", "based on", "modeled as",
    ]
    if any(kw in full_text for kw in assumption_kws):
        reasons.append("explicit_assumptions")
        score += 0.10

    signal_score: float = min(round(score, 3), 1.0)

    return {
        "signal_score": signal_score,
        "reasoning": reasons,
    }


# ---------------------------------------------------------------------------
# C. Role classification
# ---------------------------------------------------------------------------


def classify_slide_role(slide_unit: dict) -> dict:
    """
    Classify the integration role and technical tags of a slide unit.

    integration_role choices:
    - ``source_text``    — stable factual / descriptive content for paper prose
    - ``source_claim``   — assertion needing attribution / validation
    - ``source_question``— unresolved issue, ask, or open prompt
    - ``source_exhibit`` — figure / table / diagram-heavy, better as exhibit

    technical_tags drawn from the canonical taxonomy.

    Parameters
    ----------
    slide_unit:
        A dict produced by :func:`extract_slide_units`.

    Returns
    -------
    dict
        ``{"integration_role": str, "technical_tags": list[str]}``
    """
    text: str = (slide_unit.get("raw_text") or "").lower()
    title: str = (slide_unit.get("title") or "").lower()
    bullets: list[str] = [b.lower() for b in (slide_unit.get("bullets") or [])]
    full_text: str = text + " " + title + " " + " ".join(bullets)

    # --- integration role ---
    is_exhibit = (
        slide_unit.get("figures_present")
        and not slide_unit.get("bullets")
    ) or slide_unit.get("tables_present") and not bullets

    has_claim = any(
        re.search(pat, full_text, re.IGNORECASE) for pat in _CLAIM_PATTERNS
    )
    question_kws = [
        "?", "tbd", "to be determined", "open issue", "open question",
        "unknown", "unclear", "pending", "under review", "needs further",
        "requires further", "additional analysis", "not yet",
    ]
    has_question = any(kw in full_text for kw in question_kws)

    if is_exhibit:
        integration_role = "source_exhibit"
    elif has_question:
        integration_role = "source_question"
    elif has_claim:
        integration_role = "source_claim"
    else:
        integration_role = "source_text"

    # --- technical tags ---
    tag_rules: dict[str, list[str]] = {
        "background": ["background", "overview", "introduction", "context"],
        "objective": ["objective", "goal", "purpose", "scope"],
        "system_description": [
            "system description", "architecture", "deployment",
            "configuration", "topology",
        ],
        "assumptions": ["assumption", "assumed", "input parameter", "baseline"],
        "methodology": [
            "methodology", "method", "approach", "analysis", "procedure",
            "simulation", "modeling",
        ],
        "link_budget": [
            "link budget", "link-budget", "path loss", "received power",
            "EIRP", "antenna gain", "C/N", "SNR",
        ],
        "propagation": [
            "propagation", "path loss", "terrain", "clutter", "diffraction",
            "multipath", "fading",
        ],
        "interference": [
            "interference", "coexistence", "compatibility", "harmful",
            "aggregate", "co-channel", "adjacent",
        ],
        "mitigation": [
            "mitigation", "guard band", "filtering", "coordination",
            "exclusion zone", "power control",
        ],
        "findings": ["finding", "result", "outcome", "shows", "demonstrates"],
        "recommendation": [
            "recommend", "recommendation", "propose", "should", "suggested",
        ],
        "open_issue": ["open issue", "tbd", "unresolved", "pending", "open question"],
    }

    tags: list[str] = []
    for tag, keywords in tag_rules.items():
        if any(kw in full_text for kw in keywords):
            tags.append(tag)

    return {
        "integration_role": integration_role,
        "technical_tags": tags,
    }


# ---------------------------------------------------------------------------
# D. Claim extraction
# ---------------------------------------------------------------------------


def extract_claims(slide_unit: dict) -> list[dict]:
    """
    Extract declarative technical assertions (claims) from a slide unit.

    Heuristics detect spectrum-study patterns such as interference assertions,
    sufficiency claims, coexistence conclusions, and comparative statements.
    Each extracted claim is assigned a unique ``claim_id`` and linked back to
    its source slide.

    Parameters
    ----------
    slide_unit:
        A dict produced by :func:`extract_slide_units`.

    Returns
    -------
    list[dict]
        Each item: ``{claim_id, claim_text, related_entities, confidence,
        source_slide_id}``
    """
    slide_id: str = slide_unit.get("slide_id", "unknown")
    sources: list[str] = []

    title = slide_unit.get("title") or ""
    if title:
        sources.append(title)
    sources.extend(slide_unit.get("bullets") or [])
    raw = slide_unit.get("raw_text") or ""
    if raw and raw not in sources:
        # Avoid duplicating title/bullets already captured
        extra_lines = [
            ln.strip() for ln in raw.splitlines()
            if ln.strip() and ln.strip() not in sources
        ]
        sources.extend(extra_lines)

    claims: list[dict] = []
    seen: set[str] = set()

    for text in sources:
        if not text.strip():
            continue
        lower = text.lower()
        matched_patterns = [
            pat for pat in _CLAIM_PATTERNS
            if re.search(pat, lower, re.IGNORECASE)
        ]
        if not matched_patterns:
            continue

        # De-duplicate identical claim texts
        canonical = text.strip()
        if canonical in seen:
            continue
        seen.add(canonical)

        # Confidence: more patterns → higher confidence
        if len(matched_patterns) >= 2:
            confidence = "high"
        elif any(
            kw in lower
            for kw in ["may", "might", "could", "expected", "likely"]
        ):
            confidence = "low"
        else:
            confidence = "medium"

        # Related entities: systems and frequency terms found in the text
        entities = _extract_entity_names(text)

        claim_id = f"CLAIM-{slide_id}-{len(claims) + 1:03d}"
        claims.append({
            "claim_id": claim_id,
            "claim_text": canonical,
            "related_entities": entities,
            "confidence": confidence,
            "source_slide_id": slide_id,
        })

    return claims


def _extract_entity_names(text: str) -> list[str]:
    """Heuristically pull entity names (systems, bands, agencies) from text."""
    entities: list[str] = []
    all_kws = _SYSTEM_KEYWORDS + ["MHz", "GHz", "OOBE", "EIRP", "guard band"]
    lower = text.lower()
    for kw in all_kws:
        if kw.lower() in lower and kw not in entities:
            entities.append(kw)
    return entities[:8]  # cap to keep manageable


# ---------------------------------------------------------------------------
# E. Assumptions extraction
# ---------------------------------------------------------------------------


def extract_assumptions(slide_unit: dict) -> list[dict]:
    """
    Extract technical assumptions from a slide unit.

    Infers assumption type from keywords and units.  Captures values when
    present.  Supports partially populated entries when the value is missing
    but the type is evident.

    Parameters
    ----------
    slide_unit:
        A dict produced by :func:`extract_slide_units`.

    Returns
    -------
    list[dict]
        Each item: ``{assumption_id, type, value, applies_to, source_slide_id}``
    """
    slide_id: str = slide_unit.get("slide_id", "unknown")
    all_text_parts: list[str] = []

    if slide_unit.get("title"):
        all_text_parts.append(slide_unit["title"])
    all_text_parts.extend(slide_unit.get("bullets") or [])
    raw = slide_unit.get("raw_text") or ""
    if raw:
        all_text_parts.extend([ln.strip() for ln in raw.splitlines() if ln.strip()])

    assumptions: list[dict] = []
    seen_types: set[str] = set()

    for text in all_text_parts:
        if not text.strip():
            continue
        lower = text.lower()

        for asm_type, keywords in _ASSUMPTION_TYPE_MAP.items():
            if asm_type in seen_types:
                continue
            if not any(kw.lower() in lower for kw in keywords):
                continue

            # Attempt to extract a numeric value with optional unit
            value: str | None = _extract_numeric_value(text)

            # Infer applies_to from system keywords
            applies_to = _first_system_mention(text) or "unspecified"

            asm_id = f"ASM-{slide_id}-{asm_type.upper()}"
            assumptions.append({
                "assumption_id": asm_id,
                "type": asm_type,
                "value": value,
                "applies_to": applies_to,
                "source_slide_id": slide_id,
            })
            seen_types.add(asm_type)

    return assumptions


def _extract_numeric_value(text: str) -> str | None:
    """Extract the first numeric value with optional unit from text."""
    # Matches: 30 dBm, -100 dBm, 1.5 GHz, 200 MHz, 20 dB, etc.
    match = re.search(
        r"(-?\d+(?:\.\d+)?)\s*(dBm|dBW|dBi|dB|GHz|MHz|kHz|Hz|W|km|m|%)?",
        text,
    )
    if match:
        num = match.group(1)
        unit = match.group(2) or ""
        return f"{num} {unit}".strip()
    return None


def _first_system_mention(text: str) -> str | None:
    """Return the first system/band keyword found in text."""
    lower = text.lower()
    for kw in _SYSTEM_KEYWORDS:
        if kw.lower() in lower:
            return kw
    return None


# ---------------------------------------------------------------------------
# F. Entity and relationship extraction
# ---------------------------------------------------------------------------


def extract_entities_and_relationships(slide_unit: dict) -> dict:
    """
    Extract entities and directed relationships from a slide unit.

    This is the seed for future knowledge-graph capabilities.  All logic is
    deterministic keyword / pattern matching.

    Entities may include frequency bands, systems, agencies, models /
    standards, mitigations, and study objects.

    Relationships may include interferes_with, protected_by, depends_on,
    mitigated_by, assumes, evaluated_with, applies_to.

    Parameters
    ----------
    slide_unit:
        A dict produced by :func:`extract_slide_units`.

    Returns
    -------
    dict
        ``{"entities": list[dict], "relationships": list[dict]}``
    """
    slide_id: str = slide_unit.get("slide_id", "unknown")
    full_text: str = (
        (slide_unit.get("title") or "")
        + " "
        + " ".join(slide_unit.get("bullets") or [])
        + " "
        + (slide_unit.get("raw_text") or "")
    )
    lower = full_text.lower()

    entities: list[dict] = []
    entity_names: set[str] = set()

    def _add_entity(name: str, etype: str) -> None:
        if name not in entity_names:
            entities.append({
                "name": name,
                "type": etype,
                "source_slide_id": slide_id,
            })
            entity_names.add(name)

    # Frequency bands
    freq_pattern = re.compile(
        r"\b(\d+(?:\.\d+)?\s*(?:MHz|GHz|kHz)(?:\s*[-–]\s*\d+(?:\.\d+)?\s*(?:MHz|GHz|kHz))?)\b",
        re.IGNORECASE,
    )
    for m in freq_pattern.finditer(full_text):
        _add_entity(m.group(1).strip(), "frequency_band")

    # Systems
    for kw in _SYSTEM_KEYWORDS:
        if kw.lower() in lower:
            _add_entity(kw, "system")

    # Models / standards
    for kw in _MODEL_KEYWORDS:
        if kw.lower() in lower:
            _add_entity(kw, "model_standard")

    # Mitigations
    mitigation_kws = [
        "guard band", "filtering", "power control",
        "coordination zone", "exclusion zone", "beamforming",
    ]
    for kw in mitigation_kws:
        if kw in lower:
            _add_entity(kw, "mitigation")

    # Agency names (heuristic: all-caps 2–6 letter tokens adjacent to "agency" or common names)
    agency_pattern = re.compile(r"\b(FCC|NTIA|FAA|DoD|NASA|NOAA|DoT|FTC|DHS)\b")
    for m in agency_pattern.finditer(full_text):
        _add_entity(m.group(1), "agency")

    # --- Relationships ---
    relationships: list[dict] = []

    def _add_rel(source: str, rel_type: str, target: str) -> None:
        relationships.append({
            "source": source,
            "relation": rel_type,
            "target": target,
            "source_slide_id": slide_id,
        })

    # interferes_with
    interference_re = re.compile(
        r"((?:\w+\s){0,4}\w+)\s+(?:may |will |could )?interfere\s+with\s+((?:\w+\s){0,4}\w+)",
        re.IGNORECASE,
    )
    for m in interference_re.finditer(full_text):
        _add_rel(m.group(1).strip(), "interferes_with", m.group(2).strip())

    # protected_by / mitigated_by
    protect_re = re.compile(
        r"([\w\s/.-]{1,30}?)\s+(?:is\s+)?protected\s+by\s+([\w\s/.-]{1,30})",
        re.IGNORECASE,
    )
    for m in protect_re.finditer(full_text):
        _add_rel(m.group(1).strip(), "protected_by", m.group(2).strip())

    mitigated_re = re.compile(
        r"([\w\s/.-]{1,30}?)\s+(?:is\s+)?mitigated\s+by\s+([\w\s/.-]{1,30})",
        re.IGNORECASE,
    )
    for m in mitigated_re.finditer(full_text):
        _add_rel(m.group(1).strip(), "mitigated_by", m.group(2).strip())

    # assumes (model reference)
    assumes_re = re.compile(
        r"(?:assumes?|uses?|based on)\s+(ITM|Longley-Rice|Okumura|Hata|P\.\d+|COST 231|3GPP|Monte Carlo)",
        re.IGNORECASE,
    )
    for m in assumes_re.finditer(full_text):
        _add_rel(slide_id, "assumes", m.group(1).strip())

    # evaluated_with
    eval_re = re.compile(
        r"evaluated\s+(?:using|with)\s+([\w\s/.-]{1,30})",
        re.IGNORECASE,
    )
    for m in eval_re.finditer(full_text):
        _add_rel(slide_id, "evaluated_with", m.group(1).strip())

    return {
        "entities": entities,
        "relationships": relationships,
    }


# ---------------------------------------------------------------------------
# G. Gap detection — thin wrapper delegating to gap_detection module
# ---------------------------------------------------------------------------


def detect_gaps(
    slide_unit: dict,
    claims: list[dict],
    assumptions: list[dict],
    *,
    deck_assumption_index: dict | None = None,
) -> list[dict]:
    """
    Detect negative space (gaps) in a slide unit's technical content.

    This function delegates to :func:`gap_detection.detect_slide_gaps`.
    It is retained here as a public compatibility shim so that existing callers
    and tests continue to work without modification.

    Parameters
    ----------
    slide_unit:
        A dict produced by :func:`extract_slide_units`.
    claims:
        Output of :func:`extract_claims` for this slide.
    assumptions:
        Output of :func:`extract_assumptions` for this slide.
    deck_assumption_index:
        Optional dict from :func:`_build_deck_assumption_index`.  When
        provided, Rule 1 uses deck-level context so it does not fire on a
        result slide merely because *that slide* lacks the model keywords
        while another slide in the same deck already contains them.

    Returns
    -------
    list[dict]
        List of canonical gap objects (see ``gap_detection.GAP_TYPES``).
    """
    return detect_slide_gaps(
        slide_unit,
        claims,
        assumptions,
        deck_assumption_index=deck_assumption_index,
    )


# ---------------------------------------------------------------------------
# H. Working-paper section mapping
# ---------------------------------------------------------------------------


def map_to_working_paper_section(slide_unit: dict, role: dict) -> str:
    """
    Map a slide unit to the most appropriate working-paper section.

    Sections:
    - Executive Summary
    - Objective and Scope
    - System Description
    - Assumptions and Inputs
    - Methodology
    - Preliminary Findings
    - Risk Assessment
    - Mitigation Options
    - Open Questions
    - Recommended Next Steps
    - Appendix / Exhibits

    Parameters
    ----------
    slide_unit:
        A dict produced by :func:`extract_slide_units`.
    role:
        A dict produced by :func:`classify_slide_role`.

    Returns
    -------
    str
        The target working-paper section name.
    """
    integration_role: str = role.get("integration_role", "source_text")
    tags: list[str] = role.get("technical_tags") or []

    # Exhibit → appendix
    if integration_role == "source_exhibit":
        return "Appendix / Exhibits"

    # Question → open questions
    if integration_role == "source_question":
        return "Open Questions"

    # Tag-driven mapping (first matching tag wins)
    for tag in tags:
        if tag in _SECTION_ROLE_MAP:
            return _SECTION_ROLE_MAP[tag]

    # Fall back by role
    if integration_role == "source_claim":
        return "Preliminary Findings"

    return "Executive Summary"


# ---------------------------------------------------------------------------
# I. Paper-ready rewriting
# ---------------------------------------------------------------------------


def rewrite_for_working_paper(slide_unit: dict, role: dict, section: str) -> dict:
    """
    Produce a paper-ready prose block from a slide unit.

    Rules:
    - Do NOT simply join bullets.
    - Write report-ready prose preserving technical specificity.
    - Preserve uncertainty when content is provisional.
    - Downgrade overly strong slide language when support is thin.
    - Include full traceability.

    style_mode options:
    - narrative          — stable factual content → flowing sentences
    - assumptions_block  — enumerated assumptions with context
    - methods_text       — methodology paragraph with parameters
    - findings_text      — findings paragraph attributing conclusion
    - issue_statement    — issue/question framing
    - question_prompt    — agency-question format
    - exhibit_note       — exhibit reference with caption suggestion

    Parameters
    ----------
    slide_unit:
        A dict produced by :func:`extract_slide_units`.
    role:
        A dict produced by :func:`classify_slide_role`.
    section:
        Target section from :func:`map_to_working_paper_section`.

    Returns
    -------
    dict
        ``{proposed_text, style_mode, caution_flags, confidence, traceability}``
    """
    integration_role: str = role.get("integration_role", "source_text")
    tags: list[str] = role.get("technical_tags") or []
    title: str = slide_unit.get("title") or "Untitled Slide"
    bullets: list[str] = slide_unit.get("bullets") or []
    notes: str = slide_unit.get("notes") or ""
    source_slide_id: str = slide_unit.get("slide_id", "unknown")
    source_artifact_id: str = slide_unit.get("source_artifact_id", "unknown")

    # Determine style_mode
    style_mode = _STYLE_MODE_MAP.get(integration_role, "narrative")
    for tag in tags:
        if tag in _TECH_TAG_STYLE_MAP:
            style_mode = _TECH_TAG_STYLE_MAP[tag]
            break

    caution_flags: list[str] = []
    confidence: str = "medium"

    # Check for unsupported strong language
    strong_patterns = [
        r"\bwill\b", r"\bproven\b", r"\bguaranteed\b",
        r"\bno interference\b", r"\bfull compatibility\b",
    ]
    raw_text = slide_unit.get("raw_text") or ""
    for pat in strong_patterns:
        if re.search(pat, raw_text, re.IGNORECASE):
            caution_flags.append(f"Strong language detected ({pat.strip(r'\\b')}); verify support.")

    provisional_kws = [
        "preliminary", "draft", "tbd", "placeholder",
        "subject to", "pending", "to be confirmed",
    ]
    if any(kw in raw_text.lower() for kw in provisional_kws):
        caution_flags.append("Content marked provisional; do not assert as final.")
        confidence = "low"
    elif not caution_flags:
        confidence = "high" if bullets else "medium"

    # Build proposed_text by style_mode
    proposed_text: str = _build_prose(
        style_mode, title, bullets, notes, integration_role, section
    )

    return {
        "proposed_text": proposed_text,
        "style_mode": style_mode,
        "caution_flags": caution_flags,
        "confidence": confidence,
        "traceability": {
            "source_slide_id": source_slide_id,
            "source_artifact_id": source_artifact_id,
            "mapped_section": section,
        },
    }


def _build_prose(
    style_mode: str,
    title: str,
    bullets: list[str],
    notes: str,
    integration_role: str,
    section: str,
) -> str:
    """Deterministically compose prose based on style mode."""

    # Preserve original casing of the title to avoid mangling acronyms and
    # proper nouns (e.g., "ITM", "5G NR").  Only lower-case the first letter
    # of an inline continuation sentence where grammatically appropriate.
    title_inline = title[0].lower() + title[1:] if title and title[0].isupper() else title

    if style_mode == "assumptions_block":
        if bullets:
            items = "\n".join(f"  - {b}" for b in bullets)
            return (
                f"The following assumptions were applied to the {title_inline} "
                f"analysis:\n\n{items}\n\n"
                f"These inputs should be validated against the consolidated assumptions "
                f"register before the working paper is finalized."
            )
        return (
            f"Assumptions associated with {title_inline} are noted but not yet "
            f"fully enumerated. A complete assumptions block is required before "
            f"the working paper advances to review."
        )

    if style_mode == "methods_text":
        if bullets:
            method_summary = "; ".join(b.rstrip(".") for b in bullets[:3])
            return (
                f"The methodology for {title_inline} proceeded as follows: "
                f"{method_summary}. "
                f"Full parameter details are documented in the supporting technical record."
            )
        return (
            f"The analytical method described under '{title}' is noted. "
            f"A complete description of inputs, parameters, and procedures is required "
            f"before inclusion in the working paper."
        )

    if style_mode == "findings_text":
        if bullets:
            lead = bullets[0].rstrip(".")
            # Lower-case the lead sentence continuation only, not any acronyms
            lead_lc = lead[0].lower() + lead[1:] if lead and lead[0].isupper() else lead
            remainder = "; ".join(b.rstrip(".") for b in bullets[1:3])
            text = f"Analysis of {title_inline} indicates that {lead_lc}."
            if remainder:
                text += f" Supporting evidence includes: {remainder}."
            text += (
                " These findings are preliminary and subject to revision upon "
                "completion of the full study record."
            )
            return text
        return (
            f"Preliminary findings related to {title_inline} are captured on this slide. "
            f"Specific numerical results and supporting data must be incorporated "
            f"before the findings section can be finalized."
        )

    if style_mode == "issue_statement":
        issues = "; ".join(b.rstrip(".") for b in bullets[:3]) if bullets else title
        return (
            f"An open issue has been identified: {issues}. "
            f"Resolution is required before the study can advance. "
            f"Responsible parties and a resolution timeline should be assigned."
        )

    if style_mode == "question_prompt":
        questions = (
            "; ".join(b.rstrip("?") + "?" for b in bullets[:2])
            if bullets
            else f"{title}?"
        )
        return (
            f"The following questions remain unresolved and should be directed "
            f"to the responsible agency or study team:\n\n  - {questions}\n\n"
            f"Responses are required to support working-paper finalization."
        )

    if style_mode == "exhibit_note":
        return (
            f"[Exhibit Candidate] The slide titled '{title}' contains visual or "
            f"tabular material suitable for inclusion as an exhibit in the "
            f"'{section}' section. The exhibit should be accompanied by a "
            f"descriptive caption and traceable source reference."
        )

    # Default: narrative
    if bullets:
        intro = f"Regarding {title_inline}: "
        body = " ".join(b.rstrip(".") + "." for b in bullets)
        return (intro + body).strip()
    if notes:
        return notes.strip()
    return (
        f"Content from slide '{title}' has been identified for the "
        f"'{section}' section. Full prose development is pending."
    )


# ---------------------------------------------------------------------------
# J. Cross-artifact comparison
# ---------------------------------------------------------------------------


def compare_with_transcript_and_paper(
    slide_outputs: list[dict],
    transcript_artifact: dict | None = None,
    working_paper_artifact: dict | None = None,
) -> dict:
    """
    Compare slide intelligence outputs against a transcript and working paper.

    Uses deterministic text-overlap and keyword matching.  No embeddings or
    model APIs.

    Parameters
    ----------
    slide_outputs:
        A list of dicts, each with at least ``claim_text`` and ``source_slide_id``.
    transcript_artifact:
        Optional dict with ``text`` or ``segments`` field containing transcript text.
    working_paper_artifact:
        Optional dict with ``sections`` or ``text`` field.

    Returns
    -------
    dict
        ``{supported_by_transcript, challenged_in_discussion,
           unresolved, missing_from_paper, already_in_paper, better_as_question}``
    """
    transcript_text: str = _extract_text_from_artifact(transcript_artifact)
    paper_text: str = _extract_text_from_artifact(working_paper_artifact)

    supported: list[str] = []
    challenged: list[str] = []
    unresolved: list[str] = []
    missing: list[str] = []
    already_in: list[str] = []
    better_as_question: list[str] = []

    challenge_kws = [
        "disagree", "disputed", "challenge", "not correct", "incorrect",
        "concern", "objection", "questioned", "however", "but",
    ]

    for output in slide_outputs:
        claim_text: str = output.get("claim_text") or output.get("proposed_text") or ""
        if not claim_text:
            continue
        claim_id: str = output.get("claim_id") or output.get("source_slide_id") or ""

        # Keyword-overlap heuristic: check if any 4+ char words from claim appear in text
        significant_words = [
            w.lower() for w in re.findall(r"\b\w{4,}\b", claim_text)
        ]

        def _overlap(text: str) -> float:
            if not significant_words or not text:
                return 0.0
            hits = sum(1 for w in significant_words if w in text.lower())
            return hits / len(significant_words)

        transcript_overlap = _overlap(transcript_text)
        paper_overlap = _overlap(paper_text)

        is_question = "?" in claim_text or any(
            kw in claim_text.lower()
            for kw in ["tbd", "unknown", "unclear", "open issue"]
        )

        if is_question:
            better_as_question.append(claim_id)
        elif transcript_overlap >= 0.4:
            # Check if challenged
            challenge_context = any(
                kw in transcript_text.lower() for kw in challenge_kws
            )
            if challenge_context and transcript_overlap < 0.7:
                challenged.append(claim_id)
            else:
                supported.append(claim_id)
        elif transcript_overlap > 0:
            unresolved.append(claim_id)

        if paper_overlap >= 0.4:
            already_in.append(claim_id)
        elif not is_question:
            missing.append(claim_id)

    return {
        "supported_by_transcript": supported,
        "challenged_in_discussion": challenged,
        "unresolved": unresolved,
        "missing_from_paper": missing,
        "already_in_paper": already_in,
        "better_as_question": better_as_question,
    }


def _extract_text_from_artifact(artifact: dict | None) -> str:
    """Pull text content from a transcript or working-paper artifact dict."""
    if not artifact:
        return ""
    # Direct text field
    if "text" in artifact:
        return str(artifact["text"])
    # Segments (transcript-style)
    segments = artifact.get("segments") or []
    if segments:
        return " ".join(str(s.get("text") or s.get("content") or "") for s in segments)
    # Sections (working-paper-style)
    sections = artifact.get("sections") or []
    if sections:
        return " ".join(
            str(s.get("content") or s.get("text") or s.get("body") or "")
            for s in sections
        )
    return ""


# ---------------------------------------------------------------------------
# K. Integration packet builder
# ---------------------------------------------------------------------------


def build_slide_intelligence_packet(
    slide_deck_artifact: dict,
    transcript_artifact: dict | None = None,
    working_paper_artifact: dict | None = None,
) -> dict:
    """
    Build the canonical slide intelligence packet for a slide deck artifact.

    The packet is the primary output of the Slide Intelligence Layer and
    serves as the governed derived artifact consumed by downstream modules.

    Parameters
    ----------
    slide_deck_artifact:
        A governed slide deck artifact dict (see :func:`extract_slide_units`).
    transcript_artifact:
        Optional transcript artifact for cross-artifact comparison.
    working_paper_artifact:
        Optional working-paper artifact for cross-artifact comparison.

    Returns
    -------
    dict
        A ``slide_intelligence_packet`` artifact dict with full traceability.
    """
    # --- Step 1: Extract slide units ---
    slide_units = extract_slide_units(slide_deck_artifact)

    slide_to_paper_candidates: list[dict] = []
    extracted_claims: list[dict] = []
    assumptions_registry_entries: list[dict] = []
    knowledge_graph_edges: list[dict] = []
    analysis_gaps: list[dict] = []
    signal_scores: list[dict] = []
    suggested_exhibits: list[dict] = []
    traceability_index: list[dict] = []

    all_slide_outputs: list[dict] = []

    # Build deck-level assumption index before per-slide analysis so Rule 1
    # can suppress false positives when propagation context exists elsewhere
    # in the deck.
    deck_assumption_index = _build_deck_assumption_index(slide_units)

    # Map of slide_id → paper-candidate index for gap→caution propagation
    _candidate_by_slide: dict[str, int] = {}

    for unit in slide_units:
        slide_id = unit["slide_id"]

        # --- Per-slide pipeline ---
        score = score_slide_signal(unit)
        role = classify_slide_role(unit)
        claims = extract_claims(unit)
        assumptions = extract_assumptions(unit)
        entities_rels = extract_entities_and_relationships(unit)
        gaps = detect_gaps(unit, claims, assumptions, deck_assumption_index=deck_assumption_index)
        section = map_to_working_paper_section(unit, role)
        rewrite = rewrite_for_working_paper(unit, role, section)

        # --- Accumulate ---
        signal_scores.append({
            "slide_id": slide_id,
            "signal_score": score["signal_score"],
            "reasoning": score["reasoning"],
        })

        candidate_idx = len(slide_to_paper_candidates)
        _candidate_by_slide[slide_id] = candidate_idx
        slide_to_paper_candidates.append({
            "slide_id": slide_id,
            "section": section,
            "integration_role": role["integration_role"],
            "technical_tags": role["technical_tags"],
            "proposed_text": rewrite["proposed_text"],
            "style_mode": rewrite["style_mode"],
            "caution_flags": list(rewrite["caution_flags"]),  # mutable copy
            "confidence": rewrite["confidence"],
            "traceability": rewrite["traceability"],
        })

        extracted_claims.extend(claims)

        for asm in assumptions:
            assumptions_registry_entries.append({
                "assumption_id": asm["assumption_id"],
                "type": asm["type"],
                "value": asm["value"],
                "applies_to": asm["applies_to"],
                "source_slide_id": slide_id,
                "source_artifact_id": unit.get("source_artifact_id"),
            })

        for rel in entities_rels["relationships"]:
            knowledge_graph_edges.append({
                "edge_id": f"KGE-{slide_id}-{len(knowledge_graph_edges) + 1:03d}",
                "source": rel["source"],
                "relation": rel["relation"],
                "target": rel["target"],
                "source_slide_id": slide_id,
                "source_artifact_id": unit.get("source_artifact_id"),
            })

        analysis_gaps.extend(gaps)

        if role["integration_role"] == "source_exhibit":
            suggested_exhibits.append({
                "slide_id": slide_id,
                "title": unit.get("title"),
                "suggested_section": section,
                "note": rewrite["proposed_text"],
            })

        traceability_index.append({
            "slide_id": slide_id,
            "slide_number": unit["slide_number"],
            "source_artifact_id": unit.get("source_artifact_id"),
            "section": section,
            "integration_role": role["integration_role"],
            "signal_score": score["signal_score"],
            "claim_count": len(claims),
            "assumption_count": len(assumptions),
            "gap_count": len(gaps),
        })

        # Collect for cross-artifact comparison
        all_slide_outputs.extend(claims)
        all_slide_outputs.extend([{
            "claim_text": rewrite["proposed_text"],
            "source_slide_id": slide_id,
        }])

    # --- Step 1b: Cross-slide contradiction detection ---
    # Detect contradictions across slides and add them to analysis_gaps.
    contradiction_gaps = detect_cross_slide_contradictions(slide_units, extracted_claims)
    analysis_gaps.extend(contradiction_gaps)

    # --- Step 1c: Propagate all gaps (including contradictions) into paper candidate caution_flags ---
    # For each detected gap with a source_slide_id, append a human-readable
    # caution to the corresponding paper candidate.  Existing flags are
    # preserved and duplicates are suppressed.
    # Contradiction gaps affecting two slides get caution flags on both candidates.
    for gap in analysis_gaps:
        src = gap.get("source_slide_id")
        if src and src in _candidate_by_slide:
            candidate = slide_to_paper_candidates[_candidate_by_slide[src]]
            severity = gap.get("severity", "")
            desc = gap.get("description", "")
            sev_prefix = f"[{severity.upper()}] " if severity else ""
            caution_text = f"{sev_prefix}{desc}"
            flags: list[str] = candidate["caution_flags"]
            if caution_text not in flags:
                flags.append(caution_text)

        # For contradiction gaps, also apply caution flag to the second slide
        if gap.get("gap_type") == "contradiction":
            related_ids = gap.get("related_claim_ids", [])
            # Find the second slide involved (the one that isn't source_slide_id)
            for claim in extracted_claims:
                if (
                    claim["claim_id"] in related_ids
                    and claim["source_slide_id"] != src
                    and claim["source_slide_id"] in _candidate_by_slide
                ):
                    other_candidate = slide_to_paper_candidates[
                        _candidate_by_slide[claim["source_slide_id"]]
                    ]
                    other_flags: list[str] = other_candidate["caution_flags"]
                    if caution_text not in other_flags:
                        other_flags.append(caution_text)

    # --- Step 2: Cross-artifact comparison ---
    comparison = compare_with_transcript_and_paper(
        all_slide_outputs,
        transcript_artifact=transcript_artifact,
        working_paper_artifact=working_paper_artifact,
    )

    # --- Step 3: Recommended agency questions ---
    recommended_questions: list[dict] = []
    for unit in slide_units:
        role = classify_slide_role(unit)
        if role["integration_role"] in ("source_question", "source_claim"):
            bullets = unit.get("bullets") or []
            for b in bullets:
                if any(kw in b.lower() for kw in ["?", "tbd", "unknown", "unclear"]):
                    recommended_questions.append({
                        "slide_id": unit["slide_id"],
                        "question_text": b.strip(),
                        "source_artifact_id": unit.get("source_artifact_id"),
                    })

    # --- Step 4: Validation status ---
    total_claims = len(extracted_claims)
    low_confidence = sum(1 for c in extracted_claims if c["confidence"] == "low")
    high_gaps = sum(1 for g in analysis_gaps if g["severity"] == "high")
    if high_gaps > 0 or (total_claims > 0 and low_confidence / max(total_claims, 1) > 0.5):
        validation_status = "needs_review"
    elif total_claims > 0:
        validation_status = "provisional"
    else:
        validation_status = "informational"

    return {
        "artifact_type": "slide_intelligence_packet",
        "source_artifact_id": slide_deck_artifact.get("artifact_id", "unknown"),
        "slide_to_paper_candidates": slide_to_paper_candidates,
        "extracted_claims": extracted_claims,
        "assumptions_registry_entries": assumptions_registry_entries,
        "knowledge_graph_edges": knowledge_graph_edges,
        "analysis_gaps": analysis_gaps,
        "validation_status": validation_status,
        "recommended_agency_questions": recommended_questions,
        "suggested_exhibits": suggested_exhibits,
        "signal_scores": signal_scores,
        "traceability_index": traceability_index,
    }


# ---------------------------------------------------------------------------
# Pipeline-oriented API (L. ingest → normalize → align → signals → merge → gaps)
# ---------------------------------------------------------------------------

# Regex helpers for signal extraction
_VERB_START = re.compile(
    r"^(implement|develop|create|update|adopt|replace|deploy|define|establish|"
    r"recommend|propose|use|apply|evaluate|assess|revise|ensure|require|allow|"
    r"consider|provide|present|demonstrate|verify|validate|confirm|review|"
    r"add|remove|increase|decrease|adjust|align|integrate|enable|support)\b",
    re.IGNORECASE,
)
_NUMBER_PCT = re.compile(r"\b\d[\d.,]*\s*(%|dB|dBm|MHz|GHz|km|W|m|ms|us|Hz|bps)\b", re.IGNORECASE)
_UNCERTAIN = re.compile(
    r"\b(tbd|unknown|unclear|uncertain|may|might|could|possibly|approximately|"
    r"pending|assumed|assumed to be|estimate|if|unless|depending|subject to|"
    r"not yet|to be determined)\b",
    re.IGNORECASE,
)
_QUESTION_MARK = re.compile(r"\?")


def ingest_slides(pdf_path: str | Path) -> list[dict]:
    """
    Ingest a slide file and return raw per-slide objects.

    Supports:
    - JSON fixture files (``*.json``) — used in tests and CI pipelines.
    - PDF files (``*.pdf``) — parsed with ``pdfplumber`` when available.

    Parameters
    ----------
    pdf_path:
        Path to a ``.pdf`` or ``.json`` slide file.

    Returns
    -------
    list[dict]
        Raw slide objects with at minimum:
        ``slide_number``, ``title``, ``bullet_points``, ``full_text``.
    """
    path = Path(pdf_path)
    suffix = path.suffix.lower()

    if suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        # Accept both a list of raw slides and a governed slide-deck artifact.
        if isinstance(data, list):
            raw = data
        else:
            raw = data.get("slides", [])
        result = []
        for i, slide in enumerate(raw, start=1):
            full_text = slide.get("raw_text") or slide.get("full_text") or ""
            if not full_text:
                parts = []
                if slide.get("title"):
                    parts.append(slide["title"])
                parts.extend(slide.get("bullets") or slide.get("bullet_points") or [])
                full_text = "\n".join(str(p) for p in parts)
            bullets = (
                slide.get("bullet_points")
                or slide.get("bullets")
                or slide.get("content")
                or []
            )
            result.append({
                "slide_number": slide.get("slide_number", i),
                "title": slide.get("title") or "",
                "bullet_points": bullets,
                "full_text": full_text,
            })
        return result

    if suffix == ".pdf":
        try:
            import pdfplumber  # type: ignore[import]
        except ImportError:
            try:
                import pypdf as _pypdf  # type: ignore[import]

                result = []
                with _pypdf.PdfReader(str(path)) as reader:
                    for i, page in enumerate(reader.pages, start=1):
                        text = page.extract_text() or ""
                        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
                        title = lines[0] if lines else ""
                        bullets = lines[1:] if len(lines) > 1 else []
                        result.append({
                            "slide_number": i,
                            "title": title,
                            "bullet_points": bullets,
                            "full_text": text,
                        })
                return result
            except ImportError:
                pass
            # No PDF library available — return a single stub slide so the
            # pipeline does not fail hard.
            return [{
                "slide_number": 1,
                "title": "",
                "bullet_points": [],
                "full_text": "",
            }]

        result = []
        with pdfplumber.open(str(path)) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
                title = lines[0] if lines else ""
                bullets = lines[1:] if len(lines) > 1 else []
                result.append({
                    "slide_number": i,
                    "title": title,
                    "bullet_points": bullets,
                    "full_text": text,
                })
        return result

    raise ValueError(f"Unsupported slide file format: {suffix!r}. Expected .json or .pdf")


def normalize_slides(raw_slide_objects: list[dict]) -> list[dict]:
    """
    Normalize raw slide objects into the canonical slide schema.

    Parameters
    ----------
    raw_slide_objects:
        Output of :func:`ingest_slides`.

    Returns
    -------
    list[dict]
        Normalized slides, each with keys:
        ``slide_id``, ``title``, ``bullets``, ``raw_text``, ``keywords``.
    """

    def _extract_keywords(text: str) -> list[str]:
        """Simple noun-heavy token extraction without NLP libraries."""
        tokens = re.findall(r"\b[A-Za-z][A-Za-z0-9_/-]{2,}\b", text)
        stop = {
            "the", "and", "for", "that", "this", "with", "are", "was", "been",
            "from", "have", "not", "its", "but", "can", "all", "has", "also",
            "will", "use", "used", "using", "each", "more", "than", "when",
            "which", "into", "over", "both", "their", "any", "our", "they",
            "such", "may", "new", "would", "should", "must", "other", "where",
        }
        seen: set[str] = set()
        keywords = []
        for tok in tokens:
            lower = tok.lower()
            if lower in stop:
                continue
            # Prefer capitalised tokens, technical acronyms, or matched keywords
            if tok not in seen:
                seen.add(tok)
                # Boost technical terms
                is_tech = any(kw.lower() in lower for kw in _TECH_PARAM_KEYWORDS + _MODEL_KEYWORDS)
                is_upper = tok[0].isupper()
                if is_tech or is_upper or tok.isupper():
                    keywords.append(tok)
        return keywords[:15]

    normalized = []
    for i, slide in enumerate(raw_slide_objects, start=1):
        raw_text = slide.get("full_text") or slide.get("raw_text") or ""
        title = slide.get("title") or ""
        if not title and raw_text:
            title = raw_text.splitlines()[0].strip()
        bullets = slide.get("bullet_points") or slide.get("bullets") or []
        if not raw_text:
            parts = [title] + list(bullets)
            raw_text = "\n".join(p for p in parts if p)
        normalized.append({
            "slide_id": f"slide_{i:02d}",
            "title": title,
            "bullets": [str(b) for b in bullets],
            "raw_text": raw_text,
            "keywords": _extract_keywords(raw_text),
        })
    return normalized


def align_slides_to_transcript(
    slides: list[dict],
    transcript_segments: list[dict | str],
) -> list[dict]:
    """
    Align each slide to the best-matching transcript segments.

    Uses keyword overlap and TF-IDF cosine similarity (no external libraries).

    Parameters
    ----------
    slides:
        Normalized slides from :func:`normalize_slides`.
    transcript_segments:
        List of transcript segments. Each segment may be a dict with a
        ``text`` / ``content`` key or a plain string.

    Returns
    -------
    list[dict]
        One entry per slide:
        ``{"slide_id": ..., "matched_segments": [...], "confidence": float}``.
    """

    def _seg_text(seg: dict | str) -> str:
        if isinstance(seg, str):
            return seg
        return str(seg.get("text") or seg.get("content") or seg.get("body") or "")

    def _tokenize(text: str) -> list[str]:
        return re.findall(r"\b[a-z]{2,}\b", text.lower())

    seg_texts = [_seg_text(s) for s in transcript_segments]

    # Build a simple TF-IDF representation.
    all_docs = [s.get("raw_text", "") for s in slides] + seg_texts
    # Document frequency per term
    df: dict[str, int] = {}
    tokenized_docs = [_tokenize(d) for d in all_docs]
    for tok_list in tokenized_docs:
        for tok in set(tok_list):
            df[tok] = df.get(tok, 0) + 1
    n_docs = max(len(all_docs), 1)

    def _tfidf(tokens: list[str]) -> dict[str, float]:
        tf: dict[str, int] = {}
        for t in tokens:
            tf[t] = tf.get(t, 0) + 1
        vec: dict[str, float] = {}
        for t, count in tf.items():
            idf = math.log((n_docs + 1) / (df.get(t, 0) + 1)) + 1.0
            vec[t] = (count / max(len(tokens), 1)) * idf
        return vec

    def _cosine(v1: dict[str, float], v2: dict[str, float]) -> float:
        common = set(v1) & set(v2)
        if not common:
            return 0.0
        dot = sum(v1[t] * v2[t] for t in common)
        mag1 = math.sqrt(sum(x * x for x in v1.values()))
        mag2 = math.sqrt(sum(x * x for x in v2.values()))
        if mag1 == 0 or mag2 == 0:
            return 0.0
        return dot / (mag1 * mag2)

    # Pre-compute TF-IDF for each segment
    seg_vecs = [_tfidf(_tokenize(t)) for t in seg_texts]

    result = []
    for slide in slides:
        slide_id = slide.get("slide_id", "unknown")
        slide_vec = _tfidf(_tokenize(slide.get("raw_text", "")))
        slide_keywords = {k.lower() for k in slide.get("keywords", [])}

        scores: list[tuple[int, float]] = []
        for idx, seg_text in enumerate(seg_texts):
            cos_sim = _cosine(slide_vec, seg_vecs[idx])
            seg_tokens = set(_tokenize(seg_text))
            overlap = len(slide_keywords & seg_tokens) / max(len(slide_keywords), 1)
            combined = 0.6 * cos_sim + 0.4 * overlap
            scores.append((idx, combined))

        scores.sort(key=lambda x: x[1], reverse=True)

        # Keep segments above threshold or the top-1 (if any exist).
        # Threshold raised from 0.05 to 0.15 to reduce weak false-positive matches.
        threshold = _ALIGNMENT_THRESHOLD
        matched_indices = [idx for idx, sc in scores if sc >= threshold]
        if not matched_indices and scores:
            matched_indices = [scores[0][0]]

        matched_segments = []
        confidence = 0.0
        if matched_indices:
            matched_segments = [_seg_text(transcript_segments[i]) for i in matched_indices]
            confidence = round(
                sum(sc for _, sc in scores if sc >= threshold) / max(len(matched_indices), 1),
                4,
            )
            confidence = min(1.0, confidence)

        result.append({
            "slide_id": slide_id,
            "matched_segments": matched_segments,
            "confidence": confidence,
        })

    return result


def extract_slide_signals(slides: list[dict]) -> dict:
    """
    Extract structured signals from a list of normalized slides.

    Rules (deterministic, no LLM):
    - Bullets starting with action verbs → ``proposals``
    - Bullets containing numbers/units → ``metrics``
    - Bullets with uncertainty language → ``assumptions``
    - Bullets with ``?`` or TBD-style language → ``open_questions``
    - Bullets matching claim patterns → ``claims``

    Parameters
    ----------
    slides:
        Normalized slides from :func:`normalize_slides`.

    Returns
    -------
    dict
        Keys: ``claims``, ``assumptions``, ``proposals``, ``metrics``,
        ``open_questions``.
    """
    claims: list[str] = []
    assumptions: list[str] = []
    proposals: list[str] = []
    metrics: list[str] = []
    open_questions: list[str] = []

    for slide in slides:
        bullets = slide.get("bullets") or []
        raw_text = slide.get("raw_text") or ""

        # Also process full raw_text lines as fallback when bullets list is empty
        lines = bullets if bullets else [
            ln.strip() for ln in raw_text.splitlines() if ln.strip()
        ]

        for line in lines:
            text = str(line).strip()
            if not text:
                continue

            is_claim = any(re.search(pat, text, re.IGNORECASE) for pat in _CLAIM_PATTERNS)
            is_verb_start = bool(_VERB_START.match(text))
            is_metric = bool(_NUMBER_PCT.search(text))
            is_uncertain = bool(_UNCERTAIN.search(text))
            is_question = bool(_QUESTION_MARK.search(text))

            if is_question or (is_uncertain and not is_claim):
                open_questions.append(text)
            elif is_uncertain:
                assumptions.append(text)
            elif is_verb_start:
                proposals.append(text)
            elif is_claim:
                claims.append(text)

            # Metrics are collected independently — a bullet can be both a
            # claim/proposal and a metric (e.g. "EIRP exceeds 46 dBm").
            if is_metric and text not in metrics:
                metrics.append(text)

    return {
        "claims": claims,
        "assumptions": assumptions,
        "proposals": proposals,
        "metrics": metrics,
        "open_questions": open_questions,
    }


# ---------------------------------------------------------------------------
# merge_slide_transcript_outputs and compute_slide_transcript_gaps are
# imported from gap_detection at the top of this file.  They are part of the
# Prompt P subsystem and are intentionally housed in gap_detection.py.
# The names remain importable from slide_intelligence for backward
# compatibility with existing callers and tests.
# ---------------------------------------------------------------------------
