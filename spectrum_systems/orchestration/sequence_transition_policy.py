"""Authoritative fail-closed transition policy for the 3-slice sequential trust path."""

from __future__ import annotations

from dataclasses import dataclass
import json
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


def _gate_proof_passes(manifest: dict[str, Any]) -> tuple[bool, str | None]:
    gate = manifest.get("control_loop_gate_proof")
    if not isinstance(gate, dict):
        refs = manifest.get("done_certification_input_refs")
        pack_ref = refs.get("certification_pack_ref") if isinstance(refs, dict) else None
        if isinstance(pack_ref, str) and pack_ref:
            pack_path = Path(pack_ref)
            if pack_path.is_file():
                try:
                    gate = json.loads(pack_path.read_text(encoding="utf-8")).get("gate_proof_evidence")
                except (OSError, json.JSONDecodeError):
                    return False, "promotion requires readable certification pack gate_proof_evidence"
    if not isinstance(gate, dict):
        return False, "promotion requires control_loop_gate_proof"
    required_true = (
        "severity_linkage_complete",
        "deterministic_transition_consumption",
        "policy_caused_action_observed",
        "recurrence_prevention_linked",
        "failure_binding_required_for_progression",
        "missing_binding_blocks_progression",
        "advisory_only_learning_rejected",
        "transition_policy_consumes_binding_deterministically",
    )
    for field in required_true:
        if gate.get(field) is not True:
            return False, f"promotion requires gate proof field {field}=true"
    for refs_key in (
        "severity_linkage_refs",
        "transition_consumption_refs",
        "policy_action_refs",
        "recurrence_prevention_refs",
    ):
        refs = gate.get(refs_key)
        if not isinstance(refs, list) or not refs:
            return False, f"promotion requires gate proof evidence in {refs_key}"
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
        required_judgments = manifest.get("required_judgments")
        if isinstance(required_judgments, list) and "artifact_release_readiness" in required_judgments:
            required_paths = {
                "judgment_record_path": manifest.get("judgment_record_path"),
                "judgment_application_record_path": manifest.get("judgment_application_record_path"),
                "judgment_eval_result_path": manifest.get("judgment_eval_result_path"),
            }
            for field, path in required_paths.items():
                if not _path_exists(path):
                    return SequenceTransitionDecision(False, f"promotion requires {field} when artifact_release_readiness judgment is required")
        if manifest.get("certification_status") != "passed":
            return SequenceTransitionDecision(False, "promotion requires certification_status=passed")
        if not _path_exists(manifest.get("certification_record_path")):
            return SequenceTransitionDecision(False, "promotion requires certification_record_path")
        gate_passed, gate_error = _gate_proof_passes(manifest)
        if not gate_passed:
            return SequenceTransitionDecision(False, gate_error)
        if manifest.get("decision_blocked") is True:
            return SequenceTransitionDecision(False, "promotion blocked by decision_blocked=true")
        if manifest.get("control_allow_promotion") is not True:
            return SequenceTransitionDecision(False, "promotion requires explicit control_allow_promotion=true")

    if target_state in {"blocked", "frozen"}:
        issues = manifest.get("blocking_issues")
        if not isinstance(issues, list) or not issues:
            return SequenceTransitionDecision(False, f"{target_state} transition requires non-empty blocking_issues")

    return SequenceTransitionDecision(True)
