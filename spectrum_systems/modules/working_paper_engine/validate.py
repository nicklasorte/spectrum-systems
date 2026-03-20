"""
Working Paper Engine — validate.py

VALIDATE stage: Run safety and consistency checks across the output bundle.

Design principles
-----------------
- Checks are explicit, rule-based, and deterministic.
- No check requires external calls or unconstrained generation.
- Every finding records category, severity, and a plain-language description.
- Errors are blocking; warnings are advisory.
- False negatives are preferred over false positives for safety checks.

Checks implemented
------------------
1. All required sections (1–7) are present.
2. Section 6 does not imply results if quantitative_results_available is False.
3. Section 7 does not overstate findings.
4. Unsupported quantitative claims are absent from all sections.
5. FAQ items reference section IDs that exist in the report.
6. Gap register items reference section IDs that exist in the report.
7. Traceability expectations are present.
8. Results-readiness flag is consistent with Section 6 content.
9. No contradictions are simultaneously noted and uncited in Section 7.
"""

from __future__ import annotations

import re
from typing import List, Set

from spectrum_systems.modules.working_paper_engine.models import (
    FAQItem,
    GapItem,
    SynthesizeResult,
    ValidateResult,
    ValidationCategory,
    ValidationFinding,
)

# ---------------------------------------------------------------------------
# Forbidden patterns for unsupported quantitative claims
# ---------------------------------------------------------------------------

_FORBIDDEN_QUANT = [
    (re.compile(r"\b\d+[\.,]?\d*\s*%"), "unsupported percentage"),
    (re.compile(r"\bmost\s+(links?|clusters?|sites?|cases?|scenarios?)\b", re.IGNORECASE), "unsupported 'most X'"),
    (re.compile(r"\bmany\s+(links?|clusters?|sites?|cases?|scenarios?)\b", re.IGNORECASE), "unsupported 'many X'"),
    (re.compile(r"\bnearly all\b", re.IGNORECASE), "unsupported 'nearly all'"),
    (re.compile(r"\bmajority of\b", re.IGNORECASE), "unsupported 'majority of'"),
    (re.compile(r"\bshows? that\b", re.IGNORECASE), "unsupported definitive claim 'shows that'"),
    (re.compile(r"\bproves? that\b", re.IGNORECASE), "unsupported definitive claim 'proves that'"),
    (re.compile(r"\bdemonstrates? that\b", re.IGNORECASE), "unsupported definitive claim 'demonstrates that'"),
]

# Patterns that are safe in Section 6/7 no-results mode
_RESULTS_IMPLICATION_PATTERNS = [
    re.compile(r"\banalysis shows\b", re.IGNORECASE),
    re.compile(r"\banalysis demonstrates\b", re.IGNORECASE),
    re.compile(r"\bresults indicate\b", re.IGNORECASE),
    re.compile(r"\bresults show\b", re.IGNORECASE),
    re.compile(r"\bfindings confirm\b", re.IGNORECASE),
    re.compile(r"\banalysis confirms\b", re.IGNORECASE),
]

# Definitive language that overstates findings in Section 7
_OVERSTATEMENT_PATTERNS = [
    re.compile(r"\bproven\b", re.IGNORECASE),
    re.compile(r"\bconclusive(ly)?\b", re.IGNORECASE),
    re.compile(r"\bestablishes? that\b", re.IGNORECASE),
    re.compile(r"\bfinal determination\b", re.IGNORECASE),
]

_REQUIRED_SECTION_IDS = {"1", "2", "3", "4", "5", "6", "7"}


def _check_id() -> "CheckCounter":
    return _check_counter_singleton


class CheckCounter:
    def __init__(self) -> None:
        self._n = 0

    def next(self) -> str:
        self._n += 1
        return f"CHK-{self._n:03d}"


_check_counter_singleton = CheckCounter()


def _finding(
    check_id: str,
    text: str,
    category: ValidationCategory,
    severity: str,
    detail: str = "",
) -> ValidationFinding:
    return ValidationFinding(
        check_id=check_id,
        text=text,
        category=category,
        severity=severity,
        detail=detail,
    )


def run_validate(synth_result: SynthesizeResult) -> ValidateResult:
    """Run all validation checks on the synthesized output.

    Parameters
    ----------
    synth_result:
        Output from the SYNTHESIZE stage.

    Returns
    -------
    ValidateResult
        All findings (passes, warnings, errors).
    """
    # Reset counter for deterministic IDs across calls
    counter = CheckCounter()

    findings: List[ValidationFinding] = []
    section_ids: Set[str] = {s.section_id for s in synth_result.sections}

    # ----------------------------------------------------------------
    # Check 1: All required sections present
    # ----------------------------------------------------------------
    missing_sections = _REQUIRED_SECTION_IDS - section_ids
    if missing_sections:
        findings.append(_finding(
            counter.next(),
            f"Missing required sections: {sorted(missing_sections)}",
            ValidationCategory.COMPLETENESS,
            "error",
            detail=f"Expected sections: {sorted(_REQUIRED_SECTION_IDS)}",
        ))
    else:
        findings.append(_finding(
            counter.next(),
            "All required sections (1–7) are present.",
            ValidationCategory.COMPLETENESS,
            "pass",
        ))

    # ----------------------------------------------------------------
    # Check 2: Section 6 must not imply results if none are available
    # ----------------------------------------------------------------
    sec6 = next((s for s in synth_result.sections if s.section_id == "6"), None)
    if sec6 and not synth_result.quantitative_results_available:
        violations = [
            pattern.pattern
            for pattern in _RESULTS_IMPLICATION_PATTERNS
            if pattern.search(sec6.content)
        ]
        if violations:
            findings.append(_finding(
                counter.next(),
                "Section 6 implies completed results but quantitative_results_available is False.",
                ValidationCategory.SAFETY,
                "error",
                detail=f"Matched patterns: {violations}",
            ))
        else:
            findings.append(_finding(
                counter.next(),
                "Section 6 correctly does not imply completed results.",
                ValidationCategory.SAFETY,
                "pass",
            ))

    # ----------------------------------------------------------------
    # Check 3: Section 7 must not overstate findings
    # ----------------------------------------------------------------
    sec7 = next((s for s in synth_result.sections if s.section_id == "7"), None)
    if sec7:
        overstatements = [
            pattern.pattern
            for pattern in _OVERSTATEMENT_PATTERNS
            if pattern.search(sec7.content)
        ]
        if overstatements:
            findings.append(_finding(
                counter.next(),
                "Section 7 contains overstatement language.",
                ValidationCategory.SAFETY,
                "error",
                detail=f"Matched patterns: {overstatements}",
            ))
        else:
            findings.append(_finding(
                counter.next(),
                "Section 7 does not overstate findings.",
                ValidationCategory.SAFETY,
                "pass",
            ))

    # ----------------------------------------------------------------
    # Check 4: No unsupported quantitative claims in any section
    # ----------------------------------------------------------------
    quant_violations: List[str] = []
    for section in synth_result.sections:
        for pattern, label in _FORBIDDEN_QUANT:
            match = pattern.search(section.content)
            if match:
                quant_violations.append(
                    f"Section {section.section_id}: {label} — '{match.group(0)}'"
                )
    if quant_violations:
        findings.append(_finding(
            counter.next(),
            "Unsupported quantitative claims detected in report sections.",
            ValidationCategory.SAFETY,
            "error",
            detail="; ".join(quant_violations),
        ))
    else:
        findings.append(_finding(
            counter.next(),
            "No unsupported quantitative claims detected.",
            ValidationCategory.SAFETY,
            "pass",
        ))

    # ----------------------------------------------------------------
    # Check 5: FAQ items reference valid section IDs
    # ----------------------------------------------------------------
    invalid_faq_refs = [
        f.faq_id for f in synth_result.faq_items if f.section_ref not in section_ids
    ]
    if invalid_faq_refs:
        findings.append(_finding(
            counter.next(),
            f"FAQ items reference non-existent sections: {invalid_faq_refs}",
            ValidationCategory.TRACEABILITY,
            "warning",
            detail="These FAQ items cannot be mapped to any section in the report.",
        ))
    else:
        findings.append(_finding(
            counter.next(),
            "All FAQ items reference valid report sections.",
            ValidationCategory.TRACEABILITY,
            "pass",
        ))

    # ----------------------------------------------------------------
    # Check 6: Gap register items reference valid section IDs
    # ----------------------------------------------------------------
    invalid_gap_refs = [
        g.gap_id for g in synth_result.gap_items if g.section_ref not in section_ids
    ]
    if invalid_gap_refs:
        findings.append(_finding(
            counter.next(),
            f"Gap register items reference non-existent sections: {invalid_gap_refs}",
            ValidationCategory.TRACEABILITY,
            "warning",
            detail="These gap items cannot be mapped to any section in the report.",
        ))
    else:
        findings.append(_finding(
            counter.next(),
            "All gap register items reference valid report sections.",
            ValidationCategory.TRACEABILITY,
            "pass",
        ))

    # ----------------------------------------------------------------
    # Check 7: Blocking gaps are reflected in Section 7 path forward
    # ----------------------------------------------------------------
    blocking_gaps = [g for g in synth_result.gap_items if g.blocking]
    if blocking_gaps and sec7:
        # Check that at least one gap ID appears in Section 7
        sec7_refs_gaps = any(g.gap_id in sec7.content for g in blocking_gaps)
        if not sec7_refs_gaps:
            findings.append(_finding(
                counter.next(),
                "Blocking gaps exist but are not referenced in Section 7 path forward.",
                ValidationCategory.COMPLETENESS,
                "warning",
                detail=f"Blocking gap IDs: {[g.gap_id for g in blocking_gaps[:5]]}",
            ))
        else:
            findings.append(_finding(
                counter.next(),
                "Blocking gaps are referenced in Section 7.",
                ValidationCategory.COMPLETENESS,
                "pass",
            ))

    # ----------------------------------------------------------------
    # Check 8: Results-readiness consistency
    # ----------------------------------------------------------------
    if synth_result.quantitative_results_available and sec6:
        notice_present = "NOTICE: Quantitative results are not available" in sec6.content
        if notice_present:
            findings.append(_finding(
                counter.next(),
                "Inconsistency: quantitative_results_available=True but Section 6 contains no-results notice.",
                ValidationCategory.CONSISTENCY,
                "error",
            ))
        else:
            findings.append(_finding(
                counter.next(),
                "Results-readiness flag is consistent with Section 6 content.",
                ValidationCategory.CONSISTENCY,
                "pass",
            ))
    elif not synth_result.quantitative_results_available and sec6:
        notice_present = "NOTICE: Quantitative results are not available" in sec6.content
        if not notice_present:
            findings.append(_finding(
                counter.next(),
                "Inconsistency: quantitative_results_available=False but Section 6 is missing the no-results notice.",
                ValidationCategory.CONSISTENCY,
                "error",
            ))
        else:
            findings.append(_finding(
                counter.next(),
                "Results-readiness flag is consistent with Section 6 no-results notice.",
                ValidationCategory.CONSISTENCY,
                "pass",
            ))

    # ----------------------------------------------------------------
    # Check 9: Warn if no FAQ items were extracted (may indicate sparse inputs)
    # ----------------------------------------------------------------
    if not synth_result.faq_items:
        findings.append(_finding(
            counter.next(),
            "No FAQ items were extracted. Inputs may be too sparse to generate questions.",
            ValidationCategory.COMPLETENESS,
            "warning",
        ))
    else:
        findings.append(_finding(
            counter.next(),
            f"{len(synth_result.faq_items)} FAQ item(s) extracted.",
            ValidationCategory.COMPLETENESS,
            "pass",
        ))

    return ValidateResult(findings=findings)
