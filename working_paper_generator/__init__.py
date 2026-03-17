"""
working_paper_generator

A module that turns meeting transcripts, meeting minutes, and an optional
existing draft working paper into structured working-paper artifacts that help
groups move from discussion to shared written understanding.

Pipeline overview:
  1. transcript_parser   — parse raw transcript into structured segments
  2. paper_state_reader  — read existing draft (if supplied)
  3. meeting_delta_engine — compute what the meeting contributed
  4. argument_builder    — extract arguments and positions
  5. question_engine     — extract open questions
  6. readiness_scorer    — score section readiness
  7. patch_generator     — propose concrete changes
  8. draft_writer        — assemble the final WorkingPaperDraft
"""

from .schemas import (
    Argument,
    MeetingDelta,
    OpenQuestion,
    PaperPatch,
    PaperSection,
    PaperState,
    ParsedTranscript,
    ReadinessReport,
    SectionPatch,
    SectionReadiness,
    TranscriptSegment,
    WorkingPaperDraft,
)

__all__ = [
    "Argument",
    "MeetingDelta",
    "OpenQuestion",
    "PaperPatch",
    "PaperSection",
    "PaperState",
    "ParsedTranscript",
    "ReadinessReport",
    "SectionPatch",
    "SectionReadiness",
    "TranscriptSegment",
    "WorkingPaperDraft",
]
