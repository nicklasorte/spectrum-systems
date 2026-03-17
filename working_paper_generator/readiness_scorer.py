"""
readiness_scorer.py

Scores the readiness of each working paper section for writing / finalization
given the available meeting evidence.

Score components (all normalised to [0.0, 1.0]):
  - coverage  : fraction of section open_issues addressed by the meeting
  - consensus : fraction of consensus items mentioning this section
  - question  : penalty for unresolved open questions referencing this section

Overall section score = 0.5 * coverage + 0.3 * consensus - 0.2 * question_penalty
                        (clamped to [0.0, 1.0])

A section is ready-to-draft when its score >= READY_THRESHOLD.
The overall paper is ready-to-draft when >= PAPER_READY_FRACTION of sections pass.
"""

from __future__ import annotations

from typing import List, Optional

from .schemas import (
    MeetingDelta,
    OpenQuestion,
    PaperState,
    ReadinessReport,
    SectionReadiness,
)

_READY_THRESHOLD = 0.5
PAPER_READY_FRACTION = 0.6


def _coverage_score(
    section_id: str,
    open_issues: List[str],
    delta: MeetingDelta,
) -> float:
    if not open_issues:
        return 1.0
    all_discussion = " ".join(delta.consensus_items + delta.new_topics).lower()
    addressed = sum(1 for issue in open_issues if issue.lower() in all_discussion)
    return addressed / len(open_issues)


def _consensus_score(section_id: str, delta: MeetingDelta) -> float:
    if not delta.consensus_items:
        return 0.0
    hits = sum(1 for item in delta.consensus_items if section_id in item or section_id.lower() in item.lower())
    return min(hits / max(len(delta.consensus_items), 1), 1.0)


def _question_penalty(section_id: str, questions: List[OpenQuestion]) -> float:
    section_questions = [
        q for q in questions
        if q.section_ref == section_id and q.resolution_status == "open"
    ]
    if not section_questions:
        return 0.0
    return min(len(section_questions) / 5.0, 1.0)


def score_readiness(
    paper_state: PaperState,
    delta: MeetingDelta,
    questions: List[OpenQuestion],
) -> ReadinessReport:
    """Return a :class:`ReadinessReport` for *paper_state*.

    Parameters
    ----------
    paper_state:
        Current working paper state with sections.
    delta:
        Meeting delta produced by :mod:`meeting_delta_engine`.
    questions:
        Open questions extracted by :mod:`question_engine`.
    """
    section_scores: List[SectionReadiness] = []

    for sec in paper_state.sections:
        cov = _coverage_score(sec.section_id, sec.open_issues, delta)
        cons = _consensus_score(sec.section_id, delta)
        penalty = _question_penalty(sec.section_id, questions)

        raw_score = 0.5 * cov + 0.3 * cons - 0.2 * penalty
        score = max(0.0, min(1.0, raw_score))

        blocking = [
            q.text for q in questions
            if q.section_ref == sec.section_id and q.resolution_status == "open"
        ]
        rationale = (
            f"coverage={cov:.2f}, consensus={cons:.2f}, question_penalty={penalty:.2f}"
        )
        section_scores.append(
            SectionReadiness(
                section_id=sec.section_id,
                score=round(score, 3),
                rationale=rationale,
                blocking_questions=blocking,
            )
        )

    if section_scores:
        overall = sum(s.score for s in section_scores) / len(section_scores)
        ready_count = sum(1 for s in section_scores if s.score >= _READY_THRESHOLD)
        ready_to_draft = (ready_count / len(section_scores)) >= PAPER_READY_FRACTION
    else:
        overall = 0.0
        ready_to_draft = False

    return ReadinessReport(
        overall_score=round(overall, 3),
        sections=section_scores,
        ready_to_draft=ready_to_draft,
    )
