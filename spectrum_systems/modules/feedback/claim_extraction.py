"""
Claim Extraction — spectrum_systems/modules/feedback/claim_extraction.py

Breaks AI-generated documents into reviewable claim-level units.

This is the prerequisite for claim-level feedback: without fine-grained
segmentation, reviewers can only comment at the document level, which limits
the utility of feedback for downstream learning systems (AU, AV, AW, AZ).

Extraction strategy
-------------------
1. If the document is a structured dict with ``sections``, iterate sections
   and extract claims from each section's text using sentence splitting.
2. If the document is a structured dict with a ``claims`` list, use those
   directly.
3. Bullet/list items within section text are also split out as individual
   claims.
4. For plain-text documents, apply sentence splitting directly.

Public API
----------
ClaimUnit
    A single reviewable unit extracted from a document.

extract_claims(document) -> list[ClaimUnit]
    Extract all claims from a document dict or plain string.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------


@dataclass
class ClaimUnit:
    """A single reviewable unit extracted from a document.

    Attributes
    ----------
    claim_id:
        Unique identifier for this claim.
    claim_text:
        The text content of the claim.
    section_id:
        Identifier of the section this claim belongs to.  ``"root"`` if the
        document has no explicit section structure.
    source_index:
        0-based position of this claim within its section (useful for
        ordering and round-tripping back to the source).
    """

    claim_id: str
    claim_text: str
    section_id: str
    source_index: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-compatible dict."""
        return {
            "claim_id": self.claim_id,
            "claim_text": self.claim_text,
            "section_id": self.section_id,
            "source_index": self.source_index,
        }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_claims(
    document: Union[Dict[str, Any], str],
    section_id_field: str = "section_id",
    text_fields: Optional[List[str]] = None,
) -> List[ClaimUnit]:
    """Extract reviewable claim units from a document.

    Parameters
    ----------
    document:
        Either a structured dict (working paper section, synthesis output,
        meeting minutes record, etc.) or a plain string.
    section_id_field:
        Key used to identify section IDs inside structured ``sections`` lists.
    text_fields:
        Ordered list of dict keys to check for extractable text inside each
        section.  Defaults to ``["text", "content", "summary", "body"]``.

    Returns
    -------
    list[ClaimUnit]
        Extracted claim units in document order.
    """
    if text_fields is None:
        text_fields = ["text", "content", "summary", "body"]

    if isinstance(document, str):
        return _extract_from_text(document, section_id="root")

    # Structured document — try common structural patterns
    claims: List[ClaimUnit] = []

    # Pattern 1: top-level "claims" list
    if "claims" in document and isinstance(document["claims"], list):
        for idx, item in enumerate(document["claims"]):
            text = _item_to_text(item)
            if text:
                claims.append(ClaimUnit(
                    claim_id=str(uuid.uuid4()),
                    claim_text=text.strip(),
                    section_id="root",
                    source_index=idx,
                ))
        return claims

    # Pattern 2: "sections" list
    if "sections" in document and isinstance(document["sections"], list):
        for section in document["sections"]:
            if not isinstance(section, dict):
                continue
            sec_id = str(section.get(section_id_field, section.get("id", str(uuid.uuid4()))))
            section_claims = _extract_from_section(section, sec_id, text_fields)
            claims.extend(section_claims)
        return claims

    # Pattern 3: flat dict with text fields — treat as single section
    for tf in text_fields:
        if tf in document and document[tf]:
            text = str(document[tf])
            return _extract_from_text(text, section_id="root")

    # Pattern 4: lists of structured items (decisions, action_items, etc.)
    for list_key in ("decisions", "action_items", "gaps", "contradictions"):
        if list_key in document and isinstance(document[list_key], list):
            for idx, item in enumerate(document[list_key]):
                text = _item_to_text(item)
                if text:
                    claims.append(ClaimUnit(
                        claim_id=str(uuid.uuid4()),
                        claim_text=text.strip(),
                        section_id=list_key,
                        source_index=idx,
                    ))
            if claims:
                return claims

    return claims


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _extract_from_section(
    section: Dict[str, Any],
    section_id: str,
    text_fields: List[str],
) -> List[ClaimUnit]:
    """Extract claims from a single section dict."""
    claims: List[ClaimUnit] = []

    # Nested "claims" list inside the section
    if "claims" in section and isinstance(section["claims"], list):
        for idx, item in enumerate(section["claims"]):
            text = _item_to_text(item)
            if text:
                claims.append(ClaimUnit(
                    claim_id=str(uuid.uuid4()),
                    claim_text=text.strip(),
                    section_id=section_id,
                    source_index=idx,
                ))
        return claims

    # Text field in the section
    for tf in text_fields:
        if tf in section and section[tf]:
            text = str(section[tf])
            return _extract_from_text(text, section_id=section_id)

    return claims


def _extract_from_text(text: str, section_id: str) -> List[ClaimUnit]:
    """Split text into claim units by sentence and bullet points."""
    units: List[str] = []

    # Split bullet points first
    lines = text.splitlines()
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Bullet point patterns: -, *, •, numbered list
        if re.match(r"^[-*•]\s+", line) or re.match(r"^\d+[.)]\s+", line):
            cleaned = re.sub(r"^[-*•\d.)\s]+", "", line).strip()
            if cleaned:
                units.append(cleaned)
        else:
            # Sentence split for non-bullet lines
            sentences = _split_sentences(line)
            units.extend(s.strip() for s in sentences if s.strip())

    if not units:
        # Fallback: treat the whole text as one claim
        stripped = text.strip()
        if stripped:
            units = [stripped]

    return [
        ClaimUnit(
            claim_id=str(uuid.uuid4()),
            claim_text=unit,
            section_id=section_id,
            source_index=idx,
        )
        for idx, unit in enumerate(units)
        if unit
    ]


def _split_sentences(text: str) -> List[str]:
    """Simple sentence splitter using punctuation boundaries."""
    # Split on sentence-ending punctuation followed by whitespace or end
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def _item_to_text(item: Any) -> str:
    """Extract text from a list item (string or dict)."""
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        for key in ("text", "content", "description", "summary", "statement", "title"):
            if key in item and item[key]:
                return str(item[key])
    return ""
