"""
meeting_delta_engine.py

Computes a MeetingDelta — the set of differences between a meeting discussion
(captured in a ParsedTranscript) and the current state of a working paper
(PaperState).  When no existing paper state is provided the entire transcript
is treated as new content.
"""

from __future__ import annotations

from typing import List, Optional

from .schemas import MeetingDelta, PaperState, ParsedTranscript


def _extract_topics(transcript: ParsedTranscript) -> List[str]:
    """Heuristically extract topic phrases from decision-tagged segments."""
    topics: List[str] = []
    seen: set[str] = set()
    for seg in transcript.segments:
        if "decision" in seg.tags or "action" in seg.tags:
            phrase = seg.text[:120].strip()
            if phrase and phrase not in seen:
                topics.append(phrase)
                seen.add(phrase)
    return topics


def _find_updated_sections(
    transcript: ParsedTranscript, state: PaperState
) -> List[str]:
    """Return section IDs whose titles appear in the transcript text."""
    full_text = " ".join(seg.text.lower() for seg in transcript.segments)
    updated: List[str] = []
    for sec in state.sections:
        if sec.title.lower() in full_text:
            updated.append(sec.section_id)
    return updated


def _extract_unresolved(transcript: ParsedTranscript) -> List[str]:
    """Extract segments tagged as questions that were not also tagged as decisions."""
    unresolved: List[str] = []
    for seg in transcript.segments:
        if "question" in seg.tags and "decision" not in seg.tags:
            unresolved.append(seg.text[:120].strip())
    return unresolved


def _extract_consensus(transcript: ParsedTranscript) -> List[str]:
    """Extract segments tagged as decisions."""
    consensus: List[str] = []
    for seg in transcript.segments:
        if "decision" in seg.tags:
            consensus.append(seg.text[:120].strip())
    return consensus


def compute_delta(
    transcript: ParsedTranscript,
    paper_state: Optional[PaperState] = None,
) -> MeetingDelta:
    """Return a :class:`MeetingDelta` describing what the meeting contributed.

    Parameters
    ----------
    transcript:
        Parsed meeting transcript.
    paper_state:
        Optional existing working paper state for comparison.  When ``None``,
        all topics are treated as new.
    """
    topics = _extract_topics(transcript)
    updated = _find_updated_sections(transcript, paper_state) if paper_state else []
    unresolved = _extract_unresolved(transcript)
    consensus = _extract_consensus(transcript)

    # Topics that appear in existing sections are not genuinely new
    if paper_state:
        existing_titles_lower = {sec.title.lower() for sec in paper_state.sections}
        full_text_lower = " ".join(seg.text.lower() for seg in transcript.segments)
        new_topics = [
            t for t in topics
            if not any(et in full_text_lower and et in t.lower() for et in existing_titles_lower)
        ]
    else:
        new_topics = topics

    return MeetingDelta(
        new_topics=new_topics,
        updated_sections=updated,
        unresolved_items=unresolved,
        consensus_items=consensus,
    )
