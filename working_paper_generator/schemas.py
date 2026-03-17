"""
schemas.py

Data models (dataclasses) used throughout the working_paper_generator pipeline.
These types are the internal canonical representations; no shared-truth structures
are redefined here — ArtifactEnvelope and provenance fields are referenced by name
only and must be imported from the shared layer in production.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


# ---------------------------------------------------------------------------
# Transcript
# ---------------------------------------------------------------------------


@dataclass
class TranscriptSegment:
    """A single utterance or timestamped block within a meeting transcript."""

    speaker: str
    timestamp: Optional[str]
    text: str
    tags: List[str] = field(default_factory=list)


@dataclass
class ParsedTranscript:
    """The full structured result of parsing a raw meeting transcript."""

    meeting_title: str
    participants: List[str]
    segments: List[TranscriptSegment]
    raw_text: str


# ---------------------------------------------------------------------------
# Paper state
# ---------------------------------------------------------------------------


@dataclass
class PaperSection:
    """A single section of a working paper."""

    section_id: str
    title: str
    content: str
    status: str  # e.g. "draft", "reviewed", "final"
    open_issues: List[str] = field(default_factory=list)


@dataclass
class PaperState:
    """Current state of a working paper, read from an existing draft."""

    paper_id: str
    title: str
    version: str
    sections: List[PaperSection]
    source_path: Optional[str] = None


# ---------------------------------------------------------------------------
# Meeting delta
# ---------------------------------------------------------------------------


@dataclass
class MeetingDelta:
    """Delta between meeting discussion and the existing working paper state."""

    new_topics: List[str]
    updated_sections: List[str]  # section_ids affected by meeting discussion
    unresolved_items: List[str]
    consensus_items: List[str]


# ---------------------------------------------------------------------------
# Arguments
# ---------------------------------------------------------------------------


@dataclass
class Argument:
    """A structured argument or position extracted from meeting discussion."""

    argument_id: str
    claim: str
    evidence: List[str]
    speaker: Optional[str]
    section_ref: Optional[str]  # section_id this argument relates to
    stance: str  # e.g. "supporting", "opposing", "neutral"


# ---------------------------------------------------------------------------
# Questions
# ---------------------------------------------------------------------------


@dataclass
class OpenQuestion:
    """An open question identified during meeting discussion."""

    question_id: str
    text: str
    raised_by: Optional[str]
    section_ref: Optional[str]
    resolution_status: str  # e.g. "open", "deferred", "resolved"


# ---------------------------------------------------------------------------
# Readiness scoring
# ---------------------------------------------------------------------------


@dataclass
class SectionReadiness:
    """Readiness score and rationale for a single paper section."""

    section_id: str
    score: float  # 0.0 – 1.0
    rationale: str
    blocking_questions: List[str]


@dataclass
class ReadinessReport:
    """Aggregate readiness report across all sections."""

    overall_score: float
    sections: List[SectionReadiness]
    ready_to_draft: bool


# ---------------------------------------------------------------------------
# Patch
# ---------------------------------------------------------------------------


@dataclass
class SectionPatch:
    """A proposed change to a single section of the working paper."""

    section_id: str
    operation: str  # "add", "update", "delete"
    new_content: Optional[str]
    rationale: str


@dataclass
class PaperPatch:
    """A set of patches to apply to the existing working paper."""

    source_meeting: str
    patches: List[SectionPatch]


# ---------------------------------------------------------------------------
# Draft output
# ---------------------------------------------------------------------------


@dataclass
class WorkingPaperDraft:
    """The assembled working paper draft produced by the pipeline."""

    paper_id: str
    title: str
    version: str
    sections: List[PaperSection]
    open_questions: List[OpenQuestion]
    arguments: List[Argument]
    readiness: ReadinessReport
    patch_applied: bool
    source_transcript: Optional[str] = None
    source_minutes: Optional[str] = None
