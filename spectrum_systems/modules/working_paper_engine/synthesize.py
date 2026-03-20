"""
synthesize.py — SYNTHESIZE stage of the Working Paper Engine pipeline.

Responsibilities:
  - Generate all seven report sections from interpreted concerns and inputs.
  - Apply synthesis rules for neutral engineering tone.
  - Mark undefined/missing items as [need additional information].
  - Never fabricate quantitative results — if not available, Section 6
    must switch to results-framework / preliminary-observations mode.
  - Generate FAQ items from concerns mapped to sections.
  - Promote gap candidates from interpreted concerns into GapItems.

Synthesis rules (hard-coded for consistency):
  - Frame the problem as system-level and interdependent.
  - Separate feasibility analysis from implementation decisions.
  - Use controlled vocabulary: Feasible/Constrained/Infeasible,
    Candidate assignments, Modeled conditions, Normalized representations.
  - Do not make policy recommendations.
  - Do not pretend validation pathways exist if they do not.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

from .models import (
    ConcernBucket,
    FAQItem,
    GapImpact,
    GapItem,
    GapType,
    InterpretedConcern,
    ReportSection,
    ResultsReadiness,
    SectionDraft,
    SectionID,
    SourceType,
    TraceabilityRequirements,
    WorkingPaperInputs,
)

# ---------------------------------------------------------------------------
# Section metadata
# ---------------------------------------------------------------------------

SECTION_TITLES: Dict[SectionID, str] = {
    SectionID.S1: "Introduction",
    SectionID.S2: "Background and Study Context",
    SectionID.S3: "Methodology",
    SectionID.S4: "Parameters and Assumptions",
    SectionID.S5: "Data and Modeling Framework",
    SectionID.S6: "Results Framework and Observations",
    SectionID.S7: "Conclusions and Path Forward",
}

# Placeholder token for missing content
_NEED_INFO = "[need additional information]"

# Forbidden output patterns — if these appear in final content,
# the validate stage will flag them.
FORBIDDEN_PATTERNS: Tuple[str, ...] = (
    r"\bmost links?\b",
    r"\bmany clusters?\b",
    r"\bthe majority of\b",
    r"\boverwhelmingly\b",
    r"\bclearly shows?\b",
    r"\bproves?\b",
    r"\bdemonstrates? that\b",
    r"\bwe conclude\b",
    r"\bwe can confirm\b",
)

# Controlled vocabulary terms
CV_FEASIBLE = "Feasible"
CV_CONSTRAINED = "Constrained"
CV_INFEASIBLE = "Infeasible"
CV_CANDIDATE = "Candidate assignments"
CV_MODELED = "Modeled conditions"
CV_NORMALIZED = "Normalized representations"


# ---------------------------------------------------------------------------
# Helper builders
# ---------------------------------------------------------------------------


def _filter_concerns(
    concerns: List[InterpretedConcern],
    bucket: ConcernBucket,
) -> List[InterpretedConcern]:
    return [c for c in concerns if c.bucket == bucket]


def _format_bullet_list(items: List[str], prefix: str = "- ") -> str:
    return "\n".join(f"{prefix}{item}" for item in items) if items else _NEED_INFO


def _concern_texts(concerns: List[InterpretedConcern]) -> List[str]:
    return [c.description for c in concerns]


def _has_quantitative_results(concerns: List[InterpretedConcern]) -> bool:
    """
    Determine whether quantitative results are available.

    Results are available only when the DATA bucket contains at least one
    non-gap concern from a real source (not the synthetic 'context' fallback)
    that references a result-type numeric value.  Band designations appearing
    in context_description do not qualify as results.
    """
    data_concerns = _filter_concerns(concerns, ConcernBucket.DATA)
    for c in data_concerns:
        if c.is_gap_candidate:
            continue
        # Exclude concerns whose only source is the synthetic context item
        if c.source_item_ids == [] or all(
            sid.startswith("OBS-CTX") for sid in c.source_item_ids
        ):
            continue
        # Require a result-type numeric value (measurement / modeled output),
        # not just a band or frequency designation.
        if re.search(
            r"\b\d+[\.,]?\d*\s*(dB|dBm|dBi|dBW|I/N|C/N|km|ms|W|MHz|GHz)\b",
            c.description,
        ) and not re.search(
            r"(band|range|frequency|spectrum|MHz\s*band|GHz\s*band)",
            c.description,
            flags=re.IGNORECASE,
        ):
            return True
    return False


# ---------------------------------------------------------------------------
# Per-section generators
# ---------------------------------------------------------------------------


def _gen_section_1(inputs: WorkingPaperInputs) -> str:
    band = inputs.band_description or _NEED_INFO
    context = inputs.context_description or _NEED_INFO
    return (
        f"This working paper presents a preliminary engineering assessment for "
        f"federal spectrum study activities related to {band}. "
        f"The paper is designated DRAFT / PRE-DECISIONAL and does not represent "
        f"final agency positions or policy recommendations.\n\n"
        f"Study context: {context}\n\n"
        f"The analysis frames the problem as system-level and interdependent, "
        f"examining {CV_CANDIDATE}, {CV_MODELED}, and {CV_NORMALIZED} where "
        f"data are available. Gaps and uncertainties are explicitly identified "
        f"throughout. This document supports structured engineering review and "
        f"does not constitute a completed technical study."
    )


def _gen_section_2(
    inputs: WorkingPaperInputs,
    concerns: List[InterpretedConcern],
) -> str:
    agency_texts = _concern_texts(_filter_concerns(concerns, ConcernBucket.AGENCY_CONCERNS))
    context = inputs.context_description or _NEED_INFO
    bullets = _format_bullet_list(agency_texts[:6]) if agency_texts else _NEED_INFO
    return (
        f"Background and study context: {context}\n\n"
        f"Key agency inputs and study drivers include:\n{bullets}\n\n"
        f"The study scope encompasses an assessment of feasibility across the "
        f"relevant band or bands. Feasibility classifications used in this paper "
        f"follow the convention: {CV_FEASIBLE} / {CV_CONSTRAINED} / {CV_INFEASIBLE}."
    )


def _gen_section_3(concerns: List[InterpretedConcern]) -> str:
    method_texts = _concern_texts(_filter_concerns(concerns, ConcernBucket.METHODOLOGY))
    bullets = _format_bullet_list(method_texts[:8]) if method_texts else _NEED_INFO
    return (
        f"The methodology employed in this study is described below. "
        f"All analytical approaches are subject to the assumptions and constraints "
        f"documented in Section 4.\n\n"
        f"Identified methodology elements:\n{bullets}\n\n"
        f"Where methodology details are incomplete or unconfirmed, those elements "
        f"are marked {_NEED_INFO}. The study relies on {CV_MODELED} and does not "
        f"substitute modeled outputs for validated field measurements unless "
        f"explicitly stated."
    )


def _gen_section_4(concerns: List[InterpretedConcern]) -> str:
    assumption_texts = _concern_texts(_filter_concerns(concerns, ConcernBucket.ASSUMPTIONS))
    constraint_texts = _concern_texts(_filter_concerns(concerns, ConcernBucket.CONSTRAINTS))
    asm_bullets = _format_bullet_list(assumption_texts[:10]) if assumption_texts else _NEED_INFO
    con_bullets = _format_bullet_list(constraint_texts[:6]) if constraint_texts else _NEED_INFO
    return (
        f"**Assumptions:**\n{asm_bullets}\n\n"
        f"**Constraints:**\n{con_bullets}\n\n"
        f"All assumptions carry epistemic uncertainty. Parameters listed as "
        f"{_NEED_INFO} require resolution before results can be considered valid."
    )


def _gen_section_5(concerns: List[InterpretedConcern]) -> str:
    data_texts = _concern_texts(
        [c for c in _filter_concerns(concerns, ConcernBucket.DATA) if not c.is_gap_candidate]
    )
    gap_texts = _concern_texts(
        [c for c in _filter_concerns(concerns, ConcernBucket.MISSING_ELEMENTS)]
    )
    data_bullets = _format_bullet_list(data_texts[:8]) if data_texts else _NEED_INFO
    gap_bullets = _format_bullet_list(gap_texts[:6]) if gap_texts else "None identified."
    return (
        f"**Available data and modeling inputs:**\n{data_bullets}\n\n"
        f"**Data gaps and missing modeling elements:**\n{gap_bullets}\n\n"
        f"The modeling framework relies on {CV_NORMALIZED} inputs. "
        f"Any gap marked as blocking must be resolved prior to final results."
    )


def _gen_section_6(
    concerns: List[InterpretedConcern],
    quantitative_available: bool,
) -> str:
    if quantitative_available:
        data_texts = _concern_texts(
            [c for c in _filter_concerns(concerns, ConcernBucket.DATA) if not c.is_gap_candidate]
        )
        bullets = _format_bullet_list(data_texts[:8])
        return (
            f"The following observations are drawn from available modeled data. "
            f"These are preliminary and subject to revision upon full analysis:\n\n"
            f"{bullets}\n\n"
            f"All numeric values reflect {CV_MODELED} and must not be cited as "
            f"validated field results without additional confirmation."
        )
    else:
        gap_texts = _concern_texts(_filter_concerns(concerns, ConcernBucket.MISSING_ELEMENTS))
        gap_bullets = _format_bullet_list(gap_texts[:6]) if gap_texts else _NEED_INFO
        return (
            f"**RESULTS NOT YET AVAILABLE**\n\n"
            f"Quantitative results are not available at this stage of the study. "
            f"This section describes the results framework and preliminary "
            f"observations only. No numeric outcomes should be inferred from "
            f"this section.\n\n"
            f"**Results framework:** The study will evaluate {CV_CANDIDATE} using "
            f"{CV_MODELED} under defined interference scenarios. Feasibility "
            f"classifications ({CV_FEASIBLE} / {CV_CONSTRAINED} / {CV_INFEASIBLE}) "
            f"will be applied once data collection and modeling are complete.\n\n"
            f"**Blocking gaps preventing results:**\n{gap_bullets}"
        )


def _gen_section_7(
    concerns: List[InterpretedConcern],
    quantitative_available: bool,
) -> str:
    contra_texts = _concern_texts(_filter_concerns(concerns, ConcernBucket.CONTRADICTIONS))
    missing_texts = _concern_texts(_filter_concerns(concerns, ConcernBucket.MISSING_ELEMENTS))
    agency_texts = _concern_texts(_filter_concerns(concerns, ConcernBucket.AGENCY_CONCERNS))

    if quantitative_available:
        conclusion_frame = (
            "Based on the preliminary modeled results documented in Section 6, "
            "the path forward involves confirming model validity and addressing "
            "identified gaps."
        )
    else:
        conclusion_frame = (
            "As quantitative results are not yet available, this section "
            "describes the path forward needed to reach results-ready status. "
            "No findings are overstated beyond what is supported by available data."
        )

    contra_bullets = _format_bullet_list(contra_texts[:4]) if contra_texts else "None identified."
    missing_bullets = _format_bullet_list(missing_texts[:6]) if missing_texts else "None identified."
    agency_bullets = _format_bullet_list(agency_texts[:4]) if agency_texts else _NEED_INFO

    return (
        f"{conclusion_frame}\n\n"
        f"**Open contradictions requiring resolution:**\n{contra_bullets}\n\n"
        f"**Missing elements blocking path forward:**\n{missing_bullets}\n\n"
        f"**Agency coordination items:**\n{agency_bullets}\n\n"
        f"This paper does not make policy recommendations. All path-forward "
        f"items require agency review and confirmation before implementation."
    )


# ---------------------------------------------------------------------------
# FAQ generation
# ---------------------------------------------------------------------------


def _generate_faq(
    concerns: List[InterpretedConcern],
) -> List[FAQItem]:
    faq_items: List[FAQItem] = []
    idx = 1
    # Open issues → FAQ questions
    for concern in concerns:
        if concern.bucket == ConcernBucket.MISSING_ELEMENTS and len(concern.description) > 20:
            section = concern.section_refs[0].value if concern.section_refs else "5"
            faq_items.append(
                FAQItem(
                    faq_id=f"FAQ-{idx:03d}",
                    section_ref=section,
                    question=f"What information is needed to resolve: {concern.description[:200]}?",
                    source_refs=concern.source_item_ids,
                )
            )
            idx += 1
        if idx > 20:
            break
    # Contradiction-derived questions
    for concern in concerns:
        if concern.bucket == ConcernBucket.CONTRADICTIONS:
            faq_items.append(
                FAQItem(
                    faq_id=f"FAQ-{idx:03d}",
                    section_ref="6",
                    question=f"How should this contradiction be resolved: {concern.description[:200]}?",
                    source_refs=concern.source_item_ids,
                )
            )
            idx += 1
        if idx > 30:
            break
    return faq_items


# ---------------------------------------------------------------------------
# Gap register generation
# ---------------------------------------------------------------------------


_GAP_TYPE_MAP: Dict[ConcernBucket, GapType] = {
    ConcernBucket.DATA: GapType.DATA,
    ConcernBucket.METHODOLOGY: GapType.METHODOLOGY,
    ConcernBucket.ASSUMPTIONS: GapType.ASSUMPTION,
    ConcernBucket.CONSTRAINTS: GapType.VALIDATION,
    ConcernBucket.MISSING_ELEMENTS: GapType.DATA,
    ConcernBucket.CONTRADICTIONS: GapType.VALIDATION,
    ConcernBucket.AGENCY_CONCERNS: GapType.COORDINATION,
}


def _generate_gaps(concerns: List[InterpretedConcern]) -> List[GapItem]:
    gaps: List[GapItem] = []
    idx = 1
    for concern in concerns:
        if not concern.is_gap_candidate:
            continue
        gap_type = _GAP_TYPE_MAP.get(concern.bucket, GapType.OTHER)
        impact = GapImpact.HIGH if concern.bucket == ConcernBucket.MISSING_ELEMENTS else GapImpact.MEDIUM
        blocking = concern.bucket in (
            ConcernBucket.MISSING_ELEMENTS,
            ConcernBucket.CONTRADICTIONS,
        )
        section_ref = concern.section_refs[0].value if concern.section_refs else "5"
        gaps.append(
            GapItem(
                gap_id=f"GAP-{idx:03d}",
                description=concern.description[:300],
                section_ref=section_ref,
                gap_type=gap_type,
                impact=impact,
                blocking=blocking,
                suggested_resolution=f"Obtain additional information or confirmation for: {concern.description[:100]}",
                source_refs=concern.source_item_ids,
            )
        )
        idx += 1
        if idx > 50:
            break
    return gaps


# ---------------------------------------------------------------------------
# Traceability requirements
# ---------------------------------------------------------------------------


def _generate_traceability(
    inputs: WorkingPaperInputs,
    concerns: List[InterpretedConcern],
) -> TraceabilityRequirements:
    artifacts: List[str] = []
    for doc in inputs.source_documents:
        artifacts.append(f"source_document:{doc.artifact_id}")
    for tx in inputs.transcripts:
        artifacts.append(f"transcript:{tx.artifact_id}")
    for sp in inputs.study_plan_excerpts:
        artifacts.append(f"study_plan:{sp.artifact_id}")

    mappings = [
        "All quantitative claims must reference source_artifact_id",
        "All gap items must reference at least one observed item",
        "All FAQ items must reference at least one report section",
    ]

    reproducibility = [
        "Input JSON bundle must be versioned and stored",
        "Engine version must be recorded in bundle metadata",
        "All synthesis rules must be deterministic given the same inputs",
    ]

    return TraceabilityRequirements(
        required_artifacts=artifacts,
        required_mappings=mappings,
        required_reproducibility_inputs=reproducibility,
    )


# ---------------------------------------------------------------------------
# Results readiness
# ---------------------------------------------------------------------------


def _assess_readiness(
    concerns: List[InterpretedConcern],
    quantitative_available: bool,
) -> ResultsReadiness:
    blocking_gaps = [
        c.description[:100]
        for c in concerns
        if c.is_gap_candidate and c.bucket == ConcernBucket.MISSING_ELEMENTS
    ]
    if quantitative_available:
        notes = "Preliminary quantitative results are available but require validation."
    else:
        notes = (
            "Study is not results-ready. Quantitative results cannot be reported "
            "until blocking gaps are resolved."
        )
    return ResultsReadiness(
        quantitative_results_available=quantitative_available,
        missing_elements=blocking_gaps[:10],
        readiness_notes=notes,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def synthesize(
    inputs: WorkingPaperInputs,
    concerns: List[InterpretedConcern],
) -> Tuple[
    List[ReportSection],
    List[FAQItem],
    List[GapItem],
    ResultsReadiness,
    TraceabilityRequirements,
]:
    """
    SYNTHESIZE stage: generate all report sections, FAQ, gap register,
    results readiness, and traceability requirements.

    Returns a 5-tuple of (sections, faq, gaps, readiness, traceability).
    """
    quantitative_available = _has_quantitative_results(concerns)

    drafts: Dict[SectionID, str] = {
        SectionID.S1: _gen_section_1(inputs),
        SectionID.S2: _gen_section_2(inputs, concerns),
        SectionID.S3: _gen_section_3(concerns),
        SectionID.S4: _gen_section_4(concerns),
        SectionID.S5: _gen_section_5(concerns),
        SectionID.S6: _gen_section_6(concerns, quantitative_available),
        SectionID.S7: _gen_section_7(concerns, quantitative_available),
    }

    sections = [
        ReportSection(
            section_id=sid.value,
            title=SECTION_TITLES[sid],
            content=content,
        )
        for sid, content in drafts.items()
    ]

    faq = _generate_faq(concerns)
    gaps = _generate_gaps(concerns)
    readiness = _assess_readiness(concerns, quantitative_available)
    traceability = _generate_traceability(inputs, concerns)

    return sections, faq, gaps, readiness, traceability
