"""
transcript_parser.py

Parses raw meeting transcripts into structured ParsedTranscript objects.

Supports simple line-based transcripts of the form:

    [Speaker] text ...
    [HH:MM] [Speaker] text ...
    Speaker: text ...

Returns a ParsedTranscript with one TranscriptSegment per detected utterance.
Lines that do not match a speaker pattern are appended to the previous segment.
"""

from __future__ import annotations

import re
from typing import List, Optional

from .schemas import ParsedTranscript, TranscriptSegment

# Patterns for detecting speaker lines.
_BRACKET_TS_SPEAKER = re.compile(
    r"^\[(?P<ts>[0-9]{1,2}:[0-9]{2}(?::[0-9]{2})?)\]\s*\[?(?P<speaker>[^\]]+)\]?\s*[:\-]?\s*(?P<text>.*)$"
)
_BRACKET_SPEAKER = re.compile(r"^\[(?P<speaker>[^\]]+)\]\s*[:\-]?\s*(?P<text>.*)$")
_COLON_SPEAKER = re.compile(r"^(?P<speaker>[A-Za-z][A-Za-z0-9 _\-]{0,40}):\s+(?P<text>.+)$")

# Keywords used to tag segments automatically.
_ACTION_KEYWORDS = {"action", "todo", "follow-up", "follow up", "will", "should"}
_QUESTION_KEYWORDS = {"?", "open question", "question", "unclear", "need to"}
_DECISION_KEYWORDS = {"agreed", "decided", "decision", "resolved", "consensus"}


def _tag_segment(text: str) -> List[str]:
    lower = text.lower()
    tags: List[str] = []
    if any(kw in lower for kw in _ACTION_KEYWORDS):
        tags.append("action")
    if any(kw in lower for kw in _QUESTION_KEYWORDS):
        tags.append("question")
    if any(kw in lower for kw in _DECISION_KEYWORDS):
        tags.append("decision")
    return tags


def _parse_line(line: str) -> Optional[tuple[Optional[str], str, str]]:
    """Return (timestamp, speaker, text) if the line starts a new utterance, else None."""
    m = _BRACKET_TS_SPEAKER.match(line)
    if m:
        return m.group("ts"), m.group("speaker").strip(), m.group("text").strip()
    m = _BRACKET_SPEAKER.match(line)
    if m:
        return None, m.group("speaker").strip(), m.group("text").strip()
    m = _COLON_SPEAKER.match(line)
    if m:
        return None, m.group("speaker").strip(), m.group("text").strip()
    return None


def parse_transcript(raw_text: str, meeting_title: str = "Untitled Meeting") -> ParsedTranscript:
    """Parse *raw_text* into a :class:`ParsedTranscript`.

    Parameters
    ----------
    raw_text:
        The raw text of the meeting transcript.
    meeting_title:
        An optional title override; defaults to ``"Untitled Meeting"``.
    """
    participants: set[str] = set()
    segments: List[TranscriptSegment] = []
    current: Optional[TranscriptSegment] = None

    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        parsed = _parse_line(line)
        if parsed is not None:
            ts, speaker, text = parsed
            if current is not None:
                segments.append(current)
            participants.add(speaker)
            current = TranscriptSegment(
                speaker=speaker,
                timestamp=ts,
                text=text,
                tags=_tag_segment(text),
            )
        else:
            if current is not None:
                current.text = f"{current.text} {line}".strip()
                current.tags = _tag_segment(current.text)
            else:
                # Preamble / header line — no speaker yet; treat as narrator
                current = TranscriptSegment(
                    speaker="(narrator)",
                    timestamp=None,
                    text=line,
                    tags=_tag_segment(line),
                )

    if current is not None:
        segments.append(current)

    return ParsedTranscript(
        meeting_title=meeting_title,
        participants=sorted(participants),
        segments=segments,
        raw_text=raw_text,
    )
