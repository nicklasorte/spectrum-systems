"""
Working Paper Engine — synthesize.py

SYNTHESIZE stage: Generate Sections 1–7 of the working paper, FAQ items,
and gap register from interpreted concerns.

Design principles
-----------------
- Template-driven, deterministic assembly. No unconstrained free-form generation.
- Neutral engineering tone throughout.
- Gaps are marked explicitly as [need additional information].
- Section 6 switches to results-framework mode if quantitative results are absent.
- Section 7 does not overstate findings.
- Transcript concerns are integrated into narrative naturally.
- No policy recommendations are made.
- Synthesis rules are centrally defined and explicitly enforced.

Synthesis vocabulary rules (applied consistently)
--------------------------------------------------
- Feasibility labels: "Feasible / Constrained / Infeasible"
- "Candidate assignments" for frequency proposals
- "Modeled conditions" for simulation scenarios
- "Normalized representations" for derived input data
- Undefined items marked: [need additional information]
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from spectrum_systems.modules.working_paper_engine.models import (
    EngineInputs,
    FAQItem,
    GapItem,
    InterpretResult,
    InterpretedConcern,
    SectionDraft,
    SourceType,
    SynthesizeResult,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ENGINE_UNKNOWN = "[need additional information]"

# Standard section titles as specified in the problem statement
SECTION_TITLES: Dict[str, str] = {
    "1": "Introduction",
    "2": "Background and Study Context",
    "3": "Methodology",
    "4": "Parameters and Assumptions",
    "5": "Data and Modeling Framework",
    "6": "Results Framework and Observations",
    "7": "Conclusions and Path Forward",
}

# Forbidden fabrication patterns — content containing these is flagged in validate
FORBIDDEN_QUANTITATIVE_PATTERNS = [
    re.compile(r"\b\d+[\.,]?\d*\s*%"),  # percentages
    re.compile(r"\bmost\s+(links?|clusters?|sites?|cases?|scenarios?)\b", re.IGNORECASE),
    re.compile(r"\bmany\s+(links?|clusters?|sites?|cases?|scenarios?)\b", re.IGNORECASE),
    re.compile(r"\bnearly all\b", re.IGNORECASE),
    re.compile(r"\bmajority of\b", re.IGNORECASE),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _collect_by_section(
    concerns: List[InterpretedConcern], section_id: str
) -> List[InterpretedConcern]:
    return [c for c in concerns if section_id in c.section_refs]


def _collect_by_bucket(
    concerns: List[InterpretedConcern], bucket: str
) -> List[InterpretedConcern]:
    return [c for c in concerns if c.bucket == bucket]


def _bullet_list(items: List[str], indent: int = 0) -> str:
    prefix = " " * indent
    return "\n".join(f"{prefix}- {item}" for item in items) if items else ""


def _gap_inline_marker(gap_items: List[GapItem], section_ref: str) -> str:
    """Return a concise inline list of gaps for a section, marked as needed."""
    section_gaps = [g for g in gap_items if g.section_ref == section_ref]
    if not section_gaps:
        return ""
    lines = [f"  - {g.gap_id}: {g.description} [{ENGINE_UNKNOWN}]" for g in section_gaps]
    return "\nIdentified gaps requiring resolution:\n" + "\n".join(lines)


def _format_concerns(concerns: List[InterpretedConcern]) -> str:
    if not concerns:
        return ""
    return "\n".join(f"- {c.description}" for c in concerns[:10])


# ---------------------------------------------------------------------------
# Section generators
# ---------------------------------------------------------------------------


def _gen_section_1(
    inputs: EngineInputs,
    concerns: List[InterpretedConcern],
    gap_items: List[GapItem],
) -> SectionDraft:
    """Introduction."""
    title_hint = inputs.title_hint or "Federal Spectrum Study"
    study_id = inputs.study_id or ENGINE_UNKNOWN
    n_sources = len(inputs.source_documents)
    n_transcripts = len(inputs.transcripts)
    n_plans = len(inputs.study_plans)

    content = (
        f"This working paper presents an engineering assessment supporting the {title_hint} "
        f"(Study ID: {study_id}). The paper is designated DRAFT / PRE-DECISIONAL and is "
        f"intended for internal technical review only.\n\n"
        f"The assessment draws on {n_sources} source document(s), {n_transcripts} meeting "
        f"transcript(s), and {n_plans} study plan(s) provided as inputs. The purpose of this "
        f"paper is to support structured analysis, surface known uncertainties, and identify "
        f"information gaps that must be resolved before a final determination can be made.\n\n"
        f"This paper frames the problem as a system-level interdependent engineering challenge. "
        f"Feasibility analysis is explicitly separated from implementation decisions. The paper "
        f"does not make policy recommendations."
    )
    concern_ids = [c.concern_id for c in concerns if "1" in c.section_refs]
    return SectionDraft(section_id="1", title=SECTION_TITLES["1"], content=content, source_concern_ids=concern_ids)


def _gen_section_2(
    inputs: EngineInputs,
    concerns: List[InterpretedConcern],
    gap_items: List[GapItem],
) -> SectionDraft:
    """Background and Study Context."""
    agency_concerns = _collect_by_bucket(concerns, "agency_concerns")
    context_items = _collect_by_section(concerns, "2")

    context_text = _format_concerns(context_items)
    agency_text = _format_concerns(agency_concerns)

    content = (
        "This section summarizes the study context, applicable regulatory background, "
        "and known agency concerns relevant to the analysis.\n\n"
        "**Study Context**\n"
    )
    if context_text:
        content += context_text + "\n\n"
    else:
        content += f"Study context: {ENGINE_UNKNOWN}\n\n"

    content += "**Agency Concerns and Coordination Issues**\n"
    if agency_text:
        content += agency_text + "\n\n"
    else:
        content += f"No agency concerns were identified in the provided inputs. {ENGINE_UNKNOWN}\n\n"

    content += (
        "All background claims are traceable to the provided source artifacts. "
        "Unverified or unsupported context has been marked accordingly."
    )
    gap_notes = _gap_inline_marker(gap_items, "2")
    if gap_notes:
        content += "\n" + gap_notes

    concern_ids = [c.concern_id for c in context_items + agency_concerns]
    return SectionDraft(section_id="2", title=SECTION_TITLES["2"], content=content, source_concern_ids=concern_ids)


def _gen_section_3(
    inputs: EngineInputs,
    concerns: List[InterpretedConcern],
    gap_items: List[GapItem],
) -> SectionDraft:
    """Methodology."""
    method_concerns = _collect_by_bucket(concerns, "methodology")
    method_text = _format_concerns(method_concerns)

    content = (
        "This section describes the analytical methodology applied to the study. "
        "Methods are characterized using the labels Feasible, Constrained, or Infeasible "
        "to describe the operational status of candidate assignments under modeled conditions.\n\n"
        "**Analytical Framework**\n"
    )
    if method_text:
        content += method_text + "\n\n"
    else:
        content += f"Methodology: {ENGINE_UNKNOWN}\n\n"

    content += (
        "**Modeling Approach**\n"
        "Normalized representations of input data are used throughout. "
        "Modeled conditions are drawn from the provided source documents and study plans. "
        "Where modeling inputs are absent, the relevant parameters are marked as "
        f"{ENGINE_UNKNOWN}.\n\n"
        "**Limitations**\n"
        "This methodology section reflects only the inputs provided. "
        "No claims are made about analytical completeness beyond what is supported by the evidence."
    )
    gap_notes = _gap_inline_marker(gap_items, "3")
    if gap_notes:
        content += "\n" + gap_notes

    concern_ids = [c.concern_id for c in method_concerns]
    return SectionDraft(section_id="3", title=SECTION_TITLES["3"], content=content, source_concern_ids=concern_ids)


def _gen_section_4(
    inputs: EngineInputs,
    concerns: List[InterpretedConcern],
    gap_items: List[GapItem],
) -> SectionDraft:
    """Parameters and Assumptions."""
    assumption_concerns = _collect_by_bucket(concerns, "assumptions")
    constraint_concerns = _collect_by_bucket(concerns, "constraints")

    assump_text = _format_concerns(assumption_concerns)
    constraint_text = _format_concerns(constraint_concerns)

    content = (
        "This section documents the parameters, assumptions, and constraints used in the analysis. "
        "All assumptions are explicitly stated and traceable to source inputs. "
        "Assumed values not derivable from the provided inputs are marked as "
        f"{ENGINE_UNKNOWN}.\n\n"
        "**Working Assumptions**\n"
    )
    if assump_text:
        content += assump_text + "\n\n"
    else:
        content += f"No explicit assumptions identified. {ENGINE_UNKNOWN}\n\n"

    content += "**Constraints and Protection Criteria**\n"
    if constraint_text:
        content += constraint_text + "\n\n"
    else:
        content += f"No explicit constraints identified. {ENGINE_UNKNOWN}\n\n"

    content += (
        "These assumptions and constraints are subject to agency review and may require "
        "revision as additional information becomes available."
    )
    gap_notes = _gap_inline_marker(gap_items, "4")
    if gap_notes:
        content += "\n" + gap_notes

    concern_ids = [c.concern_id for c in assumption_concerns + constraint_concerns]
    return SectionDraft(section_id="4", title=SECTION_TITLES["4"], content=content, source_concern_ids=concern_ids)


def _gen_section_5(
    inputs: EngineInputs,
    concerns: List[InterpretedConcern],
    gap_items: List[GapItem],
) -> SectionDraft:
    """Data and Modeling Framework."""
    data_concerns = _collect_by_bucket(concerns, "data")
    missing_concerns = _collect_by_bucket(concerns, "missing_elements")

    data_text = _format_concerns(data_concerns)
    missing_text = _format_concerns(missing_concerns)

    content = (
        "This section describes the data sources, modeling framework, and known data gaps. "
        "Data is characterized as either available, partially available, or unavailable. "
        "Unavailable data is marked as "
        f"{ENGINE_UNKNOWN} and logged in the gap register.\n\n"
        "**Available Data and Modeling Inputs**\n"
    )
    if data_text:
        content += data_text + "\n\n"
    else:
        content += f"Data and modeling inputs: {ENGINE_UNKNOWN}\n\n"

    content += "**Missing or Incomplete Data**\n"
    if missing_text:
        content += missing_text + "\n\n"
    else:
        content += "No missing data elements explicitly identified.\n\n"

    content += (
        "Normalized representations of available data are used as inputs. "
        "Data provenance is maintained through source artifact references."
    )
    gap_notes = _gap_inline_marker(gap_items, "5")
    if gap_notes:
        content += "\n" + gap_notes

    concern_ids = [c.concern_id for c in data_concerns + missing_concerns]
    return SectionDraft(section_id="5", title=SECTION_TITLES["5"], content=content, source_concern_ids=concern_ids)


def _gen_section_6(
    inputs: EngineInputs,
    concerns: List[InterpretedConcern],
    gap_items: List[GapItem],
    quantitative_results_available: bool,
) -> SectionDraft:
    """Results Framework and Observations.

    If quantitative results are not available, this section switches to
    results-framework / preliminary-observations mode and does NOT imply
    completed results.
    """
    agency_concerns = _collect_by_bucket(concerns, "agency_concerns")
    contradiction_concerns = _collect_by_bucket(concerns, "contradictions")

    concern_ids: List[str] = []

    if not quantitative_results_available:
        content = (
            "**NOTICE: Quantitative results are not available for this study at this stage.**\n\n"
            "This section presents the results framework and preliminary observations only. "
            "No quantitative results, percentages, link counts, or cluster statistics are "
            "reported or implied. Any such claims appearing in source materials have not been "
            "verified and are not reproduced here.\n\n"
            "**Results Framework**\n"
            "When results become available, they will be organized using the following structure:\n"
            "- Feasibility assessment per candidate assignment (Feasible / Constrained / Infeasible)\n"
            "- Interference margin analysis under modeled conditions\n"
            "- Sensitivity analysis across normalized representations of key parameters\n"
            "- Comparison of scenario outcomes\n\n"
            "**Preliminary Observations**\n"
        )
        # Include agency concerns and contradictions as preliminary observations
        obs_concerns = agency_concerns + contradiction_concerns
        obs_text = _format_concerns(obs_concerns)
        if obs_text:
            content += obs_text + "\n\n"
        else:
            content += f"Preliminary observations: {ENGINE_UNKNOWN}\n\n"
        concern_ids = [c.concern_id for c in obs_concerns]
    else:
        content = (
            "This section presents the study results organized by the results framework "
            "defined in Section 3.\n\n"
            "**Feasibility Assessment**\n"
            "Results are characterized as Feasible, Constrained, or Infeasible for each "
            "candidate assignment under modeled conditions.\n\n"
            "**Observations**\n"
        )
        obs_concerns = _collect_by_section(concerns, "6")
        obs_text = _format_concerns(obs_concerns)
        if obs_text:
            content += obs_text + "\n\n"
        else:
            content += f"Observations: {ENGINE_UNKNOWN}\n\n"
        concern_ids = [c.concern_id for c in obs_concerns]

    gap_notes = _gap_inline_marker(gap_items, "6")
    if gap_notes:
        content += "\n" + gap_notes

    return SectionDraft(section_id="6", title=SECTION_TITLES["6"], content=content, source_concern_ids=concern_ids)


def _gen_section_7(
    inputs: EngineInputs,
    concerns: List[InterpretedConcern],
    gap_items: List[GapItem],
    quantitative_results_available: bool,
) -> SectionDraft:
    """Conclusions and Path Forward.

    Section 7 does not overstate findings. If results are not available,
    conclusions are limited to process and next steps.
    """
    contradictions = _collect_by_bucket(concerns, "contradictions")

    content = "This section summarizes conclusions and identifies the path forward.\n\n"

    if not quantitative_results_available:
        content += (
            "**Conclusions**\n"
            "The study is currently in a pre-results stage. No technical conclusions "
            "can be drawn from the available information. The following gaps must be "
            "resolved before conclusions can be made:\n\n"
        )
        high_impact_gaps = [g for g in gap_items if g.impact == "High" or g.blocking]
        if high_impact_gaps:
            for g in high_impact_gaps[:5]:
                content += f"- {g.gap_id}: {g.description}\n"
        else:
            content += f"- {ENGINE_UNKNOWN}\n"
        content += "\n"
    else:
        content += (
            "**Conclusions**\n"
            "Conclusions are based solely on the evidence available in the provided inputs. "
            "No policy recommendations are made. Results are traceable to specific source artifacts.\n\n"
        )

    if contradictions:
        content += "**Contradictions and Unresolved Items**\n"
        for c in contradictions[:5]:
            content += f"- {c.description}\n"
        content += "\n"

    content += (
        "**Path Forward**\n"
        "The following next steps are indicated by the current state of the analysis:\n"
        "1. Resolve all blocking gaps listed in the gap register.\n"
        "2. Obtain agency review of parameters and assumptions (Section 4).\n"
        "3. Validate data sources and modeling framework (Section 5).\n"
        "4. Complete modeling runs under all modeled conditions.\n"
        "5. Return for quantitative results review upon completion of steps 1–4.\n"
    )

    gap_notes = _gap_inline_marker(gap_items, "7")
    if gap_notes:
        content += "\n" + gap_notes

    concern_ids = [c.concern_id for c in contradictions]
    return SectionDraft(section_id="7", title=SECTION_TITLES["7"], content=content, source_concern_ids=concern_ids)


# ---------------------------------------------------------------------------
# FAQ extraction
# ---------------------------------------------------------------------------


def _extract_faq(
    concerns: List[InterpretedConcern],
) -> List[FAQItem]:
    """Extract FAQ items from concerns that represent questions or agency concerns."""
    faq_items: List[FAQItem] = []
    counter = 1

    question_buckets = {"agency_concerns", "missing_elements"}
    for concern in concerns:
        is_question_type = (
            concern.bucket in question_buckets
            or re.search(r"\?", concern.description)
            or re.search(r"\b(what|how|why|when|where|who|which|whether)\b", concern.description, re.IGNORECASE)
        )
        if not is_question_type:
            continue

        section_ref = concern.section_refs[0] if concern.section_refs else "6"

        faq_items.append(
            FAQItem(
                faq_id=f"FAQ-{counter:03d}",
                section_ref=section_ref,
                question=concern.description,
                answer="",
                source_refs=[concern.source_artifact_id] if concern.source_artifact_id else [],
                source_artifact_id=concern.source_artifact_id,
                source_type=concern.source_type,
                source_locator=concern.source_locator,
                confidence=concern.confidence,
            )
        )
        counter += 1

    return faq_items


# ---------------------------------------------------------------------------
# Main synthesize entry point
# ---------------------------------------------------------------------------


def run_synthesize(
    inputs: EngineInputs,
    interpret_result: InterpretResult,
    gap_items: List[GapItem],
    quantitative_results_available: bool = False,
) -> SynthesizeResult:
    """Run the SYNTHESIZE stage.

    Generates all 7 working paper sections, FAQ items, and integrates gap markers
    into section content.

    Parameters
    ----------
    inputs:
        Original engine inputs (used for title, study ID, etc.).
    interpret_result:
        Output from the INTERPRET stage.
    gap_items:
        Gap items extracted from the interpret result.
    quantitative_results_available:
        If False, Section 6 will switch to results-framework mode.

    Returns
    -------
    SynthesizeResult
        All sections, FAQ items, gap items, and title.
    """
    concerns = interpret_result.concerns

    title = inputs.title_hint or "Federal Spectrum Study Working Paper"

    sections = [
        _gen_section_1(inputs, concerns, gap_items),
        _gen_section_2(inputs, concerns, gap_items),
        _gen_section_3(inputs, concerns, gap_items),
        _gen_section_4(inputs, concerns, gap_items),
        _gen_section_5(inputs, concerns, gap_items),
        _gen_section_6(inputs, concerns, gap_items, quantitative_results_available),
        _gen_section_7(inputs, concerns, gap_items, quantitative_results_available),
    ]

    faq_items = _extract_faq(concerns)

    return SynthesizeResult(
        sections=sections,
        faq_items=faq_items,
        gap_items=gap_items,
        title=title,
        quantitative_results_available=quantitative_results_available,
    )
