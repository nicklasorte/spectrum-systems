"""Deterministic review/action-tracker parsing into ``review_signal_artifact`` payloads."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

from jsonschema import Draft202012Validator

from spectrum_systems.contracts import load_schema


class ReviewParsingEngineError(ValueError):
    """Raised when review/action-tracker inputs are missing or malformed."""


@dataclass(frozen=True)
class ParsedRow:
    """A parsed markdown table row with source traceability."""

    values: Dict[str, str]
    line_number: int


_HEADING_RE = re.compile(r"^(#{2,6})\s+(.+?)\s*$")
_TABLE_SEPARATOR_RE = re.compile(r"^\|?(\s*:?-{3,}:?\s*\|)+\s*:?-{3,}:?\s*\|?\s*$")
_REVIEW_DATE_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")
_FRONTMATTER_REVIEW_DATE_RE = re.compile(r"^review_date:\s*(20\d{2}-\d{2}-\d{2})\s*$", re.IGNORECASE)
_FRONTMATTER_MODULE_RE = re.compile(r"^module:\s*([a-z0-9_\-]+)\s*$", re.IGNORECASE)
_OVERALL_VERDICT_RE = re.compile(r"(?:overall\s+verdict|verdict)\s*:\s*([A-Za-z _\-]+)", re.IGNORECASE)
_REASON_CODE_RE = re.compile(r"\bR\d+\b")
_SYSTEM_CODE_RE = re.compile(r"\b(tpa|fre|pqx|ril|map|rdx|ops|sre)\b", re.IGNORECASE)
_BLOCKER_TOKEN_RE = re.compile(r"\bblock(?:er|ing)?\b", re.IGNORECASE)

_SEVERITY_BY_SECTION = {
    "critical": "critical",
    "critical items": "critical",
    "critical risks": "critical",
    "high-priority items": "high",
    "high priority items": "high",
    "medium-priority items": "medium",
    "medium priority items": "medium",
}

_SEVERITY_NORMALIZATION = {
    "critical": "critical",
    "high": "high",
    "medium": "medium",
}


def _canonical_hash(payload: Dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_review_signal_artifact(body: Dict[str, Any]) -> None:
    validator = Draft202012Validator(load_schema("review_signal_artifact"))
    errors = sorted(validator.iter_errors(body), key=lambda err: str(list(err.absolute_path)))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise ReviewParsingEngineError(f"review_signal_artifact runtime schema validation failed: {details}")


def _split_frontmatter(text: str) -> Tuple[List[str], List[str]]:
    lines = text.splitlines()
    if len(lines) < 3 or lines[0].strip() != "---":
        return [], lines
    end_index = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_index = idx
            break
    if end_index is None:
        return [], lines
    return lines[1:end_index], lines[end_index + 1 :]


def _parse_markdown_table(lines: Sequence[str], start_index: int) -> Tuple[List[ParsedRow], int]:
    if start_index + 1 >= len(lines):
        raise ReviewParsingEngineError("malformed markdown table: missing separator")

    header_line = lines[start_index]
    separator_line = lines[start_index + 1]

    if "|" not in header_line:
        raise ReviewParsingEngineError("malformed markdown table: missing header row")
    if not _TABLE_SEPARATOR_RE.match(separator_line.strip()):
        raise ReviewParsingEngineError("malformed markdown table: invalid separator row")

    headers = [cell.strip().lower() for cell in header_line.strip().strip("|").split("|")]
    if any(not header for header in headers):
        raise ReviewParsingEngineError("malformed markdown table: blank header cell")

    rows: List[ParsedRow] = []
    index = start_index + 2
    while index < len(lines):
        row_line = lines[index]
        if not row_line.strip().startswith("|"):
            break
        cells = [cell.strip() for cell in row_line.strip().strip("|").split("|")]
        if len(cells) != len(headers):
            raise ReviewParsingEngineError("malformed markdown table: row width mismatch")
        rows.append(ParsedRow(values=dict(zip(headers, cells)), line_number=index + 1))
        index += 1

    if not rows:
        raise ReviewParsingEngineError("malformed markdown table: no data rows")
    return rows, index


def _extract_section_tables(lines: Sequence[str]) -> Dict[str, List[ParsedRow]]:
    section = ""
    section_tables: Dict[str, List[ParsedRow]] = {}

    index = 0
    while index < len(lines):
        heading_match = _HEADING_RE.match(lines[index].strip())
        if heading_match:
            section = heading_match.group(2).strip().lower()
            index += 1
            continue

        if lines[index].strip().startswith("|"):
            rows, next_index = _parse_markdown_table(lines, index)
            if not section:
                raise ReviewParsingEngineError("malformed markdown table: table found before any section heading")
            section_tables[section] = rows
            index = next_index
            continue

        index += 1

    return section_tables


def _extract_review_date(review_lines: Sequence[str], frontmatter_lines: Sequence[str]) -> str:
    for line in frontmatter_lines:
        match = _FRONTMATTER_REVIEW_DATE_RE.match(line.strip())
        if match:
            return match.group(1)

    for line in review_lines:
        if "review date" in line.lower():
            match = _REVIEW_DATE_RE.search(line)
            if match:
                return match.group(1)

    raise ReviewParsingEngineError("review_date missing from structured review metadata")


def _extract_overall_verdict(lines: Sequence[str]) -> str | None:
    for line in lines:
        match = _OVERALL_VERDICT_RE.search(line)
        if match:
            verdict = match.group(1).strip().lower().replace(" ", "_")
            return verdict
    return None


def _extract_system_scope(review_path: Path, review_lines: Sequence[str], frontmatter_lines: Sequence[str]) -> str:
    for line in frontmatter_lines:
        match = _FRONTMATTER_MODULE_RE.match(line.strip())
        if match:
            return match.group(1).lower()

    lowered_name = review_path.name.lower()
    for key in ("tpa", "fre", "pqx", "ril"):
        if key in lowered_name:
            return key

    for line in review_lines:
        match = _SYSTEM_CODE_RE.search(line)
        if match:
            return match.group(1).lower()

    raise ReviewParsingEngineError("unable to derive system_scope from structured review inputs")


def _normalize_severity(raw: str | None, section_name: str) -> str:
    if raw:
        normalized = raw.strip().lower()
        if normalized in _SEVERITY_NORMALIZATION:
            return normalized
        if normalized == "critical":
            return "critical"
        if normalized == "high":
            return "high"
        if normalized == "medium":
            return "medium"

    section = section_name.strip().lower()
    if section in _SEVERITY_BY_SECTION:
        return _SEVERITY_BY_SECTION[section]

    raise ReviewParsingEngineError(f"unable to normalize severity for section '{section_name}'")


def _extract_item_from_row(row: ParsedRow, section_name: str, source_path: str) -> Dict[str, Any]:
    values = row.values
    item_id = values.get("id", "").strip()
    if not item_id:
        raise ReviewParsingEngineError(f"malformed table row at line {row.line_number}: missing ID")

    description = (values.get("risk") or values.get("action item") or values.get("description") or "").strip()
    if not description:
        raise ReviewParsingEngineError(f"malformed table row at line {row.line_number}: missing description/risk/action")

    recommended_action = (values.get("recommended action") or values.get("next step") or values.get("action item") or "").strip()
    if not recommended_action:
        raise ReviewParsingEngineError(f"malformed table row at line {row.line_number}: missing recommended action")

    status = (values.get("status") or "").strip().lower()
    if not status:
        raise ReviewParsingEngineError(f"malformed table row at line {row.line_number}: missing status")

    severity = _normalize_severity(values.get("severity"), section_name)
    return {
        "id": item_id,
        "description": description,
        "severity": severity,
        "recommended_action": recommended_action,
        "status": status,
        "trace": {
            "source_path": source_path,
            "line_number": row.line_number,
            "source_excerpt": f"{item_id}: {description}",
        },
    }


def _extract_list_section_items(lines: Sequence[str], heading: str, severity: str, source_path: str) -> List[Dict[str, Any]]:
    normalized_heading = heading.lower()
    items: List[Dict[str, Any]] = []
    in_section = False
    line_index = 0
    for line in lines:
        stripped = line.strip()
        heading_match = _HEADING_RE.match(stripped)
        if heading_match:
            name = heading_match.group(2).strip().lower()
            if in_section and name != normalized_heading:
                break
            in_section = name == normalized_heading
            line_index += 1
            continue

        if in_section and re.match(r"^([-*]|\d+\.)\s+", stripped):
            description = re.sub(r"^([-*]|\d+\.)\s+", "", stripped).strip()
            if description:
                ordinal = len(items) + 1
                items.append(
                    {
                        "id": f"{severity.upper()}-{ordinal}",
                        "description": description,
                        "severity": severity,
                        "recommended_action": description,
                        "status": "open",
                        "trace": {
                            "source_path": source_path,
                            "line_number": line_index + 1,
                            "source_excerpt": description,
                        },
                    }
                )

        line_index += 1

    return items


def _sorted_items(items: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    severity_rank = {"critical": 0, "high": 1, "medium": 2}
    return sorted(
        items,
        key=lambda item: (
            severity_rank.get(item["severity"], 99),
            str(item["id"]),
            str(item["description"]),
        ),
    )


def _extract_blocker_ids(all_items: Sequence[Dict[str, Any]], review_lines: Sequence[str], action_lines: Sequence[str]) -> List[str]:
    blocker_ids = [
        item["id"]
        for item in all_items
        if _BLOCKER_TOKEN_RE.search(item["description"])
        or _BLOCKER_TOKEN_RE.search(item["recommended_action"])
        or _BLOCKER_TOKEN_RE.search(item["status"])
    ]

    for lines in (review_lines, action_lines):
        in_blocking_section = False
        for line in lines:
            stripped = line.strip()
            heading_match = _HEADING_RE.match(stripped)
            if heading_match:
                in_blocking_section = "blocking items" in heading_match.group(2).strip().lower()
                continue
            if in_blocking_section and stripped and stripped.lower() not in {"- none", "- none.", "none", "none currently identified from this review."}:
                for item in all_items:
                    if item["id"] in stripped:
                        blocker_ids.append(item["id"])

    return sorted(set(blocker_ids))


def parse_review_to_signal(review_path: str | Path, action_tracker_path: str | Path) -> Dict[str, Any]:
    """Parse deterministic structured review artifacts into a review signal artifact."""

    review_file = Path(review_path)
    action_file = Path(action_tracker_path)

    if not review_file.exists():
        raise ReviewParsingEngineError(f"review file not found: {review_file}")
    if not action_file.exists():
        raise ReviewParsingEngineError(f"action tracker file not found: {action_file}")

    review_text = review_file.read_text(encoding="utf-8")
    action_text = action_file.read_text(encoding="utf-8")

    review_frontmatter, review_lines = _split_frontmatter(review_text)
    action_frontmatter, action_lines = _split_frontmatter(action_text)
    del action_frontmatter

    section_tables = _extract_section_tables(action_lines)
    required_sections = ["critical items", "high-priority items", "medium-priority items"]
    missing_sections = [section for section in required_sections if section not in section_tables]
    if missing_sections:
        raise ReviewParsingEngineError(
            "required action-tracker sections missing: " + ", ".join(missing_sections)
        )

    critical_risks = [_extract_item_from_row(row, "critical items", str(action_file)) for row in section_tables["critical items"]]
    high_priority_items = [_extract_item_from_row(row, "high-priority items", str(action_file)) for row in section_tables["high-priority items"]]
    medium_priority_items = [
        _extract_item_from_row(row, "medium-priority items", str(action_file)) for row in section_tables["medium-priority items"]
    ]

    if not critical_risks:
        critical_risks = _extract_list_section_items(review_lines, "Critical Risks", "critical", str(review_file))
    if not high_priority_items:
        high_priority_items = _extract_list_section_items(review_lines, "High-Priority Items", "high", str(review_file))
    if not medium_priority_items:
        medium_priority_items = _extract_list_section_items(review_lines, "Medium-Priority Items", "medium", str(review_file))

    all_items = _sorted_items([*critical_risks, *high_priority_items, *medium_priority_items])
    severity_counts = {
        "critical": sum(1 for item in all_items if item["severity"] == "critical"),
        "high": sum(1 for item in all_items if item["severity"] == "high"),
        "medium": sum(1 for item in all_items if item["severity"] == "medium"),
    }

    review_date = _extract_review_date(review_lines, review_frontmatter)
    emitted_at = f"{review_date}T00:00:00Z"

    review_corpus = "\n".join(review_lines)
    action_corpus = "\n".join(action_lines)
    affected_systems = sorted(set(match.group(1).lower() for match in _SYSTEM_CODE_RE.finditer(f"{review_corpus}\n{action_corpus}")))

    blocker_ids = _extract_blocker_ids(all_items, review_lines, action_lines)

    body = {
        "artifact_type": "review_signal_artifact",
        "schema_version": "1.0.0",
        "source_review_path": str(review_file),
        "source_action_tracker_path": str(action_file),
        "review_date": review_date,
        "system_scope": _extract_system_scope(review_file, review_lines, review_frontmatter),
        "overall_verdict": _extract_overall_verdict(review_lines),
        "critical_risks": _sorted_items(critical_risks),
        "high_priority_items": _sorted_items(high_priority_items),
        "medium_priority_items": _sorted_items(medium_priority_items),
        "blocker_flags": bool(blocker_ids),
        "blocker_ids": blocker_ids,
        "action_items": all_items,
        "severity_counts": severity_counts,
        "affected_systems": affected_systems,
        "extracted_reason_codes": sorted(set(_REASON_CODE_RE.findall(f"{review_corpus}\n{action_corpus}"))),
        "emitted_at": emitted_at,
        "provenance": {
            "parser": "review_parsing_engine",
            "deterministic_hash_basis": "canonical-json-sha256",
            "source_review_hash": _canonical_hash({"path": str(review_file), "content": review_text}),
            "source_action_tracker_hash": _canonical_hash({"path": str(action_file), "content": action_text}),
        },
    }

    body["review_signal_id"] = f"rsv-{_canonical_hash(body)[:16]}"
    _validate_review_signal_artifact(body)
    return body


__all__ = [
    "ReviewParsingEngineError",
    "parse_review_to_signal",
]
