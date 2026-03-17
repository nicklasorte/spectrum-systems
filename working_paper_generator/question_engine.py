"""
question_engine.py

Identifies open questions from a parsed meeting transcript.

A question is detected when:
  - a segment contains a literal "?" character, OR
  - a segment is tagged "question" (by the transcript parser), OR
  - a segment contains explicit marker phrases such as "open question" or
    "need to clarify".

Each question is assigned a unique identifier (QST-NNN) and its resolution
status is inferred from whether a subsequent segment by a different speaker
provides an affirmative answer cue.
"""

from __future__ import annotations

import re
from typing import List, Optional

from .schemas import OpenQuestion, ParsedTranscript, PaperState

_QUESTION_PHRASES = re.compile(
    r"\b(open question|need to (clarify|confirm|check|decide|resolve)|"
    r"unclear|unknown|not sure|tbd|to be determined)\b",
    re.I,
)
_ANSWER_CUES = re.compile(
    r"\b(agree|confirmed|decided|resolved|yes|correct|will do|done|"
    r"we will|action item)\b",
    re.I,
)
_ANSWER_LOOKAHEAD_WINDOW = 4


def _is_question(seg_text: str, tags: List[str]) -> bool:
    return "?" in seg_text or "question" in tags or bool(_QUESTION_PHRASES.search(seg_text))


def _find_section_ref(text: str, paper_state: Optional[PaperState]) -> Optional[str]:
    if paper_state is None:
        return None
    lower = text.lower()
    for sec in paper_state.sections:
        if sec.title.lower() in lower:
            return sec.section_id
    return None


def _infer_resolution(
    question_idx: int,
    speaker: str,
    transcript: "ParsedTranscript",
) -> str:
    """Look ahead for an answer cue from a different speaker."""
    for seg in transcript.segments[question_idx + 1: question_idx + 1 + _ANSWER_LOOKAHEAD_WINDOW]:
        if seg.speaker != speaker and _ANSWER_CUES.search(seg.text):
            return "resolved"
    return "open"


def extract_questions(
    transcript: ParsedTranscript,
    paper_state: Optional[PaperState] = None,
) -> List[OpenQuestion]:
    """Return a list of :class:`OpenQuestion` objects extracted from *transcript*.

    Parameters
    ----------
    transcript:
        Parsed meeting transcript.
    paper_state:
        Optional existing working paper for section-reference assignment.
    """
    questions: List[OpenQuestion] = []
    counter = 0
    seen: set[str] = set()

    for idx, seg in enumerate(transcript.segments):
        if not _is_question(seg.text, seg.tags):
            continue
        key = seg.text[:80]
        if key in seen:
            continue
        seen.add(key)

        counter += 1
        questions.append(
            OpenQuestion(
                question_id=f"QST-{counter:03d}",
                text=seg.text,
                raised_by=seg.speaker,
                section_ref=_find_section_ref(seg.text, paper_state),
                resolution_status=_infer_resolution(idx, seg.speaker, transcript),
            )
        )

    return questions
