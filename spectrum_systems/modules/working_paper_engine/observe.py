"""
Working Paper Engine — observe.py

OBSERVE stage: Extract raw facts, questions, constraints, assumptions, and
open issues from all input sources without interpretation.

Design principles
-----------------
- No interpretation beyond lightweight tagging.
- Preserve provenance to source chunks where possible.
- Each ObservedItem records its source_artifact_id, source_type, and
  source_locator so downstream stages can trace back to origin.
- Deterministic: identical inputs produce identical outputs.
"""

from __future__ import annotations

import re
from typing import List

from spectrum_systems.modules.working_paper_engine.models import (
    EngineInputs,
    ObserveResult,
    ObservedItem,
    SourceDocumentExcerpt,
    SourceType,
    StudyPlanExcerpt,
    TranscriptExcerpt,
)

# ---------------------------------------------------------------------------
# Tag detection patterns
# ---------------------------------------------------------------------------

_QUESTION_PATTERNS = [
    re.compile(r"\?"),
    re.compile(r"\b(what|how|why|when|where|who|which|whether)\b", re.IGNORECASE),
    re.compile(r"\b(unclear|unknown|undetermined|tbd|to be determined)\b", re.IGNORECASE),
]

_ASSUMPTION_PATTERNS = [
    re.compile(r"\b(assum|assume|assumed|assuming|assumption)\b", re.IGNORECASE),
    re.compile(r"\b(for the purpose|working assumption|treated as)\b", re.IGNORECASE),
]

_CONSTRAINT_PATTERNS = [
    re.compile(r"\b(constraint|constrained|limit|limitation|restricted|restriction|boundary|boundaries)\b", re.IGNORECASE),
    re.compile(r"\b(must not|shall not|cannot|prohibited|forbidden)\b", re.IGNORECASE),
    re.compile(r"\b(protection criteria|interference threshold|coordination zone)\b", re.IGNORECASE),
]

_OPEN_ISSUE_PATTERNS = [
    re.compile(r"\b(open issue|unresolved|pending|action item|follow.?up|gap|missing|need)\b", re.IGNORECASE),
    re.compile(r"\b(not available|not yet|TBD|TBA|not determined|no data)\b", re.IGNORECASE),
]

_FACT_PATTERNS = [
    re.compile(r"\b(result|finding|measurement|measured|calculated|computed|modeled|observed)\b", re.IGNORECASE),
    re.compile(r"\b(GHz|MHz|kHz|dBm|dB|km|m|watts?|power|frequency|band)\b", re.IGNORECASE),
]


def _detect_tags(text: str) -> List[str]:
    """Lightweight classification of a text snippet into item type tags."""
    tags: List[str] = []
    if any(p.search(text) for p in _QUESTION_PATTERNS):
        tags.append("question")
    if any(p.search(text) for p in _ASSUMPTION_PATTERNS):
        tags.append("assumption")
    if any(p.search(text) for p in _CONSTRAINT_PATTERNS):
        tags.append("constraint")
    if any(p.search(text) for p in _OPEN_ISSUE_PATTERNS):
        tags.append("open_issue")
    if any(p.search(text) for p in _FACT_PATTERNS):
        tags.append("fact")
    if not tags:
        tags.append("fact")
    return tags


def _primary_type(tags: List[str]) -> str:
    """Select the primary item type from a list of tags using priority order."""
    for t in ("open_issue", "question", "constraint", "assumption", "fact"):
        if t in tags:
            return t
    return "fact"


def _split_sentences(text: str) -> List[str]:
    """Split text into sentences. Returns non-empty stripped sentences."""
    raw = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    return [s.strip() for s in raw if s.strip()]


def _observe_source_document(
    excerpt: SourceDocumentExcerpt,
    id_counter: List[int],
) -> List[ObservedItem]:
    items: List[ObservedItem] = []
    sentences = _split_sentences(excerpt.content)
    for sentence in sentences:
        if not sentence:
            continue
        tags = _detect_tags(sentence)
        item_id = f"OBS-{id_counter[0]:04d}"
        id_counter[0] += 1
        items.append(
            ObservedItem(
                item_id=item_id,
                content=sentence,
                item_type=_primary_type(tags),
                source_artifact_id=excerpt.artifact_id,
                source_type=SourceType.SOURCE_DOCUMENT,
                source_locator=excerpt.source_locator,
                confidence=1.0,
                tags=tags,
            )
        )
    return items


def _observe_transcript(
    excerpt: TranscriptExcerpt,
    id_counter: List[int],
) -> List[ObservedItem]:
    items: List[ObservedItem] = []
    sentences = _split_sentences(excerpt.content)
    for sentence in sentences:
        if not sentence:
            continue
        tags = _detect_tags(sentence)
        item_id = f"OBS-{id_counter[0]:04d}"
        id_counter[0] += 1
        items.append(
            ObservedItem(
                item_id=item_id,
                content=sentence,
                item_type=_primary_type(tags),
                source_artifact_id=excerpt.artifact_id,
                source_type=SourceType.TRANSCRIPT,
                source_locator=excerpt.source_locator,
                confidence=0.9,
                tags=tags,
            )
        )
    return items


def _observe_study_plan(
    excerpt: StudyPlanExcerpt,
    id_counter: List[int],
) -> List[ObservedItem]:
    items: List[ObservedItem] = []
    sentences = _split_sentences(excerpt.content)
    for sentence in sentences:
        if not sentence:
            continue
        tags = _detect_tags(sentence)
        item_id = f"OBS-{id_counter[0]:04d}"
        id_counter[0] += 1
        items.append(
            ObservedItem(
                item_id=item_id,
                content=sentence,
                item_type=_primary_type(tags),
                source_artifact_id=excerpt.artifact_id,
                source_type=SourceType.STUDY_PLAN,
                source_locator=excerpt.source_locator,
                confidence=1.0,
                tags=tags,
            )
        )
    return items


def run_observe(inputs: EngineInputs) -> ObserveResult:
    """Run the OBSERVE stage on all provided inputs.

    Extracts raw facts, questions, constraints, assumptions, and open issues
    from source documents, transcripts, and study plans. Items are tagged
    but not interpreted.

    Parameters
    ----------
    inputs:
        Aggregated engine inputs.

    Returns
    -------
    ObserveResult
        All observed items with provenance metadata.
    """
    id_counter = [1]
    all_items: List[ObservedItem] = []

    for doc in inputs.source_documents:
        all_items.extend(_observe_source_document(doc, id_counter))

    for transcript in inputs.transcripts:
        all_items.extend(_observe_transcript(transcript, id_counter))

    for plan in inputs.study_plans:
        all_items.extend(_observe_study_plan(plan, id_counter))

    return ObserveResult(items=all_items)
