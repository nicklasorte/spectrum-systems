"""Deterministic review markdown -> review_control_signal extraction."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from spectrum_systems.contracts import load_schema
from spectrum_systems.utils.deterministic_id import deterministic_id


class ReviewSignalExtractionError(ValueError):
    """Raised when a review markdown artifact cannot be deterministically parsed."""


_FRONTMATTER_PATTERN = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", re.DOTALL)
_REQUIRED_FRONTMATTER = (
    "module",
    "review_type",
    "review_date",
    "reviewer",
    "decision",
    "status",
)
_ALLOWED_REVIEW_TYPES = {"surgical", "failure", "batch_architecture", "hard_gate", "strategic"}
_SECTION_SPLIT = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_METADATA_TABLE_ROW = re.compile(r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|$")


def _normalize_review_type(value: str) -> str:
    raw = value.strip().lower()
    if raw in _ALLOWED_REVIEW_TYPES:
        return raw
    if any(token in raw for token in ("control", "certification", "replay", "pqx")):
        return "surgical"
    if "hard" in raw and "gate" in raw:
        return "hard_gate"
    if "architect" in raw or "batch" in raw or "checkpoint" in raw:
        return "batch_architecture"
    if "strateg" in raw or "program" in raw:
        return "strategic"
    if "fail" in raw or "incident" in raw:
        return "failure"
    raise ReviewSignalExtractionError("review_type must be one of surgical|failure|batch_architecture|hard_gate|strategic")


def _parse_frontmatter(markdown_text: str) -> dict[str, str]:
    match = _FRONTMATTER_PATTERN.match(markdown_text)
    if match is None:
        raise ReviewSignalExtractionError("missing YAML frontmatter block")
    values: dict[str, str] = {}
    for raw_line in match.group(1).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise ReviewSignalExtractionError(f"malformed frontmatter line: {raw_line!r}")
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key in values:
            raise ReviewSignalExtractionError(f"duplicate frontmatter key: {key}")
        values[key] = value
    for field in _REQUIRED_FRONTMATTER:
        if not values.get(field):
            raise ReviewSignalExtractionError(f"missing required frontmatter field: {field}")
    values["review_type"] = _normalize_review_type(values.get("review_type", ""))
    return values


def _parse_metadata_table(markdown_text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in markdown_text.splitlines():
        row = _METADATA_TABLE_ROW.match(line.strip())
        if row is None:
            continue
        key = row.group(1).strip().lower()
        value = row.group(2).strip()
        if key in {"field", "---"}:
            continue
        values[key] = value
    if not values:
        raise ReviewSignalExtractionError("missing YAML frontmatter block")
    mapped = {
        "module": "spectrum-systems",
        "review_type": values.get("review type", ""),
        "review_date": values.get("review date", ""),
        "reviewer": values.get("reviewer", ""),
        "decision": values.get("verdict", values.get("decision", "")).upper(),
        "status": values.get("status", "final"),
        "review_id": values.get("review id", ""),
    }
    for field in _REQUIRED_FRONTMATTER:
        if not mapped.get(field):
            raise ReviewSignalExtractionError(f"missing required review metadata field: {field}")
    mapped["review_type"] = _normalize_review_type(mapped["review_type"])
    return mapped


def _sections(markdown_text: str) -> dict[str, str]:
    match = _FRONTMATTER_PATTERN.match(markdown_text)
    body = markdown_text[match.end() :] if match else markdown_text
    headers = list(_SECTION_SPLIT.finditer(body))
    sections: dict[str, str] = {}
    for idx, header in enumerate(headers):
        start = header.end()
        end = headers[idx + 1].start() if idx + 1 < len(headers) else len(body)
        key = header.group(1).strip().lower()
        if key in sections:
            raise ReviewSignalExtractionError(f"duplicate markdown section heading: {key}")
        sections[key] = body[start:end].strip()
    return sections


def _extract_critical_findings(section_text: str) -> list[str]:
    findings: list[str] = []
    for line in section_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(("-", "*")):
            finding = stripped[1:].strip()
            if finding:
                findings.append(finding)
        elif stripped.startswith("### "):
            findings.append(stripped.removeprefix("### ").strip())
    return sorted(dict.fromkeys(findings))


def _resolve_gate_assessment(frontmatter: dict[str, str], findings: list[str]) -> str:
    explicit = str(frontmatter.get("gate_assessment") or "").strip().upper()
    if explicit:
        if explicit not in {"PASS", "FAIL", "CONDITIONAL"}:
            raise ReviewSignalExtractionError("gate_assessment must be PASS, FAIL, or CONDITIONAL when present")
        return explicit
    decision = frontmatter["decision"].strip().upper()
    if decision == "PASS":
        return "PASS"
    if decision == "FAIL":
        return "FAIL"
    if decision == "CONDITIONAL":
        return "CONDITIONAL"
    raise ReviewSignalExtractionError("frontmatter decision must be PASS, FAIL, or CONDITIONAL")


def _resolve_scale_recommendation(frontmatter: dict[str, str], gate_assessment: str) -> str:
    explicit = str(frontmatter.get("scale_recommendation") or "").strip().upper()
    if explicit:
        if explicit not in {"YES", "NO"}:
            raise ReviewSignalExtractionError("scale_recommendation must be YES or NO when present")
        return explicit
    return "NO" if gate_assessment == "FAIL" else "YES"


def extract_review_signal(review_markdown_path: str | Path) -> dict[str, Any]:
    """Extract deterministic governed ``review_control_signal`` from review markdown."""
    review_path = Path(review_markdown_path)
    markdown_text = review_path.read_text(encoding="utf-8")
    try:
        frontmatter = _parse_frontmatter(markdown_text)
    except ReviewSignalExtractionError as exc:
        if "missing YAML frontmatter block" not in str(exc):
            raise
        frontmatter = _parse_metadata_table(markdown_text)
    sections = _sections(markdown_text)
    critical_findings = _extract_critical_findings(sections.get("critical findings", ""))
    gate_assessment = _resolve_gate_assessment(frontmatter, critical_findings)
    scale_recommendation = _resolve_scale_recommendation(frontmatter, gate_assessment)
    confidence = 0.98 if gate_assessment == "PASS" else 0.25 if gate_assessment == "FAIL" else 0.6

    review_id = str(frontmatter.get("review_id") or "").strip()
    if not review_id:
        slug = review_path.stem.upper().replace(" ", "-")
        review_id = f"REV-{slug}"

    payload_seed = {
        "review_id": review_id,
        "review_type": frontmatter["review_type"],
        "review_date": frontmatter["review_date"],
        "decision": frontmatter["decision"],
        "critical_findings": critical_findings,
        "path": review_path.as_posix(),
    }
    payload_digest = hashlib.sha256(json.dumps(payload_seed, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    artifact_id = deterministic_id(prefix="rcs", namespace="review_control_signal", payload=payload_seed)
    signal = {
        "artifact_type": "review_control_signal",
        "schema_version": "1.1.0",
        "signal_id": artifact_id,
        "review_id": review_id,
        "review_type": frontmatter["review_type"],
        "gate_assessment": gate_assessment,
        "scale_recommendation": scale_recommendation,
        "critical_findings": critical_findings,
        "confidence": confidence,
        "trace_linkage": {
            "review_markdown_path": review_path.as_posix(),
            "source_digest_sha256": payload_digest,
            "review_artifact_path": review_path.as_posix().replace(".md", ".json"),
        },
    }
    validator = Draft202012Validator(load_schema("review_control_signal"))
    errors = sorted(validator.iter_errors(signal), key=lambda err: str(list(err.absolute_path)))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise ReviewSignalExtractionError(f"review_control_signal failed schema validation: {details}")
    return signal


__all__ = ["ReviewSignalExtractionError", "extract_review_signal"]
