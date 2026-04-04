"""Operator-focused one-cycle orchestration for bounded roadmap execution and usability artifacts (BATCH-U)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_example, load_schema
from spectrum_systems.modules.runtime.autonomy_guardrails import (
    build_allow_decision_proof,
    build_decision_proof_record,
    build_unknown_state_signal,
    evaluate_autonomy_guardrails,
)
from spectrum_systems.modules.runtime.continuous_governance import (
    build_canary_rollout_record,
    build_continuous_eval_run_records,
    build_observability_reports,
    build_system_budget_status,
)
from spectrum_systems.modules.runtime.adaptive_execution_observability import (
    build_adaptive_execution_observability,
    build_adaptive_execution_policy_review,
    build_adaptive_execution_trend_report,
)
from spectrum_systems.modules.runtime.capability_readiness import evaluate_capability_readiness
from spectrum_systems.modules.runtime.roadmap_adjustment_engine import (
    apply_roadmap_adjustments,
    derive_roadmap_adjustments,
)
from spectrum_systems.modules.runtime.roadmap_multi_batch_executor import execute_bounded_roadmap_run
from spectrum_systems.modules.runtime.exception_router import (
    classify_exception_state,
    route_exception_resolution,
)
from spectrum_systems.modules.runtime.system_integration_validator import validate_core_system_integration


class SystemCycleOperatorError(ValueError):
    """Raised when a system cycle cannot be produced deterministically."""


def _canonical_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _validate_schema(instance: dict[str, Any], schema_name: str) -> None:
    validator = Draft202012Validator(load_schema(schema_name), format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda err: list(err.absolute_path))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise SystemCycleOperatorError(f"{schema_name} validation failed: {details}")


def _sorted_unique_strings(values: list[Any]) -> list[str]:
    return sorted({str(item) for item in values if str(item).strip()})


def _normalize_failure_keys(
    *,
    stop_reason: str,
    blocking_conditions: list[str],
    unknown_state_blockers: list[str],
    autonomy_blockers: list[str],
    required_validations_next: list[str],
    replay_status: str,
    program_drift_severity: str,
) -> list[str]:
    keys: set[str] = {f"stop_reason:{stop_reason}"}
    keys.update(f"blocking:{item.lower()}" for item in blocking_conditions)
    keys.update(f"unknown_state:{item.lower()}" for item in unknown_state_blockers)
    keys.update(f"autonomy:{item.lower()}" for item in autonomy_blockers)
    if required_validations_next:
        keys.add("missing_eval_coverage")
    if replay_status in {"mismatch", "failed", "error"}:
        keys.add("replay_mismatch")
    if replay_status == "unknown":
        keys.add("replay_unknown")
    if program_drift_severity in {"medium", "high"}:
        keys.add(f"drift:{program_drift_severity}")
    return sorted(keys)


def build_failure_taxonomy_record(
    *,
    source_exception_ref: str,
    source_batch_id: str,
    source_cycle_id: str,
    normalized_failure_keys: list[str],
    required_validations_next: list[str],
    replay_status: str,
    program_drift_severity: str,
    unknown_state_blockers: list[str],
    autonomy_blockers: list[str],
    prior_failure_taxonomy_records: list[dict[str, Any]],
    created_at: str,
    trace_id: str,
) -> dict[str, Any]:
    if not normalized_failure_keys:
        raise SystemCycleOperatorError("failure taxonomy requires at least one normalized failure key")
    if unknown_state_blockers:
        failure_class = "unknown_dependency_state"
        severity = "high"
    elif required_validations_next:
        failure_class = "eval_coverage_failure"
        severity = "high"
    elif replay_status in {"mismatch", "failed", "error"}:
        failure_class = "replay_consistency_failure"
        severity = "critical"
    elif replay_status == "unknown":
        failure_class = "replay_consistency_failure"
        severity = "high"
    elif autonomy_blockers:
        failure_class = "autonomy_guardrail_failure"
        severity = "high"
    elif program_drift_severity == "high":
        failure_class = "drift_instability"
        severity = "critical"
    elif program_drift_severity == "medium":
        failure_class = "drift_instability"
        severity = "high"
    elif any(item.startswith("AUTH_") or item.startswith("PROP_") for item in normalized_failure_keys):
        failure_class = "policy_blocker"
        severity = "high"
    else:
        failure_class = "execution_failure"
        severity = "medium"

    current_key_set = set(normalized_failure_keys)
    prior_matches = 0
    first_seen_at = created_at
    for row in prior_failure_taxonomy_records:
        if not isinstance(row, dict):
            raise SystemCycleOperatorError("prior failure taxonomy records must be objects")
        _validate_schema(row, "failure_taxonomy_record")
        prior_key_set = set(str(item) for item in row.get("normalized_failure_keys", []))
        if str(row.get("failure_class")) == failure_class and bool(prior_key_set & current_key_set):
            prior_matches += 1
            candidate_first_seen = str(row.get("first_seen_at") or created_at)
            if candidate_first_seen < first_seen_at:
                first_seen_at = candidate_first_seen

    seed = {
        "source_exception_ref": source_exception_ref,
        "source_batch_id": source_batch_id,
        "source_cycle_id": source_cycle_id,
        "normalized_failure_keys": normalized_failure_keys,
        "failure_class": failure_class,
        "trace_id": trace_id,
    }
    record = {
        "failure_taxonomy_id": f"FTX-{_canonical_hash(seed)[:12].upper()}",
        "source_exception_ref": source_exception_ref,
        "source_batch_id": source_batch_id,
        "source_cycle_id": source_cycle_id,
        "normalized_failure_keys": normalized_failure_keys,
        "failure_class": failure_class,
        "severity": severity,
        "recurrence_count": prior_matches + 1,
        "first_seen_at": first_seen_at,
        "last_seen_at": created_at,
        "created_at": created_at,
        "trace_id": trace_id,
    }
    _validate_schema(record, "failure_taxonomy_record")
    return record


def derive_correction_pattern(
    *,
    failure_taxonomy_record: dict[str, Any],
    source_exception_ref: str,
    unknown_state_signal_refs: list[str],
    recurrence_threshold: int,
    created_at: str,
    trace_id: str,
) -> dict[str, Any] | None:
    _validate_schema(failure_taxonomy_record, "failure_taxonomy_record")
    if int(failure_taxonomy_record["recurrence_count"]) < recurrence_threshold:
        return None

    failure_class = str(failure_taxonomy_record["failure_class"])
    if failure_class == "eval_coverage_failure":
        pattern_key = "missing_eval_coverage"
        remediation = "eval_coverage_remediation"
    elif failure_class == "replay_consistency_failure":
        pattern_key = "replay_mismatch"
        remediation = "replay_investigation"
    elif failure_class == "unknown_dependency_state":
        pattern_key = "unknown_dependency_state"
        remediation = "dependency_hardening"
    elif failure_class == "autonomy_guardrail_failure":
        pattern_key = "autonomy_guardrail_block"
        remediation = "autonomy_guardrail_remediation"
    elif failure_class == "policy_blocker":
        pattern_key = "policy_blocker"
        remediation = "policy_alignment_remediation"
    elif failure_class == "drift_instability":
        pattern_key = "drift_instability"
        remediation = "drift_stabilization"
    else:
        pattern_key = "general_failure"
        remediation = "manual_review"

    seed = {
        "source_failure_taxonomy_ref": f"failure_taxonomy_record:{failure_taxonomy_record['failure_taxonomy_id']}",
        "pattern_key": pattern_key,
        "remediation": remediation,
        "trace_id": trace_id,
    }
    record = {
        "correction_pattern_id": f"CPR-{_canonical_hash(seed)[:12].upper()}",
        "source_failure_taxonomy_ref": f"failure_taxonomy_record:{failure_taxonomy_record['failure_taxonomy_id']}",
        "pattern_key": pattern_key,
        "recommended_remediation_type": remediation,
        "supporting_artifact_refs": sorted(
            set(
                [
                    f"failure_taxonomy_record:{failure_taxonomy_record['failure_taxonomy_id']}",
                    source_exception_ref,
                ] + unknown_state_signal_refs
            )
        ),
        "recurrence_threshold_met": True,
        "created_at": created_at,
        "trace_id": trace_id,
    }
    _validate_schema(record, "correction_pattern_record")
    return record


def build_rollback_plan_record(
    *,
    source_batch_id: str,
    source_artifact_refs: list[str],
    roadmap_adjustment_refs: list[str],
    next_cycle_decision: str,
    created_at: str,
    trace_id: str,
) -> dict[str, Any]:
    promotion_sensitive = bool(roadmap_adjustment_refs) or next_cycle_decision == "run_next_cycle"
    rollback_actions: list[dict[str, Any]] = []
    sequence = 1
    for ref in sorted(set(roadmap_adjustment_refs)):
        rollback_actions.append({"action_type": "revert_roadmap_adjustment", "target_ref": ref, "sequence": sequence})
        sequence += 1
    if next_cycle_decision == "run_next_cycle":
        rollback_actions.append({"action_type": "restore_next_cycle_gate", "target_ref": f"batch:{source_batch_id}", "sequence": sequence})
        sequence += 1
    if not rollback_actions and promotion_sensitive:
        rollback_actions.append({"action_type": "manual_hold", "target_ref": f"batch:{source_batch_id}", "sequence": sequence})
    reversibility_status = "not_required"
    if promotion_sensitive and rollback_actions and all(item["action_type"] != "manual_hold" for item in rollback_actions):
        reversibility_status = "reversible"
    elif promotion_sensitive and rollback_actions:
        reversibility_status = "not_reversible"
    required_preconditions = sorted(
        set(
            ["requires_snapshot:batch_handoff_bundle", "requires_snapshot:build_summary"]
            + ([f"requires_snapshot:{item}" for item in roadmap_adjustment_refs] if roadmap_adjustment_refs else [])
        )
    )
    seed = {
        "source_batch_id": source_batch_id,
        "source_artifact_refs": sorted(set(source_artifact_refs)),
        "rollback_actions": rollback_actions,
        "trace_id": trace_id,
    }
    record = {
        "rollback_plan_id": f"RBP-{_canonical_hash(seed)[:12].upper()}",
        "source_batch_id": source_batch_id,
        "source_artifact_refs": sorted(set(source_artifact_refs)),
        "rollback_actions": rollback_actions,
        "reversibility_status": reversibility_status,
        "required_preconditions": required_preconditions,
        "created_at": created_at,
        "trace_id": trace_id,
    }
    _validate_schema(record, "rollback_plan_record")
    return record


def evaluate_promotion_consistency(
    *,
    source_batch_id: str,
    evidence_window: list[dict[str, Any]],
    rollback_plan_record: dict[str, Any],
    created_at: str,
    trace_id: str,
) -> dict[str, Any]:
    if not evidence_window:
        raise SystemCycleOperatorError("promotion consistency evidence window cannot be empty")
    runs_considered = len(evidence_window)
    deterministic_matches = sum(1 for item in evidence_window if str(item.get("determinism_status", "")).lower() == "deterministic")
    replay_matches = sum(1 for item in evidence_window if str(item.get("replay_status", "")).lower() in {"passed", "match", "replay_ready", "ready"})
    eval_matches = sum(1 for item in evidence_window if str(item.get("eval_status", "")).lower() in {"pass", "healthy"})
    drift_present = any(bool(item.get("drift_detected")) for item in evidence_window)
    deterministic_rate = deterministic_matches / runs_considered
    replay_rate = replay_matches / runs_considered
    eval_rate = eval_matches / runs_considered
    drift_free_status = "drift_present" if drift_present else "drift_free"

    reason_codes: list[str] = []
    promotion_state = "hold"
    if runs_considered < 3:
        reason_codes.append("insufficient_evidence_window")
        promotion_state = "hold"
    if replay_rate < 1.0:
        reason_codes.append("replay_inconsistency")
        promotion_state = "deny"
    if deterministic_rate < 1.0:
        reason_codes.append("deterministic_instability")
        promotion_state = "deny"
    if drift_present and promotion_state != "deny":
        reason_codes.append("drift_present")
        promotion_state = "hold"
    if eval_rate < 1.0 and promotion_state != "deny":
        reason_codes.append("eval_inconsistency")
        promotion_state = "hold"
    if rollback_plan_record["reversibility_status"] == "not_reversible":
        reason_codes.append("non_reversible_promotion_sensitive_path")
        promotion_state = "deny"
    if not reason_codes:
        reason_codes = ["stable_multi_run_evidence"]
        promotion_state = "allow"

    seed = {
        "source_batch_id": source_batch_id,
        "runs_considered": runs_considered,
        "deterministic_rate": deterministic_rate,
        "replay_rate": replay_rate,
        "eval_rate": eval_rate,
        "drift_free_status": drift_free_status,
        "promotion_state": promotion_state,
        "trace_id": trace_id,
    }
    record = {
        "promotion_consistency_id": f"PCR-{_canonical_hash(seed)[:12].upper()}",
        "source_batch_id": source_batch_id,
        "runs_considered": runs_considered,
        "deterministic_match_rate": deterministic_rate,
        "replay_match_rate": replay_rate,
        "eval_consistency_rate": eval_rate,
        "drift_free_status": drift_free_status,
        "promotion_state": promotion_state,
        "reason_codes": sorted(set(reason_codes)),
        "created_at": created_at,
        "trace_id": trace_id,
    }
    _validate_schema(record, "promotion_consistency_record")
    return record


def validate_explicit_state_dependencies(
    *,
    prior_handoff_bundle: dict[str, Any] | None,
    source_cycle_runner_result_ref: str,
    require_prior_handoff: bool,
) -> list[str]:
    missing: list[str] = []
    if not source_cycle_runner_result_ref.startswith("cycle_runner_result:CRR-"):
        missing.append("missing_governed_source_cycle_runner_result_ref")
    if require_prior_handoff and prior_handoff_bundle is None:
        missing.append("missing_prior_handoff_bundle")
    return sorted(set(missing))


def _batch_handoff_sort_key(bundle: dict[str, Any]) -> tuple[str, str]:
    return (str(bundle.get("created_at") or ""), str(bundle.get("bundle_id") or ""))


def _load_latest_prior_batch_handoff_bundle(*, handoff_root: Path | None, required: bool) -> dict[str, Any] | None:
    if handoff_root is None:
        if required:
            raise SystemCycleOperatorError("prior batch_handoff_bundle is required but no handoff root is configured")
        return None
    if not handoff_root.exists():
        if required:
            raise SystemCycleOperatorError(f"prior batch_handoff_bundle is required but directory is missing: {handoff_root}")
        return None
    if not handoff_root.is_dir():
        raise SystemCycleOperatorError(f"handoff bundle root must be a directory: {handoff_root}")

    valid: list[dict[str, Any]] = []
    latest_error: str | None = None
    for path in sorted(handoff_root.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            latest_error = f"{path}: {exc}"
            continue
        if not isinstance(payload, dict):
            latest_error = f"{path}: payload root must be object"
            continue
        try:
            _validate_schema(payload, "batch_handoff_bundle")
        except SystemCycleOperatorError as exc:
            latest_error = f"{path}: {exc}"
            continue
        valid.append(payload)

    if valid:
        return sorted(valid, key=_batch_handoff_sort_key)[-1]
    if required:
        raise SystemCycleOperatorError(f"required prior batch_handoff_bundle unavailable: {latest_error or 'none found'}")
    return None


def derive_batch_handoff_bundle(
    delivery_report: dict[str, Any],
    *,
    exception_classification_record: dict[str, Any] | None = None,
    exception_resolution_record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _validate_schema(delivery_report, "batch_delivery_report")
    risks = _sorted_unique_strings(list(delivery_report.get("remaining_risks", [])))
    followups = _sorted_unique_strings(list(delivery_report.get("open_followups", [])))
    review_findings = _sorted_unique_strings(list(delivery_report.get("blocking_issues", [])))
    required_validations_next = sorted(item for item in followups if item.startswith("validation:"))
    autonomy_blockers = sorted(item for item in followups if item.startswith("autonomy_blocker:"))
    open_contract_work = sorted(item for item in followups if item.startswith("contract:"))
    evidence_refs = _sorted_unique_strings(list(delivery_report.get("evidence_refs", [])))
    decision_proof_ref = next(
        (item for item in evidence_refs if item.startswith("decision_proof_record:")),
        "decision_proof_record:DPR-000000000000",
    )
    allow_decision_proof_ref = next(
        (item for item in evidence_refs if item.startswith("allow_decision_proof:")),
        "allow_decision_proof:ADP-000000000000",
    )
    failure_taxonomy_ref = next(
        (item for item in evidence_refs if item.startswith("failure_taxonomy_record:")),
        "failure_taxonomy_record:FTX-000000000000",
    )
    correction_pattern_ref = next(
        (item for item in evidence_refs if item.startswith("correction_pattern_record:")),
        "correction_pattern_record:CPR-000000000000",
    )
    rollback_plan_ref = next(
        (item for item in evidence_refs if item.startswith("rollback_plan_record:")),
        "rollback_plan_record:RBP-000000000000",
    )
    promotion_consistency_ref = next(
        (item for item in evidence_refs if item.startswith("promotion_consistency_record:")),
        "promotion_consistency_record:PCR-000000000000",
    )
    system_budget_status_ref = next(
        (item for item in evidence_refs if item.startswith("system_budget_status:")),
        "system_budget_status:SBS-000000000000",
    )
    canary_rollout_ref = next(
        (item for item in evidence_refs if item.startswith("canary_rollout_record:")),
        "canary_rollout_record:CNR-000000000000",
    )
    continuous_eval_run_refs = sorted(item for item in evidence_refs if item.startswith("continuous_eval_run_record:"))
    if not continuous_eval_run_refs:
        continuous_eval_run_refs = [
            "continuous_eval_run_record:CER-000000000001",
            "continuous_eval_run_record:CER-000000000002",
            "continuous_eval_run_record:CER-000000000003",
            "continuous_eval_run_record:CER-000000000004",
        ]
    trust_posture_snapshot_ref = next(
        (item for item in evidence_refs if item.startswith("trust_posture_snapshot:")),
        "trust_posture_snapshot:TPS-000000000000",
    )
    unknown_state_signal_refs = sorted(item for item in evidence_refs if item.startswith("unknown_state_signal:"))
    unknown_state_blockers = sorted(item for item in followups if item.startswith("unknown_state_blocker:"))
    program_constraints = sorted(item for item in risks if item.startswith("program_"))
    human_decision_required = bool(
        review_findings
        or any("critical" in item.lower() for item in risks)
        or delivery_report.get("recommended_next_batch") is None
    )
    seed = {
        "source_batch_id": delivery_report["batch_id"],
        "roadmap_id": delivery_report["roadmap_id"],
        "recommended_next_batch": delivery_report["recommended_next_batch"],
        "must_carry_forward_risks": risks,
        "open_review_findings": review_findings,
        "required_validations_next": required_validations_next,
        "trace_id": delivery_report["trace_id"],
    }
    latest_exception_class = str((exception_classification_record or {}).get("exception_class") or "unknown_blocker")
    latest_exception_resolution_action = str((exception_resolution_record or {}).get("recommended_action") or "require_human_review")
    latest_exception_action_type = str((exception_resolution_record or {}).get("action_type") or "stop_without_auto_action")
    latest_exception_requires_human_review = bool((exception_resolution_record or {}).get("requires_human_review", True))
    latest_exception_requires_freeze = bool((exception_resolution_record or {}).get("requires_freeze", False))
    required_next_actions = sorted(
        set(
            [f"action:{latest_exception_action_type}", f"recommendation:{latest_exception_resolution_action}"]
            + [f"followup_artifact:{item}" for item in (exception_resolution_record or {}).get("required_followup_artifacts", [])]
        )
    )
    bundle = {
        "bundle_id": f"BHB-{_canonical_hash(seed)[:12].upper()}",
        "schema_version": "1.6.0",
        "source_batch_id": delivery_report["batch_id"],
        "roadmap_id": delivery_report["roadmap_id"],
        "recommended_next_batch": delivery_report["recommended_next_batch"],
        "must_carry_forward_risks": risks,
        "must_carry_forward_artifacts": evidence_refs,
        "must_preserve_invariants": [
            "artifact_first",
            "deterministic_selection",
            "fail_closed",
            "no_hidden_memory",
            "trace_linkage",
        ],
        "required_validations_next": required_validations_next,
        "autonomy_blockers": autonomy_blockers,
        "autonomy_decision_ref": next(
            (item for item in evidence_refs if item.startswith("autonomy_decision_record:")),
            "autonomy_decision_record:ADR-000000000000",
        ),
        "decision_proof_ref": decision_proof_ref,
        "allow_decision_proof_ref": allow_decision_proof_ref,
        "failure_taxonomy_ref": failure_taxonomy_ref,
        "correction_pattern_ref": correction_pattern_ref,
        "rollback_plan_ref": rollback_plan_ref,
        "promotion_consistency_ref": promotion_consistency_ref,
        "system_budget_status_ref": system_budget_status_ref,
        "canary_rollout_ref": canary_rollout_ref,
        "continuous_eval_run_refs": continuous_eval_run_refs,
        "trust_posture_snapshot_ref": trust_posture_snapshot_ref,
        "unknown_state_signal_refs": unknown_state_signal_refs,
        "unknown_state_blockers": unknown_state_blockers,
        "open_contract_work": open_contract_work,
        "open_review_findings": review_findings,
        "program_constraints": program_constraints,
        "latest_exception_class": latest_exception_class,
        "latest_exception_resolution_action": latest_exception_resolution_action,
        "latest_exception_action_type": latest_exception_action_type,
        "latest_exception_requires_human_review": latest_exception_requires_human_review,
        "latest_exception_requires_freeze": latest_exception_requires_freeze,
        "required_next_actions": required_next_actions,
        "capability_readiness_state": "constrained",
        "capability_readiness_ref": "capability_readiness_record:CRD-000000000000",
        "human_decision_required": human_decision_required,
        "source_delivery_report_ref": f"batch_delivery_report:{delivery_report['report_id']}",
        "trace_id": delivery_report["trace_id"],
        "created_at": delivery_report["created_at"],
    }
    _validate_schema(bundle, "batch_handoff_bundle")
    return bundle



def _normalize_execution_policy(execution_policy: dict[str, Any] | None) -> dict[str, Any]:
    normalized = dict(execution_policy or {})
    normalized.setdefault("max_batches_per_run", 1)
    normalized.setdefault("max_continuation_depth", 0)
    normalized.setdefault("allow_warn_execution", True)
    normalized.setdefault("stop_on_warn", False)
    normalized.setdefault("stop_on_hard_gate", True)
    _validate_schema(normalized, "execution_policy")
    return normalized
def _next_not_started_batch_id(roadmap_artifact: dict[str, Any]) -> str | None:
    for batch in roadmap_artifact.get("batches", []):
        if isinstance(batch, dict) and batch.get("status") == "not_started":
            batch_id = batch.get("batch_id")
            if isinstance(batch_id, str):
                return batch_id
    return None


def _required_reviews(blocking_conditions: list[str]) -> list[str]:
    reviews: set[str] = set()
    for code in blocking_conditions:
        if code.startswith("AUTH_"):
            reviews.add("control_authority_review")
        if code.startswith("PROP_"):
            reviews.add("cross_layer_propagation_review")
        if code.startswith("REPLAY_"):
            reviews.add("replay_chain_review")
        if code.startswith("CERTIFICATION_"):
            reviews.add("certification_gate_review")
        if code.startswith("DETERMINISM_"):
            reviews.add("determinism_review")
    return sorted(reviews)


def _root_cause(stop_reason: str, blocking_conditions: list[str]) -> str:
    if blocking_conditions:
        return f"blocking_condition:{blocking_conditions[0]} (stop_reason={stop_reason})"
    return f"execution_stop_reason:{stop_reason}"


def _root_cause_chain(stop_reason: str, blocking_conditions: list[str]) -> list[dict[str, str]]:
    if not blocking_conditions:
        return [
            {"step": "bounded_execution", "reason": stop_reason},
            {"step": "integration_validation", "reason": "no_blocking_conditions"},
            {"step": "control_outcome", "reason": "proceed_or_continue"},
        ]
    primary = blocking_conditions[0]
    return [
        {"step": "review_or_input_condition", "reason": primary},
        {"step": "evaluation_or_propagation_gap", "reason": "eval_or_propagation_missing"},
        {"step": "control_gate", "reason": "control_block"},
    ]


def _next_action(stop_reason: str, blocking_conditions: list[str]) -> str:
    if blocking_conditions:
        return f"resolve blocker {blocking_conditions[0]} and rerun bounded governed cycle"
    if stop_reason == "max_batches_reached":
        return "run next governed cycle to continue roadmap progression"
    if stop_reason in {"authorization_block", "missing_required_signal", "authorization_freeze"}:
        return "satisfy authorization constraints before rerun"
    if stop_reason == "no_eligible_batch":
        return "refresh roadmap and signal readiness before rerun"
    return "inspect run artifacts and remediate before rerun"


def _watchouts(stop_reason: str, blocking_conditions: list[str], required_reviews: list[str]) -> list[str]:
    watchouts = [
        f"stop_reason={stop_reason}",
        "do_not_bypass_fail_closed_authority_boundaries",
    ]
    if blocking_conditions:
        watchouts.append(f"primary_blocker={blocking_conditions[0]}")
    if required_reviews:
        watchouts.append(f"required_reviews={','.join(required_reviews)}")
    return watchouts


def _resolve_remediation_risk_level(stop_reason: str, blocking_conditions: list[str], required_reviews: list[str]) -> str:
    if blocking_conditions or required_reviews:
        return "high"
    if stop_reason == "max_batches_reached":
        return "low"
    return "medium"


def _build_remediation_steps(
    *,
    stop_reason: str,
    root_cause_chain: list[dict[str, str]],
    blocking_conditions: list[str],
    required_reviews: list[str],
    required_artifacts: list[str],
    review_control_signal: dict[str, Any],
    trace_id: str,
) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    normalized_chain = [item for item in root_cause_chain if isinstance(item, dict)]
    primary_chain_reason = str(normalized_chain[0].get("reason") if normalized_chain else stop_reason)
    repeated_pattern = stop_reason == "repeated_failure_pattern"

    steps.append(
        {
            "step_id": "RMS-01",
            "action": "confirm_root_cause_chain",
            "why": f"stopped_at={stop_reason}; primary_chain_reason={primary_chain_reason}",
            "required_artifacts": sorted(set(required_artifacts + [f"trace:{trace_id}"])),
            "trace_refs": [trace_id, f"stop_reason:{stop_reason}"],
        }
    )

    if required_reviews:
        steps.append(
            {
                "step_id": "RMS-02",
                "action": f"run_required_review:{required_reviews[0]}",
                "why": f"required_reviews={','.join(required_reviews)}",
                "required_artifacts": sorted(set(required_artifacts + [f"review_control_signal:{review_control_signal.get('signal_id', 'missing')}"])),
                "trace_refs": [trace_id, f"review:{required_reviews[0]}"],
            }
        )

    if stop_reason == "contract_precondition_failed":
        steps.append(
            {
                "step_id": "RMS-03",
                "action": "update_contract_or_input_schema",
                "why": "stop_reason indicates contract precondition mismatch",
                "required_artifacts": sorted(set(required_artifacts + ["contracts/schemas/*"])),
                "trace_refs": [trace_id, "contract:precondition_failed"],
            }
        )
    elif stop_reason in {"missing_required_signal", "replay_not_ready"} or blocking_conditions:
        missing_target = blocking_conditions[0] if blocking_conditions else stop_reason
        steps.append(
            {
                "step_id": "RMS-03",
                "action": f"fix_missing_artifact_or_signal:{missing_target}",
                "why": f"bounded run cannot continue until {missing_target} is satisfied",
                "required_artifacts": sorted(set(required_artifacts + [f"blocking_condition:{missing_target}"])),
                "trace_refs": [trace_id, f"missing:{missing_target}"],
            }
        )

    if repeated_pattern:
        steps.append(
            {
                "step_id": "RMS-04",
                "action": "reuse_known_repeated_failure_playbook",
                "why": "repeated_failure_pattern matched deterministic remediation template",
                "required_artifacts": sorted(set(required_artifacts + ["known_failure_pattern:repeated_failure_pattern"])),
                "trace_refs": [trace_id, "pattern:repeated_failure_pattern"],
            }
        )

    steps.append(
        {
            "step_id": "RMS-05",
            "action": "rerun_bounded_batch_cycle",
            "why": "verify remediation resolves stop condition without bypassing governance",
            "required_artifacts": sorted(set(required_artifacts)),
            "trace_refs": [trace_id, "rerun:bounded_cycle"],
        }
    )
    return steps[:5]


def _build_remediation_plan(
    *,
    run_result: dict[str, Any],
    stop_reason: str,
    root_cause: str,
    root_cause_chain: list[dict[str, str]],
    blocking_conditions: list[str],
    required_reviews: list[str],
    integration: dict[str, Any],
    timestamp: str,
    required_artifacts: list[str],
    review_control_signal: dict[str, Any],
) -> dict[str, Any]:
    trace_id = str(integration["trace_id"])
    step_payload = {
        "stop_reason": stop_reason,
        "root_cause_chain": root_cause_chain,
        "blocking_conditions": blocking_conditions,
        "required_reviews": required_reviews,
        "trace_id": trace_id,
    }
    remediation_steps = _build_remediation_steps(
        stop_reason=stop_reason,
        root_cause_chain=root_cause_chain,
        blocking_conditions=blocking_conditions,
        required_reviews=required_reviews,
        required_artifacts=required_artifacts,
        review_control_signal=review_control_signal,
        trace_id=trace_id,
    )
    expected_outcome = (
        "restore bounded continuation readiness"
        if stop_reason != "max_batches_reached"
        else "continue deterministic roadmap progression in next governed cycle"
    )
    return {
        "plan_id": f"RMP-{_canonical_hash({'run_id': run_result['run_id'], 'trace_id': trace_id, 'stop_reason': stop_reason, 'steps': step_payload})[:12].upper()}",
        "root_cause": root_cause,
        "remediation_steps": remediation_steps,
        "required_artifacts": sorted(set(required_artifacts)),
        "expected_outcome": expected_outcome,
        "risk_level": _resolve_remediation_risk_level(stop_reason, blocking_conditions, required_reviews),
        "created_at": timestamp,
        "trace_id": trace_id,
    }


def _candidate_action(candidate_type: str, *, next_batch_id: str | None, blocker: str | None, review: str | None) -> str:
    if candidate_type == "execute_next_batch":
        return f"execute next governed cycle for {next_batch_id}" if next_batch_id else "refresh roadmap eligibility before execution"
    if candidate_type == "resolve_blocker":
        return f"resolve blocker {blocker} and rerun bounded governed cycle"
    if candidate_type == "complete_review":
        return f"complete required review {review} before next execution"
    if candidate_type == "stabilize_repeated_risk":
        return "stabilize repeated risk pattern before continuing roadmap execution"
    return "inspect governed artifacts and remediate before rerun"


def _candidate_required_artifacts(run_id: str, validation_id: str, replay_refs: list[str], *, blocker: str | None) -> list[str]:
    artifacts = {
        f"roadmap_multi_batch_run_result:{run_id}",
        f"core_system_integration_validation:{validation_id}",
    } | set(replay_refs)
    if blocker:
        artifacts.add(f"blocking_condition:{blocker}")
    return sorted(artifacts)


def _replay_entry_points(
    *,
    trace_id: str,
    run_id: str,
    validation_id: str,
    blocker_refs: list[str],
    trace_navigation: dict[str, Any],
) -> dict[str, dict[str, list[str]]]:
    trace_nav_ref = f"trace_navigation:{validation_id}"
    execution_ref = f"roadmap_multi_batch_run_result:{run_id}"
    validation_ref = f"core_system_integration_validation:{validation_id}"
    return {
        "replay_from_context": {
            "required_artifacts": sorted(
                set(
                    [
                        validation_ref,
                        trace_navigation["execution_path"][2],
                        trace_navigation["execution_path"][3],
                    ]
                )
            ),
            "trace_refs": [trace_id, trace_nav_ref],
        },
        "replay_from_plan": {
            "required_artifacts": sorted(
                set(
                    [
                        validation_ref,
                        trace_navigation["execution_path"][0],
                        trace_navigation["execution_path"][1],
                    ]
                )
            ),
            "trace_refs": [trace_id, trace_nav_ref],
        },
        "replay_from_execution": {
            "required_artifacts": sorted(
                set(
                    [
                        execution_ref,
                        validation_ref,
                    ]
                )
            ),
            "trace_refs": [trace_id, execution_ref],
        },
        "replay_from_failure": {
            "required_artifacts": sorted(set([validation_ref] + blocker_refs)),
            "trace_refs": [trace_id, validation_ref],
        },
    }


def _generate_candidates(
    *,
    next_batch_id: str | None,
    run_result: dict[str, Any],
    integration: dict[str, Any],
    required_reviews: list[str],
    blocking_conditions: list[str],
    replay_refs: list[str],
    program_artifact: dict[str, Any],
    context_bundle: dict[str, Any],
    review_control_signal: dict[str, Any],
    control_decision: dict[str, Any],
) -> list[dict[str, Any]]:
    run_id = str(run_result["run_id"])
    validation_id = str(integration["validation_id"])
    deterministic_outcome = str(integration.get("deterministic_outcome", "blocked"))
    authority_status = str(integration.get("authority_boundary_status", "violated"))
    control_state = str(control_decision.get("decision") or run_result.get("stop_reason") or "unknown")
    program_priority = str(program_artifact.get("priority") or "roadmap_progression")
    context_risks = [str(item) for item in (context_bundle.get("risks") or []) if str(item).strip()]
    gate_assessment = str(review_control_signal.get("gate_assessment") or "UNKNOWN")

    candidates: list[dict[str, Any]] = []

    candidates.append(
        {
            "candidate_id": "NSC-EXECUTE-NEXT-BATCH",
            "action": _candidate_action("execute_next_batch", next_batch_id=next_batch_id, blocker=None, review=None),
            "required_artifacts": _candidate_required_artifacts(run_id, validation_id, replay_refs, blocker=None),
            "blockers": sorted(set(blocking_conditions + (["no_eligible_batch"] if next_batch_id is None else []))),
            "risk_profile": {
                "level": "high" if blocking_conditions else ("medium" if next_batch_id is None else "low"),
                "signals": sorted(
                    set(
                        [
                            f"deterministic_outcome={deterministic_outcome}",
                            f"authority_boundary_status={authority_status}",
                            f"control_state={control_state}",
                        ]
                        + [f"context_risk={risk}" for risk in context_risks]
                    )
                ),
            },
            "alignment_with_program": {
                "priority": program_priority,
                "justification": "Advances roadmap progression when eligible and unblocked.",
            },
        }
    )

    for blocker in sorted(set(blocking_conditions)):
        candidates.append(
            {
                "candidate_id": f"NSC-RESOLVE-{blocker}",
                "action": _candidate_action("resolve_blocker", next_batch_id=None, blocker=blocker, review=None),
                "required_artifacts": _candidate_required_artifacts(run_id, validation_id, replay_refs, blocker=blocker),
                "blockers": [blocker],
                "risk_profile": {
                    "level": "high",
                    "signals": [f"blocking_condition={blocker}", f"control_state={control_state}"],
                },
                "alignment_with_program": {
                    "priority": "risk_reduction",
                    "justification": "Unblocks deterministic continuation by removing a current hard blocker.",
                },
            }
        )

    for review in sorted(set(required_reviews)):
        candidates.append(
            {
                "candidate_id": f"NSC-REVIEW-{review}",
                "action": _candidate_action("complete_review", next_batch_id=None, blocker=None, review=review),
                "required_artifacts": _candidate_required_artifacts(run_id, validation_id, replay_refs, blocker=None),
                "blockers": [] if review in required_reviews else [f"review_not_required:{review}"],
                "risk_profile": {
                    "level": "medium",
                    "signals": [f"required_review={review}", f"gate_assessment={gate_assessment}"],
                },
                "alignment_with_program": {
                    "priority": "review_readiness",
                    "justification": "Satisfies mandatory review requirements before execution.",
                },
            }
        )

    repeated_risk = any(code.startswith("PROP_") for code in blocking_conditions) or bool(
        integration.get("repeated_failure_patterns")
    )
    if repeated_risk:
        candidates.append(
            {
                "candidate_id": "NSC-STABILIZE-REPEATED-RISK",
                "action": _candidate_action("stabilize_repeated_risk", next_batch_id=None, blocker=None, review=None),
                "required_artifacts": _candidate_required_artifacts(run_id, validation_id, replay_refs, blocker=None),
                "blockers": sorted(set(blocking_conditions)),
                "risk_profile": {
                    "level": "high",
                    "signals": sorted(set(["repeated_failure_pattern_detected"] + [f"blocker={b}" for b in blocking_conditions])),
                },
                "alignment_with_program": {
                    "priority": "risk_reduction",
                    "justification": "Addresses recurring failure patterns before roadmap expansion.",
                },
            }
        )

    return candidates[:8]


def _score_candidate(candidate: dict[str, Any], *, next_batch_id: str | None, required_reviews: list[str]) -> dict[str, int]:
    blockers = [str(item) for item in candidate.get("blockers", [])]
    risk_level = str(candidate.get("risk_profile", {}).get("level", "medium"))
    priority = str(candidate.get("alignment_with_program", {}).get("priority", ""))
    action = str(candidate.get("action", ""))

    has_active_blockers = bool(blockers)
    program_alignment = 5 if "roadmap_progression" in priority else (4 if "risk_reduction" in priority else 3)
    if next_batch_id is None and "execute next governed cycle" in action:
        program_alignment = 1
    if has_active_blockers and "execute next governed cycle" in action:
        program_alignment = 1

    unblock_potential = 5 if action.startswith("resolve blocker ") else (2 if blockers else 1)
    risk_reduction = 5 if "risk_reduction" in priority else (4 if risk_level == "high" else 2)
    dependency_readiness = 5 if not blockers else 1
    review_readiness = 5 if "complete required review" in action and required_reviews else (3 if not required_reviews else 2)
    return {
        "program_alignment": program_alignment,
        "unblock_potential": unblock_potential,
        "risk_reduction": risk_reduction,
        "dependency_readiness": dependency_readiness,
        "review_readiness": review_readiness,
    }


def _rank_candidates(
    candidates: list[dict[str, Any]], *, next_batch_id: str | None, required_reviews: list[str]
) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for candidate in candidates:
        factors = _score_candidate(candidate, next_batch_id=next_batch_id, required_reviews=required_reviews)
        total = (
            factors["program_alignment"] * 100
            + factors["unblock_potential"] * 10
            + factors["risk_reduction"] * 5
            + factors["dependency_readiness"] * 3
            + factors["review_readiness"]
        )
        ranked.append(
            {
                "candidate": candidate,
                "score": total,
                "ranking_factors": factors,
            }
        )
    return sorted(ranked, key=lambda item: (-item["score"], item["candidate"]["candidate_id"]))


def _build_next_cycle_input_bundle(
    *,
    current_cycle_id: str,
    required_artifacts: list[str],
    next_batch_id: str | None,
    program_alignment_status: str,
    program_stop_cause: str,
    program_drift_severity: str,
    risk_level: str,
    risk_signals: list[str],
    blocking_conditions: list[str],
    required_reviews: list[str],
    autonomy_decision_ref: str,
    decision_proof_ref: str,
    allow_decision_proof_ref: str,
    unknown_state_signal_refs: list[str],
    unknown_state_blockers: list[str],
    autonomy_blockers: list[str],
    exception_classification_record: dict[str, Any],
    exception_resolution_record: dict[str, Any],
    continuation_depth: int,
    source_cycle_runner_result_ref: str,
    trace_navigation: dict[str, Any],
    adaptive_refs: list[str],
    prior_handoff_bundle: dict[str, Any] | None,
    trace_id: str,
    created_at: str,
) -> dict[str, Any]:
    required_reviews_final = sorted(
        set(required_reviews + (prior_handoff_bundle.get("required_validations_next", []) if isinstance(prior_handoff_bundle, dict) else []))
    )
    recommended_start_batch = next_batch_id
    if isinstance(prior_handoff_bundle, dict) and isinstance(prior_handoff_bundle.get("recommended_next_batch"), str):
        recommended_start_batch = str(prior_handoff_bundle["recommended_next_batch"])
    seed = {
        "current_cycle_id": current_cycle_id,
        "required_artifacts": sorted(set(required_artifacts)),
        "next_batch_id": next_batch_id,
        "program_alignment_status": program_alignment_status,
        "program_stop_cause": program_stop_cause,
        "program_drift_severity": program_drift_severity,
        "risk_level": risk_level,
        "blocking_conditions": sorted(set(blocking_conditions)),
        "required_reviews": required_reviews_final,
        "decision_proof_ref": decision_proof_ref,
        "allow_decision_proof_ref": allow_decision_proof_ref,
        "unknown_state_signal_refs": sorted(set(unknown_state_signal_refs)),
        "unknown_state_blockers": sorted(set(unknown_state_blockers)),
        "autonomy_blockers": sorted(set(autonomy_blockers)),
        "autonomy_decision_ref": autonomy_decision_ref,
        "continuation_depth": continuation_depth + 1,
        "source_cycle_runner_result_ref": source_cycle_runner_result_ref,
        "trace_id": trace_id,
    }
    bundle_id = f"NCB-{_canonical_hash(seed)[:12].upper()}"
    context_refs = sorted(
        set(
            [
                f"trace_navigation:{trace_navigation.get('validation_id', 'unknown')}",
                f"roadmap_multi_batch_run_result:{current_cycle_id}",
            ] + adaptive_refs
            + ([f"batch_handoff_bundle:{prior_handoff_bundle['bundle_id']}"] if isinstance(prior_handoff_bundle, dict) else [])
        )
    )
    return {
        "bundle_id": bundle_id,
        "schema_version": "1.3.0",
        "source_cycle_id": current_cycle_id,
        "required_artifacts": sorted(set(required_artifacts)),
        "active_program_constraints": sorted(
            set(
                [
                    f"program_alignment_status={program_alignment_status}",
                    f"program_stop_cause={program_stop_cause}",
                    f"program_drift_severity={program_drift_severity}",
                ]
            )
        ),
        "active_risks": sorted(set([f"risk_level={risk_level}"] + list(risk_signals))),
        "unresolved_blockers": sorted(set(blocking_conditions + autonomy_blockers + unknown_state_blockers)),
        "required_reviews": required_reviews_final,
        "autonomy_decision_ref": autonomy_decision_ref,
        "autonomy_blockers": sorted(set(autonomy_blockers)),
        "decision_proof_ref": decision_proof_ref,
        "allow_decision_proof_ref": allow_decision_proof_ref,
        "unknown_state_signal_refs": sorted(set(unknown_state_signal_refs)),
        "unknown_state_blockers": sorted(set(unknown_state_blockers)),
        "continuation_depth": continuation_depth + 1,
        "source_cycle_runner_result_ref": source_cycle_runner_result_ref,
        "recommended_start_batch": recommended_start_batch,
        "latest_exception_class": exception_classification_record["exception_class"],
        "latest_exception_resolution_action": exception_resolution_record["recommended_action"],
        "latest_exception_action_type": exception_resolution_record["action_type"],
        "latest_exception_requires_human_review": exception_resolution_record["requires_human_review"],
        "latest_exception_requires_freeze": exception_resolution_record["requires_freeze"],
        "required_next_actions": sorted(
            set(
                [f"action:{exception_resolution_record['action_type']}", f"recommendation:{exception_resolution_record['recommended_action']}"]
                + [f"followup_artifact:{item}" for item in exception_resolution_record["required_followup_artifacts"]]
            )
        ),
        "context_refs": context_refs,
        "created_at": created_at,
        "trace_id": trace_id,
    }


def decide_next_cycle(
    *,
    current_cycle_id: str,
    stop_reason: str,
    program_constraint_signal: dict[str, Any],
    program_feedback_record: dict[str, Any],
    roadmap_state: dict[str, Any],
    batch_continuation_records: list[dict[str, Any]],
    eval_control_state: dict[str, Any],
    failure_pattern_record: dict[str, Any],
    drift_signal: dict[str, Any],
    operator_summary: dict[str, Any],
    required_artifacts_for_next_cycle: list[str],
    next_cycle_input_bundle: dict[str, Any],
    allow_decision_proof_ref: str,
    created_at: str,
    trace_id: str,
) -> dict[str, Any]:
    decision = "run_next_cycle"
    reason_codes: list[str] = ["healthy_aligned_progress"]
    risk_posture = "low"

    control_decision = str(eval_control_state.get("decision") or "").strip().lower()
    if control_decision in {"freeze", "block"} or stop_reason in {"authorization_freeze", "authorization_block", "control_freeze", "control_block"}:
        decision = "escalate" if control_decision == "freeze" or stop_reason in {"authorization_freeze", "control_freeze"} else "stop"
        reason_codes = ["block_or_freeze_state"]
        risk_posture = "critical"
    elif str(operator_summary.get("program_alignment_status", "aligned")) == "misaligned":
        decision = "stop"
        reason_codes = ["program_misalignment"]
        risk_posture = "critical"
    elif str(drift_signal.get("drift_level", "low")) == "high":
        decision = "escalate"
        reason_codes = ["program_drift_high"]
        risk_posture = "high"
    elif not required_artifacts_for_next_cycle:
        decision = "stop"
        reason_codes = ["missing_required_artifacts"]
        risk_posture = "high"
    elif int(failure_pattern_record.get("repeated_failure_count", 0)) >= int(failure_pattern_record.get("stop_threshold", 2)):
        decision = "stop"
        reason_codes = ["repeated_failure_threshold_exceeded"]
        risk_posture = "high"
    elif str(eval_control_state.get("health", "healthy")) != "healthy":
        decision = "stop"
        reason_codes = ["eval_health_degraded"]
        risk_posture = "high"
    elif bool(next_cycle_input_bundle.get("unresolved_blockers")):
        decision = "stop"
        reason_codes = ["missing_required_artifacts"]
        risk_posture = "high"
    elif roadmap_state.get("next_candidate_batch_id") is None:
        decision = "stop"
        reason_codes = ["no_remaining_batch"]
        risk_posture = "medium"
    elif str(program_constraint_signal.get("enforcement_mode", "block")) == "freeze":
        decision = "escalate"
        reason_codes = ["manual_review_required"]
        risk_posture = "high"

    decision_seed = {
        "current_cycle_id": current_cycle_id,
        "decision": decision,
        "reason_codes": reason_codes,
        "trace_id": trace_id,
        "created_at": created_at,
        "stop_reason": stop_reason,
        "roadmap_state": roadmap_state,
        "batch_continuation_records": batch_continuation_records,
        "feedback": program_feedback_record,
    }
    cycle_decision_id = f"NCD-{_canonical_hash(decision_seed)[:12].upper()}"
    return {
        "cycle_decision_id": cycle_decision_id,
        "schema_version": "1.1.0",
        "current_cycle_id": current_cycle_id,
        "decision": decision,
        "decision_reason_codes": reason_codes,
        "program_alignment_status": str(operator_summary.get("program_alignment_status", "unknown")),
        "program_stop_cause": str(operator_summary.get("program_stop_cause", "unknown")),
        "risk_posture": risk_posture,
        "required_artifacts_for_next_cycle": sorted(set(required_artifacts_for_next_cycle)),
        "next_cycle_inputs_ref": f"next_cycle_input_bundle:{next_cycle_input_bundle['bundle_id']}",
        "allow_decision_proof_ref": allow_decision_proof_ref,
        "created_at": created_at,
        "trace_id": trace_id,
    }


def run_system_cycle(
    *,
    roadmap_artifact: dict[str, Any],
    selection_signals: dict[str, Any],
    authorization_signals: dict[str, Any],
    integration_inputs: dict[str, Any],
    pqx_state_path: Path,
    pqx_runs_root: Path,
    execution_policy: dict[str, Any] | None = None,
    source_refs: list[str] | None = None,
    created_at: str,
    pqx_execute_fn: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run one full bounded system cycle and emit operator-focused summary artifacts."""
    if not isinstance(created_at, str) or not created_at.strip():
        raise SystemCycleOperatorError("created_at is required for deterministic system cycle execution")
    timestamp = created_at
    normalized_execution_policy = _normalize_execution_policy(execution_policy)
    if not isinstance(integration_inputs, dict):
        raise SystemCycleOperatorError("integration_inputs must be an object")

    prior_handoff_required = bool(integration_inputs.get("require_prior_handoff", False))
    handoff_root_raw = integration_inputs.get("handoff_bundle_root")
    if isinstance(handoff_root_raw, str) and handoff_root_raw.strip():
        handoff_root = Path(handoff_root_raw)
    else:
        handoff_root = pqx_runs_root / "batch_handoffs"
    prior_handoff_bundle = _load_latest_prior_batch_handoff_bundle(handoff_root=handoff_root, required=prior_handoff_required)

    effective_selection_signals = dict(selection_signals)
    effective_authorization_signals = dict(authorization_signals)
    if isinstance(prior_handoff_bundle, dict):
        prior_recommended = prior_handoff_bundle.get("recommended_next_batch")
        if isinstance(prior_recommended, str):
            existing_priority = [str(item) for item in effective_selection_signals.get("priority_ordering", []) if str(item).strip()]
            effective_selection_signals["priority_ordering"] = [prior_recommended] + [
                item for item in existing_priority if item != prior_recommended
            ]
            effective_selection_signals["prior_handoff_recommended_next_batch"] = prior_recommended
        carry_risks = [str(item) for item in prior_handoff_bundle.get("must_carry_forward_risks", [])]
        if any("critical" in item.lower() for item in carry_risks):
            effective_authorization_signals["control_block_condition"] = True

    multi_batch = execute_bounded_roadmap_run(
        roadmap_artifact,
        effective_selection_signals,
        effective_authorization_signals,
        pqx_state_path=pqx_state_path,
        pqx_runs_root=pqx_runs_root,
        execution_policy=normalized_execution_policy,
        evaluated_at=timestamp,
        executed_at=timestamp,
        validated_at=timestamp,
        run_executed_at=timestamp,
        source_refs=source_refs,
        pqx_execute_fn=pqx_execute_fn,
    )
    run_result = multi_batch["run_result"]
    updated_roadmap = multi_batch["roadmap"]

    roadmap_loop_validation = dict(integration_inputs.get("roadmap_loop_validation") or {})
    if "validation_id" not in roadmap_loop_validation and run_result.get("loop_validation_refs"):
        roadmap_loop_validation["validation_id"] = str(run_result["loop_validation_refs"][-1])
    if "determinism_status" not in roadmap_loop_validation:
        roadmap_loop_validation["determinism_status"] = "deterministic"

    roadmap_multi_batch_result = dict(run_result)
    overrides = integration_inputs.get("roadmap_multi_batch_result_overrides")
    if isinstance(overrides, dict):
        roadmap_multi_batch_result.update(overrides)
    roadmap_multi_batch_result.setdefault("program_constraints_applied", True)

    integration = validate_core_system_integration(
        program_artifact=dict(integration_inputs.get("program_artifact") or {}),
        review_control_signal=dict(integration_inputs.get("review_control_signal") or {}),
        eval_result=dict(integration_inputs.get("eval_result") or {}),
        context_bundle=dict(integration_inputs.get("context_bundle") or {}),
        tpa_gate=dict(integration_inputs.get("tpa_gate") or {}),
        roadmap_loop_validation=roadmap_loop_validation,
        roadmap_multi_batch_result=roadmap_multi_batch_result,
        control_decision=dict(integration_inputs.get("control_decision") or {}),
        certification_pack=dict(integration_inputs.get("certification_pack") or {}),
        validation_scope=dict(integration_inputs.get("validation_scope") or {}),
        trace_id=str(integration_inputs.get("trace_id") or effective_authorization_signals.get("trace_id") or ""),
        source_refs=dict(integration_inputs.get("source_refs") or {}),
        created_at=timestamp,
    )

    blocking_conditions = [str(item) for item in integration.get("blocking_conditions", [])]
    replay_refs = sorted(set(str(item) for item in run_result.get("loop_validation_refs", [])))
    trace_navigation = dict(integration.get("trace_navigation") or {})
    validation_id = str(integration["validation_id"])
    replay_entry_points = _replay_entry_points(
        trace_id=integration["trace_id"],
        run_id=str(run_result["run_id"]),
        validation_id=validation_id,
        blocker_refs=blocking_conditions,
        trace_navigation=trace_navigation,
    )
    next_batch_id = _next_not_started_batch_id(updated_roadmap)
    required_reviews = _required_reviews(blocking_conditions)
    why = [
        f"bounded_stop_reason={run_result['stop_reason']}",
        f"integration_outcome={integration['deterministic_outcome']}",
        f"authority_boundary_status={integration['authority_boundary_status']}",
    ]
    if next_batch_id is not None:
        why.append(f"next_eligible_candidate={next_batch_id}")
    else:
        why.append("no_remaining_not_started_batch")

    risk_signals = [
        f"determinism_status={integration['determinism_status']}",
        f"replay_status={integration['replay_status']}",
        f"blocking_conditions={len(blocking_conditions)}",
    ]
    risk_level = "high" if blocking_conditions else ("medium" if run_result["stop_reason"] != "max_batches_reached" else "low")

    candidates = _generate_candidates(
        next_batch_id=next_batch_id,
        run_result=run_result,
        integration=integration,
        required_reviews=required_reviews,
        blocking_conditions=blocking_conditions,
        replay_refs=replay_refs,
        program_artifact=dict(integration_inputs.get("program_artifact") or {}),
        context_bundle=dict(integration_inputs.get("context_bundle") or {}),
        review_control_signal=dict(integration_inputs.get("review_control_signal") or {}),
        control_decision=dict(integration_inputs.get("control_decision") or {}),
    )
    ranked_candidates = _rank_candidates(candidates, next_batch_id=next_batch_id, required_reviews=required_reviews)
    selected_candidate = ranked_candidates[0]["candidate"]
    selected_factors = ranked_candidates[0]["ranking_factors"]
    why_not_selected = [
        {
            "candidate_id": item["candidate"]["candidate_id"],
            "reason": (
                "lower_priority"
                if item["score"] < ranked_candidates[0]["score"]
                else "tie_broken_by_candidate_id"
            ),
            "score": item["score"],
        }
        for item in ranked_candidates[1:]
    ]

    adaptive_inputs = integration_inputs.get("adaptive_observability_run_results")
    adaptive_run_results = [dict(item) for item in adaptive_inputs] if isinstance(adaptive_inputs, list) else []
    adaptive_run_results.append(dict(run_result))
    adaptive_observability = build_adaptive_execution_observability(
        adaptive_run_results,
        trace_id=integration["trace_id"],
        source_refs=[
            f"roadmap_multi_batch_run_result:{str(item.get('run_id') or 'unknown')}" for item in adaptive_run_results
        ],
        created_at=timestamp,
    )
    adaptive_trend_report = build_adaptive_execution_trend_report(
        adaptive_run_results,
        observability=adaptive_observability,
        trace_id=integration["trace_id"],
        created_at=timestamp,
    )
    adaptive_policy_review = build_adaptive_execution_policy_review(
        adaptive_run_results,
        observability=adaptive_observability,
        trend_report=adaptive_trend_report,
        trace_id=integration["trace_id"],
        created_at=timestamp,
    )
    adaptive_observability_ref = f"adaptive_execution_observability:{adaptive_observability['observability_id']}"
    adaptive_trend_ref = f"adaptive_execution_trend_report:{adaptive_trend_report['trend_report_id']}"
    adaptive_policy_review_ref = f"adaptive_execution_policy_review:{adaptive_policy_review['review_id']}"

    stop_reason = str(run_result["stop_reason"])
    continuation_sequence = list(run_result.get("continuation_decision_sequence", []))
    continuation_records = [row for row in run_result.get("batch_continuation_records", []) if isinstance(row, dict)]
    latest_program_signal = (
        dict(continuation_records[-1].get("signals_used", {}).get("program_constraint_signal", {}))
        if continuation_records
        else {}
    )
    latest_program_drift = (
        dict(continuation_records[-1].get("signals_used", {}).get("program_drift_signal", {}))
        if continuation_records
        else {}
    )
    program_alignment_status = str(run_result.get("program_alignment_status") or ("misaligned" if stop_reason.startswith("program_") else "aligned"))
    program_stop_cause = str(run_result.get("program_stop_cause") or (stop_reason if stop_reason.startswith("program_") else "none"))
    program_drift_severity = str(run_result.get("program_drift_severity") or latest_program_drift.get("drift_level", "low"))
    execution_path_type = str(run_result.get("execution_path_type") or ("negative_path" if program_alignment_status == "misaligned" else "positive_path"))
    program_caused_stop = program_alignment_status == "misaligned"
    last_continuation_decision = (
        str(continuation_sequence[-1].get("decision")) if continuation_sequence else ("stop" if stop_reason != "max_batches_reached" else "continue")
    )
    failure_root_cause = _root_cause(stop_reason, blocking_conditions)
    failure_root_cause_chain = _root_cause_chain(stop_reason, blocking_conditions)
    failure_next_action = _next_action(stop_reason, blocking_conditions)
    remediation_plan = _build_remediation_plan(
        run_result=run_result,
        stop_reason=stop_reason,
        root_cause=failure_root_cause,
        root_cause_chain=failure_root_cause_chain,
        blocking_conditions=blocking_conditions,
        required_reviews=required_reviews,
        integration=integration,
        timestamp=timestamp,
        required_artifacts=selected_candidate["required_artifacts"],
        review_control_signal=dict(integration_inputs.get("review_control_signal") or {}),
    )
    remediation_plan_ref = f"remediation_plan:{remediation_plan['plan_id']}"
    required_artifacts_for_next_cycle = sorted(set(selected_candidate["required_artifacts"]))
    continuation_depth = int(integration_inputs.get("continuation_depth", 0))
    source_cycle_runner_result_ref = str(integration_inputs.get("source_cycle_runner_result_ref") or "cycle_runner_result:CRR-000000000000")
    explicit_state_issues = validate_explicit_state_dependencies(
        prior_handoff_bundle=prior_handoff_bundle,
        source_cycle_runner_result_ref=source_cycle_runner_result_ref,
        require_prior_handoff=prior_handoff_required,
    )
    required_validations_next = sorted(
        set(prior_handoff_bundle.get("required_validations_next", []) if isinstance(prior_handoff_bundle, dict) else [])
    )
    unresolved_critical_risks = sorted(
        set(
            [item for item in blocking_conditions if item.startswith("AUTH_") or "critical" in item.lower()]
            + (
                [
                    item
                    for item in prior_handoff_bundle.get("must_carry_forward_risks", [])
                    if isinstance(item, str) and ("critical" in item.lower() or item.startswith("AUTH_"))
                ]
                if isinstance(prior_handoff_bundle, dict)
                else []
            )
        )
    )
    continuous_eval_inputs = dict(integration_inputs.get("continuous_eval_inputs") or {})
    eval_inputs_by_stage = {
        "offline": dict(continuous_eval_inputs.get("offline_eval_run") or {}),
        "pre_merge": dict(continuous_eval_inputs.get("pre_merge_eval_run") or {}),
        "canary": dict(continuous_eval_inputs.get("canary_eval_run") or {}),
        "production": dict(continuous_eval_inputs.get("production_sampling_eval_run") or {}),
    }
    continuous_eval_run_records = build_continuous_eval_run_records(
        artifact_family=str(continuous_eval_inputs.get("artifact_family") or "system_cycle"),
        eval_inputs_by_stage=eval_inputs_by_stage,
        created_at=timestamp,
        trace_id=integration["trace_id"],
        require_all_stages=bool(continuous_eval_inputs.get("require_all_stages", True)),
    )
    continuous_eval_refs = [f"continuous_eval_run_record:{item['eval_run_id']}" for item in continuous_eval_run_records]
    canary_eval_record = next(item for item in continuous_eval_run_records if item["eval_stage"] == "canary")
    canary_rollout_record = build_canary_rollout_record(
        target_change=str(integration_inputs.get("canary_target_change") or "policy"),
        rollout_stage=str(integration_inputs.get("rollout_stage") or "canary"),
        sample_size=int(integration_inputs.get("canary_sample_size", 10)),
        eval_run_record=canary_eval_record,
        created_at=timestamp,
        trace_id=integration["trace_id"],
    )
    canary_rollout_ref = f"canary_rollout_record:{canary_rollout_record['rollout_id']}"
    if canary_rollout_record["promotion_decision"] in {"block", "rollback"}:
        blocking_conditions = sorted(set(blocking_conditions + [f"CANARY_{canary_rollout_record['promotion_decision'].upper()}"]))

    budget_inputs = dict(integration_inputs.get("budget_inputs") or {})
    system_budget_status = build_system_budget_status(
        threshold_values=dict(
            budget_inputs.get("threshold_values")
            or {"cost": 100.0, "latency_ms": 500.0, "error_rate": 0.05}
        ),
        current_values=dict(
            budget_inputs.get("current_values")
            or {"cost": 50.0, "latency_ms": 200.0, "error_rate": 0.01}
        ),
        created_at=timestamp,
        trace_id=integration["trace_id"],
    )
    budget_status_ref = f"system_budget_status:{system_budget_status['budget_status_id']}"
    if system_budget_status["budget_exhausted"]:
        budget_breach_action = str(budget_inputs.get("breach_action") or "freeze")
        if budget_breach_action == "freeze":
            blocking_conditions = sorted(set(blocking_conditions + ["BUDGET_EXHAUSTED"]))
            effective_authorization_signals["control_freeze_condition"] = True
        else:
            blocking_conditions = sorted(set(blocking_conditions + ["BUDGET_WARNING"]))

    autonomy_policy = integration_inputs.get("autonomy_policy")
    if not isinstance(autonomy_policy, dict):
        autonomy_policy = load_example("autonomy_policy")
    autonomy_decision_record = evaluate_autonomy_guardrails(
        source_cycle_id=str(run_result["run_id"]),
        autonomy_policy=autonomy_policy,
        control_decisions=[dict(integration_inputs.get("control_decision") or {})],
        unresolved_critical_risks=unresolved_critical_risks,
        drift_signals={"drift_level": program_drift_severity},
        replay_status=str(integration.get("replay_status", "unknown")),
        review_gate_status=str(integration_inputs.get("review_control_signal", {}).get("gate_assessment", "unknown")),
        required_validation_carry_forward=required_validations_next,
        system_budget_status=system_budget_status,
        continuation_depth=continuation_depth,
        consecutive_warn_count=int(run_result.get("consecutive_warn_count", 0)),
        created_at=timestamp,
        trace_id=integration["trace_id"],
    )
    autonomy_decision_ref = f"autonomy_decision_record:{autonomy_decision_record['autonomy_decision_id']}"
    if not autonomy_decision_record.get("reason_codes"):
        raise SystemCycleOperatorError("autonomy_decision_record missing explicit reason_codes")

    unknown_state_signals: list[dict[str, Any]] = []
    if explicit_state_issues:
        unknown_state_signals.append(
            build_unknown_state_signal(
                source_cycle_id=str(run_result["run_id"]),
                source_artifact_ref=f"roadmap_multi_batch_run_result:{run_result['run_id']}",
                unknown_class="unknown_dependency_state",
                severity="high",
                blocking=True,
                reason_codes=explicit_state_issues,
                supporting_signal_refs=[source_cycle_runner_result_ref],
                created_at=timestamp,
                trace_id=integration["trace_id"],
            )
        )
    if str(integration.get("replay_status", "unknown")) == "unknown":
        unknown_state_signals.append(
            build_unknown_state_signal(
                source_cycle_id=str(run_result["run_id"]),
                source_artifact_ref=f"core_system_integration_validation:{integration['validation_id']}",
                unknown_class="insufficient_evidence",
                severity="medium",
                blocking=True,
                reason_codes=["unknown_replay_status"],
                supporting_signal_refs=[f"replay_status:{integration.get('replay_status', 'unknown')}"],
                created_at=timestamp,
                trace_id=integration["trace_id"],
            )
        )
    unknown_state_signal_refs = [f"unknown_state_signal:{item['unknown_state_signal_id']}" for item in unknown_state_signals]
    unknown_state_blockers = sorted(
        {
            f"unknown_state:{item['unknown_class']}:{code}"
            for item in unknown_state_signals
            if bool(item.get("blocking"))
            for code in item.get("reason_codes", [])
        }
    )
    autonomy_blockers = [] if autonomy_decision_record["decision"] == "continue" else [
        f"autonomy:{code}" for code in autonomy_decision_record["reason_codes"]
    ]
    control_decision_value = str(integration_inputs.get("control_decision", {}).get("decision", "unknown")).strip().lower() or "unknown"
    exception_classification_record = classify_exception_state(
        source_artifact_ref=f"roadmap_multi_batch_run_result:{run_result['run_id']}",
        source_batch_id=str(run_result["attempted_batch_ids"][-1] if run_result["attempted_batch_ids"] else "BATCH-UNKNOWN"),
        source_cycle_id=str(run_result["run_id"]),
        control_decision=control_decision_value,
        autonomy_decision=str(autonomy_decision_record["decision"]),
        stop_reason=stop_reason,
        blocking_conditions=blocking_conditions,
        drift_signals={"drift_level": program_drift_severity},
        replay_status=str(integration.get("replay_status", "unknown")),
        review_gate_status=str(integration_inputs.get("review_control_signal", {}).get("gate_assessment", "unknown")),
        missing_eval_enforcement_artifacts=required_validations_next,
        unresolved_critical_risks=unresolved_critical_risks,
        failure_keys=list(run_result.get("reason_codes", [])),
        created_at=timestamp,
        trace_id=integration["trace_id"],
    )
    exception_resolution_record = route_exception_resolution(
        exception_classification_record=exception_classification_record,
        created_at=timestamp,
    )
    exception_classification_ref = f"exception_classification_record:{exception_classification_record['exception_classification_id']}"
    exception_resolution_ref = f"exception_resolution_record:{exception_resolution_record['exception_resolution_id']}"
    normalized_failure_keys = _normalize_failure_keys(
        stop_reason=stop_reason,
        blocking_conditions=blocking_conditions,
        unknown_state_blockers=unknown_state_blockers,
        autonomy_blockers=autonomy_blockers,
        required_validations_next=required_validations_next,
        replay_status=str(integration.get("replay_status", "unknown")).strip().lower(),
        program_drift_severity=program_drift_severity,
    )
    prior_failure_taxonomy_records = [dict(item) for item in integration_inputs.get("prior_failure_taxonomy_records", [])]
    failure_taxonomy_record = build_failure_taxonomy_record(
        source_exception_ref=exception_resolution_ref,
        source_batch_id=str(run_result["attempted_batch_ids"][-1] if run_result["attempted_batch_ids"] else "BATCH-UNKNOWN"),
        source_cycle_id=str(run_result["run_id"]),
        normalized_failure_keys=normalized_failure_keys,
        required_validations_next=required_validations_next,
        replay_status=str(integration.get("replay_status", "unknown")).strip().lower(),
        program_drift_severity=program_drift_severity,
        unknown_state_blockers=unknown_state_blockers,
        autonomy_blockers=autonomy_blockers,
        prior_failure_taxonomy_records=prior_failure_taxonomy_records,
        created_at=timestamp,
        trace_id=integration["trace_id"],
    )
    failure_taxonomy_ref = f"failure_taxonomy_record:{failure_taxonomy_record['failure_taxonomy_id']}"
    correction_pattern_record = derive_correction_pattern(
        failure_taxonomy_record=failure_taxonomy_record,
        source_exception_ref=exception_resolution_ref,
        unknown_state_signal_refs=unknown_state_signal_refs,
        recurrence_threshold=int(integration_inputs.get("correction_recurrence_threshold", 2)),
        created_at=timestamp,
        trace_id=integration["trace_id"],
    )
    correction_pattern_ref = (
        f"correction_pattern_record:{correction_pattern_record['correction_pattern_id']}"
        if isinstance(correction_pattern_record, dict)
        else None
    )
    replay_status_value = str(integration.get("replay_status", "unknown")).strip().lower()
    replay_ok = replay_status_value in {"passed", "match", "ready", "replay_ready", "replayable"}
    decision_proof_record = build_decision_proof_record(
        source_decision_ref=autonomy_decision_ref,
        source_cycle_id=str(run_result["run_id"]),
        decision_type="autonomy_guardrail",
        reason_codes=list(autonomy_decision_record["reason_codes"]),
        required_inputs_present=not explicit_state_issues,
        supporting_signal_refs=sorted(
            set(
                list(autonomy_decision_record["supporting_signals"])
                + [f"stop_reason:{stop_reason}", f"control_decision:{control_decision_value}"]
            )
        ),
        supporting_artifact_refs=sorted(
            set(
                [
                    f"roadmap_multi_batch_run_result:{run_result['run_id']}",
                    f"core_system_integration_validation:{integration['validation_id']}",
                    source_cycle_runner_result_ref,
                ]
                + ([f"batch_handoff_bundle:{prior_handoff_bundle['bundle_id']}"] if isinstance(prior_handoff_bundle, dict) else [])
            )
        ),
        replay_consistency_status="match" if replay_ok else "mismatch",
        schema_validation_status="pass",
        trace_validation_status="pass",
        created_at=timestamp,
        trace_id=integration["trace_id"],
    )
    decision_proof_ref = f"decision_proof_record:{decision_proof_record['decision_proof_id']}"
    allow_decision_proof = build_allow_decision_proof(
        source_decision_ref=autonomy_decision_ref,
        eval_coverage_complete=not required_validations_next,
        required_evals_present=not any(code.startswith("missing_required_signal:") for code in autonomy_decision_record["reason_codes"]),
        no_blocking_policy_violations=control_decision_value != "freeze",
        no_replay_mismatch=replay_ok,
        no_schema_failure=True,
        no_trace_failure=True,
        no_blocking_unknown_state_signal=not unknown_state_blockers,
        supporting_signal_refs=sorted(
            set(
                [
                    f"required_validations={len(required_validations_next)}",
                    f"unknown_state_blockers={len(unknown_state_blockers)}",
                    f"replay_status={integration.get('replay_status', 'unknown')}",
                ]
            )
        ),
        created_at=timestamp,
        trace_id=integration["trace_id"],
    )
    allow_decision_proof_ref = f"allow_decision_proof:{allow_decision_proof['allow_decision_proof_id']}"
    allow_is_proven = all(
        bool(allow_decision_proof[key])
        for key in (
            "eval_coverage_complete",
            "required_evals_present",
            "no_blocking_policy_violations",
            "no_replay_mismatch",
            "no_schema_failure",
            "no_trace_failure",
            "no_blocking_unknown_state_signal",
        )
    )
    next_cycle_input_bundle = _build_next_cycle_input_bundle(
        current_cycle_id=str(run_result["run_id"]),
        required_artifacts=required_artifacts_for_next_cycle,
        next_batch_id=next_batch_id,
        program_alignment_status=program_alignment_status,
        program_stop_cause=program_stop_cause,
        program_drift_severity=program_drift_severity,
        risk_level=risk_level,
        risk_signals=risk_signals,
        blocking_conditions=blocking_conditions,
        required_reviews=required_reviews,
        autonomy_decision_ref=autonomy_decision_ref,
        decision_proof_ref=decision_proof_ref,
        allow_decision_proof_ref=allow_decision_proof_ref,
        unknown_state_signal_refs=unknown_state_signal_refs,
        unknown_state_blockers=unknown_state_blockers,
        autonomy_blockers=autonomy_blockers,
        exception_classification_record=exception_classification_record,
        exception_resolution_record=exception_resolution_record,
        continuation_depth=continuation_depth,
        source_cycle_runner_result_ref=source_cycle_runner_result_ref,
        trace_navigation=trace_navigation,
        adaptive_refs=[adaptive_observability_ref, adaptive_trend_ref, adaptive_policy_review_ref],
        prior_handoff_bundle=prior_handoff_bundle,
        trace_id=integration["trace_id"],
        created_at=timestamp,
    )
    _validate_schema(next_cycle_input_bundle, "next_cycle_input_bundle")

    decision_eval_state = {
        "decision": str(integration_inputs.get("control_decision", {}).get("decision", "unknown")),
        "health": "degraded" if blocking_conditions else "healthy",
    }
    repeated_failure_count = max(
        int(run_result.get("repeated_failure_count", 0)),
        int(continuation_records[-1].get("signals_used", {}).get("failure_pattern_record", {}).get("repeated_failure_count", 0))
        if continuation_records
        else 0,
    )
    repeated_failure_threshold = (
        int(continuation_records[-1].get("signals_used", {}).get("failure_pattern_record", {}).get("stop_threshold", 2))
        if continuation_records
        else 2
    )
    next_cycle_decision = decide_next_cycle(
        current_cycle_id=str(run_result["run_id"]),
        stop_reason=stop_reason,
        program_constraint_signal=latest_program_signal,
        program_feedback_record={
            "program_alignment_status": program_alignment_status,
            "program_stop_cause": program_stop_cause,
            "program_drift_severity": program_drift_severity,
        },
        roadmap_state={"current_batch_id": updated_roadmap.get("current_batch_id"), "next_candidate_batch_id": next_batch_id},
        batch_continuation_records=continuation_records,
        eval_control_state=decision_eval_state,
        failure_pattern_record={
            "repeated_failure_count": repeated_failure_count,
            "stop_threshold": repeated_failure_threshold,
        },
        drift_signal={"drift_level": program_drift_severity},
        operator_summary={"program_alignment_status": program_alignment_status, "program_stop_cause": program_stop_cause},
        required_artifacts_for_next_cycle=required_artifacts_for_next_cycle,
        next_cycle_input_bundle=next_cycle_input_bundle,
        allow_decision_proof_ref=allow_decision_proof_ref,
        created_at=timestamp,
        trace_id=integration["trace_id"],
    )
    if next_cycle_decision["decision"] == "run_next_cycle" and not allow_is_proven:
        next_cycle_decision["decision"] = "stop"
        next_cycle_decision["decision_reason_codes"] = ["missing_required_artifacts"]
        next_cycle_decision["risk_posture"] = "critical"
    _validate_schema(next_cycle_decision, "next_cycle_decision")
    next_cycle_decision_ref = f"next_cycle_decision:{next_cycle_decision['cycle_decision_id']}"
    next_cycle_input_bundle_ref = f"next_cycle_input_bundle:{next_cycle_input_bundle['bundle_id']}"

    recommendation = {
        "recommendation_id": f"NSR-{_canonical_hash({'run_id': run_result['run_id'], 'at': timestamp})[:12].upper()}",
        "schema_version": "1.7.0",
        "next_batch_id": next_batch_id,
        "continuation_decision": last_continuation_decision,
        "stop_reason": stop_reason,
        "next_batch_candidate": next_batch_id,
        "execution_path_type": execution_path_type,
        "program_alignment_status": program_alignment_status,
        "program_stop_cause": program_stop_cause,
        "program_drift_severity": program_drift_severity,
        "next_cycle_decision": next_cycle_decision["decision"],
        "next_cycle_decision_reason_codes": next_cycle_decision["decision_reason_codes"],
        "next_cycle_inputs_ref": next_cycle_input_bundle_ref,
        "why": sorted(
            set(
                why
                + [
                    f"adaptive_guardrail_status={adaptive_trend_report['guardrail_status']}",
                    f"adaptive_useful_batches_per_run={adaptive_observability['average_useful_batches_per_run']}",
                    f"adaptive_policy_review={adaptive_policy_review['review_id']}",
                    f"program_alignment_status={program_alignment_status}",
                    f"program_drift_severity={program_drift_severity}",
                ]
            )
        ),
        "blockers": sorted(set(blocking_conditions)),
        "required_reviews": required_reviews,
        "risk_summary": {
            "level": risk_level,
            "signals": sorted(
                set(
                    risk_signals
                    + [
                        f"adaptive_guardrail_status={adaptive_trend_report['guardrail_status']}",
                        f"adaptive_safety_trend={adaptive_trend_report['safety_trend']}",
                    ]
                )
            ),
        },
        "next_step": {
            "action": selected_candidate["action"],
            "why_now": (
                f"selected {selected_candidate['candidate_id']} via deterministic ranking: "
                f"program_alignment={selected_factors['program_alignment']}, "
                f"unblock_potential={selected_factors['unblock_potential']}, "
                f"risk_reduction={selected_factors['risk_reduction']}, "
                f"dependency_readiness={selected_factors['dependency_readiness']}, "
                f"review_readiness={selected_factors['review_readiness']}"
            ),
            "blocked_by": selected_candidate["blockers"],
            "watchouts": sorted(
                set(
                    _watchouts(str(run_result["stop_reason"]), blocking_conditions, required_reviews)
                    + [
                        f"control_state={integration_inputs.get('control_decision', {}).get('decision', 'unknown')}",
                        f"program_caused_stop={str(program_caused_stop).lower()}",
                    ]
                    + [f"required_validation:{item}" for item in required_validations_next]
                )
            ),
            "required_artifacts": selected_candidate["required_artifacts"],
        },
        "remediation_plan_ref": remediation_plan_ref,
        "remediation_steps": remediation_plan["remediation_steps"],
        "remediation_plan": remediation_plan,
        "candidate_evaluation": {
            "ranking_policy": "program_alignment>unblock_potential>risk_reduction>dependency_readiness>review_readiness",
            "candidates": [
                {
                    **item["candidate"],
                    "score": item["score"],
                    "ranking_factors": item["ranking_factors"],
                }
                for item in ranked_candidates
            ],
            "why_not_selected": why_not_selected,
        },
        "artifact_refs": {
            "roadmap_multi_batch_run_result": f"roadmap_multi_batch_run_result:{run_result['run_id']}",
            "core_system_integration_validation": f"core_system_integration_validation:{validation_id}",
            "next_cycle_decision": next_cycle_decision_ref,
            "next_cycle_input_bundle": next_cycle_input_bundle_ref,
            "trace_id": integration["trace_id"],
            "replay_refs": replay_refs,
            "upstream_refs": sorted(set(integration.get("upstream_refs", []))),
            "downstream_refs": [f"build_summary:BSR-{_canonical_hash({'run_id': run_result['run_id'], 'trace_id': integration['trace_id']})[:12].upper()}"],
            "related_artifacts": sorted(
                set(
                    [
                        f"roadmap_multi_batch_run_result:{run_result['run_id']}",
                        f"core_system_integration_validation:{validation_id}",
                        adaptive_observability_ref,
                        adaptive_trend_ref,
                        adaptive_policy_review_ref,
                        remediation_plan_ref,
                        decision_proof_ref,
                        allow_decision_proof_ref,
                        failure_taxonomy_ref,
                        next_cycle_decision_ref,
                        next_cycle_input_bundle_ref,
                    ]
                    + ([correction_pattern_ref] if correction_pattern_ref else [])
                    + unknown_state_signal_refs
                    + replay_refs
                    + list(integration.get("related_artifacts", []))
                    + (
                        [f"batch_handoff_bundle:{prior_handoff_bundle['bundle_id']}"]
                        if isinstance(prior_handoff_bundle, dict)
                        else []
                    )
                )
            ),
        },
        "trace_navigation": trace_navigation,
        "replay_entry_points": replay_entry_points,
        "quick_links": [
            f"view trace -> trace_navigation:{validation_id}",
            "replay this step -> replay_from_execution",
            "inspect failure chain -> replay_from_failure",
        ],
        "trace_id": integration["trace_id"],
        "created_at": timestamp,
        "source_refs": sorted(
            set(
                [
                    f"roadmap_multi_batch_run_result:{run_result['run_id']}",
                    f"core_system_integration_validation:{validation_id}",
                    adaptive_observability_ref,
                    adaptive_trend_ref,
                    remediation_plan_ref,
                    next_cycle_decision_ref,
                    next_cycle_input_bundle_ref,
                    decision_proof_ref,
                    allow_decision_proof_ref,
                    failure_taxonomy_ref,
                ]
                + ([correction_pattern_ref] if correction_pattern_ref else [])
                + unknown_state_signal_refs
                + list(source_refs or [])
                + (
                    [f"batch_handoff_bundle:{prior_handoff_bundle['bundle_id']}"]
                    if isinstance(prior_handoff_bundle, dict)
                    else []
                )
            )
        ),
    }
    _validate_schema(recommendation, "next_step_recommendation")

    summary = {
        "summary_id": f"BSR-{_canonical_hash({'run_id': run_result['run_id'], 'trace_id': integration['trace_id']})[:12].upper()}",
        "schema_version": "1.11.0",
        "run_id": run_result["run_id"],
        "continuation_decision": last_continuation_decision,
        "stop_reason": stop_reason,
        "next_batch_candidate": next_batch_id,
        "execution_path_type": execution_path_type,
        "program_alignment_status": program_alignment_status,
        "program_stop_cause": program_stop_cause,
        "program_drift_severity": program_drift_severity,
        "next_cycle_decision": next_cycle_decision["decision"],
        "next_cycle_decision_reason_codes": next_cycle_decision["decision_reason_codes"],
        "autonomy_decision": autonomy_decision_record["decision"],
        "autonomy_reason_codes": autonomy_decision_record["reason_codes"],
        "autonomy_decision_ref": autonomy_decision_ref,
        "decision_proof_ref": decision_proof_ref,
        "allow_decision_proof_ref": allow_decision_proof_ref,
        "failure_taxonomy_ref": failure_taxonomy_ref,
        "correction_pattern_ref": correction_pattern_ref or "correction_pattern_record:CPR-000000000000",
        "rollback_plan_ref": "rollback_plan_record:RBP-000000000000",
        "promotion_consistency_ref": "promotion_consistency_record:PCR-000000000000",
        "system_budget_status_ref": "system_budget_status:SBS-000000000000",
        "canary_rollout_ref": "canary_rollout_record:CNR-000000000000",
        "continuous_eval_run_refs": [
            "continuous_eval_run_record:CER-000000000001",
            "continuous_eval_run_record:CER-000000000002",
            "continuous_eval_run_record:CER-000000000003",
            "continuous_eval_run_record:CER-000000000004",
        ],
        "trust_posture_snapshot_ref": "trust_posture_snapshot:TPS-000000000000",
        "artifact_family_health_report_ref": "artifact_family_health_report:AFH-000000000000",
        "evidence_gap_hotspot_report_ref": "evidence_gap_hotspot_report:EGH-000000000000",
        "override_hotspot_report_ref": "override_hotspot_report:OVH-000000000000",
        "unknown_state_signal_refs": unknown_state_signal_refs,
        "unknown_state_blockers": unknown_state_blockers,
        "next_cycle_inputs_ref": next_cycle_input_bundle_ref,
        "exception_class": exception_classification_record["exception_class"],
        "recommended_exception_action": exception_resolution_record["recommended_action"],
        "exception_action_type": exception_resolution_record["action_type"],
        "exception_requires_human_review": exception_resolution_record["requires_human_review"],
        "exception_requires_freeze": exception_resolution_record["requires_freeze"],
        "capability_readiness_state": "constrained",
        "capability_readiness_ref": "capability_readiness_record:CRD-000000000000",
        "what_ran": [
            "roadmap selection",
            "control authorization",
            "bounded execution (RDX-006)",
            "integration validation (BATCH-Z)",
        ],
        "what_changed": [
                f"attempted_batches={','.join(run_result['attempted_batch_ids']) or 'none'}",
                f"completed_batches={','.join(run_result['completed_batch_ids']) or 'none'}",
                f"program_alignment_status={program_alignment_status}",
                f"program_enforcement_mode={latest_program_signal.get('enforcement_mode', 'block')}",
            ],
        "what_failed": sorted(set(blocking_conditions + ([stop_reason] if stop_reason != "max_batches_reached" else []))),
        "run_outcome": {
            "status": "blocked" if blocking_conditions or stop_reason != "max_batches_reached" else "success",
            "stop_reason": stop_reason,
            "has_blockers": bool(blocking_conditions),
        },
        "watch_next": [
            f"next_batch_id={next_batch_id or 'none'}",
            f"next_action={failure_next_action}",
                f"adaptive_safety_trend={adaptive_trend_report['safety_trend']}",
                f"adaptive_guardrail_status={adaptive_trend_report['guardrail_status']}",
                f"adaptive_tuning_warranted={str(adaptive_trend_report['tuning_warranted']).lower()}",
                f"adaptive_policy_tuning_signal={adaptive_policy_review['operator_tuning_signals'][0]}",
                f"program_caused_stop={str(program_caused_stop).lower()}",
                f"recommended_program_aligned_move={selected_candidate['action']}",
            ] + [f"required_validation:{item}" for item in required_validations_next],
        "artifact_index": {
            "roadmap_multi_batch_run_result": f"roadmap_multi_batch_run_result:{run_result['run_id']}",
            "core_system_integration_validation": f"core_system_integration_validation:{validation_id}",
            "next_step_recommendation": f"next_step_recommendation:{recommendation['recommendation_id']}",
            "next_cycle_decision": next_cycle_decision_ref,
            "next_cycle_input_bundle": next_cycle_input_bundle_ref,
            "trace_id": integration["trace_id"],
            "replay_refs": replay_refs,
            "upstream_refs": sorted(set(integration.get("upstream_refs", []))),
            "downstream_refs": [f"next_step_recommendation:{recommendation['recommendation_id']}"],
            "related_artifacts": sorted(
                set(
                    [
                        f"roadmap_multi_batch_run_result:{run_result['run_id']}",
                        f"core_system_integration_validation:{validation_id}",
                        f"next_step_recommendation:{recommendation['recommendation_id']}",
                        adaptive_observability_ref,
                        adaptive_trend_ref,
                        adaptive_policy_review_ref,
                        remediation_plan_ref,
                        decision_proof_ref,
                        allow_decision_proof_ref,
                        failure_taxonomy_ref,
                        next_cycle_decision_ref,
                        next_cycle_input_bundle_ref,
                    ]
                    + ([correction_pattern_ref] if correction_pattern_ref else [])
                    + unknown_state_signal_refs
                    + replay_refs
                    + list(integration.get("related_artifacts", []))
                    + (
                        [f"batch_handoff_bundle:{prior_handoff_bundle['bundle_id']}"]
                        if isinstance(prior_handoff_bundle, dict)
                        else []
                    )
                )
            ),
        },
        "failure_surface": {
            "stop_reason": stop_reason,
            "root_cause": failure_root_cause,
            "root_cause_chain": failure_root_cause_chain,
            "next_action": failure_next_action,
            "blocker_refs": sorted(set(blocking_conditions)),
            "source_refs": sorted(
                {
                    f"core_system_integration_validation:{validation_id}",
                    f"roadmap_multi_batch_run_result:{run_result['run_id']}",
                }
                | set(replay_refs)
            ),
        },
        "trace_navigation": trace_navigation,
        "replay_entry_points": replay_entry_points,
        "quick_links": [
            f"view trace -> trace_navigation:{validation_id}",
            "replay this step -> replay_from_execution",
            "inspect failure chain -> replay_from_failure",
        ],
        "trace_id": integration["trace_id"],
        "created_at": timestamp,
        "source_refs": sorted(
            {
                f"roadmap_multi_batch_run_result:{run_result['run_id']}",
                f"core_system_integration_validation:{integration['validation_id']}",
                f"next_step_recommendation:{recommendation['recommendation_id']}",
                remediation_plan_ref,
                adaptive_observability_ref,
                adaptive_trend_ref,
                adaptive_policy_review_ref,
                decision_proof_ref,
                allow_decision_proof_ref,
                failure_taxonomy_ref,
                next_cycle_decision_ref,
                next_cycle_input_bundle_ref,
                exception_classification_ref,
                exception_resolution_ref,
            }
            | ({correction_pattern_ref} if correction_pattern_ref else set())
            | set(unknown_state_signal_refs)
        ),
    }
    _validate_schema(summary, "build_summary")
    delivery_seed = {
        "batch_id": run_result["attempted_batch_ids"][-1] if run_result["attempted_batch_ids"] else "BATCH-UNKNOWN",
        "roadmap_id": run_result["roadmap_id"],
        "trace_id": integration["trace_id"],
        "created_at": timestamp,
        "stop_reason": stop_reason,
    }
    delivery_status = "completed" if stop_reason == "max_batches_reached" and not blocking_conditions else (
        "completed_with_risk" if stop_reason == "max_batches_reached" else ("blocked" if blocking_conditions else "failed")
    )
    batch_delivery_report = {
        "report_id": f"BDR-{_canonical_hash(delivery_seed)[:12].upper()}",
        "schema_version": "1.0.0",
        "batch_id": delivery_seed["batch_id"],
        "roadmap_id": run_result["roadmap_id"],
        "intent": "Execute governed roadmap batch and emit deterministic handoff memory artifacts.",
        "status": delivery_status,
        "files_changed": [],
        "contracts_added_or_updated": [],
        "tests_run": [],
        "results_summary": _sorted_unique_strings(
            [
                f"stop_reason={stop_reason}",
                f"next_cycle_decision={next_cycle_decision['decision']}",
                f"autonomy_decision={autonomy_decision_record['decision']}",
                f"program_alignment_status={program_alignment_status}",
            ]
        ),
        "remaining_risks": _sorted_unique_strings(
            list(blocking_conditions)
            + [f"critical_risk:{item}" for item in blocking_conditions if item.startswith("AUTH_")]
        ),
        "open_followups": _sorted_unique_strings(
            [f"validation:{item}" for item in required_reviews]
            + [f"contract:{item}" for item in required_reviews if "contract" in item]
            + [f"autonomy_blocker:{item}" for item in autonomy_blockers]
            + [f"unknown_state_blocker:{item}" for item in unknown_state_blockers]
        ),
        "recommended_next_batch": next_cycle_input_bundle.get("recommended_start_batch"),
        "blocking_issues": _sorted_unique_strings(blocking_conditions),
        "evidence_refs": _sorted_unique_strings(
            [
                f"roadmap_multi_batch_run_result:{run_result['run_id']}",
                next_cycle_decision_ref,
                next_cycle_input_bundle_ref,
                autonomy_decision_ref,
                decision_proof_ref,
                allow_decision_proof_ref,
                f"next_step_recommendation:{recommendation['recommendation_id']}",
                f"build_summary:{summary['summary_id']}",
                exception_classification_ref,
                exception_resolution_ref,
            ]
            + unknown_state_signal_refs
        ),
        "source_refs": _sorted_unique_strings(list(run_result.get("source_refs", []))),
        "trace_id": integration["trace_id"],
        "created_at": timestamp,
    }
    _validate_schema(batch_delivery_report, "batch_delivery_report")
    batch_handoff_bundle = derive_batch_handoff_bundle(
        batch_delivery_report,
        exception_classification_record=exception_classification_record,
        exception_resolution_record=exception_resolution_record,
    )
    readiness_inputs = dict(integration_inputs.get("capability_readiness_inputs") or {})
    prior_readiness_state = (
        str(prior_handoff_bundle.get("capability_readiness_state"))
        if isinstance(prior_handoff_bundle, dict) and prior_handoff_bundle.get("capability_readiness_state")
        else None
    )
    capability_readiness_record = evaluate_capability_readiness(
        roadmap_id=run_result["roadmap_id"],
        trace_id=integration["trace_id"],
        created_at=timestamp,
        batch_delivery_reports=[*list(readiness_inputs.get("batch_delivery_reports") or []), batch_delivery_report],
        eval_results=[
            *list(readiness_inputs.get("eval_results") or []),
            dict(integration_inputs.get("eval_result") or {}),
            *[
                {
                    "result_status": "pass" if row["pass_rate"] >= 0.95 else ("fail" if row["fail_rate"] > 0 else "indeterminate"),
                    "eval_stage": row["eval_stage"],
                }
                for row in continuous_eval_run_records
            ],
        ],
        autonomy_decisions=[*list(readiness_inputs.get("autonomy_decisions") or []), autonomy_decision_record],
        exception_routing_outputs=[
            *list(readiness_inputs.get("exception_routing_outputs") or []),
            exception_resolution_record,
        ],
        drift_signals=[
            *list(readiness_inputs.get("drift_signals") or []),
            {"drift_level": program_drift_severity, "stop_reason": stop_reason},
            *[
                {"drift_level": "high" if abs(float(row["drift_delta"])) >= 0.2 else "low", "eval_stage": row["eval_stage"]}
                for row in continuous_eval_run_records
            ],
        ],
        replay_metrics=[
            *list(readiness_inputs.get("replay_metrics") or []),
            {"status": str(integration.get("replay_status", "unknown"))},
        ],
        unresolved_risks=[
            *[str(item) for item in readiness_inputs.get("unresolved_risks", [])],
            *[str(item) for item in unresolved_critical_risks],
        ],
        recent_batches_considered=int(readiness_inputs.get("recent_batches_considered", 5)),
        prior_readiness_state=prior_readiness_state,
    )
    _validate_schema(capability_readiness_record, "capability_readiness_record")
    readiness_state = str(capability_readiness_record["readiness_state"])
    readiness_ref = f"capability_readiness_record:{capability_readiness_record['readiness_id']}"
    observability_reports = build_observability_reports(
        eval_run_records=continuous_eval_run_records,
        budget_status=system_budget_status,
        readiness_state=readiness_state,
        replay_status=str(integration.get("replay_status", "unknown")).strip().lower(),
        override_rate=float(capability_readiness_record.get("override_rate", 0.0)),
        created_at=timestamp,
        trace_id=integration["trace_id"],
    )
    trust_posture_snapshot = observability_reports["trust_posture_snapshot"]
    artifact_family_health_report = observability_reports["artifact_family_health_report"]
    evidence_gap_hotspot_report = observability_reports["evidence_gap_hotspot_report"]
    override_hotspot_report = observability_reports["override_hotspot_report"]
    trust_posture_ref = f"trust_posture_snapshot:{trust_posture_snapshot['snapshot_id']}"
    artifact_family_health_ref = f"artifact_family_health_report:{artifact_family_health_report['report_id']}"
    evidence_gap_hotspot_ref = f"evidence_gap_hotspot_report:{evidence_gap_hotspot_report['report_id']}"
    override_hotspot_ref = f"override_hotspot_report:{override_hotspot_report['report_id']}"

    if readiness_state == "unsafe":
        autonomy_decision_record["decision"] = "stop"
        autonomy_decision_record["reason_codes"] = sorted(
            set(list(autonomy_decision_record["reason_codes"]) + ["critical_risk_threshold_exceeded"])
        )
    elif readiness_state == "constrained" and autonomy_decision_record["decision"] == "continue":
        autonomy_decision_record["decision"] = "require_human_review"
        autonomy_decision_record["reason_codes"] = sorted(
            set(list(autonomy_decision_record["reason_codes"]) + ["review_gate_required"])
        )
    _validate_schema(autonomy_decision_record, "autonomy_decision_record")
    autonomy_decision_ref = f"autonomy_decision_record:{autonomy_decision_record['autonomy_decision_id']}"
    autonomy_blockers = [] if autonomy_decision_record["decision"] == "continue" else [
        f"autonomy:{code}" for code in autonomy_decision_record["reason_codes"]
    ]
    next_cycle_input_bundle["autonomy_decision_ref"] = autonomy_decision_ref
    next_cycle_input_bundle["autonomy_blockers"] = sorted(set(autonomy_blockers))
    summary["autonomy_decision"] = autonomy_decision_record["decision"]
    summary["autonomy_reason_codes"] = autonomy_decision_record["reason_codes"]
    summary["autonomy_decision_ref"] = autonomy_decision_ref
    batch_delivery_report["results_summary"] = _sorted_unique_strings(
        [
            f"stop_reason={stop_reason}",
            f"next_cycle_decision={next_cycle_decision['decision']}",
            f"autonomy_decision={autonomy_decision_record['decision']}",
            f"program_alignment_status={program_alignment_status}",
        ]
    )
    batch_delivery_report["open_followups"] = _sorted_unique_strings(
        [f"validation:{item}" for item in required_reviews]
        + [f"contract:{item}" for item in required_reviews if "contract" in item]
        + [f"autonomy_blocker:{item}" for item in autonomy_blockers]
        + [f"unknown_state_blocker:{item}" for item in unknown_state_blockers]
    )
    batch_delivery_report["evidence_refs"] = _sorted_unique_strings(
        [
            f"roadmap_multi_batch_run_result:{run_result['run_id']}",
            next_cycle_decision_ref,
            next_cycle_input_bundle_ref,
            autonomy_decision_ref,
            decision_proof_ref,
            allow_decision_proof_ref,
            f"next_step_recommendation:{recommendation['recommendation_id']}",
            f"build_summary:{summary['summary_id']}",
            exception_classification_ref,
            exception_resolution_ref,
            readiness_ref,
        ]
        + unknown_state_signal_refs
    )
    batch_handoff_bundle = derive_batch_handoff_bundle(
        batch_delivery_report,
        exception_classification_record=exception_classification_record,
        exception_resolution_record=exception_resolution_record,
    )
    eval_coverage_signal = dict(integration_inputs.get("eval_coverage_signal") or {})
    drift_signals = {
        "drift_detected": program_drift_severity in {"medium", "high"} or stop_reason == "program_drift_detected",
        "repeated_failure": repeated_failure_count >= repeated_failure_threshold,
    }
    roadmap_adjustments = derive_roadmap_adjustments(
        roadmap_artifact=updated_roadmap,
        exception_resolution_record=exception_resolution_record,
        batch_handoff_bundle=batch_handoff_bundle,
        eval_coverage_signal=eval_coverage_signal,
        drift_signals=drift_signals,
        unresolved_risks=unresolved_critical_risks,
        created_at=timestamp,
    )
    adjusted_roadmap = apply_roadmap_adjustments(
        roadmap_artifact=updated_roadmap,
        adjustments=roadmap_adjustments,
        created_at=timestamp,
    )
    adjusted_next_batch_id = _next_not_started_batch_id(adjusted_roadmap)
    adjustment_refs = [f"roadmap_adjustment_record:{row['adjustment_id']}" for row in roadmap_adjustments]
    rollback_plan_record = build_rollback_plan_record(
        source_batch_id=str(run_result["attempted_batch_ids"][-1] if run_result["attempted_batch_ids"] else "BATCH-UNKNOWN"),
        source_artifact_refs=[
            f"build_summary:{summary['summary_id']}",
            f"next_step_recommendation:{recommendation['recommendation_id']}",
            failure_taxonomy_ref,
            *([correction_pattern_ref] if correction_pattern_ref else []),
            *adjustment_refs,
        ],
        roadmap_adjustment_refs=adjustment_refs,
        next_cycle_decision=next_cycle_decision["decision"],
        created_at=timestamp,
        trace_id=integration["trace_id"],
    )
    rollback_plan_ref = f"rollback_plan_record:{rollback_plan_record['rollback_plan_id']}"
    promotion_evidence_window = [dict(item) for item in integration_inputs.get("promotion_consistency_evidence", [])]
    promotion_evidence_window.append(
        {
            "determinism_status": str(integration.get("determinism_status", "unknown")),
            "replay_status": str(integration.get("replay_status", "unknown")),
            "eval_status": "pass" if str(integration_inputs.get("eval_result", {}).get("result_status", "")).lower() == "pass" else "fail",
            "drift_detected": program_drift_severity in {"medium", "high"} or stop_reason == "program_drift_detected",
        }
    )
    promotion_consistency_record = evaluate_promotion_consistency(
        source_batch_id=str(run_result["attempted_batch_ids"][-1] if run_result["attempted_batch_ids"] else "BATCH-UNKNOWN"),
        evidence_window=promotion_evidence_window,
        rollback_plan_record=rollback_plan_record,
        created_at=timestamp,
        trace_id=integration["trace_id"],
    )
    promotion_consistency_ref = f"promotion_consistency_record:{promotion_consistency_record['promotion_consistency_id']}"
    if next_cycle_decision["decision"] == "run_next_cycle" and promotion_consistency_record["promotion_state"] != "allow":
        next_cycle_decision["decision"] = "stop"
        next_cycle_decision["decision_reason_codes"] = sorted(
            set(list(next_cycle_decision["decision_reason_codes"]) + ["missing_required_artifacts"])
        )
        next_cycle_decision["risk_posture"] = "critical"
    recommendation["next_batch_id"] = adjusted_next_batch_id
    recommendation["next_batch_candidate"] = adjusted_next_batch_id
    recommendation["why"] = sorted(set(list(recommendation["why"]) + [f"roadmap_adjustments_applied={len(roadmap_adjustments)}"]))
    recommendation["source_refs"] = sorted(set(list(recommendation["source_refs"]) + adjustment_refs))
    recommendation["artifact_refs"]["related_artifacts"] = sorted(
        set(list(recommendation["artifact_refs"]["related_artifacts"]) + adjustment_refs + [rollback_plan_ref, promotion_consistency_ref])
    )
    summary["next_batch_candidate"] = adjusted_next_batch_id
    summary["capability_readiness_state"] = readiness_state
    summary["capability_readiness_ref"] = readiness_ref
    summary["watch_next"] = sorted(set(list(summary["watch_next"]) + [f"roadmap_adjustments_applied={len(roadmap_adjustments)}"]))
    summary["source_refs"] = sorted(
        set(
            list(summary["source_refs"])
            + adjustment_refs
            + [
                readiness_ref,
                rollback_plan_ref,
                promotion_consistency_ref,
                budget_status_ref,
                canary_rollout_ref,
                trust_posture_ref,
                artifact_family_health_ref,
                evidence_gap_hotspot_ref,
                override_hotspot_ref,
                *continuous_eval_refs,
            ]
        )
    )
    summary["artifact_index"]["related_artifacts"] = sorted(
        set(list(summary["artifact_index"]["related_artifacts"]) + adjustment_refs + [rollback_plan_ref, promotion_consistency_ref])
    )
    summary["rollback_plan_ref"] = rollback_plan_ref
    summary["promotion_consistency_ref"] = promotion_consistency_ref
    summary["system_budget_status_ref"] = budget_status_ref
    summary["canary_rollout_ref"] = canary_rollout_ref
    summary["continuous_eval_run_refs"] = continuous_eval_refs
    summary["trust_posture_snapshot_ref"] = trust_posture_ref
    summary["artifact_family_health_report_ref"] = artifact_family_health_ref
    summary["evidence_gap_hotspot_report_ref"] = evidence_gap_hotspot_ref
    summary["override_hotspot_report_ref"] = override_hotspot_ref
    next_cycle_input_bundle["recommended_start_batch"] = adjusted_next_batch_id
    batch_delivery_report["recommended_next_batch"] = adjusted_next_batch_id
    batch_delivery_report["evidence_refs"] = _sorted_unique_strings(
        list(batch_delivery_report["evidence_refs"])
        + [failure_taxonomy_ref, rollback_plan_ref, promotion_consistency_ref]
        + ([correction_pattern_ref] if correction_pattern_ref else [])
    )
    batch_handoff_bundle["recommended_next_batch"] = adjusted_next_batch_id
    batch_handoff_bundle["capability_readiness_state"] = readiness_state
    batch_handoff_bundle["capability_readiness_ref"] = readiness_ref
    batch_handoff_bundle["failure_taxonomy_ref"] = failure_taxonomy_ref
    batch_handoff_bundle["correction_pattern_ref"] = correction_pattern_ref or "correction_pattern_record:CPR-000000000000"
    batch_handoff_bundle["rollback_plan_ref"] = rollback_plan_ref
    batch_handoff_bundle["promotion_consistency_ref"] = promotion_consistency_ref
    batch_handoff_bundle["system_budget_status_ref"] = budget_status_ref
    batch_handoff_bundle["canary_rollout_ref"] = canary_rollout_ref
    batch_handoff_bundle["continuous_eval_run_refs"] = continuous_eval_refs
    batch_handoff_bundle["trust_posture_snapshot_ref"] = trust_posture_ref
    batch_handoff_bundle["must_carry_forward_artifacts"] = sorted(
        set(
            list(batch_handoff_bundle["must_carry_forward_artifacts"])
            + adjustment_refs
            + [
                readiness_ref,
                failure_taxonomy_ref,
                rollback_plan_ref,
                promotion_consistency_ref,
                budget_status_ref,
                canary_rollout_ref,
                trust_posture_ref,
                artifact_family_health_ref,
                evidence_gap_hotspot_ref,
                override_hotspot_ref,
                *continuous_eval_refs,
            ]
            + ([correction_pattern_ref] if correction_pattern_ref else [])
        )
    )
    batch_handoff_bundle["required_next_actions"] = sorted(
        set(list(batch_handoff_bundle["required_next_actions"]) + [f"apply:{item}" for item in adjustment_refs])
    )
    _validate_schema(next_cycle_input_bundle, "next_cycle_input_bundle")
    _validate_schema(recommendation, "next_step_recommendation")
    _validate_schema(summary, "build_summary")
    _validate_schema(batch_delivery_report, "batch_delivery_report")
    _validate_schema(batch_handoff_bundle, "batch_handoff_bundle")

    return {
        "updated_roadmap": adjusted_roadmap,
        "roadmap_multi_batch_run_result": run_result,
        "adaptive_execution_observability": adaptive_observability,
        "adaptive_execution_trend_report": adaptive_trend_report,
        "adaptive_execution_policy_review": adaptive_policy_review,
        "autonomy_decision_record": autonomy_decision_record,
        "decision_proof_record": decision_proof_record,
        "allow_decision_proof": allow_decision_proof,
        "unknown_state_signals": unknown_state_signals,
        "exception_classification_record": exception_classification_record,
        "exception_resolution_record": exception_resolution_record,
        "failure_taxonomy_record": failure_taxonomy_record,
        "correction_pattern_record": correction_pattern_record,
        "rollback_plan_record": rollback_plan_record,
        "promotion_consistency_record": promotion_consistency_record,
        "continuous_eval_run_records": continuous_eval_run_records,
        "system_budget_status": system_budget_status,
        "canary_rollout_record": canary_rollout_record,
        "trust_posture_snapshot": trust_posture_snapshot,
        "artifact_family_health_report": artifact_family_health_report,
        "evidence_gap_hotspot_report": evidence_gap_hotspot_report,
        "override_hotspot_report": override_hotspot_report,
        "core_system_integration_validation": integration,
        "next_step_recommendation": recommendation,
        "next_cycle_decision": next_cycle_decision,
        "next_cycle_input_bundle": next_cycle_input_bundle,
        "roadmap_adjustments": roadmap_adjustments,
        "capability_readiness_record": capability_readiness_record,
        "batch_delivery_report": batch_delivery_report,
        "batch_handoff_bundle": batch_handoff_bundle,
        "prior_batch_handoff_bundle": prior_handoff_bundle,
        "build_summary": summary,
    }


__all__ = [
    "SystemCycleOperatorError",
    "build_failure_taxonomy_record",
    "build_rollback_plan_record",
    "decide_next_cycle",
    "derive_correction_pattern",
    "derive_batch_handoff_bundle",
    "evaluate_promotion_consistency",
    "run_system_cycle",
    "validate_explicit_state_dependencies",
]
