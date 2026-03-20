"""
models.py — typed dataclasses for the Working Paper Engine pipeline.

Design rules:
  - All public types are frozen dataclasses for determinism.
  - Provenance fields (source_artifact_id, source_type, source_locator)
    are present on all observed/interpreted items.
  - Confidence fields are float in [0.0, 1.0] where applicable.
  - Enums drive all controlled-vocabulary fields to prevent drift.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Controlled vocabularies
# ---------------------------------------------------------------------------


class SourceType(str, Enum):
    DOCUMENT = "document"
    TRANSCRIPT = "transcript"
    STUDY_PLAN = "study_plan"
    DERIVED = "derived"


class GapType(str, Enum):
    DATA = "Data"
    METHODOLOGY = "Methodology"
    ASSUMPTION = "Assumption"
    VALIDATION = "Validation"
    COORDINATION = "Coordination"
    MODELING = "Modeling"
    OTHER = "Other"


class GapImpact(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class ValidationCategory(str, Enum):
    TRACEABILITY = "traceability"
    CONSISTENCY = "consistency"
    COMPLETENESS = "completeness"
    SAFETY = "safety"
    RESULTS_READINESS = "results_readiness"


class ValidationSeverity(str, Enum):
    PASS = "pass"
    WARNING = "warning"
    ERROR = "error"


class SectionID(str, Enum):
    S1 = "1"
    S2 = "2"
    S3 = "3"
    S4 = "4"
    S5 = "5"
    S6 = "6"
    S7 = "7"


class ConcernBucket(str, Enum):
    METHODOLOGY = "methodology"
    DATA = "data"
    ASSUMPTIONS = "assumptions"
    CONSTRAINTS = "constraints"
    AGENCY_CONCERNS = "agency_concerns"
    CONTRADICTIONS = "contradictions"
    MISSING_ELEMENTS = "missing_elements"


# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceDocumentExcerpt:
    """A chunk from a source reference document."""
    artifact_id: str
    source_type: SourceType = SourceType.DOCUMENT
    locator: str = ""          # e.g. "page 12" or "section 3.2"
    content: str = ""
    title: str = ""


@dataclass(frozen=True)
class TranscriptExcerpt:
    """A chunk from a meeting transcript."""
    artifact_id: str
    source_type: SourceType = SourceType.TRANSCRIPT
    locator: str = ""
    speaker: str = ""
    content: str = ""


@dataclass(frozen=True)
class StudyPlanExcerpt:
    """A chunk from a study plan or tasking guidance document."""
    artifact_id: str
    source_type: SourceType = SourceType.STUDY_PLAN
    locator: str = ""
    content: str = ""
    objective: str = ""


@dataclass(frozen=True)
class WorkingPaperInputs:
    """Top-level input bundle for a working paper engine run."""
    title: str
    source_documents: List[SourceDocumentExcerpt] = field(default_factory=list)
    transcripts: List[TranscriptExcerpt] = field(default_factory=list)
    study_plan_excerpts: List[StudyPlanExcerpt] = field(default_factory=list)
    # Optional free-text fields for simpler callers
    context_description: str = ""
    band_description: str = ""


# ---------------------------------------------------------------------------
# Observe-stage models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ObservedItem:
    """A single raw item extracted during the OBSERVE stage."""
    item_id: str
    source_artifact_id: str
    source_type: SourceType
    source_locator: str
    text: str
    tag: str = ""              # lightweight semantic tag, e.g. "assumption", "open_issue"
    confidence: float = 1.0


# ---------------------------------------------------------------------------
# Interpret-stage models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InterpretedConcern:
    """A structured concern derived during the INTERPRET stage."""
    concern_id: str
    bucket: ConcernBucket
    description: str
    source_item_ids: List[str] = field(default_factory=list)
    section_refs: List[SectionID] = field(default_factory=list)
    is_gap_candidate: bool = False
    confidence: float = 1.0


# ---------------------------------------------------------------------------
# Synthesize-stage models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SectionDraft:
    """A drafted report section."""
    section_id: SectionID
    title: str
    content: str


# ---------------------------------------------------------------------------
# Output artifact models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FAQItem:
    """A single FAQ item extracted from the working paper."""
    faq_id: str
    section_ref: str
    question: str
    source_refs: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class GapItem:
    """A single gap register entry."""
    gap_id: str
    description: str
    section_ref: str
    gap_type: GapType
    impact: GapImpact
    blocking: bool
    suggested_resolution: str
    source_refs: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class ValidationFinding:
    """A single validation check result."""
    check_id: str
    text: str
    category: ValidationCategory
    severity: ValidationSeverity
    detail: str = ""


@dataclass(frozen=True)
class ResultsReadiness:
    """Status of quantitative results availability."""
    quantitative_results_available: bool
    missing_elements: List[str] = field(default_factory=list)
    readiness_notes: str = ""


@dataclass(frozen=True)
class TraceabilityRequirements:
    """Traceability requirements for the bundle."""
    required_artifacts: List[str] = field(default_factory=list)
    required_mappings: List[str] = field(default_factory=list)
    required_reproducibility_inputs: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class ReportSection:
    """A final report section in the output bundle."""
    section_id: str
    title: str
    content: str


@dataclass(frozen=True)
class Report:
    """The final structured working paper report."""
    title: str
    sections: List[ReportSection] = field(default_factory=list)


@dataclass(frozen=True)
class ValidationResult:
    """Aggregated validation result."""
    passes: List[ValidationFinding] = field(default_factory=list)
    warnings: List[ValidationFinding] = field(default_factory=list)
    errors: List[ValidationFinding] = field(default_factory=list)


@dataclass(frozen=True)
class BundleMetadata:
    """Metadata block for the working paper bundle."""
    engine_version: str
    created_at: str
    input_summary: Dict[str, Any] = field(default_factory=dict)
    provenance_mode: str = "best_effort"


@dataclass(frozen=True)
class WorkingPaperBundle:
    """
    Governed output bundle for a working paper engine run.

    This is the canonical output artifact — all downstream consumers
    should import from this type only.
    """
    artifact_id: str
    source_artifact_ids: List[str]
    report: Report
    faq: List[FAQItem]
    gap_register: List[GapItem]
    validation_checklist: List[ValidationFinding]
    results_readiness: ResultsReadiness
    traceability_requirements: TraceabilityRequirements
    validation: ValidationResult
    metadata: BundleMetadata
