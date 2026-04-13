"""HNX bounded harness semantics: contracts, state machine, continuity integrity, replay, and red-team hardening."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any, Mapping

from spectrum_systems.contracts import validate_artifact


class HNXHardeningError(ValueError):
    """Raised when HNX invariants fail closed."""


_ALLOWED_STATES: dict[str, set[str]] = {
    "initialized": {"candidate_ready", "halted"},
    "candidate_ready": {"checkpointed", "halted"},
    "checkpointed": {"resumed", "halted", "frozen"},
    "resumed": {"completed", "checkpointed", "halted", "frozen"},
    "frozen": {"resumed", "halted"},
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
    """HNX consumes only harness/state inputs and emits harness artifacts only."""
    allowed_inputs = {
        "hnx_stage_contract_record",
        "hnx_checkpoint_record",
        "hnx_resume_record",
        "hnx_continuity_state_record",
        "hnx_stop_condition_record",
    }
    allowed_outputs = {
        "hnx_harness_eval_result",
        "hnx_harness_readiness_record",
        "hnx_harness_conflict_record",
        "hnx_harness_bundle",
        "hnx_harness_effectiveness_record",
        "hnx_continuity_debt_record",
    }
    forbidden_terms = ("pqx_execution", "tlc_route", "tpa_policy", "cde_closeout", "sel_enforcement", "fre_repair", "ril_interpretation")
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


def evaluate_stage_transition(*, from_state: str, to_state: str, stage_index: int, next_stage_index: int, required_human_checkpoint: bool, human_checkpoint_recorded: bool) -> dict[str, Any]:
    failures: list[str] = []
    allowed_next = _ALLOWED_STATES.get(from_state)
    if allowed_next is None:
        failures.append("UNKNOWN_FROM_STATE")
    elif to_state not in allowed_next:
        failures.append("ILLEGAL_TRANSITION")

    if next_stage_index != stage_index + 1:
        failures.append("STAGE_SKIP_DETECTED")

    if required_human_checkpoint and not human_checkpoint_recorded:
        failures.append("HUMAN_CHECKPOINT_REQUIRED")

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
    checks = {
        "stage_contract_complete": isinstance(stage_contract.get("required_stages"), list) and bool(stage_contract.get("required_stages")),
        "checkpoint_valid": isinstance(checkpoint_record, Mapping) and checkpoint_record.get("artifact_type") == "hnx_checkpoint_record",
        "resume_valid": isinstance(resume_record, Mapping) and resume_record.get("artifact_type") == "hnx_resume_record",
        "continuity_complete": isinstance(continuity_state, Mapping) and bool(continuity_state.get("continuity_refs")),
        "stop_condition_complete": isinstance(stop_condition_record, Mapping) and stop_condition_record.get("artifact_type") == "hnx_stop_condition_record",
    }

    fail_reasons = [name for name, passed in checks.items() if not passed]
    if isinstance(resume_record, Mapping) and resume_record.get("downstream_lineage") != expected_lineage_chain:
        checks["resume_to_execution_integrity"] = False
        fail_reasons.append("resume_to_execution_integrity")
    else:
        checks["resume_to_execution_integrity"] = True

    result = {
        "artifact_type": "hnx_harness_eval_result",
        "schema_version": "1.0.0",
        "eval_id": f"hnx-eval-{_hash([stage_contract.get('contract_id'), fail_reasons, evaluated_at])[:12]}",
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

    created = int(checkpoint_record.get("created_epoch_minutes") or -1)
    max_age = int(continuity_state.get("max_checkpoint_age_minutes") or -1)
    if created < 0 or max_age < 1:
        fails.append("CHECKPOINT_FRESHNESS_POLICY_INVALID")
    elif now_epoch_minutes - created > max_age:
        fails.append("CHECKPOINT_STALE")
    return sorted(set(fails))


def validate_stop_conditions(*, stop_condition_record: Mapping[str, Any], requested_transition: str) -> list[str]:
    fails: list[str] = []
    if stop_condition_record.get("stop_required") is True and requested_transition not in {"halted", "frozen"}:
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


def validate_harness_replay(*, prior_bundle: Mapping[str, Any], replay_bundle: Mapping[str, Any], prior_eval: Mapping[str, Any], replay_eval: Mapping[str, Any]) -> tuple[bool, list[str]]:
    fails: list[str] = []
    if prior_bundle.get("input_fingerprint") != replay_bundle.get("input_fingerprint"):
        fails.append("REPLAY_INPUT_DRIFT")
    if prior_eval.get("fail_reasons") != replay_eval.get("fail_reasons"):
        fails.append("REPLAY_OUTPUT_DRIFT")
    if not prior_bundle.get("continuity_refs") or not replay_bundle.get("continuity_refs"):
        fails.append("REPLAY_EVIDENCE_INCOMPLETE")
    return (not fails, fails)


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
