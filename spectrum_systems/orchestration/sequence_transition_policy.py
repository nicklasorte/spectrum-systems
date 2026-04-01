"""Authoritative fail-closed transition policy for the 3-slice sequential trust path."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

SEQUENCE_STATES = {
    "admitted",
    "executing_slice_1",
    "executing_slice_2",
    "executing_slice_3",
    "review_pending",
    "remediation_pending",
    "certification_pending",
    "promoted",
    "blocked",
    "frozen",
}

_ALLOWED: dict[str, set[str]] = {
    "admitted": {"executing_slice_1", "blocked", "frozen"},
    "executing_slice_1": {"executing_slice_2", "blocked", "frozen"},
    "executing_slice_2": {"executing_slice_3", "blocked", "frozen"},
    "executing_slice_3": {"review_pending", "blocked", "frozen"},
    "review_pending": {"remediation_pending", "certification_pending", "blocked", "frozen"},
    "remediation_pending": {"certification_pending", "blocked", "frozen"},
    "certification_pending": {"promoted", "blocked", "frozen"},
    "promoted": {"promoted"},
    "blocked": {"blocked", "frozen"},
    "frozen": {"frozen"},
}


@dataclass(frozen=True)
class SequenceTransitionDecision:
    allowed: bool
    reason: str | None = None


def _path_exists(value: Any) -> bool:
    return isinstance(value, str) and value != "" and Path(value).is_file()


def _has_traceability(manifest: dict[str, Any]) -> bool:
    trace_id = manifest.get("sequence_trace_id")
    lineage = manifest.get("sequence_lineage")
    return isinstance(trace_id, str) and trace_id and isinstance(lineage, list) and bool(lineage)


def _reports_count(manifest: dict[str, Any]) -> int:
    reports = manifest.get("execution_report_paths")
    if not isinstance(reports, list):
        return 0
    return sum(1 for item in reports if _path_exists(item))


def _has_failure_binding_enforcement(manifest: dict[str, Any]) -> tuple[bool, str | None]:
    payload = manifest.get("failure_binding_enforcement")
    if not isinstance(payload, dict):
        return False, "promotion requires failure_binding_enforcement evidence"
    required = (
        "severity_qualified_failure_count",
        "bound_failure_count",
        "missing_failure_bindings",
        "eval_update_refs",
        "policy_update_refs",
        "transition_enforcement_refs",
        "learning_authority_applied",
    )
    for field in required:
        if field not in payload:
            return False, f"promotion requires failure_binding_enforcement.{field}"
    if not isinstance(payload["severity_qualified_failure_count"], int) or payload["severity_qualified_failure_count"] < 0:
        return False, "failure_binding_enforcement.severity_qualified_failure_count must be integer >= 0"
    if not isinstance(payload["bound_failure_count"], int) or payload["bound_failure_count"] < 0:
        return False, "failure_binding_enforcement.bound_failure_count must be integer >= 0"
    if payload["bound_failure_count"] < payload["severity_qualified_failure_count"]:
        return False, "missing severity-qualified failure binding evidence"
    missing = payload["missing_failure_bindings"]
    if not isinstance(missing, list):
        return False, "failure_binding_enforcement.missing_failure_bindings must be a list"
    if missing:
        return False, "missing severity-qualified failure binding evidence"
    for field in ("eval_update_refs", "policy_update_refs", "transition_enforcement_refs"):
        refs = payload[field]
        if not isinstance(refs, list) or not refs or not all(isinstance(item, str) and item for item in refs):
            return False, f"failure_binding_enforcement.{field} must be a non-empty list of refs"
    if payload.get("learning_authority_applied") is not True:
        return False, "learning authority not applied on promotion surface"
    return True, None


def evaluate_sequence_transition(manifest: dict[str, Any], target_state: str) -> SequenceTransitionDecision:
    current_state = manifest.get("current_state")
    if not isinstance(current_state, str) or current_state not in SEQUENCE_STATES:
        return SequenceTransitionDecision(False, "unknown current sequence state")
    if target_state not in SEQUENCE_STATES:
        return SequenceTransitionDecision(False, "unknown target sequence state")
    if target_state not in _ALLOWED[current_state]:
        return SequenceTransitionDecision(False, f"illegal transition: {current_state} -> {target_state}")

    if current_state != target_state and not _has_traceability(manifest):
        return SequenceTransitionDecision(False, "missing required sequence traceability")

    if target_state == "executing_slice_1":
        if not _path_exists(manifest.get("roadmap_artifact_path")):
            return SequenceTransitionDecision(False, "missing required artifact: roadmap_artifact_path")
    elif target_state == "executing_slice_2":
        if _reports_count(manifest) < 1:
            return SequenceTransitionDecision(False, "slice_2 requires slice_1 execution evidence")
    elif target_state == "executing_slice_3":
        if _reports_count(manifest) < 2:
            return SequenceTransitionDecision(False, "slice_3 requires slice_1 and slice_2 execution evidence")
    elif target_state == "review_pending":
        if _reports_count(manifest) < 3:
            return SequenceTransitionDecision(False, "review_pending requires 3 completed slice execution artifacts")
    elif target_state == "remediation_pending":
        reviews = manifest.get("implementation_review_paths")
        if not isinstance(reviews, list) or not reviews:
            return SequenceTransitionDecision(False, "remediation_pending requires review artifacts")
    elif target_state == "certification_pending":
        review_paths = manifest.get("implementation_review_paths")
        if not isinstance(review_paths, list) or not review_paths:
            return SequenceTransitionDecision(False, "certification_pending requires review artifacts")
    elif target_state == "promoted":
        if manifest.get("certification_status") != "passed":
            return SequenceTransitionDecision(False, "promotion requires certification_status=passed")
        if not _path_exists(manifest.get("certification_record_path")):
            return SequenceTransitionDecision(False, "promotion requires certification_record_path")
        if manifest.get("decision_blocked") is True:
            return SequenceTransitionDecision(False, "promotion blocked by decision_blocked=true")
        if manifest.get("control_allow_promotion") is not True:
            return SequenceTransitionDecision(False, "promotion requires explicit control_allow_promotion=true")
        valid_binding, reason = _has_failure_binding_enforcement(manifest)
        if not valid_binding:
            return SequenceTransitionDecision(False, reason)

    if target_state in {"blocked", "frozen"}:
        issues = manifest.get("blocking_issues")
        if not isinstance(issues, list) or not issues:
            return SequenceTransitionDecision(False, f"{target_state} transition requires non-empty blocking_issues")

    return SequenceTransitionDecision(True)
