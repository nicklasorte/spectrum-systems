"""
validate.py — VALIDATE stage of the Working Paper Engine pipeline.

Responsibilities:
  - Check for contradictions across sections.
  - Check that Section 6 does not imply results if none exist.
  - Check that Section 7 does not overstate findings.
  - Check that FAQ, gap register, and report are aligned.
  - Check for forbidden output patterns (invented percentages, etc.).
  - Check for missing required sections.
  - Check results-readiness inconsistency.
  - Check traceability completeness.

Every check emits a ValidationFinding with severity pass/warning/error.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Set

from .models import (
    FAQItem,
    GapItem,
    ReportSection,
    ResultsReadiness,
    TraceabilityRequirements,
    ValidationCategory,
    ValidationFinding,
    ValidationResult,
    ValidationSeverity,
)
from .synthesize import FORBIDDEN_PATTERNS

# ---------------------------------------------------------------------------
# Check IDs
# ---------------------------------------------------------------------------

CHECK_REQUIRED_SECTIONS = "VAL-001"
CHECK_S6_NO_RESULTS_CLAIM = "VAL-002"
CHECK_S7_NO_OVERSTATEMENT = "VAL-003"
CHECK_FAQ_SECTION_ALIGNED = "VAL-004"
CHECK_GAP_REFLECTED_IN_REPORT = "VAL-005"
CHECK_FORBIDDEN_PATTERNS = "VAL-006"
CHECK_TRACEABILITY = "VAL-007"
CHECK_RESULTS_READINESS = "VAL-008"
CHECK_CONTRADICTION_FLAGGED = "VAL-009"

REQUIRED_SECTION_IDS = {"1", "2", "3", "4", "5", "6", "7"}

# Patterns that would imply completed quantitative results
_RESULTS_IMPLICATION_PATTERNS = (
    r"\d+\s*%",                         # percentages
    r"the results show",
    r"results indicate",
    r"our analysis confirms",
    r"we have confirmed",
    r"the study found",
    r"study results",
    r"quantitative results show",
    r"\bproved?\b",
    r"\bverified\b",
)

# Overstatement patterns for Section 7
_OVERSTATEMENT_PATTERNS = (
    r"\bconcludes that\b",
    r"\bproves?\b",
    r"\bdemonstrates? that\b",
    r"\bclearly shows?\b",
    r"\bconfirms? that\b",
    r"\bwe have shown\b",
    r"\bfinal result\b",
    r"\bdefinitively\b",
)


def _make_finding(
    check_id: str,
    text: str,
    category: ValidationCategory,
    severity: ValidationSeverity,
    detail: str = "",
) -> ValidationFinding:
    return ValidationFinding(
        check_id=check_id,
        text=text,
        category=category,
        severity=severity,
        detail=detail,
    )


def _section_content(sections: List[ReportSection], section_id: str) -> Optional[str]:
    for s in sections:
        if s.section_id == section_id:
            return s.content
    return None


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def check_required_sections(sections: List[ReportSection]) -> ValidationFinding:
    present = {s.section_id for s in sections}
    missing = REQUIRED_SECTION_IDS - present
    if missing:
        return _make_finding(
            CHECK_REQUIRED_SECTIONS,
            "Required report sections missing.",
            ValidationCategory.COMPLETENESS,
            ValidationSeverity.ERROR,
            detail=f"Missing section IDs: {sorted(missing)}",
        )
    return _make_finding(
        CHECK_REQUIRED_SECTIONS,
        "All required sections present.",
        ValidationCategory.COMPLETENESS,
        ValidationSeverity.PASS,
    )


def check_s6_no_results_claim(
    sections: List[ReportSection],
    readiness: ResultsReadiness,
) -> ValidationFinding:
    """Section 6 must not claim results when quantitative results are unavailable."""
    content = _section_content(sections, "6") or ""
    lower = content.lower()
    if not readiness.quantitative_results_available:
        violations = [
            p for p in _RESULTS_IMPLICATION_PATTERNS
            if re.search(p, lower)
        ]
        if violations:
            return _make_finding(
                CHECK_S6_NO_RESULTS_CLAIM,
                "Section 6 implies quantitative results that are not available.",
                ValidationCategory.SAFETY,
                ValidationSeverity.ERROR,
                detail=f"Problematic patterns found: {violations}",
            )
    return _make_finding(
        CHECK_S6_NO_RESULTS_CLAIM,
        "Section 6 results-claim check passed.",
        ValidationCategory.SAFETY,
        ValidationSeverity.PASS,
    )


def check_s7_no_overstatement(sections: List[ReportSection]) -> ValidationFinding:
    content = _section_content(sections, "7") or ""
    lower = content.lower()
    violations = [p for p in _OVERSTATEMENT_PATTERNS if re.search(p, lower)]
    if violations:
        return _make_finding(
            CHECK_S7_NO_OVERSTATEMENT,
            "Section 7 contains overstatement language.",
            ValidationCategory.SAFETY,
            ValidationSeverity.WARNING,
            detail=f"Patterns found: {violations}",
        )
    return _make_finding(
        CHECK_S7_NO_OVERSTATEMENT,
        "Section 7 overstatement check passed.",
        ValidationCategory.SAFETY,
        ValidationSeverity.PASS,
    )


def check_faq_section_aligned(
    faq: List[FAQItem],
    sections: List[ReportSection],
) -> ValidationFinding:
    section_ids = {s.section_id for s in sections}
    misaligned = [
        f.faq_id for f in faq if f.section_ref not in section_ids
    ]
    if misaligned:
        return _make_finding(
            CHECK_FAQ_SECTION_ALIGNED,
            "FAQ items reference section IDs not present in the report.",
            ValidationCategory.CONSISTENCY,
            ValidationSeverity.WARNING,
            detail=f"Misaligned FAQ IDs: {misaligned}",
        )
    return _make_finding(
        CHECK_FAQ_SECTION_ALIGNED,
        "All FAQ section references are valid.",
        ValidationCategory.CONSISTENCY,
        ValidationSeverity.PASS,
    )


def check_gap_reflected_in_report(
    gaps: List[GapItem],
    sections: List[ReportSection],
) -> ValidationFinding:
    """Each gap's section_ref should exist in the report."""
    section_ids = {s.section_id for s in sections}
    orphaned = [g.gap_id for g in gaps if g.section_ref not in section_ids]
    if orphaned:
        return _make_finding(
            CHECK_GAP_REFLECTED_IN_REPORT,
            "Gap register items reference sections not present in the report.",
            ValidationCategory.CONSISTENCY,
            ValidationSeverity.WARNING,
            detail=f"Orphaned gap IDs: {orphaned}",
        )
    # Also check that blocking gaps appear in Section 5 or 6 content
    s5 = (_section_content(sections, "5") or "").lower()
    s6 = (_section_content(sections, "6") or "").lower()
    blocking_not_mentioned: List[str] = []
    for gap in gaps:
        if gap.blocking:
            # Verify a keyword from the gap description appears in s5 or s6
            keywords = gap.description.lower().split()[:5]
            mentioned = any(kw in s5 or kw in s6 for kw in keywords if len(kw) > 4)
            if not mentioned:
                blocking_not_mentioned.append(gap.gap_id)
    if blocking_not_mentioned:
        return _make_finding(
            CHECK_GAP_REFLECTED_IN_REPORT,
            "Some blocking gaps may not be reflected in Sections 5/6.",
            ValidationCategory.CONSISTENCY,
            ValidationSeverity.WARNING,
            detail=f"Gap IDs to review: {blocking_not_mentioned}",
        )
    return _make_finding(
        CHECK_GAP_REFLECTED_IN_REPORT,
        "Gap register reflection check passed.",
        ValidationCategory.CONSISTENCY,
        ValidationSeverity.PASS,
    )


def check_forbidden_patterns(sections: List[ReportSection]) -> ValidationFinding:
    """Check all sections for forbidden output patterns."""
    violations: List[str] = []
    for section in sections:
        lower = section.content.lower()
        for pat in FORBIDDEN_PATTERNS:
            if re.search(pat, lower):
                violations.append(f"Section {section.section_id}: pattern '{pat}'")
    if violations:
        return _make_finding(
            CHECK_FORBIDDEN_PATTERNS,
            "Forbidden output patterns detected.",
            ValidationCategory.SAFETY,
            ValidationSeverity.ERROR,
            detail="; ".join(violations[:10]),
        )
    return _make_finding(
        CHECK_FORBIDDEN_PATTERNS,
        "No forbidden output patterns detected.",
        ValidationCategory.SAFETY,
        ValidationSeverity.PASS,
    )


def check_traceability(
    traceability: TraceabilityRequirements,
) -> ValidationFinding:
    missing: List[str] = []
    if not traceability.required_artifacts:
        missing.append("required_artifacts is empty")
    if not traceability.required_mappings:
        missing.append("required_mappings is empty")
    if not traceability.required_reproducibility_inputs:
        missing.append("required_reproducibility_inputs is empty")
    if missing:
        return _make_finding(
            CHECK_TRACEABILITY,
            "Traceability requirements are incomplete.",
            ValidationCategory.TRACEABILITY,
            ValidationSeverity.WARNING,
            detail="; ".join(missing),
        )
    return _make_finding(
        CHECK_TRACEABILITY,
        "Traceability requirements are present.",
        ValidationCategory.TRACEABILITY,
        ValidationSeverity.PASS,
    )


def check_results_readiness(
    sections: List[ReportSection],
    readiness: ResultsReadiness,
) -> ValidationFinding:
    """
    If quantitative_results_available is False, Section 6 must contain
    the 'RESULTS NOT YET AVAILABLE' marker.
    """
    if not readiness.quantitative_results_available:
        s6 = _section_content(sections, "6") or ""
        if "RESULTS NOT YET AVAILABLE" not in s6:
            return _make_finding(
                CHECK_RESULTS_READINESS,
                "Section 6 does not contain the required 'RESULTS NOT YET AVAILABLE' marker.",
                ValidationCategory.RESULTS_READINESS,
                ValidationSeverity.ERROR,
                detail="Add the marker to Section 6 when quantitative_results_available is False.",
            )
    return _make_finding(
        CHECK_RESULTS_READINESS,
        "Results readiness consistency check passed.",
        ValidationCategory.RESULTS_READINESS,
        ValidationSeverity.PASS,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate(
    sections: List[ReportSection],
    faq: List[FAQItem],
    gaps: List[GapItem],
    readiness: ResultsReadiness,
    traceability: TraceabilityRequirements,
) -> ValidationResult:
    """
    VALIDATE stage: run all validation checks and return a ValidationResult.
    """
    findings: List[ValidationFinding] = [
        check_required_sections(sections),
        check_s6_no_results_claim(sections, readiness),
        check_s7_no_overstatement(sections),
        check_faq_section_aligned(faq, sections),
        check_gap_reflected_in_report(gaps, sections),
        check_forbidden_patterns(sections),
        check_traceability(traceability),
        check_results_readiness(sections, readiness),
    ]

    passes = [f for f in findings if f.severity == ValidationSeverity.PASS]
    warnings = [f for f in findings if f.severity == ValidationSeverity.WARNING]
    errors = [f for f in findings if f.severity == ValidationSeverity.ERROR]

    return ValidationResult(passes=passes, warnings=warnings, errors=errors)
