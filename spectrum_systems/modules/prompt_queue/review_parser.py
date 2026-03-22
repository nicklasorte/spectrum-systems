"""Fail-closed markdown parser for governed prompt queue review artifacts."""

from __future__ import annotations

import re
from dataclasses import dataclass


class ReviewParseError(ValueError):
    """Raised when a review artifact is malformed or incomplete."""


_REQUIRED_CANONICAL_SECTIONS = {
    "metadata",
    "decision",
    "failure_mode_summary",
}

_SECTION_ALIASES = {
    "metadata": "metadata",
    "review metadata": "metadata",
    "decision": "decision",
    "critical findings": "critical_findings",
    "required fixes": "required_fixes",
    "optional improvements": "optional_improvements",
    "trust assessment": "trust_assessment",
    "failure mode summary": "failure_mode_summary",
}

_HEADING_RE = re.compile(r"^(#{2,6})\s+(.+?)\s*$", re.MULTILINE)
_DECISION_RE = re.compile(r"\b(pass|fail)\b", re.IGNORECASE)
_TRUST_RE = re.compile(r"\b(yes|no)\b", re.IGNORECASE)


@dataclass(frozen=True)
class ParsedReview:
    provider: str
    sections: dict[str, str]
    review_decision: str
    trust_assessment: str | None


def _normalize_heading(label: str) -> str:
    normalized = re.sub(r"^\d+[\.)]\s*", "", label.strip())
    normalized = normalized.replace("**", "")
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = normalized.strip(" :-").lower()
    return _SECTION_ALIASES.get(normalized, "")


def _extract_sections(markdown_text: str) -> dict[str, str]:
    headings = list(_HEADING_RE.finditer(markdown_text))
    sections: dict[str, str] = {}
    for idx, heading in enumerate(headings):
        section_name = _normalize_heading(heading.group(2))
        if not section_name:
            continue
        start = heading.end()
        end = headings[idx + 1].start() if idx + 1 < len(headings) else len(markdown_text)
        body = markdown_text[start:end].strip()
        sections[section_name] = body
    return sections


def _extract_decision(sections: dict[str, str]) -> str:
    decision_text = sections.get("decision", "")
    match = _DECISION_RE.search(decision_text)
    if not match:
        raise ReviewParseError("Decision section is missing or malformed.")
    return match.group(1).upper()


def _extract_trust(sections: dict[str, str]) -> str | None:
    trust_text = sections.get("trust_assessment", "")
    if not trust_text:
        return None
    match = _TRUST_RE.search(trust_text)
    return match.group(1).upper() if match else None


def parse_review_markdown(markdown_text: str, *, provider: str) -> ParsedReview:
    provider_normalized = provider.strip().lower()
    if provider_normalized not in {"claude", "codex"}:
        raise ReviewParseError(f"Unsupported review provider '{provider}'.")

    sections = _extract_sections(markdown_text)
    missing_required = sorted(section for section in _REQUIRED_CANONICAL_SECTIONS if not sections.get(section))
    if missing_required:
        raise ReviewParseError(f"Missing required section(s): {', '.join(missing_required)}")

    review_decision = _extract_decision(sections)

    if review_decision == "FAIL":
        if not sections.get("critical_findings"):
            raise ReviewParseError("FAIL review missing required 'Critical Findings' section.")
        if not sections.get("required_fixes"):
            raise ReviewParseError("FAIL review missing required 'Required Fixes' section.")

    sections.setdefault("critical_findings", "")
    sections.setdefault("required_fixes", "")
    sections.setdefault("optional_improvements", "")
    sections.setdefault("trust_assessment", "")

    return ParsedReview(
        provider=provider_normalized,
        sections=sections,
        review_decision=review_decision,
        trust_assessment=_extract_trust(sections),
    )
