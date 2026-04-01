"""Deterministic review markdown -> review_control_signal extraction."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema


class ReviewSignalExtractionError(ValueError):
    """Raised when review markdown cannot be deterministically parsed into control signal."""


_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
_BULLET_RE = re.compile(r"^\s*-\s+", re.MULTILINE)
_ALLOWED_GATE = {"PASS", "FAIL", "CONDITIONAL"}
_ALLOWED_SCALE = {"YES", "NO"}


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _extract_frontmatter(markdown: str) -> dict[str, str]:
    match = _FRONTMATTER_RE.match(markdown)
    if not match:
        raise ReviewSignalExtractionError("review markdown must begin with YAML frontmatter")

    frontmatter = match.group(1)
    parsed: dict[str, str] = {}
    for raw in frontmatter.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise ReviewSignalExtractionError(f"malformed frontmatter line: {raw!r}")
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key:
            raise ReviewSignalExtractionError("frontmatter key cannot be empty")
        if key in parsed:
            raise ReviewSignalExtractionError(f"duplicate frontmatter key: {key}")
        parsed[key] = value
    return parsed


def _extract_section(markdown: str, heading: str) -> str:
    marker = f"## {heading}\n"
    start = markdown.find(marker)
    if start == -1:
        return ""
    start += len(marker)
    tail = markdown[start:]
    next_heading = tail.find("\n## ")
    return tail[:next_heading].strip() if next_heading != -1 else tail.strip()


def _normalize_gate(frontmatter: dict[str, str]) -> str:
    raw = (frontmatter.get("decision") or frontmatter.get("gate_assessment") or "").strip().upper()
    if raw in _ALLOWED_GATE:
        return raw
    normalized = (frontmatter.get("normalized_decision") or "").strip().lower()
    if normalized in {"pass", "approved"}:
        return "PASS"
    if normalized in {"fail", "rejected"}:
        return "FAIL"
    if normalized in {"pass_with_fixes", "conditional", "changes_requested"}:
        return "CONDITIONAL"
    raise ReviewSignalExtractionError("frontmatter decision must resolve to PASS|FAIL|CONDITIONAL")


def _normalize_scale(frontmatter: dict[str, str], markdown: str) -> str:
    raw = (frontmatter.get("scale_recommendation") or "").strip().upper()
    if raw in _ALLOWED_SCALE:
        return raw

    body = markdown.lower()
    if "block expansion" in body or "expansion is blocked" in body:
        return "NO"
    if "allow expansion" in body or "scale-up approved" in body:
        return "YES"

    gate = _normalize_gate(frontmatter)
    return "NO" if gate == "FAIL" else "YES"


def _extract_critical_findings(markdown: str) -> list[str]:
    section = _extract_section(markdown, "Critical Findings")
    if not section:
        return []
    findings: list[str] = []
    for line in section.splitlines():
        if _BULLET_RE.match(line):
            normalized = _BULLET_RE.sub("", line).strip()
            if normalized:
                findings.append(normalized)
    return list(dict.fromkeys(findings))


def _confidence(frontmatter: dict[str, str]) -> float:
    trust = (frontmatter.get("trust_assessment") or "").strip().lower()
    mapping = {"high": 0.9, "medium": 0.7, "low": 0.5}
    if trust in mapping:
        return mapping[trust]
    return 0.6


def extract_review_signal(review_markdown_path: str | Path) -> dict[str, Any]:
    """Extract a governed review_control_signal artifact from canonical review markdown."""
    path = Path(review_markdown_path)
    try:
        markdown = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ReviewSignalExtractionError(f"cannot read review markdown: {path}") from exc

    frontmatter = _extract_frontmatter(markdown)
    required = ("review_type", "review_date")
    missing = [field for field in required if not frontmatter.get(field)]
    if missing:
        raise ReviewSignalExtractionError(f"missing required frontmatter fields: {', '.join(missing)}")

    review_id = (frontmatter.get("review_id") or "").strip()
    if not review_id:
        review_date = frontmatter["review_date"].strip()
        review_type = frontmatter["review_type"].strip()
        review_id = f"RCS-{_hash_text(f'{path.as_posix()}|{review_date}|{review_type}')[:16].upper()}"

    gate_assessment = _normalize_gate(frontmatter)
    scale_recommendation = _normalize_scale(frontmatter, markdown)
    critical_findings = _extract_critical_findings(markdown)

    trace_source = f"{path.as_posix()}|{frontmatter.get('review_date','')}|{review_id}"
    trace_linkage = {
        "source_type": "review_markdown",
        "source_path": path.as_posix(),
        "source_digest": _hash_text(markdown),
        "trace_id": f"TRC-{_hash_text(trace_source)[:16].upper()}",
    }

    artifact = {
        "artifact_type": "review_control_signal",
        "schema_version": "1.0.0",
        "artifact_id": _hash_text(
            _canonical_json(
                {
                    "review_id": review_id,
                    "gate_assessment": gate_assessment,
                    "scale_recommendation": scale_recommendation,
                    "source_digest": trace_linkage["source_digest"],
                }
            )
        ),
        "review_id": review_id,
        "review_type": frontmatter["review_type"].strip(),
        "gate_assessment": gate_assessment,
        "scale_recommendation": scale_recommendation,
        "critical_findings": critical_findings,
        "confidence": _confidence(frontmatter),
        "trace_linkage": trace_linkage,
    }

    validator = Draft202012Validator(load_schema("review_control_signal"), format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(artifact), key=lambda err: str(list(err.absolute_path)))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise ReviewSignalExtractionError(f"review_control_signal failed validation: {details}")

    return artifact
