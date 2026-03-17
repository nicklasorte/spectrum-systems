"""
paper_state_reader.py

Reads an existing working paper draft (plain text or JSON) and returns a
PaperState object representing the current state of the paper.

Supported input formats:
  - JSON (dict with ``paper_id``, ``title``, ``version``, ``sections`` keys)
  - Plain text (sections delimited by ``## Heading`` markers)
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List

from .schemas import PaperSection, PaperState

_HEADING_RE = re.compile(r"^#{1,3}\s+(?P<title>.+)$", re.MULTILINE)


def read_plain_text(text: str, source_path: str) -> PaperState:
    """Parse a plain-text working paper into a :class:`PaperState`.

    This is the public API for parsing plain-text / Markdown content that has
    already been loaded into a string (e.g., from meeting minutes).  For
    file-based access, use :func:`read_paper_state` instead.
    """
    return _read_plain_text(text, source_path)


def _read_plain_text(text: str, source_path: str) -> PaperState:
    """Parse a plain-text working paper into a :class:`PaperState`."""
    sections: List[PaperSection] = []
    headings = list(_HEADING_RE.finditer(text))

    title = "Untitled Working Paper"
    if headings:
        title = headings[0].group("title").strip()
        headings = headings[1:]  # first heading is the document title

    for idx, match in enumerate(headings):
        start = match.end()
        end = headings[idx + 1].start() if idx + 1 < len(headings) else len(text)
        content = text[start:end].strip()
        section_id = f"SEC-{idx + 1:03d}"
        sections.append(
            PaperSection(
                section_id=section_id,
                title=match.group("title").strip(),
                content=content,
                status="draft",
            )
        )

    return PaperState(
        paper_id="WP-UNKNOWN",
        title=title,
        version="0.1",
        sections=sections,
        source_path=source_path,
    )


def _read_json(data: dict, source_path: str) -> PaperState:
    """Deserialize a JSON working paper dict into a :class:`PaperState`."""
    raw_sections = data.get("sections", [])
    sections: List[PaperSection] = []
    for idx, sec in enumerate(raw_sections):
        sections.append(
            PaperSection(
                section_id=sec.get("section_id", f"SEC-{idx + 1:03d}"),
                title=sec.get("title", "Untitled Section"),
                content=sec.get("content", ""),
                status=sec.get("status", "draft"),
                open_issues=sec.get("open_issues", []),
            )
        )
    return PaperState(
        paper_id=data.get("paper_id", "WP-UNKNOWN"),
        title=data.get("title", "Untitled Working Paper"),
        version=data.get("version", "0.1"),
        sections=sections,
        source_path=source_path,
    )


def read_paper_state(path: str) -> PaperState:
    """Read a working paper from *path* and return its :class:`PaperState`.

    Parameters
    ----------
    path:
        Filesystem path to a ``.json`` or plain-text (``.md`` / ``.txt``) file.
    """
    p = Path(path)
    text = p.read_text(encoding="utf-8")

    if p.suffix.lower() == ".json":
        try:
            data = json.loads(text)
            return _read_json(data, str(p))
        except json.JSONDecodeError:
            pass  # fall through to plain-text parser

    return _read_plain_text(text, str(p))
