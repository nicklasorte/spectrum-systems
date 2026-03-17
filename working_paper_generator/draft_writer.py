"""
draft_writer.py

Assembles the final WorkingPaperDraft by combining:
  - An existing PaperState (if provided)
  - A PaperPatch with proposed changes
  - Extracted arguments, open questions, and a readiness report

When no existing paper state is supplied, a new paper is scaffolded from the
patch alone.
"""

from __future__ import annotations

import copy
from typing import List, Optional

from .schemas import (
    Argument,
    OpenQuestion,
    PaperPatch,
    PaperSection,
    PaperState,
    ReadinessReport,
    WorkingPaperDraft,
)

_DEFAULT_PAPER_ID = "WP-DRAFT-001"
_DEFAULT_VERSION = "0.1-draft"


def _apply_patch(state: PaperState, patch: PaperPatch) -> List[PaperSection]:
    """Return a new list of sections with *patch* applied to *state*."""
    sections: List[PaperSection] = [copy.deepcopy(sec) for sec in state.sections]
    section_map = {sec.section_id: sec for sec in sections}

    for sp in patch.patches:
        if sp.operation == "update" and sp.section_id in section_map:
            target = section_map[sp.section_id]
            if sp.new_content:
                separator = "\n\n" if target.content else ""
                target.content = target.content + separator + sp.new_content
        elif sp.operation == "add":
            new_sec = PaperSection(
                section_id=sp.section_id,
                title=sp.new_content[:80] if sp.new_content else sp.section_id,
                content=sp.new_content or "",
                status="draft",
            )
            if sp.section_id not in section_map:
                sections.append(new_sec)
        elif sp.operation == "delete" and sp.section_id in section_map:
            sections = [sec for sec in sections if sec.section_id != sp.section_id]
            section_map = {sec.section_id: sec for sec in sections}

    return sections


def write_draft(
    patch: PaperPatch,
    paper_state: Optional[PaperState],
    arguments: List[Argument],
    questions: List[OpenQuestion],
    readiness: ReadinessReport,
    source_transcript: Optional[str] = None,
    source_minutes: Optional[str] = None,
) -> WorkingPaperDraft:
    """Assemble and return a :class:`WorkingPaperDraft`.

    Parameters
    ----------
    patch:
        Proposed changes to apply.
    paper_state:
        Optional existing working paper state.  When ``None`` the draft is
        scaffolded from scratch.
    arguments:
        Arguments extracted from the transcript.
    questions:
        Open questions extracted from the transcript.
    readiness:
        Readiness report produced by the scorer.
    source_transcript:
        Path to the source transcript (for provenance).
    source_minutes:
        Path to the source minutes (for provenance).
    """
    if paper_state is not None:
        sections = _apply_patch(paper_state, patch)
        paper_id = paper_state.paper_id
        title = paper_state.title
        base_version = paper_state.version
        # Bump minor version
        parts = base_version.split(".")
        try:
            parts[-1] = str(int(parts[-1].split("-")[0]) + 1)
        except (ValueError, IndexError):
            parts.append("1")
        version = ".".join(parts) + "-draft"
        patch_applied = bool(patch.patches)
    else:
        # Scaffold from patch alone
        sections = []
        for sp in patch.patches:
            if sp.operation == "add":
                sections.append(
                    PaperSection(
                        section_id=sp.section_id,
                        title=sp.new_content[:80] if sp.new_content else sp.section_id,
                        content=sp.new_content or "",
                        status="draft",
                    )
                )
        paper_id = _DEFAULT_PAPER_ID
        title = patch.source_meeting + " — Working Paper Draft"
        version = _DEFAULT_VERSION
        patch_applied = bool(sections)

    return WorkingPaperDraft(
        paper_id=paper_id,
        title=title,
        version=version,
        sections=sections,
        open_questions=questions,
        arguments=arguments,
        readiness=readiness,
        patch_applied=patch_applied,
        source_transcript=source_transcript,
        source_minutes=source_minutes,
    )
