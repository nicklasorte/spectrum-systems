"""
Working Paper Engine — models.py

Typed dataclasses for all internal and output structures.

Each input/intermediate/output object supports provenance fields:
  - source_artifact_id
  - source_type
  - source_locator
  - confidence (where appropriate)

Design principles
-----------------
- All structures are deterministic and inspectable.
- No hidden fields. additionalProperties semantics enforced at JSON Schema layer.
- Enums used wherever the value set is bounded.
- Provenance is first-class, not an afterthought.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class SourceType(str, Enum):
    SOURCE_DOCUMENT = "source_document"
    TRANSCRIPT = "transcript"
    STUDY_PLAN = "study_plan"
    DERIVED = "derived"


class GapType(str, Enum):
    DATA = "Data"
    METHOD = "Method"
    ASSUMPTION = "Assumption"
    CONSTRAINT = "Constraint"
    COORDINATION = "Coordination"
    UNKNOWN = "Unknown"


class ImpactLevel(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class FeasibilityLabel(str, Enum):
    FEASIBLE = "Feasible"
    CONSTRAINED = "Constrained"
    INFEASIBLE = "Infeasible"
    UNKNOWN = "Unknown"


class ValidationCategory(str, Enum):
    TRACEABILITY = "traceability"
    COMPLETENESS = "completeness"
    CONSISTENCY = "consistency"
    SAFETY = "safety"
    READINESS = "readiness"


class ProvenanceMode(str, Enum):
    BEST_EFFORT = "best_effort"
    STRICT = "strict"
    NONE = "none"


# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------


@dataclass
class SourceDocumentExcerpt:
    """A chunk from a source document (e.g., technical report, study reference)."""

    content: str
    artifact_id: str = ""
    source_type: SourceType = SourceType.SOURCE_DOCUMENT
    source_locator: str = ""
    title: str = ""
    document_date: str = ""


@dataclass
class TranscriptExcerpt:
    """A chunk from a meeting transcript."""

    content: str
    artifact_id: str = ""
    source_type: SourceType = SourceType.TRANSCRIPT
    source_locator: str = ""
    speaker: str = ""
    meeting_title: str = ""
    meeting_date: str = ""


@dataclass
class StudyPlanExcerpt:
    """A chunk from a study plan or tasking guidance document."""

    content: str
    artifact_id: str = ""
    source_type: SourceType = SourceType.STUDY_PLAN
    source_locator: str = ""
    study_title: str = ""
    study_date: str = ""


@dataclass
class EngineInputs:
    """Aggregated inputs for the working paper engine pipeline."""

    source_documents: List[SourceDocumentExcerpt] = field(default_factory=list)
    transcripts: List[TranscriptExcerpt] = field(default_factory=list)
    study_plans: List[StudyPlanExcerpt] = field(default_factory=list)
    title_hint: str = ""
    study_id: str = ""


# ---------------------------------------------------------------------------
# OBSERVE stage output models
# ---------------------------------------------------------------------------


@dataclass
class ObservedItem:
    """A raw fact, question, constraint, or assumption extracted in the OBSERVE stage."""

    item_id: str
    content: str
    item_type: str  # "fact" | "question" | "constraint" | "assumption" | "open_issue"
    source_artifact_id: str = ""
    source_type: SourceType = SourceType.DERIVED
    source_locator: str = ""
    confidence: float = 1.0
    tags: List[str] = field(default_factory=list)


@dataclass
class ObserveResult:
    """Output of the OBSERVE stage."""

    items: List[ObservedItem] = field(default_factory=list)


# ---------------------------------------------------------------------------
# INTERPRET stage output models
# ---------------------------------------------------------------------------


@dataclass
class InterpretedConcern:
    """A concern or element mapped to a structural bucket in the INTERPRET stage."""

    concern_id: str
    bucket: str  # "methodology" | "data" | "assumptions" | "constraints" |
    #             "agency_concerns" | "contradictions" | "missing_elements"
    description: str
    section_refs: List[str] = field(default_factory=list)
    source_item_ids: List[str] = field(default_factory=list)
    source_artifact_id: str = ""
    source_type: SourceType = SourceType.DERIVED
    source_locator: str = ""
    confidence: float = 1.0
    is_gap_candidate: bool = False


@dataclass
class InterpretResult:
    """Output of the INTERPRET stage."""

    concerns: List[InterpretedConcern] = field(default_factory=list)


# ---------------------------------------------------------------------------
# SYNTHESIZE stage output models
# ---------------------------------------------------------------------------


@dataclass
class SectionDraft:
    """A drafted section of the working paper."""

    section_id: str  # "1" through "7"
    title: str
    content: str
    source_concern_ids: List[str] = field(default_factory=list)


@dataclass
class FAQItem:
    """An extracted FAQ item."""

    faq_id: str
    section_ref: str
    question: str
    answer: str = ""
    source_refs: List[str] = field(default_factory=list)
    source_artifact_id: str = ""
    source_type: SourceType = SourceType.DERIVED
    source_locator: str = ""
    confidence: float = 1.0


@dataclass
class GapItem:
    """An identified gap."""

    gap_id: str
    description: str
    section_ref: str
    gap_type: GapType = GapType.UNKNOWN
    impact: ImpactLevel = ImpactLevel.MEDIUM
    blocking: bool = False
    suggested_resolution: str = ""
    source_refs: List[str] = field(default_factory=list)
    source_artifact_id: str = ""
    source_type: SourceType = SourceType.DERIVED
    source_locator: str = ""


@dataclass
class SynthesizeResult:
    """Output of the SYNTHESIZE stage."""

    sections: List[SectionDraft] = field(default_factory=list)
    faq_items: List[FAQItem] = field(default_factory=list)
    gap_items: List[GapItem] = field(default_factory=list)
    title: str = ""
    quantitative_results_available: bool = False


# ---------------------------------------------------------------------------
# VALIDATE stage output models
# ---------------------------------------------------------------------------


@dataclass
class ValidationFinding:
    """A single finding from the VALIDATE stage."""

    check_id: str
    text: str
    category: ValidationCategory
    severity: str  # "pass" | "warning" | "error"
    detail: str = ""


@dataclass
class ValidateResult:
    """Output of the VALIDATE stage."""

    findings: List[ValidationFinding] = field(default_factory=list)

    @property
    def passes(self) -> List[str]:
        return [f.text for f in self.findings if f.severity == "pass"]

    @property
    def warnings(self) -> List[str]:
        return [f.text for f in self.findings if f.severity == "warning"]

    @property
    def errors(self) -> List[str]:
        return [f.text for f in self.findings if f.severity == "error"]

    @property
    def has_errors(self) -> bool:
        return any(f.severity == "error" for f in self.findings)


# ---------------------------------------------------------------------------
# Validation checklist items (for the output bundle)
# ---------------------------------------------------------------------------


@dataclass
class ChecklistItem:
    """A validation checklist item for the output bundle."""

    check_id: str
    text: str
    category: ValidationCategory
