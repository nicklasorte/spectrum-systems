"""HNX bounded harness semantics: contracts, state machine, continuity integrity, replay, and governed feedback hardening."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any, Mapping

from spectrum_systems.contracts import validate_artifact


class HNXHardeningError(ValueError):
    """Raised when HNX invariants fail closed."""


_ALLOWED_STATES: dict[str, set[str]] = {
    "initialized": {"candidate_ready", "halted", "frozen", "human_checkpoint"},
    "candidate_ready": {"checkpointed", "halted", "frozen", "human_checkpoint"},
    "checkpointed": {"resumed", "halted", "frozen", "human_checkpoint"},
    "resumed": {"completed", "checkpointed", "halted", "frozen", "human_checkpoint"},
    "human_checkpoint": {"resumed", "halted", "frozen"},
    "frozen": {"resumed", "halted", "human_checkpoint"},
    "completed": set(),
    "halted": set(),
}


def _hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def _require_ref(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HNXHardeningError(f"{name}_required")
    return value


def enforce_hnx_boundary(*, consumed_inputs: list[str], emitted_outputs: list[str]) -> list[str]:
    """HNX consumes harness/state inputs and emits structure+signal artifacts only."""
    allowed_inputs = {
        "hnx_stage_contract_record",
        "hnx_checkpoint_record",
        "hnx_resume_record",
        "hnx_continuity_state_record",
        "hnx_stop_condition_record",
        "hnx_feedback_record",
    }
    allowed_outputs = {
        "hnx_harness_eval_result",
        "hnx_harness_readiness_record",
        "hnx_harness_conflict_record",
        "hnx_harness_bundle",
        "hnx_harness_effectiveness_record",
        "hnx_continuity_debt_record",
        "hnx_feedback_routing_record",
        "hnx_feedback_eval_scaffold",
        "hnx_contract_tightening_record",
        "hnx_control_signal_record",
        "hnx_feedback_gate_decision",
        "hnx_readiness_certification_record",
        "hnx_maintain_cycle_record",
    }
    forbidden_terms = (
        "pqx_execution",
        "tlc_route",
        "tpa_policy",
        "cde_closeout",
        "sel_enforcement",
        "fre_repair",
        "ril_interpretation",
        "promotion_decision",
        "policy_decision",
        "release_decision",
    )
    failures: list[str] = []
    for name in consumed_inputs:
        if name not in allowed_inputs:
            failures.append(f"invalid_hnx_upstream_input:{name}")
    for name in emitted_outputs:
        if name not in allowed_outputs:
            failures.append(f"invalid_hnx_downstream_output:{name}")
        if any(term in name for term in forbidden_terms):
            failures.append(f"forbidden_hnx_owner_overlap:{name}")
    return sorted(set(failures))


def evaluate_stage_transition(
    *,
    from_state: str,
    to_state: str,
    stage_index: int,
    next_stage_index: int,
    required_human_checkpoint: bool,
    human_checkpoint_recorded: bool,
    stop_required: bool = False,
    freeze_required: bool = False,
) -> dict[str, Any]:
    failures: list[str] = []
    allowed_next = _ALLOWED_STATES.get(from_state)
    if allowed_next is None:
        failures.append("UNKNOWN_FROM_STATE")
    elif to_state not in allowed_next:
        failures.append("ILLEGAL_TRANSITION")

    if from_state in {"completed", "halted"}:
        failures.append("TERMINAL_STATE_VIOLATION")

    if next_stage_index != stage_index + 1 and to_state not in {"halted", "frozen", "human_checkpoint"}:
        failures.append("STAGE_SKIP_DETECTED")

    if required_human_checkpoint and not human_checkpoint_recorded:
        failures.append("HUMAN_CHECKPOINT_REQUIRED")

    if stop_required and to_state not in {"halted", "frozen", "human_checkpoint"}:
        failures.append("STOP_REQUIRED_TRANSITION_BLOCK")

    if freeze_required and to_state not in {"frozen", "halted"}:
        failures.append("FREEZE_REQUIRED_TRANSITION_BLOCK")

    return {
        "allowed": not failures,
        "reason_codes": failures or ["TRANSITION_ALLOWED"],
        "recommended_state": "halted" if failures else to_state,
    }


def evaluate_harness_contracts(
    *,
    stage_contract: Mapping[str, Any],
    checkpoint_record: Mapping[str, Any] | None,
    resume_record: Mapping[str, Any] | None,
    continuity_state: Mapping[str, Any] | None,
    stop_condition_record: Mapping[str, Any] | None,
    expected_lineage_chain: list[str],
    evaluated_at: str,
) -> dict[str, Any]:
    required_stage_fields = {
        "contract_id",
        "run_id",
        "trace_id",
        "required_inputs",
        "required_outputs",
        "required_evals",
        "required_trace_fields",
        "required_continuity_artifacts",
        "stop_conditions",
    }
    stage_fields = set(stage_contract.keys())
    missing_stage_fields = sorted(required_stage_fields - stage_fields)

    checks = {
        "stage_contract_complete": not missing_stage_fields,
        "checkpoint_valid": isinstance(checkpoint_record, Mapping) and checkpoint_record.get("artifact_type") == "hnx_checkpoint_record",
        "resume_valid": isinstance(resume_record, Mapping) and resume_record.get("artifact_type") == "hnx_resume_record",
        "continuity_complete": isinstance(continuity_state, Mapping) and bool(continuity_state.get("continuity_refs")),
        "stop_condition_complete": isinstance(stop_condition_record, Mapping) and stop_condition_record.get("artifact_type") == "hnx_stop_condition_record",
    }

    fail_reasons = [name for name, passed in checks.items() if not passed]
    if missing_stage_fields:
        fail_reasons.extend([f"stage_contract_missing:{field}" for field in missing_stage_fields])

    if isinstance(resume_record, Mapping) and resume_record.get("downstream_lineage") != expected_lineage_chain:
        checks["resume_to_execution_integrity"] = False
        fail_reasons.append("resume_to_execution_integrity")
    else:
        checks["resume_to_execution_integrity"] = True

    if isinstance(checkpoint_record, Mapping) and isinstance(resume_record, Mapping):
        if checkpoint_record.get("trace_id") != resume_record.get("trace_id"):
            checks["trace_linkage_integrity"] = False
            fail_reasons.append("trace_linkage_integrity")
        else:
            checks["trace_linkage_integrity"] = True
    else:
        checks["trace_linkage_integrity"] = False
        fail_reasons.append("trace_linkage_integrity")

    result = {
        "artifact_type": "hnx_harness_eval_result",
        "schema_version": "1.0.0",
        "eval_id": f"hnx-eval-{_hash([stage_contract.get('contract_id'), sorted(set(fail_reasons)), evaluated_at])[:12]}",
        "evaluation_status": "pass" if not fail_reasons else "fail",
        "checks": checks,
        "fail_reasons": sorted(set(fail_reasons)),
        "evaluated_at": evaluated_at,
        "trace_id": str((continuity_state or {}).get("trace_id") or stage_contract.get("trace_id") or "unknown"),
    }
    validate_artifact(result, "hnx_harness_eval_result")
    return result


def validate_checkpoint_resume_integrity(*, checkpoint_record: Mapping[str, Any], resume_record: Mapping[str, Any], continuity_state: Mapping[str, Any], now_epoch_minutes: int) -> list[str]:
    fails: list[str] = []
    if resume_record.get("checkpoint_id") != checkpoint_record.get("checkpoint_id"):
        fails.append("CHECKPOINT_RESUME_ID_MISMATCH")
    if checkpoint_record.get("content_hash") != resume_record.get("checkpoint_hash"):
        fails.append("CHECKPOINT_HASH_MISMATCH")
    if checkpoint_record.get("lineage_ref") not in set(continuity_state.get("continuity_refs") or []):
        fails.append("CONTINUITY_LINEAGE_MISSING")
    if checkpoint_record.get("trace_id") != resume_record.get("trace_id"):
        fails.append("TRACE_LINKAGE_MISMATCH")
    if "resume_lineage_ref" in resume_record and resume_record.get("resume_lineage_ref") != checkpoint_record.get("lineage_ref"):
        fails.append("RESUME_LINEAGE_MISMATCH")

    created = int(checkpoint_record.get("created_epoch_minutes") or -1)
    max_age = int(continuity_state.get("max_checkpoint_age_minutes") or -1)
    if created < 0 or max_age < 1:
        fails.append("CHECKPOINT_FRESHNESS_POLICY_INVALID")
    elif now_epoch_minutes - created > max_age:
        fails.append("CHECKPOINT_STALE")
    return sorted(set(fails))


def validate_stop_conditions(*, stop_condition_record: Mapping[str, Any], requested_transition: str) -> list[str]:
    fails: list[str] = []
    if stop_condition_record.get("stop_required") is True and requested_transition not in {"halted", "frozen", "human_checkpoint"}:
        fails.append("STOP_CONDITION_BYPASS")
    if stop_condition_record.get("freeze_required") is True and requested_transition not in {"frozen", "halted"}:
        fails.append("FREEZE_BYPASS")
    if stop_condition_record.get("human_checkpoint_required") is True and stop_condition_record.get("human_checkpoint_recorded") is not True:
        fails.append("HUMAN_CHECKPOINT_BYPASS")
    return sorted(set(fails))


def build_harness_bundle(*, run_id: str, trace_id: str, stage_contract: Mapping[str, Any], checkpoint_record: Mapping[str, Any], resume_record: Mapping[str, Any], continuity_state: Mapping[str, Any], stop_condition_record: Mapping[str, Any], eval_result: Mapping[str, Any], created_at: str) -> dict[str, Any]:
    payload = {
        "stage_contract": stage_contract,
        "checkpoint_record": checkpoint_record,
        "resume_record": resume_record,
        "continuity_state": continuity_state,
        "stop_condition_record": stop_condition_record,
    }
    input_fingerprint = _hash(payload)
    bundle = {
        "artifact_type": "hnx_harness_bundle",
        "schema_version": "1.0.0",
        "bundle_id": f"hnx-bundle-{_hash([run_id, trace_id, input_fingerprint])[:12]}",
        "run_id": run_id,
        "trace_id": trace_id,
        "input_fingerprint": input_fingerprint,
        "eval_ref": f"hnx_harness_eval_result:{eval_result.get('eval_id')}",
        "continuity_refs": list(dict.fromkeys([_require_ref(checkpoint_record.get("lineage_ref"), "checkpoint_lineage_ref"), *[str(v) for v in continuity_state.get("continuity_refs", [])]])),
        "created_at": created_at,
    }
    validate_artifact(bundle, "hnx_harness_bundle")
    return bundle


def validate_harness_replay(*, prior_bundle: Mapping[str, Any], replay_bundle: Mapping[str, Any], prior_eval: Mapping[str, Any], replay_eval: Mapping[str, Any], prior_runs: list[Mapping[str, Any]] | None = None) -> tuple[bool, list[str]]:
    fails: list[str] = []
    if prior_bundle.get("input_fingerprint") != replay_bundle.get("input_fingerprint"):
        fails.append("REPLAY_INPUT_DRIFT")
    if prior_eval.get("fail_reasons") != replay_eval.get("fail_reasons"):
        fails.append("REPLAY_OUTPUT_DRIFT")
    if not prior_bundle.get("continuity_refs") or not replay_bundle.get("continuity_refs"):
        fails.append("REPLAY_EVIDENCE_INCOMPLETE")

    prior_runs = prior_runs or []
    if prior_runs:
        baseline = sorted(set(tuple(sorted((row.get("fail_reasons") or []))) for row in prior_runs))
        candidate = tuple(sorted((replay_eval.get("fail_reasons") or [])))
        if tuple(candidate) not in baseline:
            fails.append("HIDDEN_STATE_VARIANCE_DETECTED")

    return (not fails, sorted(set(fails)))


def build_harness_readiness(*, run_id: str, trace_id: str, eval_result: Mapping[str, Any], continuity_failures: list[str], created_at: str) -> dict[str, Any]:
    fail_reasons = sorted(set([*eval_result.get("fail_reasons", []), *continuity_failures]))
    artifact = {
        "artifact_type": "hnx_harness_readiness_record",
        "schema_version": "1.0.0",
        "readiness_id": f"hnx-ready-{_hash([run_id, trace_id, fail_reasons])[:12]}",
        "run_id": run_id,
        "trace_id": trace_id,
        "readiness_status": "candidate_only" if not fail_reasons else "blocked",
        "fail_reasons": fail_reasons,
        "non_authority_assertions": [
            "candidate_only_non_authoritative",
            "does_not_replace_tlc_orchestration",
            "does_not_replace_tpa_policy_authority",
            "does_not_replace_cde_or_sel_authority",
            "does_not_replace_pqx_execution_authority",
        ],
        "created_at": created_at,
    }
    validate_artifact(artifact, "hnx_harness_readiness_record")
    return artifact


def build_continuity_debt_record(*, run_id: str, trace_id: str, violations: list[str], created_at: str) -> dict[str, Any]:
    counter = Counter(violations)
    repeated = sorted([name for name, count in counter.items() if count > 1])
    artifact = {
        "artifact_type": "hnx_continuity_debt_record",
        "schema_version": "1.0.0",
        "debt_id": f"hnx-debt-{_hash([run_id, trace_id, sorted(counter.items())])[:12]}",
        "run_id": run_id,
        "trace_id": trace_id,
        "violation_counts": {k: int(v) for k, v in sorted(counter.items())},
        "repeat_violation_codes": repeated,
        "debt_status": "elevated" if repeated else "normal",
        "created_at": created_at,
    }
    validate_artifact(artifact, "hnx_continuity_debt_record")
    return artifact


def compute_harness_effectiveness(*, window_id: str, created_at: str, outcomes: list[Mapping[str, Any]]) -> dict[str, Any]:
    if not outcomes:
        raise HNXHardeningError("harness_effectiveness_requires_outcomes")
    total = len(outcomes)
    success = sum(1 for row in outcomes if row.get("completed") is True)
    broken_resumes = sum(1 for row in outcomes if row.get("broken_resume") is True)
    stop_bypass_blocked = sum(1 for row in outcomes if row.get("stop_bypass_blocked") is True)
    invalid_transitions = sum(1 for row in outcomes if row.get("invalid_transition") is True)
    unresolved_feedback = sum(1 for row in outcomes if row.get("unresolved_feedback") is True)
    stale_checkpoints = sum(1 for row in outcomes if row.get("stale_checkpoint") is True)
    replay_mismatch = sum(1 for row in outcomes if row.get("replay_mismatch") is True)
    handoff_incomplete = sum(1 for row in outcomes if row.get("handoff_complete") is False)
    completion_quality = success / total
    broken_resume_rate = broken_resumes / total
    stop_guard_rate = stop_bypass_blocked / total
    value_status = "improving" if completion_quality >= 0.7 and broken_resume_rate <= 0.2 else "degraded"
    artifact = {
        "artifact_type": "hnx_harness_effectiveness_record",
        "schema_version": "1.0.0",
        "effectiveness_id": f"hnx-eff-{_hash([window_id, total, success, broken_resumes, stop_bypass_blocked])[:12]}",
        "window_id": window_id,
        "runs_evaluated": total,
        "completion_quality": completion_quality,
        "broken_resume_rate": broken_resume_rate,
        "stop_bypass_block_rate": stop_guard_rate,
        "invalid_transition_rate": invalid_transitions / total,
        "handoff_completeness_rate": (total - handoff_incomplete) / total,
        "stale_checkpoint_rate": stale_checkpoints / total,
        "resume_breakage_rate": broken_resume_rate,
        "replay_mismatch_rate": replay_mismatch / total,
        "unresolved_feedback_count": unresolved_feedback,
        "value_status": value_status,
        "created_at": created_at,
    }
    validate_artifact(artifact, "hnx_harness_effectiveness_record")
    return artifact


def run_hnx_boundary_redteam(*, fixtures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in fixtures if row.get("expected") == "blocked" and row.get("observed") != "blocked"]


def run_hnx_semantic_redteam(*, fixtures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in fixtures if row.get("semantic_risk") is True and row.get("observed") != "blocked"]


def build_hnx_conflict_record(*, run_id: str, trace_id: str, conflict_codes: list[str], created_at: str) -> dict[str, Any]:
    artifact = {
        "artifact_type": "hnx_harness_conflict_record",
        "schema_version": "1.0.0",
        "conflict_id": f"hnx-conflict-{_hash([run_id, trace_id, sorted(set(conflict_codes))])[:12]}",
        "run_id": run_id,
        "trace_id": trace_id,
        "conflict_codes": sorted(set(conflict_codes)),
        "created_at": created_at,
    }
    validate_artifact(artifact, "hnx_harness_conflict_record")
    return artifact


def build_hnx_feedback_record(
    *,
    created_at: str,
    trace_id: str,
    source: str,
    stage_ref: str,
    failure_type: str,
    severity: str,
    affected_artifact_ids: list[str],
    reproduction_context: str,
    structural_root_cause: str,
    recommended_action: str,
    requires_eval_update: bool,
    requires_contract_update: bool,
    requires_policy_signal: bool,
    resolution_status: str,
    resolution_refs: list[str],
) -> dict[str, Any]:
    seed = [trace_id, source, stage_ref, failure_type, severity, sorted(affected_artifact_ids)]
    feedback_hash = _hash(seed)
    artifact = {
        "artifact_type": "hnx_feedback_record",
        "schema_version": "1.0.0",
        "feedback_id": f"hnx-feedback-{feedback_hash[:12]}",
        "created_at": created_at,
        "schema_ref": "contracts/schemas/hnx_feedback_record.schema.json",
        "trace_id": trace_id,
        "source": source,
        "stage_ref": stage_ref,
        "failure_type": failure_type,
        "severity": severity,
        "affected_artifact_ids": sorted(set(affected_artifact_ids)),
        "reproduction_context": reproduction_context,
        "structural_root_cause": structural_root_cause,
        "recommended_action": recommended_action,
        "requires_eval_update": requires_eval_update,
        "requires_contract_update": requires_contract_update,
        "requires_policy_signal": requires_policy_signal,
        "resolution_status": resolution_status,
        "resolution_refs": sorted(set(resolution_refs)),
        "feedback_hash": feedback_hash,
    }
    validate_artifact(artifact, "hnx_feedback_record")
    return artifact


def route_hnx_feedback(*, feedback_record: Mapping[str, Any], created_at: str) -> dict[str, Any]:
    routes: list[str] = []
    if feedback_record.get("requires_eval_update") is True:
        routes.append("eval_expansion")
    if feedback_record.get("requires_contract_update") is True:
        routes.append("stage_contract_tightening")
    if str(feedback_record.get("source")) in {"replay", "checkpoint", "handoff", "maintain"}:
        routes.append("continuity_replay_hardening")
    routes.append("drift_structural_health_signal")
    if feedback_record.get("requires_policy_signal") is True:
        routes.append("control_facing_structural_signal")
    if str(feedback_record.get("severity")) in {"high", "critical"}:
        routes.append("redteam_regression_bundle")

    artifact = {
        "artifact_type": "hnx_feedback_routing_record",
        "schema_version": "1.0.0",
        "routing_id": f"hnx-route-{_hash([feedback_record.get('feedback_id'), routes])[:12]}",
        "feedback_id": feedback_record.get("feedback_id"),
        "trace_id": feedback_record.get("trace_id"),
        "routes": sorted(set(routes)),
        "created_at": created_at,
    }
    validate_artifact(artifact, "hnx_feedback_routing_record")
    return artifact


def compile_feedback_to_eval(*, feedback_record: Mapping[str, Any], created_at: str) -> dict[str, Any]:
    failure_type = str(feedback_record.get("failure_type"))
    eval_family = {
        "invalid_transition": "invalid_transition_eval",
        "handoff_incomplete": "handoff_completeness_eval",
        "stale_checkpoint": "stale_checkpoint_eval",
        "replay_mismatch": "replay_mismatch_eval",
        "hidden_state_variance": "hidden_state_consistency_eval",
        "unresolved_feedback": "unresolved_feedback_blocking_eval",
    }.get(failure_type, "hnx_structural_failure_eval")
    artifact = {
        "artifact_type": "hnx_feedback_eval_scaffold",
        "schema_version": "1.0.0",
        "scaffold_id": f"hnx-eval-scaffold-{_hash([feedback_record.get('feedback_id'), eval_family])[:12]}",
        "feedback_id": feedback_record.get("feedback_id"),
        "trace_id": feedback_record.get("trace_id"),
        "eval_family": eval_family,
        "expected_block_on_failure": str(feedback_record.get("severity")) in {"high", "critical"},
        "created_at": created_at,
    }
    validate_artifact(artifact, "hnx_feedback_eval_scaffold")
    return artifact


def feedback_to_contract_tightening(*, feedback_record: Mapping[str, Any], created_at: str) -> dict[str, Any]:
    required_contract_fields = [
        "required_inputs",
        "required_outputs",
        "required_trace_fields",
        "required_evals",
        "required_continuity_artifacts",
        "stop_conditions",
    ]
    artifact = {
        "artifact_type": "hnx_contract_tightening_record",
        "schema_version": "1.0.0",
        "tightening_id": f"hnx-tighten-{_hash([feedback_record.get('feedback_id'), required_contract_fields])[:12]}",
        "feedback_id": feedback_record.get("feedback_id"),
        "trace_id": feedback_record.get("trace_id"),
        "required_contract_fields": required_contract_fields,
        "failure_type": feedback_record.get("failure_type"),
        "tightening_action": "enforce_required_contract_fields",
        "created_at": created_at,
    }
    validate_artifact(artifact, "hnx_contract_tightening_record")
    return artifact


def emit_hnx_control_signal(*, effectiveness_record: Mapping[str, Any], unresolved_feedback_count: int, continuity_debt_record: Mapping[str, Any], created_at: str) -> dict[str, Any]:
    artifact = {
        "artifact_type": "hnx_control_signal_record",
        "schema_version": "1.0.0",
        "signal_id": f"hnx-signal-{_hash([effectiveness_record.get('effectiveness_id'), unresolved_feedback_count, continuity_debt_record.get('debt_id')])[:12]}",
        "structural_health": "degraded" if unresolved_feedback_count > 0 or continuity_debt_record.get("debt_status") == "elevated" else "stable",
        "continuity_status": "at_risk" if continuity_debt_record.get("debt_status") == "elevated" else "healthy",
        "replay_status": "mismatch_risk" if (effectiveness_record.get("replay_mismatch_rate") or 0.0) > 0 else "consistent",
        "unresolved_feedback_count": int(unresolved_feedback_count),
        "trace_id": continuity_debt_record.get("trace_id") or "unknown",
        "created_at": created_at,
        "non_authority_note": "signal_only_no_allow_warn_freeze_block_authority",
    }
    validate_artifact(artifact, "hnx_control_signal_record")
    return artifact


def evaluate_feedback_completeness_gate(*, feedback_records: list[Mapping[str, Any]], created_at: str, freeze_on_high: bool = True) -> dict[str, Any]:
    unresolved_critical = [
        rec for rec in feedback_records if rec.get("resolution_status") != "resolved" and rec.get("severity") == "critical"
    ]
    unresolved_high = [rec for rec in feedback_records if rec.get("resolution_status") != "resolved" and rec.get("severity") == "high"]
    decision = "allow"
    if unresolved_critical:
        decision = "block"
    elif freeze_on_high and unresolved_high:
        decision = "freeze"

    artifact = {
        "artifact_type": "hnx_feedback_gate_decision",
        "schema_version": "1.0.0",
        "gate_id": f"hnx-feedback-gate-{_hash([decision, [r.get('feedback_id') for r in unresolved_critical], [r.get('feedback_id') for r in unresolved_high]])[:12]}",
        "decision": decision,
        "unresolved_critical_feedback_ids": [str(r.get("feedback_id")) for r in unresolved_critical],
        "unresolved_high_feedback_ids": [str(r.get("feedback_id")) for r in unresolved_high],
        "created_at": created_at,
    }
    validate_artifact(artifact, "hnx_feedback_gate_decision")
    return artifact


def verify_hnx_closeout_gate(*, harness_eval: Mapping[str, Any], readiness: Mapping[str, Any], replay_match: bool, stop_failures: list[str], checkpoint_resume_failures: list[str]) -> dict[str, Any]:
    """HNX closeout gate proving checkpoint/resume, stop-guard, replay, and continuity are operationally real."""
    checks = {
        "checkpoint_resume_integrity": not checkpoint_resume_failures,
        "stop_condition_integrity": not stop_failures,
        "harness_replay_valid": replay_match is True,
        "continuity_semantics_real": harness_eval.get("evaluation_status") == "pass",
        "hnx_bounded_scope_preserved": "does_not_replace_pqx_execution_authority" in readiness.get("non_authority_assertions", []),
    }
    fail_reasons = [name for name, passed in checks.items() if not passed]
    return {"closeout_status": "closed" if not fail_reasons else "open", "checks": checks, "fail_reasons": fail_reasons}


def build_hnx_readiness_certification(
    *,
    run_id: str,
    trace_id: str,
    harness_eval: Mapping[str, Any],
    replay_pass: bool,
    trace_complete: bool,
    required_eval_complete: bool,
    feedback_gate: Mapping[str, Any],
    redteam_clean: bool,
    non_authority_proof_refs: list[str],
    created_at: str,
) -> dict[str, Any]:
    checks = {
        "schema_contract_pass": harness_eval.get("evaluation_status") == "pass",
        "replay_pass": replay_pass,
        "trace_completeness": trace_complete,
        "required_eval_completeness": required_eval_complete,
        "no_unresolved_critical_hnx_feedback": feedback_gate.get("decision") != "block",
        "redteam_clean": redteam_clean,
        "hnx_non_authority_boundary_proven": bool(non_authority_proof_refs),
    }
    fail_reasons = [name for name, passed in checks.items() if not passed]
    artifact = {
        "artifact_type": "hnx_readiness_certification_record",
        "schema_version": "1.0.0",
        "certification_id": f"hnx-cert-{_hash([run_id, trace_id, sorted(fail_reasons)])[:12]}",
        "run_id": run_id,
        "trace_id": trace_id,
        "status": "pass" if not fail_reasons else "fail",
        "checks": checks,
        "fail_reasons": fail_reasons,
        "non_authority_proof_refs": sorted(set(non_authority_proof_refs)),
        "created_at": created_at,
    }
    validate_artifact(artifact, "hnx_readiness_certification_record")
    return artifact


def build_hnx_maintain_cycle_record(
    *,
    maintain_cycle_id: str,
    trace_id: str,
    continuity_drift_detected: bool,
    stage_contract_drift_detected: bool,
    docs_runtime_drift_detected: bool,
    incidents_converted_to_evals: list[str],
    structural_debt_refs: list[str],
    created_at: str,
) -> dict[str, Any]:
    artifact = {
        "artifact_type": "hnx_maintain_cycle_record",
        "schema_version": "1.0.0",
        "maintain_cycle_id": maintain_cycle_id,
        "trace_id": trace_id,
        "continuity_drift_detected": continuity_drift_detected,
        "stage_contract_drift_detected": stage_contract_drift_detected,
        "docs_runtime_drift_detected": docs_runtime_drift_detected,
        "incidents_converted_to_evals": sorted(set(incidents_converted_to_evals)),
        "structural_debt_refs": sorted(set(structural_debt_refs)),
        "maintain_status": "action_required" if continuity_drift_detected or stage_contract_drift_detected or docs_runtime_drift_detected else "healthy",
        "created_at": created_at,
    }
    validate_artifact(artifact, "hnx_maintain_cycle_record")
    return artifact
