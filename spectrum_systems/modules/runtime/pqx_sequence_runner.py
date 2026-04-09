"""Deterministic, fail-closed sequential PQX slice runner with persisted resumable state."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.pqx_backbone import LEGACY_EXECUTION_ROADMAP_PATH, parse_system_roadmap
from spectrum_systems.modules.prompt_queue.queue_models import iso_now, utc_now
from spectrum_systems.modules.runtime.repo_review_snapshot_store import (
    RepoReviewSnapshotStoreError,
    validate_repo_review_snapshot,
)
from spectrum_systems.modules.runtime.pqx_slice_runner import (
    confirm_slice_completion_after_enforcement_allow,
    run_pqx_slice,
)
from spectrum_systems.modules.runtime.repo_write_lineage_guard import RepoWriteLineageGuardError, validate_repo_write_lineage
from spectrum_systems.modules.runtime.tpa_complexity_governance import (
    build_complexity_budget,
    build_complexity_trend,
    build_control_priority_signal,
    calculate_tpa_priority_score,
    build_simplification_campaign,
    build_tpa_observability_consumer_record,
    build_complexity_budget_recalibration_record,
    enforce_budget_trend_control,
)
from spectrum_systems.modules.runtime.pqx_bundle_state import (
    PQXBundleStateError,
    block_step as bundle_block_step,
    initialize_bundle_state,
    load_bundle_state,
    mark_bundle_complete,
    mark_step_complete,
    save_bundle_state,
)
from spectrum_systems.modules.governance.tpa_policy_composition import (
    load_tpa_policy_composition,
    resolve_tpa_policy_decision,
)
from spectrum_systems.modules.governance.tpa_scope_policy import is_tpa_required, load_tpa_scope_policy
from spectrum_systems.utils.deterministic_id import canonical_json


class PQXSequenceRunnerError(ValueError):
    """Raised when sequence-run orchestration fails closed."""


SliceExecutor = Callable[[dict], dict]
_TPA_PHASE_BY_SUFFIX = {"P": "plan", "B": "build", "S": "simplify", "G": "gate"}


def _default_control_surface_gap_visibility() -> dict:
    return {
        "control_surface_gap_packet_ref": None,
        "control_surface_gap_packet_consumed": False,
        "prioritized_control_surface_gaps": [],
        "pqx_gap_work_items": [],
        "control_surface_gap_influence": {
            "influenced_execution_block": False,
            "influenced_next_step_selection": False,
            "influenced_priority_ordering": False,
            "influenced_transition_decision": False,
            "reason_codes": [],
            "control_surface_blocking_reason_refs": [],
        },
    }


def _validate_control_surface_gap_visibility(visibility: dict) -> dict:
    if not isinstance(visibility, dict):
        raise PQXSequenceRunnerError("control_surface_gap_visibility must be an object")
    required_top = (
        "control_surface_gap_packet_ref",
        "control_surface_gap_packet_consumed",
        "prioritized_control_surface_gaps",
        "pqx_gap_work_items",
        "control_surface_gap_influence",
    )
    missing = [field for field in required_top if field not in visibility]
    if missing:
        raise PQXSequenceRunnerError(
            f"control_surface_gap_visibility missing required fields: {', '.join(missing)}"
        )
    influence = visibility["control_surface_gap_influence"]
    if not isinstance(influence, dict):
        raise PQXSequenceRunnerError("control_surface_gap_visibility.control_surface_gap_influence must be an object")
    return visibility


def _validate_slice_requests(slice_requests: list[dict]) -> None:
    if not isinstance(slice_requests, list) or not slice_requests:
        raise PQXSequenceRunnerError("slice_requests must be a non-empty ordered list.")

    seen: set[str] = set()
    for index, request in enumerate(slice_requests):
        if not isinstance(request, dict):
            raise PQXSequenceRunnerError(f"slice request at index {index} must be an object.")
        slice_id = request.get("slice_id")
        trace_id = request.get("trace_id")
        if not isinstance(slice_id, str) or not slice_id:
            raise PQXSequenceRunnerError(f"slice request at index {index} missing required slice_id.")
        if not isinstance(trace_id, str) or not trace_id:
            raise PQXSequenceRunnerError(f"slice request '{slice_id}' missing required trace_id.")
        if slice_id in seen:
            raise PQXSequenceRunnerError(f"duplicate slice_id not allowed: {slice_id}")
        seen.add(slice_id)
    _validate_tpa_grouping(slice_requests)


def _parse_tpa_slice_id(slice_id: str) -> tuple[str, str | None]:
    parts = slice_id.split("-")
    if len(parts) == 3 and parts[0] == "AI" and parts[1].isdigit() and parts[2] in _TPA_PHASE_BY_SUFFIX:
        return f"AI-{parts[1]}", _TPA_PHASE_BY_SUFFIX[parts[2]]
    return slice_id, None


def _validate_tpa_grouping(slice_requests: list[dict]) -> None:
    grouped: dict[str, dict[str, int]] = {}
    for index, request in enumerate(slice_requests):
        step_id, phase = _parse_tpa_slice_id(request["slice_id"])
        if phase is None:
            continue
        grouped.setdefault(step_id, {})[phase] = index

    required_order = ("plan", "build", "simplify", "gate")
    for step_id, phase_positions in grouped.items():
        missing = [phase for phase in required_order if phase not in phase_positions]
        if missing:
            raise PQXSequenceRunnerError(
                f"TPA slice group for {step_id} missing required phases: {', '.join(missing)}"
            )
        order = [phase_positions[phase] for phase in required_order]
        if order != sorted(order):
            raise PQXSequenceRunnerError(
                f"TPA slice group for {step_id} must be ordered plan->build->simplify->gate"
            )


def _canonical_step_id(slice_id: str) -> str:
    tpa_step_id, tpa_phase = _parse_tpa_slice_id(slice_id)
    if tpa_phase is not None:
        return tpa_step_id
    if slice_id.startswith("fix-step:"):
        return slice_id
    if slice_id.startswith("AI-"):
        return slice_id
    if slice_id == "PQX-QUEUE-01":
        return "AI-01"
    if slice_id == "PQX-QUEUE-02":
        return "AI-02"
    return "TRUST-01"


def _admit_slice_batch(
    *, slice_requests: list[dict], already_completed_slice_ids: list[str], enforce_dependencies: bool = True
) -> dict:
    """Fail-closed admission for a bounded ordered sequential batch."""

    rows = parse_system_roadmap(LEGACY_EXECUTION_ROADMAP_PATH)
    row_by_id = {row.step_id: row for row in rows}
    already_completed_canonical = {_canonical_step_id(slice_id) for slice_id in already_completed_slice_ids}
    admitted_prefix: set[str] = set()
    violations: list[dict[str, str]] = []

    for request in slice_requests:
        slice_id = request["slice_id"]
        canonical_step_id = _canonical_step_id(slice_id)
        row = row_by_id.get(canonical_step_id)
        if row is None:
            if slice_id.startswith("fix-step:"):
                admitted_prefix.add(canonical_step_id)
                continue
            violations.append(
                {
                    "code": "MISSING_STEP_ID",
                    "slice_id": slice_id,
                    "step_id": canonical_step_id,
                    "message": "slice references step_id missing from authoritative roadmap",
                }
            )
            continue

        if enforce_dependencies:
            for dependency in row.dependencies:
                if dependency in already_completed_canonical or dependency in admitted_prefix:
                    continue
                violations.append(
                    {
                        "code": "DEPENDENCY_UNSATISFIED",
                        "slice_id": slice_id,
                        "step_id": canonical_step_id,
                        "dependency": dependency,
                        "message": "required dependency must be completed already or appear earlier in admitted batch",
                    }
                )
        admitted_prefix.add(canonical_step_id)

    if violations:
        raise PQXSequenceRunnerError(
            "slice batch admission failed closed: "
            + json.dumps(
                {
                    "admission_status": "rejected",
                    "violation_count": len(violations),
                    "violations": violations,
                },
                sort_keys=True,
            )
        )

    return {
        "admission_status": "admitted",
        "admitted_slice_ids": [entry["slice_id"] for entry in slice_requests],
        "admitted_canonical_step_ids": [_canonical_step_id(entry["slice_id"]) for entry in slice_requests],
        "already_completed_slice_ids": sorted(set(already_completed_slice_ids)),
        "violations": [],
    }


def _canonical_hash(payload: Any) -> str:
    try:
        encoded = canonical_json(payload)
    except TypeError as exc:
        raise PQXSequenceRunnerError(f"payload must be JSON-serializable for deterministic hashing: {exc}") from exc
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _build_admission_preflight_artifact(
    *,
    queue_run_id: str,
    run_id: str,
    trace_id: str,
    slice_requests: list[dict],
    already_completed_slice_ids: list[str],
    enforce_dependencies: bool,
) -> dict[str, Any]:
    admission = _admit_slice_batch(
        slice_requests=slice_requests,
        already_completed_slice_ids=already_completed_slice_ids,
        enforce_dependencies=enforce_dependencies,
    )
    admitted_snapshot = {
        "slice_requests": deepcopy(slice_requests),
        "admitted_slice_ids": admission["admitted_slice_ids"],
        "admitted_canonical_step_ids": admission["admitted_canonical_step_ids"],
        "enforce_dependencies": enforce_dependencies,
    }
    admitted_hash = _canonical_hash(admitted_snapshot)
    admission_id = f"pqx-admission-{admitted_hash[:16]}"
    return {
        "artifact_type": "pqx_admission_preflight_artifact",
        "schema_version": "1.0.0",
        "admission_id": admission_id,
        "queue_run_id": queue_run_id,
        "run_id": run_id,
        "trace_id": trace_id,
        "admission_status": "admitted",
        "admitted_input_hash": admitted_hash,
        "admitted_input_snapshot": admitted_snapshot,
        "admission_result": admission,
    }


def _build_replayable_run_snapshot(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "admitted_input_hash": state.get("admitted_input_hash"),
        "admitted_input_snapshot": deepcopy(state.get("admitted_input_snapshot")),
        "execution_history": deepcopy(state.get("execution_history", [])),
        "completed_slice_ids": list(state.get("completed_slice_ids", [])),
        "failed_slice_ids": list(state.get("failed_slice_ids", [])),
        "status": state.get("status"),
        "termination_reason": state.get("termination_reason"),
        "blocked_reason": state.get("blocked_reason"),
    }


def _build_run_fingerprint(state: dict[str, Any]) -> dict[str, Any]:
    decision_sequence = [
        {"slice_id": row.get("slice_id"), "status": row.get("status"), "error": row.get("error")}
        for row in state.get("execution_history", [])
        if isinstance(row, dict)
    ]
    payload = {
        "requested_slice_ids": list(state.get("requested_slice_ids", [])),
        "completed_slice_ids": list(state.get("completed_slice_ids", [])),
        "failed_slice_ids": list(state.get("failed_slice_ids", [])),
        "decision_sequence": decision_sequence,
        "stopping_slice_id": next((row.get("slice_id") for row in state.get("execution_history", []) if row.get("status") == "failed"), None),
        "termination_reason": state.get("termination_reason"),
        "final_status": state.get("status"),
    }
    return {
        "fingerprint_hash": _canonical_hash(payload),
        "decision_sequence": decision_sequence,
        "stopping_slice_id": payload["stopping_slice_id"],
    }


def _validate_trace_completeness(state: dict[str, Any]) -> None:
    for row in state.get("execution_history", []):
        if not isinstance(row, dict):
            raise PQXSequenceRunnerError("execution_history rows must be objects")
        if not isinstance(row.get("execution_ref"), str) or not row["execution_ref"]:
            raise PQXSequenceRunnerError("trace completeness failed: execution_ref required")
        if row.get("status") not in {"success", "failed"}:
            raise PQXSequenceRunnerError("trace completeness failed: unsupported execution_history status")
        required_keys = (
            "slice_execution_record_ref",
            "certification_ref",
            "audit_bundle_ref",
            "control_surface_gap_visibility",
            "started_at",
            "completed_at",
        )
        for key in required_keys:
            if key not in row:
                raise PQXSequenceRunnerError(f"trace completeness failed: slice missing required key {key}")


def _set_termination_reason(state: dict[str, Any], reason: str) -> None:
    state["termination_reason"] = reason
    state["run_fingerprint"] = _build_run_fingerprint(state)
    state["replayable_run_snapshot"] = _build_replayable_run_snapshot(state)


def _build_batch_result(state: dict) -> dict:
    history_by_slice = {row.get("slice_id"): row for row in state.get("execution_history", []) if isinstance(row, dict)}
    requested = list(state.get("requested_slice_ids", []))
    completed = set(state.get("completed_slice_ids", []))
    failed = set(state.get("failed_slice_ids", []))
    ordered_statuses: list[dict[str, str]] = []
    for slice_id in requested:
        if slice_id in completed:
            status = "completed"
        elif slice_id in failed:
            status = "failed"
        else:
            status = "pending"
        ordered_statuses.append({"slice_id": slice_id, "status": status})

    stopping_slice_id = None
    for row in state.get("execution_history", []):
        if row.get("status") == "failed":
            stopping_slice_id = row.get("slice_id")
            break

    if state.get("status") == "blocked" and stopping_slice_id:
        stopping_error = str(history_by_slice.get(stopping_slice_id, {}).get("error") or state.get("blocked_reason") or "")
        stopped_status = "require_review" if "review" in stopping_error.lower() else "blocked"
        for row in ordered_statuses:
            if row["slice_id"] == stopping_slice_id:
                row["status"] = stopped_status
                break

    overall_status = "completed" if state.get("status") == "completed" else "stopped"
    return {
        "overall_batch_status": overall_status,
        "per_slice_statuses": ordered_statuses,
        "stopping_slice_id": stopping_slice_id,
        "completed_step_ids": list(state.get("completed_slice_ids", [])),
        "pending_step_ids": [row["slice_id"] for row in ordered_statuses if row["status"] == "pending"],
        "termination_reason": state.get("termination_reason"),
        "decision_sequence": deepcopy(state.get("run_fingerprint", {}).get("decision_sequence", [])),
        "final_outcome": state.get("status"),
        "run_fingerprint_hash": state.get("run_fingerprint", {}).get("fingerprint_hash"),
    }


def _build_tpa_slice_artifact(
    *,
    run_id: str,
    trace_id: str,
    slice_id: str,
    produced_at: str,
    artifact_payload: dict[str, Any],
    tpa_mode: str = "full",
) -> dict[str, Any]:
    step_id, phase = _parse_tpa_slice_id(slice_id)
    if phase is None:
        raise PQXSequenceRunnerError("TPA artifact requested for non-TPA slice id")
    artifact = {
        "artifact_type": "tpa_slice_artifact",
        "schema_version": "1.2.0",
        "artifact_id": f"tpa:{run_id}:{slice_id}",
        "run_id": run_id,
        "trace_id": trace_id,
        "slice_id": slice_id,
        "step_id": step_id,
        "phase": phase,
        "tpa_mode": tpa_mode,
        "produced_at": produced_at,
        "artifact": artifact_payload,
    }
    try:
        validate_artifact(artifact, "tpa_slice_artifact")
    except Exception as exc:
        raise PQXSequenceRunnerError(f"invalid TPA {phase} artifact for {slice_id}: {exc}") from exc
    return artifact


_REQUIRED_COMPLEXITY_SIGNAL_KEYS = (
    "files_changed_count",
    "lines_added",
    "lines_removed",
    "net_line_delta",
    "functions_added_count",
    "functions_removed_count",
    "helpers_added_count",
    "helpers_removed_count",
    "wrappers_collapsed_count",
    "deletions_count",
    "public_surface_delta_count",
    "approximate_max_nesting_delta",
    "approximate_branching_delta",
    "abstraction_added_count",
    "abstraction_removed_count",
)


def _normalized_complexity_signals(payload: dict[str, Any], *, field_name: str) -> dict[str, int]:
    signals = payload.get(field_name)
    if not isinstance(signals, dict):
        raise PQXSequenceRunnerError(f"TPA {payload.get('artifact_kind', 'unknown')} requires {field_name} object")
    missing = [key for key in _REQUIRED_COMPLEXITY_SIGNAL_KEYS if key not in signals]
    if missing:
        raise PQXSequenceRunnerError(f"TPA complexity signals missing required fields: {', '.join(missing)}")
    normalized: dict[str, int] = {}
    for key in _REQUIRED_COMPLEXITY_SIGNAL_KEYS:
        value = signals.get(key)
        if not isinstance(value, int):
            raise PQXSequenceRunnerError(f"TPA complexity signal {key} must be integer")
        normalized[key] = value
    if normalized["net_line_delta"] != normalized["lines_added"] - normalized["lines_removed"]:
        raise PQXSequenceRunnerError("TPA complexity signal net_line_delta must equal lines_added-lines_removed")
    return normalized


def _complexity_delta(build_signals: dict[str, int], simplify_signals: dict[str, int]) -> dict[str, int]:
    return {key: simplify_signals[key] - build_signals[key] for key in _REQUIRED_COMPLEXITY_SIGNAL_KEYS}


def _complexity_score(signals: dict[str, int]) -> int:
    return (
        (signals["lines_added"] - signals["lines_removed"])
        + signals["helpers_added_count"] * 2
        + signals["functions_added_count"] * 2
        + signals["abstraction_added_count"] * 3
        + signals["public_surface_delta_count"] * 3
        + signals["approximate_max_nesting_delta"] * 2
        + signals["approximate_branching_delta"] * 2
        - signals["helpers_removed_count"] * 2
        - signals["functions_removed_count"] * 2
        - signals["abstraction_removed_count"] * 3
        - signals["wrappers_collapsed_count"] * 2
        - signals["deletions_count"] * 2
    )


def _deterministic_selection_from_signals(
    *, build_signals: dict[str, int], simplify_signals: dict[str, int], simplicity_decision: str
) -> str:
    if simplicity_decision == "block":
        return "pass_1_build"
    build_score = _complexity_score(build_signals)
    simplify_score = _complexity_score(simplify_signals)
    return "pass_2_simplify" if simplify_score <= build_score else "pass_1_build"


def _build_tpa_observability_summary(
    *,
    run_id: str,
    trace_id: str,
    step_id: str,
    generated_at: str,
    gate_payload: dict[str, Any],
    plan_payload: dict[str, Any],
    bypass_signals: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    selected = gate_payload["selected_pass"]
    simplify_win = selected == "pass_2_simplify"
    regression = bool(gate_payload["complexity_regression_gate"]["regression_detected"])
    delete_count = int(gate_payload["selection_metrics"]["simplify"]["deletions_count"])
    modules = plan_payload.get("modules_affected", [])
    failures = plan_payload.get("prior_failure_pattern_refs", [])
    signals = bypass_signals or []
    hotspots = Counter(str((row.get("execution_context") or {}).get("file_path") or "unknown") for row in signals)
    offenders = Counter(str((row.get("execution_context") or {}).get("step_id") or "unknown") for row in signals)
    summary = {
        "artifact_type": "tpa_observability_summary",
        "schema_version": "1.0.0",
        "run_id": run_id,
        "trace_id": trace_id,
        "generated_at": generated_at,
        "step_id": step_id,
        "metrics": {
            "pass2_promotion_rate": 1.0 if selected == "pass_2_simplify" else 0.0,
            "pass1_retained_rate": 1.0 if selected == "pass_1_build" else 0.0,
            "simplify_win_rate": 1.0 if simplify_win else 0.0,
            "simplify_loss_rate": 0.0 if simplify_win else 1.0,
            "complexity_regression_rate": 1.0 if regression else 0.0,
            "cleanup_deletion_rate": 1.0 if delete_count > 0 else 0.0,
        },
        "bypass_attempt_count": len(signals),
        "bypass_hotspots": [{"path": path, "count": count} for path, count in hotspots.most_common(5)],
        "repeated_offenders": [{"scope": scope, "count": count} for scope, count in offenders.most_common(5)],
        "top_tpa_hotspot_modules": [
            {"module_ref": module_ref, "count": count} for module_ref, count in Counter(modules).most_common(5)
        ],
        "repeated_tpa_failure_patterns": [
            {"pattern_ref": pattern_ref, "count": count} for pattern_ref, count in Counter(failures).most_common(5)
        ],
    }
    try:
        validate_artifact(summary, "tpa_observability_summary")
    except Exception as exc:
        raise PQXSequenceRunnerError(f"invalid TPA observability summary artifact for {step_id}: {exc}") from exc
    return summary


def _build_tpa_certification_envelope(
    *,
    run_id: str,
    trace_id: str,
    step_id: str,
    generated_at: str,
    plan_artifact: dict[str, Any],
    build_artifact: dict[str, Any],
    simplify_artifact: dict[str, Any],
    gate_artifact: dict[str, Any],
    observability_summary: dict[str, Any],
    observability_consumer: dict[str, Any],
    complexity_budget: dict[str, Any],
    complexity_trend: dict[str, Any],
    simplification_campaign: dict[str, Any],
    complexity_recalibration: dict[str, Any],
) -> dict[str, Any]:
    plan_payload = dict(plan_artifact.get("artifact") or {})
    gate_payload = dict(gate_artifact.get("artifact") or {})
    execution_mode = str(plan_payload.get("execution_mode") or "feature_build")
    cleanup_validation = gate_payload.get("cleanup_only_validation")
    simplicity_decision = str((gate_payload.get("simplicity_review") or {}).get("decision") or "allow")
    complexity_decision = str((gate_payload.get("complexity_regression_gate") or {}).get("decision") or "allow")
    promotion_ready = bool(gate_payload.get("promotion_ready"))

    blocking_reasons: list[str] = []
    if not bool(gate_payload.get("behavioral_equivalence")):
        blocking_reasons.append("missing_behavioral_equivalence")
    if not bool(gate_payload.get("contract_valid")):
        blocking_reasons.append("missing_contract_validity")
    if not bool(gate_payload.get("tests_valid")):
        blocking_reasons.append("missing_test_validity")
    if complexity_decision in {"freeze", "block"}:
        blocking_reasons.append(f"complexity_decision_{complexity_decision}")
    if simplicity_decision in {"freeze", "block"}:
        blocking_reasons.append(f"simplicity_decision_{simplicity_decision}")
    if not promotion_ready:
        blocking_reasons.append("promotion_not_ready")
    if execution_mode == "cleanup_only":
        if not isinstance(cleanup_validation, dict):
            blocking_reasons.append("cleanup_only_validation_missing")
        else:
            if not bool(cleanup_validation.get("mode_enabled")):
                blocking_reasons.append("cleanup_only_mode_not_enabled")
            if not bool(cleanup_validation.get("equivalence_proven")):
                blocking_reasons.append("cleanup_only_equivalence_not_proven")
            if not str(cleanup_validation.get("replay_ref") or "").strip():
                blocking_reasons.append("cleanup_only_replay_ref_missing")

    envelope = {
        "artifact_type": "tpa_certification_envelope",
        "schema_version": "1.0.0",
        "envelope_id": f"tpa-cert:{run_id}:{step_id}",
        "run_id": run_id,
        "trace_id": trace_id,
        "step_id": step_id,
        "generated_at": generated_at,
        "execution_mode": execution_mode,
        "tpa_mode": str(plan_artifact.get("tpa_mode") or "full"),
        "evidence_refs": {
            "tpa_plan_artifact_ref": f"tpa_slice_artifact:{plan_artifact['artifact_id']}",
            "tpa_build_artifact_ref": f"tpa_slice_artifact:{build_artifact['artifact_id']}",
            "tpa_simplify_artifact_ref": f"tpa_slice_artifact:{simplify_artifact['artifact_id']}",
            "tpa_gate_artifact_ref": f"tpa_slice_artifact:{gate_artifact['artifact_id']}",
            "equivalence_evidence_refs": [
                f"gate.behavioral_equivalence:{bool(gate_payload.get('behavioral_equivalence'))}",
                f"gate.contract_valid:{bool(gate_payload.get('contract_valid'))}",
                f"gate.tests_valid:{bool(gate_payload.get('tests_valid'))}",
            ],
            "replay_ref": str((cleanup_validation or {}).get("replay_ref") or f"replay_result:{run_id}:{trace_id}"),
            "observability_summary_ref": f"tpa_observability_summary:{run_id}:{step_id}",
            "observability_consumer_ref": f"tpa_observability_consumer_record:{run_id}:{step_id}",
            "complexity_budget_ref": f"complexity_budget:{complexity_budget['run_id']}:{complexity_budget['step_id']}",
            "complexity_trend_ref": f"complexity_trend:{complexity_trend['run_id']}:{complexity_trend['step_id']}",
            "simplification_campaign_ref": f"tpa_simplification_campaign:{simplification_campaign['run_id']}:{simplification_campaign['step_id']}",
            "complexity_recalibration_ref": f"complexity_budget_recalibration_record:{complexity_recalibration['run_id']}:{complexity_recalibration['step_id']}",
        },
        "gate_decision": {
            "selected_pass": str(gate_payload.get("selected_pass") or "pass_1_build"),
            "promotion_ready": promotion_ready,
            "simplicity_decision": simplicity_decision,
            "complexity_regression_decision": complexity_decision,
        },
        "certification_decision": "blocked" if blocking_reasons else "certified",
        "blocking_reasons": sorted(set(blocking_reasons)),
    }
    if execution_mode == "cleanup_only":
        envelope["cleanup_only_validation"] = dict(cleanup_validation or {})
    try:
        validate_artifact(envelope, "tpa_certification_envelope")
    except Exception as exc:
        raise PQXSequenceRunnerError(f"invalid tpa_certification_envelope for {step_id}: {exc}") from exc
    return envelope


def _apply_lightweight_allowlisted_omissions(
    *,
    selection_metrics: dict[str, Any],
    build_signals: dict[str, int],
    simplify_signals: dict[str, int],
    allowlist: list[str],
) -> tuple[dict[str, Any], list[str]]:
    metrics = deepcopy(selection_metrics)
    omissions: list[str] = []
    mapping = {
        "tpa_gate.selection_metrics.build": build_signals,
        "tpa_gate.selection_metrics.simplify": simplify_signals,
        "tpa_gate.selection_metrics.simplify_delta": _complexity_delta(build_signals, simplify_signals),
    }
    for path, value in mapping.items():
        key = path.split(".")[-1]
        if key not in metrics:
            omissions.append(path)
            if path in allowlist:
                metrics[key] = value
    return metrics, sorted(omissions)


def _is_lightweight_eligible(request: dict[str, Any], plan_payload: dict[str, Any]) -> bool:
    changed_paths = request.get("changed_paths")
    if not isinstance(changed_paths, list):
        changed_paths = []
    files_count = len(changed_paths) if changed_paths else len(plan_payload.get("files_touched", []))
    loc_delta = request.get("estimated_loc_delta", 0)
    if not isinstance(loc_delta, int):
        loc_delta = 0
    if any(path.startswith("tests/") or path.startswith("docs/") for path in changed_paths):
        return True
    return files_count <= 2 and abs(loc_delta) <= 40


def _build_bypass_signal(
    *,
    run_id: str,
    trace_id: str,
    slice_id: str,
    step_id: str,
    request: dict[str, Any],
    missing_components: list[str],
    occurrence_count: int,
    detected_at: str,
) -> dict[str, Any]:
    severity = "warn" if occurrence_count == 1 else "freeze"
    if step_id.startswith("AI-"):
        severity = "block" if occurrence_count >= 3 else severity
    return {
        "artifact_type": "tpa_bypass_drift_signal",
        "schema_version": "1.0.0",
        "signal_id": f"tpa-bypass:{run_id}:{step_id}:{occurrence_count}",
        "run_id": run_id,
        "trace_id": trace_id,
        "drift_type": "tpa_bypass",
        "affected_artifact_id": f"pqx_slice_execution_record:{slice_id}",
        "missing_tpa_components": missing_components,
        "execution_context": {
            "slice_id": slice_id,
            "step_id": step_id,
            "required_scope": True,
            "module": str(request.get("module") or ""),
            "file_path": str((request.get("changed_paths") or [""])[0] if isinstance(request.get("changed_paths"), list) and request.get("changed_paths") else ""),
        },
        "severity": severity,
        "occurrence_count": occurrence_count,
        "reason_code": "tpa_bypass_detected",
        "detected_at": detected_at,
    }


def _request_has_tpa_scope_evidence(request: dict[str, Any]) -> bool:
    if request.get("tpa_scope_required") is True:
        return True
    if isinstance(request.get("tpa_scope_context"), dict):
        return True
    if isinstance(request.get("changed_paths"), list) and bool(request.get("changed_paths")):
        return True
    return any(bool(str(request.get(key) or "").strip()) for key in ("module", "artifact_type"))


def _persist_with_batch_result(state: dict, state_path: Path) -> dict:
    persisted = _persist_and_reload_exact(state, state_path)
    result = deepcopy(persisted)
    result["batch_result"] = _build_batch_result(persisted)
    return result


def _attach_tpa_outputs(result: dict[str, Any], tpa_artifacts_by_step: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if not tpa_artifacts_by_step:
        return result
    enriched = deepcopy(result)
    enriched["tpa_artifacts"] = deepcopy(tpa_artifacts_by_step)
    return enriched


def _validate_state_contract(state: dict) -> None:
    try:
        validate_artifact(state, "prompt_queue_sequence_run")
    except Exception as exc:  # fail-closed contract boundary
        raise PQXSequenceRunnerError(f"invalid prompt_queue_sequence_run artifact: {exc}") from exc


def _build_initial_state(*, queue_run_id: str, run_id: str, trace_id: str, slice_requests: list[dict], now: str) -> dict:
    requested = [entry["slice_id"] for entry in slice_requests]
    return {
        "schema_version": "1.5.0",
        "queue_run_id": queue_run_id,
        "run_id": run_id,
        "trace_id": trace_id,
        "status": "pending",
        "created_at": now,
        "updated_at": now,
        "requested_slice_ids": requested,
        "completed_slice_ids": [],
        "failed_slice_ids": [],
        "current_slice_id": None,
        "prior_slice_ref": None,
        "next_slice_ref": requested[0] if requested else None,
        "execution_history": [],
        "continuation_records": [],
        "lineage": {"prior_run_id": None, "prior_trace_id": None},
        "certification_complete_by_slice": {slice_id: False for slice_id in requested},
        "audit_complete_by_slice": {slice_id: False for slice_id in requested},
        "blocked_continuation_context": None,
        "replay_verification": {"status": "not_run", "replay_record_ref": None},
        "review_checkpoint_status": {
            "slice_1_optional_review": "not_required",
            "slice_2_required_review": "required_pending",
            "slice_3_strict_review": "required_pending",
        },
        "review_artifact_refs": [],
        "sequence_budget_status": "not_started",
        "sequence_budget_ref": None,
        "chain_certification_status": "pending",
        "chain_certification_refs": [],
        "bundle_readiness_decision": {"ready": True, "reason": "initial readiness satisfied"},
        "bundle_certification_status": "pending",
        "bundle_certification_ref": None,
        "bundle_audit_status": "pending",
        "bundle_audit_ref": None,
        "unresolved_fix_ids": [],
        "termination_reason": "not_terminated",
        "admission_preflight_artifact": None,
        "admitted_input_snapshot": None,
        "admitted_input_hash": None,
        "run_fingerprint": {"fingerprint_hash": None, "decision_sequence": [], "stopping_slice_id": None},
        "replayable_run_snapshot": None,
        "blocked_reason": None,
        "resume_token": f"resume:{queue_run_id}:0",
        "control_surface_gap_visibility": {
            "by_slice": {},
            "summary": _default_control_surface_gap_visibility(),
        },
    }


def _persist_and_reload_exact(state: dict, state_path: Path) -> dict:
    _validate_state_contract(state)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    reloaded = json.loads(state_path.read_text(encoding="utf-8"))
    _validate_state_contract(reloaded)
    if reloaded != state:
        raise PQXSequenceRunnerError("persisted-reload mismatch detected for prompt_queue_sequence_run state")
    return reloaded


def _verify_continuity(state: dict, slice_requests: list[dict]) -> None:
    requested_ids = [entry["slice_id"] for entry in slice_requests]
    trace_by_slice = {entry["slice_id"]: entry["trace_id"] for entry in slice_requests}

    if state.get("requested_slice_ids") != requested_ids:
        raise PQXSequenceRunnerError("persisted requested_slice_ids do not match requested execution order")

    completed = state.get("completed_slice_ids", [])
    failed = state.get("failed_slice_ids", [])
    history = state.get("execution_history", [])
    queue_run_id = state.get("queue_run_id")
    run_id = state.get("run_id")

    if set(completed) & set(failed):
        raise PQXSequenceRunnerError("slice cannot be both completed and failed")

    prev_ref = None
    history_completed: list[str] = []
    history_failed: list[str] = []
    continuation_by_next = {entry["next_step_id"]: entry for entry in state.get("continuation_records", [])}
    for index, record in enumerate(history):
        if record.get("queue_run_id") != queue_run_id:
            raise PQXSequenceRunnerError("all slices must inherit identical queue_run_id")
        if record.get("run_id") != run_id:
            raise PQXSequenceRunnerError("all slices must inherit stable batch run_id")
        slice_id = record.get("slice_id")
        if slice_id not in requested_ids:
            raise PQXSequenceRunnerError("execution_history contains unknown slice_id")
        expected_trace = trace_by_slice.get(slice_id)
        if record.get("trace_id") != expected_trace:
            raise PQXSequenceRunnerError("per-slice trace linkage mismatch detected")

        expected_parent = prev_ref if index > 0 else None
        if record.get("parent_execution_ref") != expected_parent:
            raise PQXSequenceRunnerError("parent-child execution order continuity mismatch")

        prev_ref = record.get("execution_ref")
        if record.get("status") == "success":
            history_completed.append(slice_id)
            if index > 0:
                continuation = continuation_by_next.get(slice_id)
                if continuation is None:
                    raise PQXSequenceRunnerError("missing continuation record for successful non-initial slice")
                previous = history[index - 1]
                if continuation.get("prior_step_id") != previous.get("slice_id"):
                    raise PQXSequenceRunnerError("continuation record prior_step_id mismatch")
                if continuation.get("prior_run_id") != previous.get("run_id"):
                    raise PQXSequenceRunnerError("continuation record prior_run_id mismatch")
                if continuation.get("prior_trace_id") != previous.get("trace_id"):
                    raise PQXSequenceRunnerError("continuation record prior_trace_id mismatch")
        else:
            history_failed.append(slice_id)

    if completed != history_completed:
        raise PQXSequenceRunnerError("completed_slice_ids mismatch with execution_history success entries")
    if failed != history_failed:
        raise PQXSequenceRunnerError("failed_slice_ids mismatch with execution_history failed entries")


def _next_pending_slice(requested_ids: list[str], completed_ids: list[str], failed_ids: list[str]) -> str | None:
    done = set(completed_ids) | set(failed_ids)
    for slice_id in requested_ids:
        if slice_id not in done:
            return slice_id
    return None


def _default_bundle_plan(slice_requests: list[dict], bundle_id: str) -> list[dict]:
    return [{"bundle_id": bundle_id, "step_ids": [entry["slice_id"] for entry in slice_requests], "depends_on": []}]


def _parse_resume_token(token: str, *, expected_segments: int, label: str) -> list[str]:
    parts = token.split(":")
    if len(parts) != expected_segments or parts[0] != "resume":
        raise PQXSequenceRunnerError(f"{label} malformed; expected resume token with {expected_segments} segments")
    return parts


def _assert_queue_bundle_state_consistency(
    *,
    queue_state: dict[str, Any],
    bundle_state: dict[str, Any],
    queue_run_id: str,
    is_resume_boundary: bool,
) -> None:
    divergence_reasons: list[str] = []
    queue_completed = list(queue_state.get("completed_slice_ids", []))
    queue_failed = list(queue_state.get("failed_slice_ids", []))
    bundle_completed = list(bundle_state.get("completed_step_ids", []))
    bundle_blocked = list(bundle_state.get("blocked_step_ids", []))

    if queue_completed != bundle_completed:
        divergence_reasons.append("completed progress mismatch between queue completed_slice_ids and bundle completed_step_ids")

    failed_not_blocked = [step_id for step_id in queue_failed if step_id not in bundle_blocked]
    if failed_not_blocked:
        divergence_reasons.append(
            "failed queue slices missing in bundle blocked_step_ids: " + ",".join(failed_not_blocked)
        )

    queue_resume_token = str(queue_state.get("resume_token") or "")
    queue_token_parts = _parse_resume_token(
        queue_resume_token,
        expected_segments=3,
        label="queue resume_token",
    )
    if queue_token_parts[1] != queue_run_id:
        divergence_reasons.append("queue resume_token queue_run_id mismatch")
    if int(queue_token_parts[2]) != len(queue_completed):
        divergence_reasons.append("queue resume_token progression index mismatch")

    bundle_resume = bundle_state.get("resume_position") or {}
    bundle_resume_token = str(bundle_resume.get("resume_token") or "")
    bundle_token_parts = _parse_resume_token(
        bundle_resume_token,
        expected_segments=4,
        label="bundle resume_position.resume_token",
    )
    if bundle_token_parts[1] != queue_run_id:
        divergence_reasons.append("bundle resume token sequence_run_id mismatch")
    if bundle_token_parts[2] != str(bundle_resume.get("bundle_id") or ""):
        divergence_reasons.append("bundle resume token bundle_id mismatch")
    if int(bundle_token_parts[3]) != len(bundle_completed):
        divergence_reasons.append("bundle resume token progression index mismatch")

    queue_next = _next_pending_slice(
        queue_state.get("requested_slice_ids", []),
        queue_completed,
        queue_failed,
    )
    bundle_next = bundle_resume.get("next_step_id")
    if queue_next != bundle_next:
        divergence_reasons.append("queue next pending step disagrees with bundle resume_position.next_step_id")

    if divergence_reasons:
        boundary = "resume" if is_resume_boundary else "continuation"
        raise PQXSequenceRunnerError(
            "queue_bundle_state_divergence fail-closed at "
            f"{boundary} boundary: "
            + json.dumps(
                {
                    "queue_run_id": queue_run_id,
                    "boundary": boundary,
                    "queue_resume_token": queue_resume_token,
                    "bundle_resume_token": bundle_resume_token,
                    "queue_completed": queue_completed,
                    "bundle_completed": bundle_completed,
                    "queue_failed": queue_failed,
                    "bundle_blocked": bundle_blocked,
                    "reasons": divergence_reasons,
                },
                sort_keys=True,
            )
        )


def _load_or_initialize_bundle_state(
    *,
    bundle_state_path: Path,
    bundle_plan: list[dict],
    queue_run_id: str,
    run_id: str,
    roadmap_authority_ref: str,
    execution_plan_ref: str,
    clock,
    resume: bool,
) -> dict:
    if bundle_state_path.exists():
        return load_bundle_state(bundle_state_path, bundle_plan=bundle_plan)
    if resume:
        raise PQXSequenceRunnerError("resume requested but pqx_bundle_state artifact is missing")

    try:
        initialized = initialize_bundle_state(
            bundle_plan=bundle_plan,
            run_id=run_id,
            sequence_run_id=queue_run_id,
            roadmap_authority_ref=roadmap_authority_ref,
            execution_plan_ref=execution_plan_ref,
            now=iso_now(clock),
        )
        return save_bundle_state(initialized, bundle_state_path, bundle_plan=bundle_plan)
    except PQXBundleStateError as exc:
        raise PQXSequenceRunnerError(str(exc)) from exc


def _build_continuation_record(*, prior_record: dict, next_slice_id: str, now: str) -> dict:
    continuation = {
        "artifact_id": f"cont:{prior_record['queue_run_id']}:{prior_record['slice_id']}:{next_slice_id}",
        "artifact_type": "pqx_slice_continuation_record",
        "schema_version": "1.0.0",
        "prior_step_id": prior_record["slice_id"],
        "next_step_id": next_slice_id,
        "prior_run_id": prior_record["run_id"],
        "prior_trace_id": prior_record["trace_id"],
        "prior_slice_execution_record_ref": prior_record["slice_execution_record_ref"],
        "prior_certification_ref": prior_record["certification_ref"],
        "prior_audit_bundle_ref": prior_record["audit_bundle_ref"],
        "continuation_status": "ready",
        "continuation_decision": "allow",
        "continuation_reasons": [
            "prior slice emitted canonical execution, certification, and audit artifacts",
            "lineage continuity satisfied for run_id and trace_id",
        ],
        "created_at": now,
    }
    validate_artifact(continuation, "pqx_slice_continuation_record")
    return continuation


def _apply_continuation_block(*, state: dict, queue_run_id: str, next_slice_id: str, block_type: str, reason: str, now: str) -> None:
    state["status"] = "blocked"
    state["blocked_reason"] = reason
    state["blocked_continuation_context"] = {
        "block_type": block_type,
        "reason": reason,
        "next_slice_id": next_slice_id,
    }
    state["current_slice_id"] = None
    state["next_slice_ref"] = next_slice_id
    state["updated_at"] = now
    state["resume_token"] = f"resume:{queue_run_id}:{len(state['completed_slice_ids'])}"
    _set_termination_reason(state, f"BLOCKED_{block_type}")


def _resolve_review_gate_response(
    *,
    review_gate_required: bool,
    review_snapshot: dict[str, Any] | None,
    review_eval_artifacts: dict[str, Any] | None,
    review_control_decision: dict[str, Any] | None,
) -> str:
    if not review_gate_required:
        return "allow"
    if review_snapshot is None:
        raise PQXSequenceRunnerError("review gate requires repo_review_snapshot artifact")
    try:
        validate_repo_review_snapshot(review_snapshot)
    except RepoReviewSnapshotStoreError as exc:
        raise PQXSequenceRunnerError(str(exc)) from exc
    if not isinstance(review_eval_artifacts, dict):
        raise PQXSequenceRunnerError("review gate requires repo_health_eval artifacts")
    eval_summary = review_eval_artifacts.get("eval_summary")
    if not isinstance(eval_summary, dict):
        raise PQXSequenceRunnerError("review gate requires eval_summary in repo_health_eval artifacts")
    try:
        validate_artifact(eval_summary, "eval_summary")
    except Exception as exc:
        raise PQXSequenceRunnerError(f"review gate eval_summary invalid: {exc}") from exc
    if not isinstance(review_control_decision, dict):
        raise PQXSequenceRunnerError("review gate requires evaluation_control_decision artifact")
    response = str(review_control_decision.get("system_response") or "").strip()
    if response not in {"allow", "warn", "freeze", "block"}:
        raise PQXSequenceRunnerError("review gate system_response must be allow|warn|freeze|block")
    return response


def execute_sequence_run(
    *,
    slice_requests: list[dict],
    state_path: str | Path,
    queue_run_id: str,
    run_id: str,
    trace_id: str,
    execute_slice: SliceExecutor | None = None,
    resume: bool = False,
    rerun_completed: bool = False,
    max_slices: int | None = None,
    bundle_state_path: str | Path | None = None,
    bundle_id: str = "BUNDLE-03",
    bundle_plan: list[dict] | None = None,
    roadmap_authority_ref: str = "docs/roadmaps/system_roadmap.md",
    execution_plan_ref: str = "docs/roadmaps/execution_bundles.md",
    clock=utc_now,
    review_results_by_slice: dict[str, dict] | None = None,
    sequence_budget_thresholds: dict | None = None,
    canary_control: dict | None = None,
    enforce_dependency_admission: bool = True,
    review_gate_required: bool = False,
    review_snapshot: dict[str, Any] | None = None,
    review_eval_artifacts: dict[str, Any] | None = None,
    review_control_decision: dict[str, Any] | None = None,
    tpa_scope_policy_path: str | Path | None = None,
    execution_class: str = "read_only",
    repo_write_lineage: dict[str, Any] | None = None,
) -> dict:
    """Run a narrow deterministic sequential PQX batch (2–3 slices) with persistent resumable state."""

    if not isinstance(queue_run_id, str) or not queue_run_id:
        raise PQXSequenceRunnerError("queue_run_id is required")
    if not isinstance(run_id, str) or not run_id:
        raise PQXSequenceRunnerError("run_id is required")
    if not isinstance(trace_id, str) or not trace_id:
        raise PQXSequenceRunnerError("trace_id is required")
    if execution_class not in {"read_only", "repo_write"}:
        raise PQXSequenceRunnerError("execution_class must be read_only or repo_write")
    if execution_class == "repo_write":
        lineage = repo_write_lineage if isinstance(repo_write_lineage, dict) else {}
        try:
            validate_repo_write_lineage(
                build_admission_record=lineage.get("build_admission_record"),
                normalized_execution_request=lineage.get("normalized_execution_request"),
                tlc_handoff_record=lineage.get("tlc_handoff_record"),
                expected_trace_id=trace_id,
                enforce_replay_protection=False,
                replay_context=run_id,
            )
        except (RepoWriteLineageGuardError, Exception) as exc:
            raise PQXSequenceRunnerError(f"direct_pqx_repo_write_forbidden:{exc}") from exc

    _validate_slice_requests(slice_requests)
    review_results = review_results_by_slice or {}
    enforce_review_policy = review_results_by_slice is not None
    state_path = Path(state_path)
    resolved_bundle_plan = bundle_plan or _default_bundle_plan(slice_requests, bundle_id)
    resolved_bundle_state_path = Path(bundle_state_path) if bundle_state_path is not None else None
    bundle_state = None

    if execute_slice is None:

        def _default_executor(payload: dict) -> dict:
            slice_id = str(payload.get("slice_id", ""))
            canonical_step_id = _canonical_step_id(slice_id)
            step_result = run_pqx_slice(
                step_id=canonical_step_id,
                roadmap_path=Path("docs/roadmap/system_roadmap.md"),
                state_path=Path(state_path).parent / "pqx_state.json",
                runs_root=Path(state_path).parent / "pqx_slice_runs",
                clock=clock,
                pqx_output_text=f"deterministic output for {payload['slice_id']}",
                execution_intent="non_repo_write",
            )
            if step_result.get("status") != "complete":
                return {
                    "execution_status": "failed",
                    "error": step_result.get("reason") or step_result.get("block_type", "blocked"),
                }
            completion_confirmation = confirm_slice_completion_after_enforcement_allow(
                slice_result=step_result,
                state_path=Path(state_path).parent / "pqx_state.json",
                step_id=canonical_step_id,
            )
            if completion_confirmation.get("status") != "complete":
                return {
                    "execution_status": "failed",
                    "error": completion_confirmation.get("reason")
                    or completion_confirmation.get("block_type", "post_enforcement_blocked"),
                }
            return {
                "execution_status": "success",
                "slice_execution_record": step_result.get("slice_execution_record"),
                "done_certification_record": step_result.get("done_certification_record"),
                "pqx_slice_audit_bundle": step_result.get("pqx_slice_audit_bundle"),
                "certification_complete": step_result.get("certification_status") == "certified",
                "audit_complete": bool(step_result.get("pqx_slice_audit_bundle")),
                "control_surface_gap_visibility": step_result.get("control_surface_gap_visibility"),
            }

        executor = _default_executor
    else:
        executor = execute_slice

    if resume:
        if not state_path.exists():
            raise PQXSequenceRunnerError("resume requested but state artifact is missing")
        state = json.loads(state_path.read_text(encoding="utf-8"))
        _validate_state_contract(state)
        if state["queue_run_id"] != queue_run_id or state["run_id"] != run_id or state["trace_id"] != trace_id:
            raise PQXSequenceRunnerError("resume identity mismatch for queue_run_id/run_id/trace_id")
    else:
        now = iso_now(clock)
        state = _build_initial_state(
            queue_run_id=queue_run_id,
            run_id=run_id,
            trace_id=trace_id,
            slice_requests=slice_requests,
            now=now,
        )

    admission_artifact = _build_admission_preflight_artifact(
        queue_run_id=queue_run_id,
        run_id=run_id,
        trace_id=trace_id,
        slice_requests=slice_requests,
        already_completed_slice_ids=state["completed_slice_ids"],
        enforce_dependencies=enforce_dependency_admission,
    )
    if state.get("admission_preflight_artifact") is None:
        state["admission_preflight_artifact"] = admission_artifact
        state["admitted_input_snapshot"] = admission_artifact["admitted_input_snapshot"]
        state["admitted_input_hash"] = admission_artifact["admitted_input_hash"]
    else:
        if state.get("admitted_input_hash") != admission_artifact["admitted_input_hash"]:
            raise PQXSequenceRunnerError("resume admitted_input_hash mismatch; fail-closed")
    _set_termination_reason(state, state.get("termination_reason") or "not_terminated")

    _verify_continuity(state, slice_requests)
    state = _persist_and_reload_exact(state, state_path)
    _verify_continuity(state, slice_requests)

    if resolved_bundle_state_path is not None:
        bundle_state = _load_or_initialize_bundle_state(
            bundle_state_path=resolved_bundle_state_path,
            bundle_plan=resolved_bundle_plan,
            queue_run_id=queue_run_id,
            run_id=run_id,
            roadmap_authority_ref=roadmap_authority_ref,
            execution_plan_ref=execution_plan_ref,
            clock=clock,
            resume=resume,
        )
        _assert_queue_bundle_state_consistency(
            queue_state=state,
            bundle_state=bundle_state,
            queue_run_id=queue_run_id,
            is_resume_boundary=resume,
        )

    requested_ids = state["requested_slice_ids"]
    budget_thresholds = sequence_budget_thresholds or {"max_failed_slices": 1, "max_cumulative_severity": 5}
    canary = canary_control or {"status": "not_applicable", "frozen_slice_ids": []}
    executed_this_call = 0
    tpa_artifacts_by_step: dict[str, dict[str, Any]] = {}
    review_gate_response = _resolve_review_gate_response(
        review_gate_required=review_gate_required,
        review_snapshot=review_snapshot,
        review_eval_artifacts=review_eval_artifacts,
        review_control_decision=review_control_decision,
    )
    tpa_scope_policy = load_tpa_scope_policy(tpa_scope_policy_path) if tpa_scope_policy_path is not None else load_tpa_scope_policy()
    tpa_policy_composition = load_tpa_policy_composition()
    bypass_signals: list[dict[str, Any]] = []
    while True:
        _verify_continuity(state, slice_requests)
        if bundle_state is not None:
            _assert_queue_bundle_state_consistency(
                queue_state=state,
                bundle_state=bundle_state,
                queue_run_id=queue_run_id,
                is_resume_boundary=False,
            )
        next_slice_id = _next_pending_slice(requested_ids, state["completed_slice_ids"], state["failed_slice_ids"])
        if next_slice_id is None:
            if len(requested_ids) >= 3:
                first_three = requested_ids[:3]
                all_three_certified = all(state["certification_complete_by_slice"].get(sid, False) for sid in first_three)
                reviews_satisfied = True
                if enforce_review_policy:
                    reviews_satisfied = (
                        state["review_checkpoint_status"]["slice_2_required_review"] == "satisfied"
                        and state["review_checkpoint_status"]["slice_3_strict_review"] == "satisfied"
                    )
                chain_status = "certified" if all_three_certified and reviews_satisfied and not state["unresolved_fix_ids"] else "blocked"
                if chain_status != "certified":
                    state["status"] = "blocked"
                    state["chain_certification_status"] = "blocked"
                    state["blocked_reason"] = "chain certification blocked: reviews/fixes/certification incomplete"
                    _set_termination_reason(state, "BLOCKED_CHAIN_CERTIFICATION")
                    return _persist_with_batch_result(state, state_path)
                chain_ref = f"{queue_run_id}:chain-3"
                if chain_ref not in state["chain_certification_refs"]:
                    state["chain_certification_refs"].append(chain_ref)
                state["chain_certification_status"] = "certified"
            else:
                state["chain_certification_status"] = "pending"
            if not state.get("bundle_readiness_decision", {}).get("ready", False):
                state["status"] = "blocked"
                state["bundle_certification_status"] = "failed"
                state["blocked_reason"] = "bundle readiness unresolved"
                _set_termination_reason(state, "BLOCKED_BUNDLE_READINESS")
                return _persist_with_batch_result(state, state_path)
            state["bundle_certification_status"] = "certified"
            state["bundle_certification_ref"] = f"{queue_run_id}:bundle-cert"
            history_refs = [row.get("slice_execution_record_ref") for row in state["execution_history"] if row.get("slice_execution_record_ref")]
            if not history_refs:
                state["status"] = "blocked"
                state["bundle_audit_status"] = "missing"
                state["blocked_reason"] = "missing bundle audit artifacts"
                _set_termination_reason(state, "BLOCKED_MISSING_BUNDLE_AUDIT_ARTIFACTS")
                return _persist_with_batch_result(state, state_path)
            state["bundle_audit_status"] = "synthesized"
            state["bundle_audit_ref"] = f"{queue_run_id}:bundle-audit"
            state["status"] = "completed"
            state["current_slice_id"] = None
            state["next_slice_ref"] = None
            if review_gate_required and review_gate_response == "warn":
                state["blocked_reason"] = "degraded review gate state: warn"
            else:
                state["blocked_reason"] = None
            state["blocked_continuation_context"] = None
            state["updated_at"] = iso_now(clock)
            state["resume_token"] = f"resume:{queue_run_id}:{len(state['completed_slice_ids'])}"
            _set_termination_reason(state, "COMPLETED_ALL_SLICES")
            _validate_trace_completeness(state)
            persisted = _persist_and_reload_exact(state, state_path)
            if bundle_state is not None and bundle_state["active_bundle_id"] not in bundle_state["completed_bundle_ids"]:
                try:
                    bundle_state = mark_bundle_complete(
                        bundle_state,
                        resolved_bundle_plan,
                        bundle_id=bundle_state["active_bundle_id"],
                        now=iso_now(clock),
                    )
                    save_bundle_state(bundle_state, resolved_bundle_state_path, bundle_plan=resolved_bundle_plan)
                except PQXBundleStateError as exc:
                    raise PQXSequenceRunnerError(str(exc)) from exc
            result = deepcopy(persisted)
            result["batch_result"] = _build_batch_result(persisted)
            return _attach_tpa_outputs(result, tpa_artifacts_by_step)

        if max_slices is not None and executed_this_call >= max_slices:
            state["status"] = "running"
            state["current_slice_id"] = next_slice_id
            state["next_slice_ref"] = next_slice_id
            state["blocked_reason"] = None
            state["blocked_continuation_context"] = None
            state["updated_at"] = iso_now(clock)
            _set_termination_reason(state, "PAUSED_MAX_SLICES")
            return _persist_with_batch_result(state, state_path)

        if review_gate_required:
            if review_gate_response == "warn":
                state["blocked_reason"] = "degraded review gate state: warn"
            elif review_gate_response == "freeze":
                _apply_continuation_block(
                    state=state,
                    queue_run_id=queue_run_id,
                    next_slice_id=next_slice_id,
                    block_type="PRIOR_SLICE_NOT_GOVERNED",
                    reason="review gate system_response=freeze; progression halted",
                    now=iso_now(clock),
                )
                return _persist_with_batch_result(state, state_path)
            elif review_gate_response == "block":
                _apply_continuation_block(
                    state=state,
                    queue_run_id=queue_run_id,
                    next_slice_id=next_slice_id,
                    block_type="PRIOR_SLICE_NOT_GOVERNED",
                    reason="review gate system_response=block; progression denied",
                    now=iso_now(clock),
                )
                return _persist_with_batch_result(state, state_path)

        already_completed = next_slice_id in state["completed_slice_ids"]
        if already_completed and not rerun_completed:
            raise PQXSequenceRunnerError("invalid transition: completed slice selected for rerun without explicit override")

        request = next(entry for entry in slice_requests if entry["slice_id"] == next_slice_id)
        if canary.get("status") == "frozen" and next_slice_id in set(canary.get("frozen_slice_ids", [])):
            _apply_continuation_block(
                state=state,
                queue_run_id=queue_run_id,
                next_slice_id=next_slice_id,
                block_type="CANARY_FROZEN",
                reason="canary rollout failure froze this slice path",
                now=iso_now(clock),
            )
            return _persist_with_batch_result(state, state_path)
        current_index = requested_ids.index(next_slice_id)
        state["bundle_readiness_decision"] = {
            "ready": len(state["unresolved_fix_ids"]) == 0,
            "reason": "dependencies/artifacts valid and no blocking findings"
            if len(state["unresolved_fix_ids"]) == 0
            else "blocking findings unresolved",
        }
        if not state["bundle_readiness_decision"]["ready"]:
            state["status"] = "blocked"
            state["blocked_reason"] = "bundle readiness gate blocked"
            _set_termination_reason(state, "BLOCKED_BUNDLE_READINESS_GATE")
            return _persist_with_batch_result(state, state_path)
        if current_index > 0:
            prior_slice_id = requested_ids[current_index - 1]
            prior_success = [
                row for row in state["execution_history"] if row["slice_id"] == prior_slice_id and row["status"] == "success"
            ]
            if not prior_success:
                _apply_continuation_block(
                    state=state,
                    queue_run_id=queue_run_id,
                    next_slice_id=next_slice_id,
                    block_type="PRIOR_SLICE_NOT_GOVERNED",
                    reason="prior slice not completed successfully through canonical path",
                    now=iso_now(clock),
                )
                return _persist_with_batch_result(state, state_path)
            prior_record = prior_success[-1]
            if not prior_record.get("certification_complete") or not prior_record.get("audit_complete"):
                _apply_continuation_block(
                    state=state,
                    queue_run_id=queue_run_id,
                    next_slice_id=next_slice_id,
                    block_type="PRIOR_SLICE_NOT_GOVERNED",
                    reason="prior slice missing required certification or audit completion",
                    now=iso_now(clock),
                )
                return _persist_with_batch_result(state, state_path)
            try:
                continuation = _build_continuation_record(prior_record=prior_record, next_slice_id=next_slice_id, now=iso_now(clock))
            except Exception as exc:
                _apply_continuation_block(
                    state=state,
                    queue_run_id=queue_run_id,
                    next_slice_id=next_slice_id,
                    block_type="INVALID_SLICE_CONTINUATION",
                    reason=f"invalid continuation record: {exc}",
                    now=iso_now(clock),
                )
                return _persist_with_batch_result(state, state_path)
            existing = [entry for entry in state["continuation_records"] if entry["next_step_id"] == next_slice_id]
            if existing and existing[-1] != continuation:
                _apply_continuation_block(
                    state=state,
                    queue_run_id=queue_run_id,
                    next_slice_id=next_slice_id,
                    block_type="CONTINUATION_STATE_MISMATCH",
                    reason="persisted continuation record mismatches governed prior artifacts",
                    now=iso_now(clock),
                )
                return _persist_with_batch_result(state, state_path)
            if not existing:
                state["continuation_records"].append(continuation)
                state["lineage"] = {
                    "prior_run_id": continuation["prior_run_id"],
                    "prior_trace_id": continuation["prior_trace_id"],
                }

        parent_ref = state["execution_history"][-1]["execution_ref"] if state["execution_history"] else None
        attempt = 1 + sum(1 for row in state["execution_history"] if row["slice_id"] == next_slice_id)
        execution_ref = f"exec:{queue_run_id}:{next_slice_id}:{attempt}"
        started_at = iso_now(clock)

        state["status"] = "running"
        state["current_slice_id"] = next_slice_id
        state["next_slice_ref"] = next_slice_id
        state["updated_at"] = started_at
        state = _persist_and_reload_exact(state, state_path)

        payload = {
            "queue_run_id": queue_run_id,
            "run_id": run_id,
            "trace_id": request["trace_id"],
            "slice_id": next_slice_id,
            "parent_execution_ref": parent_ref,
            "execution_ref": execution_ref,
            "resume_token": state["resume_token"],
        }
        result = executor(deepcopy(payload))
        if not isinstance(result, dict):
            raise PQXSequenceRunnerError("slice executor must return an object result")

        child_queue_run_id = result.get("queue_run_id", queue_run_id)
        child_run_id = result.get("run_id", run_id)
        child_trace_id = result.get("trace_id", request["trace_id"])
        child_parent_ref = result.get("parent_execution_ref", parent_ref)

        if child_queue_run_id != queue_run_id:
            raise PQXSequenceRunnerError("child continuity mismatch: queue_run_id changed")
        if child_run_id != run_id:
            raise PQXSequenceRunnerError("child continuity mismatch: run_id changed")
        if child_trace_id != request["trace_id"]:
            raise PQXSequenceRunnerError("child continuity mismatch: trace_id changed")
        if child_parent_ref != parent_ref:
            raise PQXSequenceRunnerError("child continuity mismatch: parent_execution_ref changed")

        execution_status = result.get("execution_status")
        if execution_status not in {"success", "failed", "blocked", "review_required"}:
            raise PQXSequenceRunnerError("slice executor must return execution_status of success/failed/blocked/review_required")
        step_id, tpa_phase = _parse_tpa_slice_id(next_slice_id)
        required_scope = False
        if tpa_phase is None:
            if _request_has_tpa_scope_evidence(request):
                tpa_context = dict(request.get("tpa_scope_context") or {})
                tpa_context.setdefault(
                    "file_path",
                    (request.get("changed_paths") or [""])[0]
                    if isinstance(request.get("changed_paths"), list) and request.get("changed_paths")
                    else "",
                )
                tpa_context.setdefault("module", request.get("module"))
                tpa_context.setdefault("artifact_type", request.get("artifact_type"))
                tpa_context.setdefault("pqx_step_metadata", {"step_id": step_id})
                required_scope = bool(request.get("tpa_scope_required")) or is_tpa_required(
                    tpa_context, policy=tpa_scope_policy
                )
        if tpa_phase is not None and execution_status != "success":
            raise PQXSequenceRunnerError(f"TPA slice {next_slice_id} must succeed; fail-closed on {execution_status}")

        if tpa_phase is not None:
            artifacts = tpa_artifacts_by_step.setdefault(step_id, {})
            tpa_mode = "full"
            if tpa_phase == "plan":
                plan_payload = request.get("tpa_plan")
                if not isinstance(plan_payload, dict):
                    raise PQXSequenceRunnerError(f"TPA plan slice {next_slice_id} missing request.tpa_plan artifact payload")
                if plan_payload.get("execution_mode") not in {"feature_build", "cleanup_only"}:
                    raise PQXSequenceRunnerError("TPA plan must declare execution_mode feature_build or cleanup_only")
                if not str(plan_payload.get("context_bundle_ref") or "").startswith("context_bundle_v2:"):
                    raise PQXSequenceRunnerError("TPA plan must reference context_bundle_v2 via context_bundle_ref")
                if not plan_payload.get("modules_affected"):
                    raise PQXSequenceRunnerError("TPA plan must declare modules_affected from governed context")
                if plan_payload.get("execution_mode") == "cleanup_only":
                    cleanup_scope = plan_payload.get("cleanup_scope")
                    if not isinstance(cleanup_scope, dict) or not cleanup_scope.get("bounded_files"):
                        raise PQXSequenceRunnerError("TPA cleanup-only plan must declare cleanup_scope.bounded_files")
                if not str(plan_payload.get("improvement_objective") or "").strip():
                    raise PQXSequenceRunnerError("TPA plan must declare improvement_objective")
                if not str(plan_payload.get("context_rationale") or "").strip():
                    raise PQXSequenceRunnerError("TPA plan must declare context_rationale")
                requested_mode = str(plan_payload.get("tpa_mode") or "full")
                lightweight_eligible = _is_lightweight_eligible(request, plan_payload)
                if requested_mode not in {"full", "lightweight"}:
                    raise PQXSequenceRunnerError("TPA plan tpa_mode must be full|lightweight")
                composition_decision = resolve_tpa_policy_decision(
                    {
                        "required_scope": bool(required_scope),
                        "tpa_lineage_present": True,
                        "tpa_mode": requested_mode,
                        "lightweight_eligible": lightweight_eligible,
                    },
                    composition=tpa_policy_composition,
                )
                if requested_mode == "lightweight" and composition_decision["final_decision"] in {"freeze", "block"}:
                    raise PQXSequenceRunnerError("tpa_bypass_detected: lightweight mode not eligible for this scope")
                tpa_mode = requested_mode
                artifacts["plan"] = _build_tpa_slice_artifact(
                    run_id=run_id,
                    trace_id=request["trace_id"],
                    slice_id=next_slice_id,
                    produced_at=iso_now(clock),
                    artifact_payload=plan_payload,
                    tpa_mode=tpa_mode,
                )
            elif tpa_phase == "build":
                if "plan" not in artifacts:
                    raise PQXSequenceRunnerError(f"TPA build slice {next_slice_id} requires completed plan artifact")
                tpa_mode = artifacts["plan"].get("tpa_mode", "full")
                build_payload = result.get("tpa_build")
                if not isinstance(build_payload, dict):
                    raise PQXSequenceRunnerError(f"TPA build slice {next_slice_id} missing result.tpa_build artifact payload")
                plan_fields = artifacts["plan"]["artifact"]
                planned_files = set(plan_fields["files_touched"])
                build_files = set(build_payload.get("files_touched", []))
                if not build_files.issubset(planned_files):
                    raise PQXSequenceRunnerError("TPA build scope exceeds declared plan files_touched")
                if not bool(build_payload.get("plan_scope_match")):
                    raise PQXSequenceRunnerError("TPA build must declare plan_scope_match=true")
                if build_payload.get("unused_helpers"):
                    raise PQXSequenceRunnerError("TPA build small guardrail failed: unused_helpers detected")
                if build_payload.get("unnecessary_indirection"):
                    raise PQXSequenceRunnerError("TPA build small guardrail failed: unnecessary_indirection detected")
                if int(build_payload.get("new_layers", 0)) > 0:
                    raise PQXSequenceRunnerError("TPA build small guardrail failed: new_layers must be 0")
                if build_payload.get("context_bundle_ref") != plan_fields.get("context_bundle_ref"):
                    raise PQXSequenceRunnerError("TPA build must use same context_bundle_ref as TPA plan")
                if bool(build_payload.get("speculative_expansion_detected")):
                    raise PQXSequenceRunnerError("TPA build must not perform speculative expansion beyond required scope")
                if not bool(build_payload.get("existing_abstractions_satisfied")):
                    raise PQXSequenceRunnerError("TPA build must confirm existing abstractions are reused when available")
                _normalized_complexity_signals(build_payload, field_name="complexity_signals")
                plan_failure_patterns = set(plan_fields.get("prior_failure_pattern_refs", []))
                avoided_patterns = set(build_payload.get("known_failure_patterns_avoided", []))
                if not plan_failure_patterns.issubset(avoided_patterns):
                    raise PQXSequenceRunnerError("TPA build must avoid prior failure patterns declared in plan context")
                planned_modules = set(plan_fields.get("modules_affected", []))
                reused_modules = set(build_payload.get("reused_module_refs", []))
                if planned_modules and not planned_modules.intersection(reused_modules):
                    raise PQXSequenceRunnerError("TPA build must reuse modules surfaced by plan context")
                artifacts["build"] = _build_tpa_slice_artifact(
                    run_id=run_id,
                    trace_id=request["trace_id"],
                    slice_id=next_slice_id,
                    produced_at=iso_now(clock),
                    artifact_payload=build_payload,
                    tpa_mode=tpa_mode,
                )
            elif tpa_phase == "simplify":
                if "build" not in artifacts:
                    raise PQXSequenceRunnerError(f"TPA simplify slice {next_slice_id} requires completed build artifact")
                tpa_mode = artifacts["plan"].get("tpa_mode", "full")
                simplify_payload = result.get("tpa_simplify")
                if not isinstance(simplify_payload, dict):
                    if tpa_mode == "lightweight":
                        simplify_payload = {
                            "artifact_kind": "simplify",
                            "source_build_artifact_id": artifacts["build"]["artifact_id"],
                            "actions": ["delete_unnecessary_code"],
                            "behavior_changed": False,
                            "new_layers_introduced": 0,
                            "context_bundle_ref": artifacts["plan"]["artifact"].get("context_bundle_ref"),
                            "redundant_code_paths_removed": 0,
                            "duplicate_logic_collapsed": [],
                            "pattern_consistency_refs": ["pattern:tpa-lightweight-minimal"],
                            "complexity_signals": _normalized_complexity_signals(
                                artifacts["build"]["artifact"], field_name="complexity_signals"
                            ),
                            "delete_pass": {
                                "deletion_considered": True,
                                "deletion_performed": False,
                                "deletion_rejected_reason": "lightweight_mode_minimal_simplify",
                                "deleted_items": [],
                                "collapsed_abstractions": [],
                                "removed_helpers": [],
                                "removed_wrappers": [],
                                "indirection_avoided": [],
                            },
                        }
                    else:
                        raise PQXSequenceRunnerError(
                            f"TPA simplify slice {next_slice_id} missing result.tpa_simplify artifact payload"
                        )
                if bool(simplify_payload.get("behavior_changed")):
                    raise PQXSequenceRunnerError("TPA simplify must not change behavior")
                if int(simplify_payload.get("new_layers_introduced", 0)) > 0:
                    raise PQXSequenceRunnerError("TPA simplify must not introduce new abstraction layers")
                if simplify_payload.get("context_bundle_ref") != artifacts["plan"]["artifact"].get("context_bundle_ref"):
                    raise PQXSequenceRunnerError("TPA simplify must use same context_bundle_ref as TPA plan")
                _normalized_complexity_signals(simplify_payload, field_name="complexity_signals")
                delete_pass = simplify_payload.get("delete_pass")
                if not isinstance(delete_pass, dict) or not bool(delete_pass.get("deletion_considered")):
                    raise PQXSequenceRunnerError("TPA simplify must include delete_pass with deletion_considered=true")
                if (
                    tpa_mode != "lightweight"
                    and int(simplify_payload.get("redundant_code_paths_removed", 0)) <= 0
                    and not simplify_payload.get("duplicate_logic_collapsed")
                    and not delete_pass.get("deleted_items")
                ):
                    raise PQXSequenceRunnerError("TPA simplify must remove redundancy using context-informed simplification")
                if not simplify_payload.get("pattern_consistency_refs"):
                    raise PQXSequenceRunnerError("TPA simplify must declare pattern consistency references")
                artifacts["simplify"] = _build_tpa_slice_artifact(
                    run_id=run_id,
                    trace_id=request["trace_id"],
                    slice_id=next_slice_id,
                    produced_at=iso_now(clock),
                    artifact_payload=simplify_payload,
                    tpa_mode=tpa_mode,
                )
            elif tpa_phase == "gate":
                if "build" not in artifacts or "simplify" not in artifacts:
                    raise PQXSequenceRunnerError(f"TPA gate slice {next_slice_id} requires build and simplify artifacts")
                tpa_mode = artifacts["plan"].get("tpa_mode", "full")
                gate_payload = result.get("tpa_gate")
                if not isinstance(gate_payload, dict):
                    raise PQXSequenceRunnerError(f"TPA gate slice {next_slice_id} missing result.tpa_gate artifact payload")
                if not all(
                    bool(gate_payload.get(key))
                    for key in ("behavioral_equivalence", "contract_valid", "tests_valid")
                ):
                    raise PQXSequenceRunnerError("TPA gate must prove behavioral equivalence, contract validity, and test validity")
                selection_inputs = gate_payload.get("selection_inputs")
                if not isinstance(selection_inputs, dict):
                    raise PQXSequenceRunnerError("TPA gate must include selection_inputs")
                if not bool(selection_inputs.get("comparison_inputs_present")):
                    raise PQXSequenceRunnerError("TPA gate must fail closed when selection comparison inputs are missing")
                if selection_inputs.get("build_artifact_id") != artifacts["build"]["artifact_id"] or selection_inputs.get("simplify_artifact_id") != artifacts["simplify"]["artifact_id"]:
                    raise PQXSequenceRunnerError("TPA gate selection_inputs artifact refs must match governed build/simplify artifacts")
                build_signals = _normalized_complexity_signals(artifacts["build"]["artifact"], field_name="complexity_signals")
                simplify_signals = _normalized_complexity_signals(artifacts["simplify"]["artifact"], field_name="complexity_signals")
                simplicity_review = gate_payload.get("simplicity_review")
                if not isinstance(simplicity_review, dict):
                    raise PQXSequenceRunnerError("TPA gate must include simplicity_review")
                simplicity_decision = simplicity_review.get("decision")
                if simplicity_decision not in {"allow", "warn", "freeze", "block"}:
                    raise PQXSequenceRunnerError("TPA gate simplicity_review.decision invalid")
                deterministic_selected = _deterministic_selection_from_signals(
                    build_signals=build_signals,
                    simplify_signals=simplify_signals,
                    simplicity_decision=simplicity_decision,
                )
                if gate_payload.get("selected_pass") != deterministic_selected:
                    raise PQXSequenceRunnerError("TPA gate selected_pass mismatch with deterministic control decision")
                rejected_pass = "pass_2_simplify" if deterministic_selected == "pass_1_build" else "pass_1_build"
                if gate_payload.get("rejected_pass") != rejected_pass:
                    raise PQXSequenceRunnerError("TPA gate rejected_pass mismatch with deterministic control decision")
                selection_metrics = gate_payload.get("selection_metrics")
                if not isinstance(selection_metrics, dict):
                    raise PQXSequenceRunnerError("TPA gate must include selection_metrics")
                expected_metrics = {
                    "build": build_signals,
                    "simplify": simplify_signals,
                    "simplify_delta": _complexity_delta(build_signals, simplify_signals),
                }
                if tpa_mode == "lightweight":
                    allowlist = list(composition_decision.get("lightweight_evidence_omission_allowlist") or [])
                    normalized_metrics, omissions = _apply_lightweight_allowlisted_omissions(
                        selection_metrics=selection_metrics,
                        build_signals=build_signals,
                        simplify_signals=simplify_signals,
                        allowlist=allowlist,
                    )
                    allowlist_decision = resolve_tpa_policy_decision(
                        {
                            "required_scope": bool(required_scope),
                            "tpa_lineage_present": True,
                            "tpa_mode": "lightweight",
                            "lightweight_eligible": True,
                            "lightweight_evidence_omissions": omissions,
                        },
                        composition=tpa_policy_composition,
                    )
                    if allowlist_decision["final_decision"] in {"freeze", "block"}:
                        raise PQXSequenceRunnerError(
                            "TPA lightweight evidence omission blocked: "
                            + ",".join(allowlist_decision["blocking_reasons"])
                        )
                    gate_payload["selection_metrics"] = normalized_metrics
                    selection_metrics = normalized_metrics
                if tpa_mode != "lightweight":
                    if selection_metrics.get("build") != expected_metrics["build"] or selection_metrics.get("simplify") != expected_metrics["simplify"]:
                        raise PQXSequenceRunnerError("TPA gate selection_metrics build/simplify must match governed complexity signals")
                    if selection_metrics.get("simplify_delta") != expected_metrics["simplify_delta"]:
                        raise PQXSequenceRunnerError("TPA gate selection_metrics simplify_delta mismatch")
                if gate_payload.get("context_bundle_ref") != artifacts["plan"]["artifact"].get("context_bundle_ref"):
                    raise PQXSequenceRunnerError("TPA gate must use same context_bundle_ref as plan/build/simplify")
                if gate_payload.get("unaddressed_failure_pattern_refs"):
                    raise PQXSequenceRunnerError("TPA gate must block when context indicates unaddressed repeated failure patterns")
                planned_failure_patterns = set(artifacts["plan"]["artifact"].get("prior_failure_pattern_refs", []))
                addressed_failure_patterns = set(gate_payload.get("addressed_failure_pattern_refs", []))
                if not planned_failure_patterns.issubset(addressed_failure_patterns):
                    raise PQXSequenceRunnerError("TPA gate must enforce mitigation of all planned prior failure patterns")
                plan_risks = artifacts["plan"]["artifact"].get("known_risk_refs", [])
                if plan_risks and bool(gate_payload.get("high_risk_unmitigated")):
                    raise PQXSequenceRunnerError("TPA gate must freeze/block when high-risk context lacks mitigation")
                if plan_risks and not gate_payload.get("risk_mitigation_refs"):
                    raise PQXSequenceRunnerError("TPA gate must include risk mitigation refs for known risks")
                trend_history = artifacts.get("complexity_trend_history", [])
                if not isinstance(trend_history, list):
                    raise PQXSequenceRunnerError("TPA complexity trend history must be a list")
                trend_points = [point for point in trend_history if isinstance(point, dict)]
                build_complexity_score = _complexity_score(build_signals)
                simplify_complexity_score = _complexity_score(simplify_signals)
                trend_points.append(
                    {
                        "index": len(trend_points),
                        "step_id": step_id,
                        "complexity": simplify_complexity_score,
                        "complexity_delta": simplify_complexity_score - build_complexity_score,
                        "simplify_effectiveness": float(build_complexity_score - simplify_complexity_score),
                        "deletions_count": int(simplify_signals["deletions_count"]),
                        "abstraction_growth": int(
                            simplify_signals["abstraction_added_count"] - simplify_signals["abstraction_removed_count"]
                        ),
                    }
                )
                artifacts["complexity_trend_history"] = deepcopy(trend_points)
                historical_scores = [int(point.get("complexity", 0)) for point in trend_points[:-1]]
                module_ref = str((artifacts["plan"]["artifact"].get("modules_affected") or ["unknown"])[0])
                budget_artifact = build_complexity_budget(
                    run_id=run_id,
                    trace_id=request["trace_id"],
                    step_id=step_id,
                    module_or_path=module_ref,
                    build_signals=build_signals,
                    simplify_signals=simplify_signals,
                    last_updated=iso_now(clock),
                    historical_scores=historical_scores,
                )
                trend_artifact = build_complexity_trend(
                    run_id=run_id,
                    trace_id=request["trace_id"],
                    step_id=step_id,
                    module=module_ref,
                    artifact_type_scope=str(request.get("artifact_type") or "unknown"),
                    slice_family="TPA",
                    points=trend_points,
                )
                campaign_artifact = build_simplification_campaign(
                    run_id=run_id,
                    trace_id=request["trace_id"],
                    step_id=step_id,
                    target_module=module_ref,
                    trend=trend_artifact,
                    budget=budget_artifact,
                )
                regression_gate = gate_payload.get("complexity_regression_gate")
                if not isinstance(regression_gate, dict):
                    raise PQXSequenceRunnerError("TPA gate must include complexity_regression_gate")
                enforced_regression_decision = enforce_budget_trend_control(
                    existing_decision=str(regression_gate.get("decision")),
                    budget=budget_artifact,
                    trend=trend_artifact,
                )
                if enforced_regression_decision != regression_gate.get("decision"):
                    raise PQXSequenceRunnerError(
                        "TPA gate complexity_regression_gate.decision under-enforced relative to complexity budget/trend"
                    )
                regression_gate = gate_payload.get("complexity_regression_gate")
                if not isinstance(regression_gate, dict):
                    raise PQXSequenceRunnerError("TPA gate must include complexity_regression_gate")
                if regression_gate.get("decision") not in {"allow", "warn", "freeze", "block"}:
                    raise PQXSequenceRunnerError("TPA gate complexity_regression_gate.decision invalid")
                if regression_gate.get("regression_detected") and regression_gate.get("decision") == "allow":
                    raise PQXSequenceRunnerError("TPA gate must block/freeze/warn regressions per policy")
                cleanup_validation = gate_payload.get("cleanup_only_validation")
                execution_mode = str(artifacts["plan"]["artifact"].get("execution_mode") or "")
                if execution_mode == "cleanup_only":
                    if not isinstance(cleanup_validation, dict):
                        raise PQXSequenceRunnerError("TPA cleanup-only gate requires cleanup_only_validation")
                    if not bool(cleanup_validation.get("mode_enabled")):
                        raise PQXSequenceRunnerError("TPA cleanup-only gate requires mode_enabled=true")

                composition_decision = resolve_tpa_policy_decision(
                    {
                        "required_scope": bool(required_scope),
                        "tpa_lineage_present": True,
                        "execution_mode": execution_mode,
                        "cleanup_only_validation": cleanup_validation,
                        "complexity_decision": str(regression_gate.get("decision") or "allow"),
                        "simplicity_decision": str(simplicity_decision or "allow"),
                        "promotion_ready_requested": bool(gate_payload.get("promotion_ready")),
                        "tpa_mode": tpa_mode,
                        "lightweight_eligible": True,
                    },
                    composition=tpa_policy_composition,
                )
                if execution_mode == "cleanup_only" and "cleanup_only_missing_equivalence" in composition_decision["blocking_reasons"]:
                    raise PQXSequenceRunnerError("TPA cleanup-only gate requires strict equivalence proof")
                if execution_mode == "cleanup_only" and "cleanup_only_missing_replay_ref" in composition_decision["blocking_reasons"]:
                    raise PQXSequenceRunnerError("TPA cleanup-only gate requires replay_ref")
                if bool(gate_payload.get("promotion_ready")) and not composition_decision["promotion_ready"]:
                    raise PQXSequenceRunnerError(
                        "TPA gate cannot mark promotion_ready when contract-backed policy composition resolves freeze/block"
                    )
                artifacts["gate"] = _build_tpa_slice_artifact(
                    run_id=run_id,
                    trace_id=request["trace_id"],
                    slice_id=next_slice_id,
                    produced_at=iso_now(clock),
                    artifact_payload=gate_payload,
                    tpa_mode=tpa_mode,
                )
                artifacts["determinism_comparison_artifact"] = {
                    "artifact_type": "tpa_determinism_comparison",
                    "run_id": run_id,
                    "trace_id": request["trace_id"],
                    "step_id": step_id,
                    "selected_pass": deterministic_selected,
                    "phase_order": ["plan", "build", "simplify", "gate"],
                    "selection_hash": _canonical_hash(
                        {
                            "run_id": run_id,
                            "step_id": step_id,
                            "selected_pass": deterministic_selected,
                            "selection_inputs": selection_inputs,
                            "selection_metrics": gate_payload.get("selection_metrics"),
                        }
                    ),
                }
                artifacts["observability_summary"] = _build_tpa_observability_summary(
                    run_id=run_id,
                    trace_id=request["trace_id"],
                    step_id=step_id,
                    generated_at=iso_now(clock),
                    gate_payload=gate_payload,
                    plan_payload=artifacts["plan"]["artifact"],
                    bypass_signals=bypass_signals,
                )
                artifacts["complexity_budget"] = budget_artifact
                artifacts["complexity_trend"] = trend_artifact
                artifacts["simplification_campaign"] = campaign_artifact
                priority_history = artifacts.get("control_priority_signal_history", [])
                if not isinstance(priority_history, list):
                    raise PQXSequenceRunnerError("TPA control priority signal history must be a list")
                previous_priority_signal = priority_history[-1] if priority_history else None
                corroborating_refs = sorted(
                    {
                        str(ref).strip()
                        for ref in (
                            list(gate_payload.get("risk_mitigation_refs") or [])
                            + list(gate_payload.get("addressed_failure_pattern_refs") or [])
                            + list(gate_payload.get("selection_inputs") or [])
                        )
                        if str(ref).strip()
                    }
                )
                priority_signal = build_control_priority_signal(
                    existing_decision=str(regression_gate.get("decision") or "allow"),
                    budget=budget_artifact,
                    trend=trend_artifact,
                    previous_priority_signal=previous_priority_signal if isinstance(previous_priority_signal, dict) else None,
                    driver_signal_sources=[
                        "tpa_local:complexity_budget",
                        "tpa_local:complexity_trend",
                        "tpa_local:simplification_campaign",
                    ],
                    corroborating_signal_refs=corroborating_refs,
                )
                priority_history.append(deepcopy(priority_signal))
                artifacts["control_priority_signal_history"] = priority_history
                artifacts["control_priority_signal"] = deepcopy(priority_signal)
                artifacts["observability_consumer"] = build_tpa_observability_consumer_record(
                    run_id=run_id,
                    trace_id=request["trace_id"],
                    step_id=step_id,
                    generated_at=iso_now(clock),
                    observability_summary_ref=f"tpa_observability_summary:{run_id}:{step_id}",
                    observability_summary=artifacts["observability_summary"],
                    priority_score=calculate_tpa_priority_score(
                        budget=budget_artifact,
                        trend=trend_artifact,
                        campaign=campaign_artifact,
                    ),
                    recommended_control_decision=priority_signal["effective_control_decision"],
                )
                artifacts["complexity_recalibration"] = build_complexity_budget_recalibration_record(
                    run_id=run_id,
                    trace_id=request["trace_id"],
                    step_id=step_id,
                    generated_at=iso_now(clock),
                    complexity_budget_ref=f"complexity_budget:{budget_artifact['run_id']}:{budget_artifact['step_id']}",
                    complexity_trend_ref=f"complexity_trend:{trend_artifact['run_id']}:{trend_artifact['step_id']}",
                    observability_summary_ref=f"tpa_observability_summary:{run_id}:{step_id}",
                    observed_slice_count=len(trend_points),
                )
                artifacts["certification_envelope"] = _build_tpa_certification_envelope(
                    run_id=run_id,
                    trace_id=request["trace_id"],
                    step_id=step_id,
                    generated_at=iso_now(clock),
                    plan_artifact=artifacts["plan"],
                    build_artifact=artifacts["build"],
                    simplify_artifact=artifacts["simplify"],
                    gate_artifact=artifacts["gate"],
                    observability_summary=artifacts["observability_summary"],
                    observability_consumer=artifacts["observability_consumer"],
                    complexity_budget=budget_artifact,
                    complexity_trend=trend_artifact,
                    simplification_campaign=campaign_artifact,
                    complexity_recalibration=artifacts["complexity_recalibration"],
                )
        elif required_scope:
            missing_components = ["plan", "build", "simplify", "gate"]
            occurrence_count = len(bypass_signals) + 1
            drift = _build_bypass_signal(
                run_id=run_id,
                trace_id=request["trace_id"],
                slice_id=next_slice_id,
                step_id=step_id,
                request=request,
                missing_components=missing_components,
                occurrence_count=occurrence_count,
                detected_at=iso_now(clock),
            )
            validate_artifact(drift, "tpa_bypass_drift_signal")
            bypass_signals.append(drift)
            state["tpa_bypass_signals"] = deepcopy(bypass_signals)
            raise PQXSequenceRunnerError("tpa_bypass_detected: required scope execution missing mandatory TPA lineage")

        completed_at = iso_now(clock)
        continuation_record_id = None
        if current_index > 0:
            continuation_record_id = next(
                (entry["artifact_id"] for entry in state["continuation_records"] if entry["next_step_id"] == next_slice_id),
                None,
            )
        record = {
            "execution_ref": execution_ref,
            "queue_run_id": queue_run_id,
            "run_id": run_id,
            "trace_id": request["trace_id"],
            "slice_id": next_slice_id,
            "status": "success" if execution_status == "success" else "failed",
            "parent_execution_ref": parent_ref,
            "started_at": started_at,
            "completed_at": completed_at,
            "error": result.get("error"),
            "slice_execution_record_ref": result.get("slice_execution_record"),
            "certification_ref": result.get("done_certification_record"),
            "audit_bundle_ref": result.get("pqx_slice_audit_bundle"),
            "certification_complete": bool(result.get("certification_complete") or result.get("done_certification_record")),
            "audit_complete": bool(result.get("audit_complete") or result.get("pqx_slice_audit_bundle")),
            "continuation_record_id": continuation_record_id,
            "control_surface_gap_visibility": _default_control_surface_gap_visibility(),
        }
        raw_visibility = result.get("control_surface_gap_visibility")
        if raw_visibility is not None:
            record["control_surface_gap_visibility"] = _validate_control_surface_gap_visibility(raw_visibility)
        elif result.get("control_surface_gap_packet_ref") is not None:
            raise PQXSequenceRunnerError(
                "missing control_surface_gap_visibility for slice result carrying control_surface_gap_packet_ref"
            )
        state["execution_history"].append(record)
        state_visibility = state.get("control_surface_gap_visibility")
        if not isinstance(state_visibility, dict):
            raise PQXSequenceRunnerError("prompt_queue_sequence_run missing control_surface_gap_visibility projection")
        by_slice = state_visibility.get("by_slice")
        if not isinstance(by_slice, dict):
            raise PQXSequenceRunnerError("prompt_queue_sequence_run control_surface_gap_visibility.by_slice must be object")
        by_slice[next_slice_id] = record["control_surface_gap_visibility"]
        consumed_entries = [
            entry
            for _, entry in sorted(by_slice.items(), key=lambda pair: pair[0])
            if isinstance(entry, dict) and entry.get("control_surface_gap_packet_consumed") is True
        ]
        if consumed_entries:
            summary = consumed_entries[-1]
        else:
            summary = _default_control_surface_gap_visibility()
        state["control_surface_gap_visibility"] = {"by_slice": by_slice, "summary": summary}
        state["prior_slice_ref"] = execution_ref

        if execution_status == "success":
            state["completed_slice_ids"].append(next_slice_id)
            state["status"] = "running"
            state["blocked_reason"] = None
            state["blocked_continuation_context"] = None
            state["certification_complete_by_slice"][next_slice_id] = record["certification_complete"]
            state["audit_complete_by_slice"][next_slice_id] = record["audit_complete"]
            if bundle_state is not None:
                try:
                    bundle_state = mark_step_complete(
                        bundle_state,
                        resolved_bundle_plan,
                        step_id=next_slice_id,
                        artifact_refs=[],
                        now=completed_at,
                    )
                    save_bundle_state(bundle_state, resolved_bundle_state_path, bundle_plan=resolved_bundle_plan)
                except PQXBundleStateError as exc:
                    raise PQXSequenceRunnerError(str(exc)) from exc
            if current_index == 0 and enforce_review_policy:
                review = review_results.get(next_slice_id)
                if review is None:
                    state["review_checkpoint_status"]["slice_1_optional_review"] = "not_required"
                elif review.get("has_blocking_findings"):
                    state["review_checkpoint_status"]["slice_1_optional_review"] = "blocked"
                    state["status"] = "blocked"
                    state["blocked_reason"] = "optional slice-1 review contains blocking findings"
                    _set_termination_reason(state, "BLOCKED_SLICE1_OPTIONAL_REVIEW")
                    return _persist_with_batch_result(state, state_path)
                else:
                    state["review_checkpoint_status"]["slice_1_optional_review"] = "satisfied"
                    state["review_artifact_refs"].append(str(review.get("review_id", f"review:{next_slice_id}")))
            elif current_index == 1 and enforce_review_policy:
                review = review_results.get(next_slice_id)
                if review is None:
                    state["review_checkpoint_status"]["slice_2_required_review"] = "missing"
                    state["status"] = "blocked"
                    state["chain_certification_status"] = "blocked"
                    state["blocked_reason"] = "missing required review after slice 2"
                    _set_termination_reason(state, "BLOCKED_MISSING_REVIEW_SLICE_2")
                    return _persist_with_batch_result(state, state_path)
                if review.get("has_blocking_findings"):
                    state["review_checkpoint_status"]["slice_2_required_review"] = "blocked"
                    state["status"] = "blocked"
                    state["chain_certification_status"] = "blocked"
                    state["blocked_reason"] = "blocking findings after slice 2 review"
                    state["unresolved_fix_ids"].extend(review.get("pending_fix_ids", []))
                    state["bundle_readiness_decision"] = {"ready": False, "reason": "blocking findings unresolved"}
                    _set_termination_reason(state, "BLOCKED_REVIEW_FINDINGS_SLICE_2")
                    return _persist_with_batch_result(state, state_path)
                state["review_checkpoint_status"]["slice_2_required_review"] = "satisfied"
                state["review_artifact_refs"].append(str(review.get("review_id", f"review:{next_slice_id}")))
            elif current_index == 2 and enforce_review_policy:
                review = review_results.get(next_slice_id)
                if review is None:
                    state["review_checkpoint_status"]["slice_3_strict_review"] = "missing"
                    state["status"] = "blocked"
                    state["chain_certification_status"] = "blocked"
                    state["blocked_reason"] = "missing strict review after slice 3"
                    _set_termination_reason(state, "BLOCKED_MISSING_REVIEW_SLICE_3")
                    return _persist_with_batch_result(state, state_path)
                if review.get("overall_disposition") != "approved" or review.get("has_blocking_findings"):
                    state["review_checkpoint_status"]["slice_3_strict_review"] = "blocked"
                    state["status"] = "blocked"
                    state["chain_certification_status"] = "blocked"
                    state["blocked_reason"] = "strict slice-3 review did not pass"
                    state["unresolved_fix_ids"].extend(review.get("pending_fix_ids", []))
                    state["bundle_readiness_decision"] = {"ready": False, "reason": "blocking findings unresolved"}
                    _set_termination_reason(state, "BLOCKED_REVIEW_FINDINGS_SLICE_3")
                    return _persist_with_batch_result(state, state_path)
                state["review_checkpoint_status"]["slice_3_strict_review"] = "satisfied"
                state["review_artifact_refs"].append(str(review.get("review_id", f"review:{next_slice_id}")))
        else:
            state["failed_slice_ids"].append(next_slice_id)
            if execution_status == "review_required":
                state["status"] = "blocked"
                state["blocked_reason"] = result.get("error") or "slice_requires_review"
                _set_termination_reason(state, "STOPPED_REVIEW_REQUIRED")
            elif execution_status == "blocked":
                state["status"] = "blocked"
                state["blocked_reason"] = result.get("error") or "slice_execution_blocked"
                _set_termination_reason(state, "STOPPED_BLOCKED")
            else:
                state["status"] = "failed"
                state["blocked_reason"] = result.get("error") or "slice_execution_failed"
                _set_termination_reason(state, "STOPPED_FAILED")
            if bundle_state is not None:
                try:
                    bundle_state = bundle_block_step(
                        bundle_state,
                        resolved_bundle_plan,
                        step_id=next_slice_id,
                        now=completed_at,
                    )
                    save_bundle_state(bundle_state, resolved_bundle_state_path, bundle_plan=resolved_bundle_plan)
                except PQXBundleStateError as exc:
                    raise PQXSequenceRunnerError(str(exc)) from exc

        failure_rows = [row for row in state["execution_history"] if row["status"] == "failed"]
        severity_total = sum(1 if not row.get("error") else 2 for row in failure_rows)
        budget = {
            "schema_version": "1.0.0",
            "artifact_type": "pqx_sequence_budget",
            "sequence_id": queue_run_id,
            "thresholds": {
                "max_failed_slices": int(budget_thresholds.get("max_failed_slices", 1)),
                "max_cumulative_severity": int(budget_thresholds.get("max_cumulative_severity", 5)),
            },
            "slice_failures": [
                {
                    "slice_id": row["slice_id"],
                    "failure_count": 1 if row["status"] == "failed" else 0,
                    "failure_severity": 0 if row["status"] != "failed" else (1 if not row.get("error") else 2),
                }
                for row in state["execution_history"]
            ],
            "cumulative_failure_severity": severity_total,
            "threshold_breached": len(failure_rows) > int(budget_thresholds.get("max_failed_slices", 1))
            or severity_total > int(budget_thresholds.get("max_cumulative_severity", 5)),
            "created_at": iso_now(clock),
        }
        budget["status"] = "exceeded_budget" if budget["threshold_breached"] else "within_budget"
        validate_artifact(budget, "pqx_sequence_budget")
        state["sequence_budget_ref"] = f"{queue_run_id}:sequence-budget"
        state["sequence_budget_status"] = budget["status"]
        if budget["threshold_breached"]:
            state["status"] = "blocked"
            state["blocked_reason"] = "sequence failure budget exceeded"
            _set_termination_reason(state, "BLOCKED_SEQUENCE_BUDGET_EXCEEDED")
            return _persist_with_batch_result(state, state_path)

        state["current_slice_id"] = None
        state["next_slice_ref"] = _next_pending_slice(requested_ids, state["completed_slice_ids"], state["failed_slice_ids"])
        state["updated_at"] = completed_at
        state["resume_token"] = f"resume:{queue_run_id}:{len(state['completed_slice_ids'])}"
        if execution_status == "success":
            _set_termination_reason(state, "not_terminated")
        _validate_trace_completeness(state)
        state = _persist_and_reload_exact(state, state_path)
        executed_this_call += 1

        if execution_status != "success":
            result = deepcopy(state)
            result["batch_result"] = _build_batch_result(state)
            return result


def verify_two_slice_replay(
    *,
    baseline_state_path: str | Path,
    replay_state_path: str | Path,
    output_path: str | Path,
    queue_run_id: str,
    run_id: str,
    trace_id: str,
    clock=utc_now,
) -> dict:
    baseline = json.loads(Path(baseline_state_path).read_text(encoding="utf-8"))
    replay = json.loads(Path(replay_state_path).read_text(encoding="utf-8"))
    _validate_state_contract(baseline)
    _validate_state_contract(replay)

    def _normalize_continuations(rows: list[dict]) -> list[dict]:
        normalized = []
        for row in rows:
            clone = {k: v for k, v in row.items() if k != "created_at"}
            normalized.append(clone)
        return normalized

    def _normalize_history(rows: list[dict]) -> list[dict]:
        keys = [
            "slice_id",
            "status",
            "trace_id",
            "slice_execution_record_ref",
            "certification_ref",
            "audit_bundle_ref",
            "certification_complete",
            "audit_complete",
            "continuation_record_id",
        ]
        return [{k: row.get(k) for k in keys} for row in rows]

    if baseline.get("queue_run_id") != queue_run_id or replay.get("queue_run_id") != queue_run_id:
        raise PQXSequenceRunnerError("two-slice replay identity mismatch for queue_run_id")
    if baseline.get("run_id") != run_id or replay.get("run_id") != run_id:
        raise PQXSequenceRunnerError("two-slice replay identity mismatch for run_id")
    if baseline.get("trace_id") != trace_id or replay.get("trace_id") != trace_id:
        raise PQXSequenceRunnerError("two-slice replay identity mismatch for trace_id")

    normalized_baseline_continuations = _normalize_continuations(baseline["continuation_records"])
    normalized_replay_continuations = _normalize_continuations(replay["continuation_records"])
    normalized_baseline_history = _normalize_history(baseline["execution_history"])
    normalized_replay_history = _normalize_history(replay["execution_history"])
    decision_sequence_match = baseline.get("run_fingerprint", {}).get("decision_sequence") == replay.get("run_fingerprint", {}).get(
        "decision_sequence"
    )
    termination_reason_match = baseline.get("termination_reason") == replay.get("termination_reason")
    final_outcome_match = baseline.get("status") == replay.get("status")
    completed_step_ids_match = baseline["completed_slice_ids"] == replay["completed_slice_ids"]
    baseline_history_trace_ids = [
        record.get("trace_id")
        for record in baseline.get("execution_history", [])
        if isinstance(record, dict)
    ]
    replay_history_trace_ids = [
        record.get("trace_id")
        for record in replay.get("execution_history", [])
        if isinstance(record, dict)
    ]
    trace_linkage_match = baseline_history_trace_ids == replay_history_trace_ids
    admitted_input_hash_match = baseline.get("admitted_input_hash") == replay.get("admitted_input_hash")
    mismatch_details = {
        "termination_reason_mismatch": not termination_reason_match,
        "decision_sequence_mismatch": not decision_sequence_match,
        "final_outcome_mismatch": not final_outcome_match,
        "admitted_input_hash_mismatch": not admitted_input_hash_match,
        "completed_step_ids_mismatch": not completed_step_ids_match,
        "trace_linkage_mismatch": not trace_linkage_match,
    }
    mismatch_order = [
        "termination_reason_mismatch",
        "decision_sequence_mismatch",
        "final_outcome_mismatch",
        "admitted_input_hash_mismatch",
        "completed_step_ids_mismatch",
        "trace_linkage_mismatch",
    ]
    active_mismatches = [field for field in mismatch_order if mismatch_details[field]]

    parity = (
        not active_mismatches
        and normalized_baseline_continuations == normalized_replay_continuations
        and normalized_baseline_history == normalized_replay_history
        and baseline["certification_complete_by_slice"] == replay["certification_complete_by_slice"]
        and baseline["audit_complete_by_slice"] == replay["audit_complete_by_slice"]
        and baseline.get("chain_certification_status") == replay.get("chain_certification_status")
        and baseline.get("bundle_certification_status") == replay.get("bundle_certification_status")
        and baseline.get("run_fingerprint", {}).get("fingerprint_hash") == replay.get("run_fingerprint", {}).get("fingerprint_hash")
    )
    replay_id = "queue-replay-" + hashlib.sha256(
        f"{queue_run_id}:{run_id}:{trace_id}:{baseline['resume_token']}:{replay['resume_token']}".encode("utf-8")
    ).hexdigest()
    record = {
        "replay_id": replay_id,
        "queue_id": queue_run_id,
        "checkpoint_ref": baseline_state_path if isinstance(baseline_state_path, str) else str(baseline_state_path),
        "input_refs": [
            baseline_state_path if isinstance(baseline_state_path, str) else str(baseline_state_path),
            replay_state_path if isinstance(replay_state_path, str) else str(replay_state_path),
        ],
        "replay_result_summary": {
            "replayed_step_id": "step-002",
            "decision_match": normalized_baseline_continuations == normalized_replay_continuations,
            "state_match": completed_step_ids_match,
            "transition_match": normalized_baseline_history == normalized_replay_history,
            "termination_reason_match": termination_reason_match,
            "decision_sequence_match": decision_sequence_match,
            "final_outcome_match": final_outcome_match,
        },
        "parity_status": "match" if parity else "mismatch",
        "mismatch_summary": None if parity else "; ".join(active_mismatches),
        "trace_id": trace_id,
        "timestamp": iso_now(clock),
    }
    validate_artifact(record, "prompt_queue_replay_record")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

    replay_status = "pass" if parity else "fail"
    baseline["replay_verification"] = {"status": replay_status, "replay_record_ref": str(output)}
    replay["replay_verification"] = {"status": replay_status, "replay_record_ref": str(output)}
    Path(baseline_state_path).write_text(json.dumps(baseline, indent=2) + "\n", encoding="utf-8")
    Path(replay_state_path).write_text(json.dumps(replay, indent=2) + "\n", encoding="utf-8")

    if not parity:
        raise PQXSequenceRunnerError(
            "two-slice replay verification failed closed: "
            + json.dumps(
                {
                    "parity_status": "mismatch",
                    "mismatch_details": mismatch_details,
                    "mismatch_summary": record["mismatch_summary"],
                },
                sort_keys=True,
            )
        )
    return {
        **record,
        "mismatch_details": mismatch_details,
        "mismatch_summary_human": "match" if parity else f"mismatch: {record['mismatch_summary']}",
    }


def execute_bundle_sequence_run(
    *,
    bundle_id: str,
    bundle_state_path: str | Path,
    output_dir: str | Path,
    run_id: str,
    queue_run_id: str,
    trace_id: str,
    bundle_plan_path: str | Path = "docs/roadmaps/execution_bundles.md",
    execute_step: SliceExecutor | None = None,
    clock=utc_now,
) -> dict:
    """Additive bundle invocation path preserving existing step-oriented flows."""

    from spectrum_systems.modules.runtime.pqx_bundle_orchestrator import execute_bundle_run

    return execute_bundle_run(
        bundle_id=bundle_id,
        bundle_state_path=bundle_state_path,
        output_dir=output_dir,
        run_id=run_id,
        sequence_run_id=queue_run_id,
        trace_id=trace_id,
        bundle_plan_path=bundle_plan_path,
        execute_step=execute_step,
        clock=clock,
    )
