"""Provider-aware normalization from parsed review markdown into findings artifacts."""

from __future__ import annotations

import re
from pathlib import Path

from spectrum_systems.modules.prompt_queue.queue_models import iso_now, utc_now
from spectrum_systems.modules.prompt_queue.review_parser import ParsedReview

PARSER_VERSION = "1.0.0"
_FILE_REF_RE = re.compile(r"`([^`]+\.[a-zA-Z0-9]+)`")
_SEVERITY_HINTS = ("critical", "high", "medium", "low")


def _parse_fallback_metadata(metadata_text: str) -> tuple[bool | None, str | None]:
    used_match = re.search(r"fallback\s+used\s*:\s*(true|false)", metadata_text, re.IGNORECASE)
    reason_match = re.search(r"fallback\s+reason\s*:\s*([a-z_]+)", metadata_text, re.IGNORECASE)
    used = None if not used_match else used_match.group(1).lower() == "true"
    reason = reason_match.group(1).lower() if reason_match else None
    return used, reason


def _split_markdown_list(section_body: str) -> list[str]:
    lines = section_body.splitlines()
    items: list[list[str]] = []
    current: list[str] = []

    for line in lines:
        if re.match(r"^\s*(?:[-*]|\d+\.)\s+", line):
            if current:
                items.append(current)
            current = [re.sub(r"^\s*(?:[-*]|\d+\.)\s+", "", line).strip()]
        elif current:
            current.append(line.strip())

    if current:
        items.append(current)

    if not items and section_body.strip():
        return [section_body.strip()]

    return ["\n".join(part for part in item if part).strip() for item in items if any(p.strip() for p in item)]


def _infer_severity(text: str) -> str | None:
    lowered = text.lower()
    for value in _SEVERITY_HINTS:
        if re.search(rf"\b{value}\b", lowered):
            return value
    return None


def _summarize(item_text: str) -> str:
    first_line = item_text.splitlines()[0].strip()
    first_line = re.sub(r"^[\[\(]?([A-Z]+-\d+)[\]\)]?[:\s-]*", "", first_line)
    if ":" in first_line:
        return first_line.split(":", 1)[0].strip()
    return first_line[:160]


def _normalize_items(section_body: str, *, source_section: str) -> list[dict]:
    items = _split_markdown_list(section_body)
    normalized: list[dict] = []

    for idx, item_text in enumerate(items, start=1):
        normalized.append(
            {
                "finding_id": f"{source_section}-{idx}",
                "summary": _summarize(item_text),
                "body": item_text,
                "severity": _infer_severity(item_text),
                "file_references": sorted(set(_FILE_REF_RE.findall(item_text))),
                "source_section": source_section,
            }
        )

    return normalized


def build_findings_artifact(
    *,
    work_item: dict,
    parsed_review: ParsedReview,
    source_review_artifact_path: str,
    clock=utc_now,
) -> dict:
    parsed_at = iso_now(clock)
    artifact_id = f"findings-{work_item['work_item_id']}-{parsed_at.replace(':', '').replace('-', '')}"

    metadata_fallback_used, metadata_fallback_reason = _parse_fallback_metadata(parsed_review.sections.get("metadata", ""))
    fallback_used = work_item.get("review_fallback_used")
    if fallback_used is None:
        fallback_used = metadata_fallback_used if metadata_fallback_used is not None else False
    fallback_reason = work_item.get("review_fallback_reason") or metadata_fallback_reason

    return {
        "findings_artifact_id": artifact_id,
        "work_item_id": work_item["work_item_id"],
        "source_review_artifact_path": source_review_artifact_path,
        "review_provider": parsed_review.provider,
        "fallback_used": bool(fallback_used),
        "fallback_reason": fallback_reason,
        "review_decision": parsed_review.review_decision,
        "trust_assessment": parsed_review.trust_assessment,
        "critical_findings": _normalize_items(
            parsed_review.sections.get("critical_findings", ""), source_section="critical_findings"
        ),
        "required_fixes": _normalize_items(
            parsed_review.sections.get("required_fixes", ""), source_section="required_fixes"
        ),
        "optional_improvements": _normalize_items(
            parsed_review.sections.get("optional_improvements", ""), source_section="optional_improvements"
        ),
        "failure_mode_summary": parsed_review.sections["failure_mode_summary"],
        "raw_sections": {
            "metadata": parsed_review.sections.get("metadata", ""),
            "decision": parsed_review.sections.get("decision", ""),
            "critical_findings": parsed_review.sections.get("critical_findings", ""),
            "required_fixes": parsed_review.sections.get("required_fixes", ""),
            "optional_improvements": parsed_review.sections.get("optional_improvements", ""),
            "trust_assessment": parsed_review.sections.get("trust_assessment", ""),
            "failure_mode_summary": parsed_review.sections.get("failure_mode_summary", ""),
        },
        "parsed_at": parsed_at,
        "parser_version": PARSER_VERSION,
    }


def default_findings_path(*, work_item_id: str, root_dir: Path) -> Path:
    return root_dir / "artifacts" / "prompt_queue" / "findings" / f"{work_item_id}.findings.json"
