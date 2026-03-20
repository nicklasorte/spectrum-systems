"""
observe.py — OBSERVE stage of the Working Paper Engine pipeline.

Responsibilities:
  - Extract raw facts, questions, constraints, assumptions, and open issues
    from all input excerpts.
  - Apply lightweight semantic tagging (no interpretation beyond tagging).
  - Preserve source provenance on every extracted item.
  - Return a flat list of ObservedItems ordered by source then position.

Design constraints:
  - Fully deterministic; no LLM calls, no embeddings.
  - Prefer recall over precision — interpretation is deferred to INTERPRET.
  - Every item carries source_artifact_id + source_locator for downstream
    traceability.
"""
from __future__ import annotations

import re
import uuid
from typing import List, Tuple

from .models import (
    ObservedItem,
    SourceDocumentExcerpt,
    SourceType,
    StudyPlanExcerpt,
    TranscriptExcerpt,
    WorkingPaperInputs,
)

# ---------------------------------------------------------------------------
# Tag keyword tables
# ---------------------------------------------------------------------------

_ASSUMPTION_KEYWORDS: Tuple[str, ...] = (
    "assume", "assumed", "assumption", "assuming",
    "presume", "presumed", "taking as given",
)

_OPEN_ISSUE_KEYWORDS: Tuple[str, ...] = (
    "open question", "open issue", "tbd", "to be determined",
    "not yet", "pending", "unclear", "unknown", "unresolved",
    "needs clarification", "needs confirmation", "need to confirm",
)

_CONSTRAINT_KEYWORDS: Tuple[str, ...] = (
    "constraint", "limit", "limitation", "restricted", "not allowed",
    "must not", "shall not", "prohibited", "cannot exceed",
    "exclusion zone", "coordination zone", "protection criteria",
)

_UNCERTAINTY_KEYWORDS: Tuple[str, ...] = (
    "uncertain", "uncertainty", "not validated", "unvalidated",
    "may vary", "could differ", "sensitivity", "variability",
    "confidence", "error bound", "margin",
)

_METHODOLOGY_KEYWORDS: Tuple[str, ...] = (
    "method", "methodology", "model", "approach", "technique",
    "algorithm", "propagation", "link budget", "path loss",
    "simulation", "analysis", "framework",
)

_DECISION_KEYWORDS: Tuple[str, ...] = (
    "decided", "agreed", "resolved", "confirmed", "approved",
    "will proceed", "action item", "shall be",
)


def _tag_sentence(text: str) -> str:
    """Return the most specific semantic tag for a text fragment."""
    lower = text.lower()
    if any(kw in lower for kw in _OPEN_ISSUE_KEYWORDS):
        return "open_issue"
    if any(kw in lower for kw in _ASSUMPTION_KEYWORDS):
        return "assumption"
    if any(kw in lower for kw in _CONSTRAINT_KEYWORDS):
        return "constraint"
    if any(kw in lower for kw in _UNCERTAINTY_KEYWORDS):
        return "uncertainty"
    if any(kw in lower for kw in _METHODOLOGY_KEYWORDS):
        return "methodology"
    if any(kw in lower for kw in _DECISION_KEYWORDS):
        return "decision"
    return "fact"


def _split_sentences(text: str) -> List[str]:
    """Split text into non-empty sentence fragments."""
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _make_item_id(prefix: str, index: int) -> str:
    return f"OBS-{prefix[:8].upper()}-{index:04d}"


# ---------------------------------------------------------------------------
# Per-source-type extraction
# ---------------------------------------------------------------------------


def _observe_document(
    doc: SourceDocumentExcerpt,
    counter: List[int],
) -> List[ObservedItem]:
    items: List[ObservedItem] = []
    sentences = _split_sentences(doc.content)
    for sent in sentences:
        if not sent:
            continue
        counter[0] += 1
        items.append(
            ObservedItem(
                item_id=_make_item_id(doc.artifact_id, counter[0]),
                source_artifact_id=doc.artifact_id,
                source_type=SourceType.DOCUMENT,
                source_locator=doc.locator,
                text=sent,
                tag=_tag_sentence(sent),
                confidence=0.9,
            )
        )
    return items


def _observe_transcript(
    tx: TranscriptExcerpt,
    counter: List[int],
) -> List[ObservedItem]:
    items: List[ObservedItem] = []
    sentences = _split_sentences(tx.content)
    for sent in sentences:
        if not sent:
            continue
        counter[0] += 1
        text = f"[{tx.speaker}] {sent}" if tx.speaker else sent
        items.append(
            ObservedItem(
                item_id=_make_item_id(tx.artifact_id, counter[0]),
                source_artifact_id=tx.artifact_id,
                source_type=SourceType.TRANSCRIPT,
                source_locator=tx.locator,
                text=text,
                tag=_tag_sentence(sent),
                confidence=0.85,
            )
        )
    return items


def _observe_study_plan(
    sp: StudyPlanExcerpt,
    counter: List[int],
) -> List[ObservedItem]:
    items: List[ObservedItem] = []
    sentences = _split_sentences(sp.content)
    if sp.objective:
        sentences = [f"Objective: {sp.objective}"] + sentences
    for sent in sentences:
        if not sent:
            continue
        counter[0] += 1
        items.append(
            ObservedItem(
                item_id=_make_item_id(sp.artifact_id, counter[0]),
                source_artifact_id=sp.artifact_id,
                source_type=SourceType.STUDY_PLAN,
                source_locator=sp.locator,
                text=sent,
                tag=_tag_sentence(sent),
                confidence=0.95,
            )
        )
    return items


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def observe(inputs: WorkingPaperInputs) -> List[ObservedItem]:
    """
    OBSERVE stage: extract and tag all raw items from inputs.

    Returns a flat, ordered list of ObservedItem instances.
    Order: source_documents → transcripts → study_plan_excerpts.
    """
    observed: List[ObservedItem] = []
    counter = [0]  # mutable reference for sequential IDs

    for doc in inputs.source_documents:
        observed.extend(_observe_document(doc, counter))

    for tx in inputs.transcripts:
        observed.extend(_observe_transcript(tx, counter))

    for sp in inputs.study_plan_excerpts:
        observed.extend(_observe_study_plan(sp, counter))

    # If a context_description was given and no other inputs produced items,
    # synthesise a minimal observed item so the pipeline never runs empty.
    if not observed and inputs.context_description:
        counter[0] += 1
        observed.append(
            ObservedItem(
                item_id=_make_item_id("CTX", counter[0]),
                source_artifact_id="context",
                source_type=SourceType.DERIVED,
                source_locator="",
                text=inputs.context_description,
                tag=_tag_sentence(inputs.context_description),
                confidence=0.7,
            )
        )

    return observed
