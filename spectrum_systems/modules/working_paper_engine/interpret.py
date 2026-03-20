"""
Working Paper Engine — interpret.py

INTERPRET stage: Map observed items into structured buckets, generate initial
gap candidates, and map concerns to working paper sections.

Design principles
-----------------
- Each InterpretedConcern is mapped to exactly one primary bucket.
- Gap candidates are flagged conservatively: prefer false negatives over
  fabricating gaps that are not supported by observations.
- Section mapping uses a deterministic rule table.
- No prose is generated here; this stage only organizes evidence.
"""

from __future__ import annotations

import re
from typing import Dict, List

from spectrum_systems.modules.working_paper_engine.models import (
    GapItem,
    GapType,
    ImpactLevel,
    InterpretedConcern,
    InterpretResult,
    ObserveResult,
    ObservedItem,
    SourceType,
)

# ---------------------------------------------------------------------------
# Bucket classification rules
# ---------------------------------------------------------------------------

_METHODOLOGY_PATTERNS = [
    re.compile(r"\b(method|approach|model|simulation|analysis|framework|technique|procedure)\b", re.IGNORECASE),
    re.compile(r"\b(propagation|path loss|Monte Carlo|link budget|interference model)\b", re.IGNORECASE),
]

_DATA_PATTERNS = [
    re.compile(r"\b(data|dataset|database|measurement|empirical|sample|survey|record)\b", re.IGNORECASE),
    re.compile(r"\b(spectrum monitor|radar data|frequency assignment|license record)\b", re.IGNORECASE),
]

_ASSUMPTION_PATTERNS = [
    re.compile(r"\b(assum|assume|assumed|assuming|assumption|working assumption)\b", re.IGNORECASE),
    re.compile(r"\b(for the purpose|treated as|modeled as|considered as)\b", re.IGNORECASE),
]

_CONSTRAINT_PATTERNS = [
    re.compile(r"\b(constraint|constrained|limit|limitation|restricted|restriction|boundary)\b", re.IGNORECASE),
    re.compile(r"\b(protection criteria|threshold|coordination zone|exclusion zone)\b", re.IGNORECASE),
    re.compile(r"\b(must not|shall not|cannot|prohibited|forbidden|regulatory)\b", re.IGNORECASE),
]

_AGENCY_CONCERN_PATTERNS = [
    re.compile(r"\b(agency|federal|FCC|NTIA|DoD|FAA|NASA|concern|objection|question|raised)\b", re.IGNORECASE),
    re.compile(r"\b(stakeholder|comment|feedback|hearing|coordination request)\b", re.IGNORECASE),
]

_CONTRADICTION_PATTERNS = [
    re.compile(r"\b(contradict|inconsistent|conflict|conflict|disagree|discrepancy|mismatch)\b", re.IGNORECASE),
    re.compile(r"\b(however|but|on the other hand|contrary|whereas|yet)\b", re.IGNORECASE),
]

_MISSING_PATTERNS = [
    re.compile(r"\b(missing|not available|no data|gap|unknown|undetermined|TBD|TBA)\b", re.IGNORECASE),
    re.compile(r"\b(need|require|must be provided|to be determined|pending)\b", re.IGNORECASE),
]

# ---------------------------------------------------------------------------
# Section routing for concern buckets
# ---------------------------------------------------------------------------

_BUCKET_TO_SECTIONS: Dict[str, List[str]] = {
    "methodology":       ["3", "4"],
    "data":              ["5"],
    "assumptions":       ["4"],
    "constraints":       ["4", "5"],
    "agency_concerns":   ["2", "6"],
    "contradictions":    ["6", "7"],
    "missing_elements":  ["5", "6"],
}

# ---------------------------------------------------------------------------
# Gap type inference from bucket
# ---------------------------------------------------------------------------

_BUCKET_TO_GAP_TYPE: Dict[str, GapType] = {
    "methodology":       GapType.METHOD,
    "data":              GapType.DATA,
    "assumptions":       GapType.ASSUMPTION,
    "constraints":       GapType.CONSTRAINT,
    "agency_concerns":   GapType.COORDINATION,
    "contradictions":    GapType.UNKNOWN,
    "missing_elements":  GapType.DATA,
}


def _classify_bucket(item: ObservedItem) -> str:
    """Classify an observed item into a structural bucket."""
    text = item.content

    # Contradictions are checked first — they override other classifications
    if any(p.search(text) for p in _CONTRADICTION_PATTERNS):
        return "contradictions"

    if item.item_type == "open_issue" or any(p.search(text) for p in _MISSING_PATTERNS):
        return "missing_elements"

    if item.item_type == "assumption" or any(p.search(text) for p in _ASSUMPTION_PATTERNS):
        return "assumptions"

    if item.item_type == "constraint" or any(p.search(text) for p in _CONSTRAINT_PATTERNS):
        return "constraints"

    if any(p.search(text) for p in _AGENCY_CONCERN_PATTERNS):
        return "agency_concerns"

    if any(p.search(text) for p in _DATA_PATTERNS):
        return "data"

    if any(p.search(text) for p in _METHODOLOGY_PATTERNS):
        return "methodology"

    return "missing_elements"


def _is_gap_candidate(item: ObservedItem, bucket: str) -> bool:
    """Determine if an observed item should be promoted to a gap candidate."""
    gap_buckets = {"missing_elements", "data", "contradictions"}
    if bucket in gap_buckets:
        return True
    if item.item_type in ("open_issue", "question"):
        return True
    return False


def _infer_impact(item: ObservedItem, bucket: str) -> ImpactLevel:
    text = item.content.lower()
    if re.search(r"\b(critical|blocking|required|must|shall)\b", text):
        return ImpactLevel.HIGH
    if re.search(r"\b(important|significant|major)\b", text):
        return ImpactLevel.HIGH
    if bucket in ("missing_elements", "data", "constraints"):
        return ImpactLevel.MEDIUM
    return ImpactLevel.LOW


def run_interpret(observe_result: ObserveResult) -> InterpretResult:
    """Run the INTERPRET stage on the observed items.

    Maps each ObservedItem into a structural bucket, flags gap candidates,
    and assigns section references for downstream synthesis.

    Parameters
    ----------
    observe_result:
        Output from the OBSERVE stage.

    Returns
    -------
    InterpretResult
        All interpreted concerns with bucket assignments and section mappings.
    """
    concerns: List[InterpretedConcern] = []

    for idx, item in enumerate(observe_result.items):
        bucket = _classify_bucket(item)
        section_refs = _BUCKET_TO_SECTIONS.get(bucket, ["6"])
        is_gap = _is_gap_candidate(item, bucket)

        concern = InterpretedConcern(
            concern_id=f"CON-{idx + 1:04d}",
            bucket=bucket,
            description=item.content,
            section_refs=section_refs,
            source_item_ids=[item.item_id],
            source_artifact_id=item.source_artifact_id,
            source_type=item.source_type,
            source_locator=item.source_locator,
            confidence=item.confidence,
            is_gap_candidate=is_gap,
        )
        concerns.append(concern)

    return InterpretResult(concerns=concerns)


def extract_gap_items(interpret_result: InterpretResult) -> List[GapItem]:
    """Extract GapItem instances from gap-candidate concerns.

    Only concerns flagged as is_gap_candidate are promoted to gaps.
    Gap IDs are sequential and deterministic.

    Parameters
    ----------
    interpret_result:
        Output from the INTERPRET stage.

    Returns
    -------
    List[GapItem]
        Structured gap items ready for the output bundle.
    """
    gaps: List[GapItem] = []
    counter = 1

    for concern in interpret_result.concerns:
        if not concern.is_gap_candidate:
            continue

        gap_type = _BUCKET_TO_GAP_TYPE.get(concern.bucket, GapType.UNKNOWN)
        section_ref = concern.section_refs[0] if concern.section_refs else "6"

        # Infer impact from content
        text = concern.description.lower()
        if re.search(r"\b(critical|blocking|required|must|shall)\b", text):
            impact = ImpactLevel.HIGH
        elif re.search(r"\b(important|significant|major)\b", text):
            impact = ImpactLevel.HIGH
        else:
            impact = ImpactLevel.MEDIUM

        blocking = impact == ImpactLevel.HIGH or concern.bucket == "missing_elements"

        gaps.append(
            GapItem(
                gap_id=f"GAP-{counter:03d}",
                description=concern.description,
                section_ref=section_ref,
                gap_type=gap_type,
                impact=impact,
                blocking=blocking,
                suggested_resolution="[need additional information]",
                source_refs=[concern.source_artifact_id] if concern.source_artifact_id else [],
                source_artifact_id=concern.source_artifact_id,
                source_type=concern.source_type,
                source_locator=concern.source_locator,
            )
        )
        counter += 1

    return gaps
