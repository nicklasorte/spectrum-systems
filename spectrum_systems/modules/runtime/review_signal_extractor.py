"""Deterministic markdown review parsing into governed review control signals."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.utils.deterministic_id import deterministic_id


class ReviewSignalExtractionError(ValueError):
    """Raised when a review markdown artifact cannot be parsed fail-closed."""


_DATE_PATTERNS = (
    re.compile(r"\*\*Date:\*\*\s*(\d{4}-\d{2}-\d{2})"),
    re.compile(r"\*\*Review Date:\*\*\s*(\d{4}-\d{2}-\d{2})"),
    re.compile(r"^##\s*Date\s*$\n\s*(\d{4}-\d{2}-\d{2})", re.MULTILINE),
)


def _extract_first_heading(markdown: str) -> str:
    match = re.search(r"^#\s+(.+?)\s*$", markdown, re.MULTILINE)
    if not match:
        raise ReviewSignalExtractionError("malformed review: missing top-level heading")
    return match.group(1).strip()


def _extract_review_date(markdown: str) -> str:
    for pattern in _DATE_PATTERNS:
        match = pattern.search(markdown)
        if match:
            return match.group(1)
    raise ReviewSignalExtractionError("malformed review: missing deterministic review date")


def _extract_explicit(markdown: str, key: str, allowed: set[str]) -> str | None:
    pattern = re.compile(rf"{re.escape(key)}\s*[:\-]\s*([A-Z]+)", re.IGNORECASE)
    match = pattern.search(markdown)
    if not match:
        return None
    value = match.group(1).upper()
    if value in allowed:
        return value
    raise ReviewSignalExtractionError(f"malformed review: invalid {key} value '{value}'")


def _extract_critical_findings(markdown: str) -> list[str]:
    findings: list[str] = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if not stripped.startswith(("-", "*")):
            continue
        normalized = stripped.lstrip("-* ").strip()
        if not normalized:
            continue
        lower = normalized.lower()
        if any(token in lower for token in ("critical", "blocking", "high", "risk", "fail", "block")):
            findings.append(normalized)
    seen: set[str] = set()
    deduped: list[str] = []
    for finding in findings:
        if finding not in seen:
            seen.add(finding)
            deduped.append(finding)
    return deduped[:12]


def _infer_gate(markdown: str, findings: list[str]) -> str:
    explicit = _extract_explicit(markdown, "Gate Assessment", {"PASS", "FAIL", "CONDITIONAL"})
    if explicit is not None:
        return explicit
    lower = markdown.lower()
    if "blocking items" in lower or "critical contract violation" in lower:
        return "FAIL"
    if any("critical" in item.lower() or "blocking" in item.lower() for item in findings):
        return "FAIL"
    if "risk level" in lower or findings:
        return "CONDITIONAL"
    return "PASS"


def _infer_scale(markdown: str, gate: str) -> str:
    explicit = _extract_explicit(markdown, "Scale Recommendation", {"YES", "NO"})
    if explicit is not None:
        return explicit
    lower = markdown.lower()
    if gate == "FAIL":
        return "NO"
    if any(token in lower for token in ("block expansion", "do not advance", "highest-risk", "high risk")):
        return "NO"
    return "YES"


def extract_review_signal(review_markdown_path: str) -> dict[str, Any]:
    """Extract deterministic review_control_signal artifact from markdown review file."""
    review_path = Path(review_markdown_path)
    if not review_path.is_file():
        raise ReviewSignalExtractionError(f"review markdown not found: {review_markdown_path}")
    if review_path.suffix.lower() != ".md":
        raise ReviewSignalExtractionError("malformed review: expected markdown file")

    markdown = review_path.read_text(encoding="utf-8").strip()
    if not markdown:
        raise ReviewSignalExtractionError("malformed review: file is empty")

    review_type = _extract_first_heading(markdown)
    review_date = _extract_review_date(markdown)
    critical_findings = _extract_critical_findings(markdown)
    gate_assessment = _infer_gate(markdown, critical_findings)
    scale_recommendation = _infer_scale(markdown, gate_assessment)

    payload_seed = {
        "path": review_path.as_posix(),
        "review_date": review_date,
        "review_type": review_type,
        "gate_assessment": gate_assessment,
        "scale_recommendation": scale_recommendation,
        "critical_findings": critical_findings,
    }
    review_id = deterministic_id(prefix="review", namespace="review_control_signal", payload=payload_seed, digest_length=20)

    confidence = min(0.95, 0.5 + (0.05 * min(6, len(critical_findings))) + (0.1 if gate_assessment != "PASS" else 0.0))
    trace_hash = hashlib.sha256(markdown.encode("utf-8")).hexdigest()

    artifact = {
        "artifact_type": "review_control_signal",
        "schema_version": "1.0.0",
        "review_signal_id": deterministic_id(
            prefix="rcs",
            namespace="review_control_signal",
            payload={"review_id": review_id, "trace_hash": trace_hash},
            digest_length=20,
        ),
        "review_id": review_id,
        "review_type": review_type,
        "gate_assessment": gate_assessment,
        "scale_recommendation": scale_recommendation,
        "critical_findings": critical_findings,
        "confidence": round(confidence, 4),
        "trace_linkage": {
            "source_review_path": review_path.as_posix(),
            "source_hash": trace_hash,
            "review_date": review_date,
        },
    }
    try:
        validate_artifact(artifact, "review_control_signal")
    except Exception as exc:  # pragma: no cover
        raise ReviewSignalExtractionError(f"extracted review signal failed contract validation: {exc}") from exc
    return artifact
