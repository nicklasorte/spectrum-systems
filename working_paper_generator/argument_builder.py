"""
argument_builder.py

Extracts and structures arguments and positions from a parsed meeting transcript.

An argument is a speaker's claim together with supporting evidence sentences
found in adjacent segments.  Each argument is assigned:
- a unique identifier (ARG-NNN)
- a stance inferred from language cues ("supporting" / "opposing" / "neutral")
- an optional section reference if the claim text overlaps a known paper section
"""

from __future__ import annotations

import re
from typing import List, Optional

from .schemas import Argument, ParsedTranscript, PaperState

_OPPOSING_PATTERNS = re.compile(
    r"\b(however|but|disagree|concern|risk|problem|issue|unclear|question)\b", re.I
)
_SUPPORTING_PATTERNS = re.compile(
    r"\b(agree|support|confirm|validates?|good|correct|yes|recommend)\b", re.I
)

_EVIDENCE_LOOKBACK_WINDOW = 2
_CLAIM_MIN_WORDS = 5


def _infer_stance(text: str) -> str:
    if _OPPOSING_PATTERNS.search(text):
        return "opposing"
    if _SUPPORTING_PATTERNS.search(text):
        return "supporting"
    return "neutral"


def _find_section_ref(text: str, paper_state: Optional[PaperState]) -> Optional[str]:
    if paper_state is None:
        return None
    lower = text.lower()
    for sec in paper_state.sections:
        if sec.title.lower() in lower:
            return sec.section_id
    return None


def build_arguments(
    transcript: ParsedTranscript,
    paper_state: Optional[PaperState] = None,
) -> List[Argument]:
    """Return a list of :class:`Argument` objects extracted from *transcript*.

    Parameters
    ----------
    transcript:
        Parsed meeting transcript.
    paper_state:
        Optional existing working paper state used to assign section references.
    """
    arguments: List[Argument] = []
    arg_counter = 0

    for idx, seg in enumerate(transcript.segments):
        if len(seg.text.split()) < _CLAIM_MIN_WORDS:
            continue  # too short to be an argument

        # Collect evidence from adjacent segments by the same speaker
        evidence: List[str] = []
        for nearby in transcript.segments[max(0, idx - _EVIDENCE_LOOKBACK_WINDOW): idx]:
            if nearby.speaker == seg.speaker and len(nearby.text.split()) >= _CLAIM_MIN_WORDS:
                evidence.append(nearby.text)

        arg_counter += 1
        arguments.append(
            Argument(
                argument_id=f"ARG-{arg_counter:03d}",
                claim=seg.text,
                evidence=evidence,
                speaker=seg.speaker,
                section_ref=_find_section_ref(seg.text, paper_state),
                stance=_infer_stance(seg.text),
            )
        )

    return arguments
