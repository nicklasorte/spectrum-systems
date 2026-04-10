"""Provider-aware normalization into governed findings artifacts."""

from __future__ import annotations

import re
from pathlib import Path

from spectrum_systems.modules.prompt_queue.queue_models import iso_now, utc_now
from spectrum_systems.modules.prompt_queue.review_parser import ParsedReview

PARSER_VERSION = "1.1.0"
_FILE_REF_RE = re.compile(r"`([^`]+\.[a-zA-Z0-9]+)`")
_SEVERITY_HINTS = ("critical", "high", "medium", "low")

FINDING_TYPE_ENUM = {
    "execution_status",
    "error_summary",
    "output_reference",
    "artifact_reference",
    "validation",
    "execution_mode",
}
SEVERITY_ENUM = {"info", "warning", "error", "ambiguous"}
_VALIDATION_STATUS_ENUM = {"valid", "invalid"}


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


def normalize_queue_step_findings(execution_result: dict) -> dict:
    """Normalize prompt_queue_execution_result into deterministic queue-step findings."""
    step_id = execution_result["step_id"]
    validation_status = "valid"
    findings: list[dict] = []

    status = execution_result["execution_status"]
    if status == "failure":
        findings.append(
            {
                "finding_id": f"{step_id}-status-failure",
                "finding_type": "execution_status",
                "severity": "error",
                "summary": "execution_status indicates failure",
                "details": execution_result.get("error_summary") or "Execution failure with no explicit summary.",
            }
        )

    error_summary = execution_result.get("error_summary")
    if error_summary:
        findings.append(
            {
                "finding_id": f"{step_id}-error-summary",
                "finding_type": "error_summary",
                "severity": "error",
                "summary": "error_summary present",
                "details": error_summary,
            }
        )

    output_reference = execution_result.get("output_reference")
    if not output_reference:
        findings.append(
            {
                "finding_id": f"{step_id}-output-missing",
                "finding_type": "output_reference",
                "severity": "ambiguous",
                "summary": "output_reference missing",
                "details": "Execution result is missing output_reference.",
            }
        )


    execution_mode = execution_result.get("execution_mode")
    if execution_mode == "simulated":
        findings.append(
            {
                "finding_id": f"{step_id}-execution-mode-simulated",
                "finding_type": "execution_mode",
                "severity": "info",
                "summary": "execution_mode is simulated",
                "details": "Simulated execution is non-production and cannot be treated as live execution evidence.",
            }
        )
    elif execution_mode != "live":
        findings.append(
            {
                "finding_id": f"{step_id}-execution-mode-unknown",
                "finding_type": "execution_mode",
                "severity": "error",
                "summary": "execution_mode is invalid",
                "details": "Execution result has an unsupported execution_mode value.",
            }
        )

    produced_refs = execution_result.get("produced_artifact_refs", [])
    if isinstance(produced_refs, list) and output_reference and output_reference not in produced_refs:
        findings.append(
            {
                "finding_id": f"{step_id}-output-unlisted",
                "finding_type": "artifact_reference",
                "severity": "info",
                "summary": "output_reference not included in produced_artifact_refs",
                "details": "Output reference is not present in produced_artifact_refs.",
            }
        )

    for finding in findings:
        if finding["finding_type"] not in FINDING_TYPE_ENUM:
            raise ValueError("Unsupported finding_type during normalization.")
        if finding["severity"] not in SEVERITY_ENUM:
            raise ValueError("Unsupported severity during normalization.")

    summary = {
        "error": sum(1 for finding in findings if finding["severity"] == "error"),
        "warning": sum(1 for finding in findings if finding["severity"] == "warning"),
        "ambiguous": sum(1 for finding in findings if finding["severity"] == "ambiguous"),
        "info": sum(1 for finding in findings if finding["severity"] == "info"),
    }

    if validation_status not in _VALIDATION_STATUS_ENUM:
        raise ValueError("Unsupported validation_status during normalization.")

    validation_refs = execution_result.get("validation_result_refs") or []
    if not isinstance(validation_refs, list) or not validation_refs:
        findings.append(
            {
                "finding_id": f"{step_id}-validation-missing",
                "finding_type": "validation",
                "severity": "error",
                "summary": "validation_result_refs missing",
                "details": "Decision cannot proceed without validation_result_record evidence.",
            }
        )
        summary["error"] += 1

    preflight_decision = execution_result.get("preflight_decision")
    if preflight_decision != "ALLOW":
        findings.append(
            {
                "finding_id": f"{step_id}-preflight-blocked",
                "finding_type": "validation",
                "severity": "error",
                "summary": "preflight decision is not ALLOW",
                "details": "Decision cannot proceed when preflight is BLOCK or missing.",
            }
        )
        summary["error"] += 1

    return {
        "step_id": step_id,
        "queue_id": execution_result.get("queue_id"),
        "trace_linkage": execution_result.get("trace_linkage"),
        "source_execution_result_artifact_id": execution_result["execution_result_artifact_id"],
        "review_evidence_ref": f"review_result_artifact:rqx-{step_id}",
        "validation_result_refs": validation_refs,
        "preflight_decision": preflight_decision,
        "findings": findings,
        "severity_summary": summary,
        "validation_status": validation_status,
    }


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
