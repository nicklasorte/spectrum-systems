"""
patch_generator.py

Generates a PaperPatch — a set of proposed changes to apply to an existing
working paper based on meeting discussion.

Patch operations:
  - ``update`` : append new consensus material to an existing section
  - ``add``    : add a new section for a topic raised in the meeting that has
                 no corresponding section in the existing paper
"""

from __future__ import annotations

import re
from typing import List, Optional

from .schemas import MeetingDelta, PaperPatch, PaperState, SectionPatch

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(text: str) -> str:
    return _SLUG_RE.sub("-", text.lower()[:60]).strip("-")


def generate_patch(
    delta: MeetingDelta,
    paper_state: Optional[PaperState],
    meeting_title: str = "Meeting",
) -> PaperPatch:
    """Return a :class:`PaperPatch` derived from *delta*.

    Parameters
    ----------
    delta:
        Meeting delta produced by :mod:`meeting_delta_engine`.
    paper_state:
        Optional existing paper state.  When ``None`` every new topic becomes
        an ``add`` patch.
    meeting_title:
        Used to attribute the patch source.
    """
    patches: List[SectionPatch] = []

    # Update sections that were explicitly discussed in the meeting
    if paper_state:
        existing_ids = {sec.section_id for sec in paper_state.sections}
        for section_id in delta.updated_sections:
            if section_id in existing_ids:
                relevant_consensus = [
                    item for item in delta.consensus_items
                    if section_id in item
                ]
                appended = "\n".join(f"- {item}" for item in relevant_consensus) if relevant_consensus else ""
                patches.append(
                    SectionPatch(
                        section_id=section_id,
                        operation="update",
                        new_content=appended or None,
                        rationale=f"Section discussed during {meeting_title}; consensus items appended.",
                    )
                )

    # Add new sections for topics not represented in the existing paper
    existing_titles_lower: set[str] = set()
    if paper_state:
        existing_titles_lower = {sec.title.lower() for sec in paper_state.sections}

    for topic in delta.new_topics:
        topic_lower = topic.lower()
        if any(et in topic_lower or topic_lower in et for et in existing_titles_lower):
            continue  # already covered by an existing section
        section_id = f"SEC-NEW-{_slugify(topic[:40])}"
        patches.append(
            SectionPatch(
                section_id=section_id,
                operation="add",
                new_content=topic,
                rationale=f"New topic raised during {meeting_title}.",
            )
        )

    return PaperPatch(source_meeting=meeting_title, patches=patches)
