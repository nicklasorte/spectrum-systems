"""Deterministic judgment escalation -> enforcement/remediation/closure artifact wiring."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Mapping, Sequence

from spectrum_systems.contracts import validate_artifact


class JudgmentEnforcementError(ValueError):
    """Raised when judgment enforcement artifacts cannot be built or validated."""


_DECISION_ACTION_MAP: dict[str, str] = {
    "allow": "promote_or_continue",
    "warn": "continue_with_warning",
    "freeze": "freeze_pipeline_or_freeze_scope",
    "block": "block_artifact_or_block_progression",
}

_ALLOWED_REMEDIATION_TRANSITIONS: dict[str, set[str]] = {
    "open": {"in_progress", "rejected"},
    "in_progress": {"evidence_submitted", "rejected"},
    "evidence_submitted": {"pending_review", "rejected"},
    "pending_review": {"approved_for_closure", "rejected"},
    "approved_for_closure": {"closed", "rejected"},
    "rejected": {"in_progress"},
    "closed": set(),
}


_REQUIRED_REPLAY_SAFE_CHECKS: tuple[str, ...] = (
    "required_evidence_present",
    "required_enforcement_outcome_present",
    "thresholds_satisfied",
    "source_condition_addressed",
    "policy_version_bound",
)


def _stable_id(prefix: str, payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _require_dict(name: str, value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise JudgmentEnforcementError(f"{name} must be a dict")
    return value


def _remediation_requirements(action_type: str) -> tuple[str, str, list[str]]:
    if action_type == "continue_with_warning":
        return (
            "warning threshold exceeded",
            "judgment_policy_reviewer",
            [
                "judgment_enforcement_outcome_record",
                "judgment_calibration_result",
                "judgment_drift_signal",
            ],
        )
    if action_type == "freeze_pipeline_or_freeze_scope":
        return (
            "freeze decision requires operator release",
            "release_manager",
            [
                "judgment_enforcement_outcome_record",
                "judgment_calibration_result",
                "judgment_error_budget_status",
                "operator_release_approval_record",
            ],
        )
    return (
        "block decision requires governance override",
        "governance_approver",
        [
            "judgment_enforcement_outcome_record",
            "judgment_eval_result",
            "judgment_error_budget_status",
            "governance_override_record",
        ],
    )


def _initial_status_history(*, changed_at: str, changed_by_role: str, rationale: str) -> list[dict[str, str]]:
    return [
        {
            "from_status": "open",
            "to_status": "open",
            "changed_at": changed_at,
            "changed_by_role": changed_by_role,
            "rationale": rationale,
        }
    ]


def transition_judgment_remediation_status(
    remediation_record: dict[str, Any],
    *,
    target_status: str,
    changed_at: str,
    changed_by_role: str,
    rationale: str,
) -> dict[str, Any]:
    """Deterministically transition remediation status with explicit validation and history."""
    _require_dict("remediation_record", remediation_record)
    try:
        validate_artifact(remediation_record, "judgment_operator_remediation_record")
    except Exception as exc:  # pragma: no cover - fail-closed wrapper
        raise JudgmentEnforcementError(f"invalid judgment_operator_remediation_record: {exc}") from exc

    if not isinstance(target_status, str) or not target_status:
        raise JudgmentEnforcementError("target_status must be a non-empty string")
    if target_status not in _ALLOWED_REMEDIATION_TRANSITIONS:
        raise JudgmentEnforcementError(f"unsupported remediation status: {target_status}")

    current_status = remediation_record["status"]
    if target_status == current_status:
        raise JudgmentEnforcementError("status transition must change status")

    allowed = _ALLOWED_REMEDIATION_TRANSITIONS[current_status]
    if target_status not in allowed:
        raise JudgmentEnforcementError(
            f"invalid remediation status transition: {current_status} -> {target_status}"
        )

    updated = copy.deepcopy(remediation_record)
    transition = {
        "from_status": current_status,
        "to_status": target_status,
        "changed_at": changed_at,
        "changed_by_role": changed_by_role,
        "rationale": rationale,
    }
    history = list(updated.get("status_history") or [])
    history.append(transition)
    updated["status"] = target_status
    updated["status_history"] = history

    try:
        validate_artifact(updated, "judgment_operator_remediation_record")
    except Exception as exc:  # pragma: no cover - fail-closed wrapper
        raise JudgmentEnforcementError(f"status transition produced invalid remediation record: {exc}") from exc
    return updated


def evaluate_replay_safe_closure_checks(
    *,
    remediation_record: dict[str, Any],
    escalation_record: dict[str, Any],
    outcome_record: dict[str, Any],
    evidence_artifact_refs: Sequence[str],
    threshold_checks: Mapping[str, bool],
    policy_version: str,
) -> dict[str, Any]:
    """Deterministically evaluate replay-safe closure eligibility checks."""
    _require_dict("remediation_record", remediation_record)
    _require_dict("escalation_record", escalation_record)
    _require_dict("outcome_record", outcome_record)
    if not isinstance(policy_version, str) or not policy_version:
        raise JudgmentEnforcementError("policy_version must be a non-empty string")

    evidence_set = {
        item
        for item in evidence_artifact_refs
        if isinstance(item, str) and item.strip()
    }
    required_evidence = {
        item
        for item in remediation_record.get("required_evidence_artifacts", [])
        if isinstance(item, str) and item.strip()
    }
    missing_required = sorted(required_evidence - evidence_set)
    checks: list[dict[str, Any]] = [
        {
            "check_name": "required_evidence_present",
            "passed": len(missing_required) == 0,
            "details": "all required evidence refs present"
            if not missing_required
            else f"missing required evidence refs: {', '.join(missing_required)}",
        }
    ]

    outcome_present = remediation_record.get("source_outcome_id") == outcome_record.get("outcome_id")
    checks.append(
        {
            "check_name": "required_enforcement_outcome_present",
            "passed": outcome_present,
            "details": "source enforcement outcome present and linked"
            if outcome_present
            else "source enforcement outcome missing or mismatched",
        }
    )

    thresholds_satisfied = all(bool(threshold_checks.get(name, False)) for name in threshold_checks)
    checks.append(
        {
            "check_name": "thresholds_satisfied",
            "passed": thresholds_satisfied,
            "details": "all threshold checks passed"
            if thresholds_satisfied
            else "one or more threshold checks failed",
        }
    )

    source_addressed = bool(threshold_checks.get("source_condition_addressed", False))
    checks.append(
        {
            "check_name": "source_condition_addressed",
            "passed": source_addressed,
            "details": "source freeze/block/warn condition addressed"
            if source_addressed
            else "source freeze/block/warn condition not addressed",
        }
    )

    policy_bound = bool(
        policy_version
        and escalation_record.get("artifact_version")
        and isinstance(escalation_record.get("artifact_version"), str)
    )
    checks.append(
        {
            "check_name": "policy_version_bound",
            "passed": policy_bound,
            "details": "closure decision bound to explicit policy version"
            if policy_bound
            else "policy version binding missing",
        }
    )

    all_passed = all(row["passed"] for row in checks)
    return {
        "all_passed": all_passed,
        "checks": checks,
        "missing_required_evidence_refs": missing_required,
        "policy_version": policy_version,
    }


def build_judgment_remediation_closure_record(
    *,
    remediation_record: dict[str, Any],
    escalation_record: dict[str, Any],
    action_record: dict[str, Any],
    outcome_record: dict[str, Any],
    evidence_artifact_refs: Sequence[str],
    threshold_checks: Mapping[str, bool],
    policy_version: str,
    created_at: str,
    approval_status: str,
    approval_actor_ref: str | None,
    rationale: str,
) -> dict[str, Any]:
    """Build deterministic remediation closure artifact with replay-safe checks."""
    for artifact, schema_name in (
        (remediation_record, "judgment_operator_remediation_record"),
        (escalation_record, "judgment_control_escalation_record"),
        (action_record, "judgment_enforcement_action_record"),
        (outcome_record, "judgment_enforcement_outcome_record"),
    ):
        _require_dict(schema_name, artifact)
        try:
            validate_artifact(artifact, schema_name)
        except Exception as exc:  # pragma: no cover - fail-closed wrapper
            raise JudgmentEnforcementError(f"invalid {schema_name}: {exc}") from exc

    if remediation_record.get("status") != "approved_for_closure":
        raise JudgmentEnforcementError("remediation must be in approved_for_closure before closure can be built")

    check_result = evaluate_replay_safe_closure_checks(
        remediation_record=remediation_record,
        escalation_record=escalation_record,
        outcome_record=outcome_record,
        evidence_artifact_refs=evidence_artifact_refs,
        threshold_checks=threshold_checks,
        policy_version=policy_version,
    )

    missing_checks = [
        name
        for name in _REQUIRED_REPLAY_SAFE_CHECKS
        if not any(row.get("check_name") == name for row in check_result["checks"])
    ]
    if missing_checks:
        raise JudgmentEnforcementError(
            "closure checks incomplete, missing: " + ", ".join(missing_checks)
        )

    decision = "approved" if check_result["all_passed"] and approval_status in {"approved", "not_required"} else "rejected"

    escalation_decision = escalation_record["decision"]
    if decision == "approved" and escalation_decision == "warn":
        resulting_effect = "resume_with_warning"
    elif decision == "approved" and escalation_decision == "allow":
        resulting_effect = "resume_allowed"
    elif escalation_decision == "freeze":
        resulting_effect = "remain_frozen"
    else:
        resulting_effect = "remain_blocked"

    closure_identity = {
        "remediation_id": remediation_record["remediation_id"],
        "source_escalation_record_id": escalation_record["artifact_id"],
        "source_action_id": action_record["action_id"],
        "source_outcome_id": outcome_record["outcome_id"],
        "decision": decision,
        "approval_status": approval_status,
        "policy_version": policy_version,
    }
    closure_id = _stable_id("JRC", closure_identity)

    closure_record = {
        "artifact_type": "judgment_remediation_closure_record",
        "artifact_id": closure_id,
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": "1.0.97",
        "closure_id": closure_id,
        "remediation_id": remediation_record["remediation_id"],
        "source_escalation_record_id": escalation_record["artifact_id"],
        "source_action_id": action_record["action_id"],
        "source_outcome_id": outcome_record["outcome_id"],
        "closure_decision": decision,
        "evidence_artifact_refs_reviewed": sorted(
            item for item in evidence_artifact_refs if isinstance(item, str) and item.strip()
        ),
        "replay_safe_checks": check_result["checks"],
        "approval_status": approval_status,
        "approval_actor_ref": approval_actor_ref or "",
        "resulting_system_effect": resulting_effect,
        "rationale": rationale,
        "trace": {
            "trace_id": remediation_record["trace"]["trace_id"],
            "run_id": remediation_record["trace"]["run_id"],
            "source_escalation_record_id": escalation_record["artifact_id"],
            "action_id": action_record["action_id"],
            "outcome_id": outcome_record["outcome_id"],
            "remediation_id": remediation_record["remediation_id"],
        },
        "policy_version": policy_version,
        "created_at": created_at,
    }
    try:
        validate_artifact(closure_record, "judgment_remediation_closure_record")
    except Exception as exc:  # pragma: no cover - fail-closed wrapper
        raise JudgmentEnforcementError(f"invalid judgment_remediation_closure_record: {exc}") from exc
    return closure_record


def build_judgment_progression_reinstatement_record(
    *,
    closure_record: dict[str, Any],
    affected_scope: dict[str, str],
    reinstatement_type: str,
    required_gates_satisfied: list[str],
    approved_by_role: str,
    approved_at: str,
    resulting_next_allowed_state: str,
) -> dict[str, Any]:
    """Build deterministic reinstatement artifact authorizing resumed progression."""
    _require_dict("closure_record", closure_record)
    try:
        validate_artifact(closure_record, "judgment_remediation_closure_record")
    except Exception as exc:  # pragma: no cover
        raise JudgmentEnforcementError(f"invalid judgment_remediation_closure_record: {exc}") from exc

    if closure_record["closure_decision"] != "approved":
        raise JudgmentEnforcementError("reinstatement requires approved closure decision")

    if reinstatement_type not in {"unblock", "unfreeze", "warning_acknowledged_continue"}:
        raise JudgmentEnforcementError(f"unsupported reinstatement_type: {reinstatement_type}")

    if not isinstance(affected_scope, dict):
        raise JudgmentEnforcementError("affected_scope must be a dict")

    reinstatement_identity = {
        "closure_id": closure_record["closure_id"],
        "reinstatement_type": reinstatement_type,
        "approved_by_role": approved_by_role,
        "resulting_next_allowed_state": resulting_next_allowed_state,
        "affected_scope": affected_scope,
    }
    reinstatement_id = _stable_id("JPR", reinstatement_identity)
    record = {
        "artifact_type": "judgment_progression_reinstatement_record",
        "artifact_id": reinstatement_id,
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": "1.0.97",
        "reinstatement_id": reinstatement_id,
        "source_closure_id": closure_record["closure_id"],
        "affected_scope": affected_scope,
        "reinstatement_type": reinstatement_type,
        "required_gates_satisfied": sorted(set(required_gates_satisfied)),
        "approved_by_role": approved_by_role,
        "approved_at": approved_at,
        "resulting_next_allowed_state": resulting_next_allowed_state,
        "trace": {
            "trace_id": closure_record["trace"]["trace_id"],
            "run_id": closure_record["trace"]["run_id"],
            "closure_id": closure_record["closure_id"],
            "remediation_id": closure_record["remediation_id"],
        },
    }
    try:
        validate_artifact(record, "judgment_progression_reinstatement_record")
    except Exception as exc:  # pragma: no cover
        raise JudgmentEnforcementError(f"invalid judgment_progression_reinstatement_record: {exc}") from exc
    return record


def build_judgment_enforcement_artifacts(
    escalation_record: dict[str, Any],
    *,
    created_at: str,
) -> dict[str, Any]:
    """Emit deterministic action/outcome/remediation artifacts from escalation decisions."""
    _require_dict("escalation_record", escalation_record)
    try:
        validate_artifact(escalation_record, "judgment_control_escalation_record")
    except Exception as exc:  # pragma: no cover - fail-closed wrapper
        raise JudgmentEnforcementError(f"invalid judgment_control_escalation_record: {exc}") from exc

    decision = escalation_record["decision"]
    action_type = _DECISION_ACTION_MAP.get(decision)
    if action_type is None:
        raise JudgmentEnforcementError(f"unsupported escalation decision: {decision}")

    trace = escalation_record["trace"]
    trace_id = trace["trace_id"]
    run_id = trace["run_id"]

    action_identity = {
        "escalation_id": escalation_record["artifact_id"],
        "decision": decision,
        "action_type": action_type,
        "trace_id": trace_id,
        "run_id": run_id,
    }
    action_id = _stable_id("JEA", action_identity)

    action_record = {
        "artifact_type": "judgment_enforcement_action_record",
        "artifact_id": action_id,
        "artifact_version": "1.1.0",
        "schema_version": "1.1.0",
        "standards_version": "1.0.97",
        "action_id": action_id,
        "source_escalation_record_id": escalation_record["artifact_id"],
        "decision": decision,
        "action_type": action_type,
        "target_scope": "judgment_run",
        "target_identifiers": {
            "run_id": run_id,
            "trace_id": trace_id,
            "judgment_eval_result_id": trace["judgment_eval_result_id"],
            "judgment_drift_signal_id": trace["judgment_drift_signal_id"],
        },
        "execution_status": "completed",
        "requested_at": created_at,
        "started_at": created_at,
        "completed_at": created_at,
        "trace": {
            "trace_id": trace_id,
            "run_id": run_id,
            "source_escalation_record_id": escalation_record["artifact_id"],
        },
        "policy_refs": {
            "judgment_policy_id": trace["judgment_policy_id"],
            "judgment_policy_version": trace["judgment_policy_version"],
            "policy_lifecycle_status": trace["policy_lifecycle_status"],
            "policy_rollout_id": trace["policy_rollout_id"],
            "threshold_snapshot": escalation_record["thresholds_used"],
        },
    }
    try:
        validate_artifact(action_record, "judgment_enforcement_action_record")
    except Exception as exc:  # pragma: no cover
        raise JudgmentEnforcementError(f"invalid judgment_enforcement_action_record: {exc}") from exc

    progression = {
        "allow": "allowed",
        "warn": "allowed_with_warning",
        "freeze": "frozen",
        "block": "prevented",
    }[decision]

    operator_action_required = decision in {"freeze", "block"}
    if decision == "warn" and escalation_record["triggering_signals"].get("calibration") != "healthy":
        operator_action_required = True

    outcome_identity = {
        "action_id": action_id,
        "progression": progression,
        "operator_action_required": operator_action_required,
    }
    outcome_id = _stable_id("JEO", outcome_identity)

    outcome_record = {
        "artifact_type": "judgment_enforcement_outcome_record",
        "artifact_id": outcome_id,
        "artifact_version": "1.1.0",
        "schema_version": "1.1.0",
        "standards_version": "1.0.97",
        "outcome_id": outcome_id,
        "action_id": action_id,
        "final_outcome_status": "enforced",
        "progression_status": progression,
        "resulting_artifact_refs": [action_id],
        "failure_reason": "",
        "operator_action_required": operator_action_required,
        "trace": {
            "trace_id": trace_id,
            "run_id": run_id,
            "source_escalation_record_id": escalation_record["artifact_id"],
            "action_id": action_id,
            "judgment_policy_id": trace["judgment_policy_id"],
            "judgment_policy_version": trace["judgment_policy_version"],
            "policy_lifecycle_status": trace["policy_lifecycle_status"],
            "policy_rollout_id": trace["policy_rollout_id"],
        },
    }
    try:
        validate_artifact(outcome_record, "judgment_enforcement_outcome_record")
    except Exception as exc:  # pragma: no cover
        raise JudgmentEnforcementError(f"invalid judgment_enforcement_outcome_record: {exc}") from exc

    remediation_record: dict[str, Any] | None = None
    if operator_action_required:
        reason, role, required_artifacts = _remediation_requirements(action_type)
        remediation_identity = {
            "source_escalation_record_id": escalation_record["artifact_id"],
            "action_id": action_id,
            "reason": reason,
            "role": role,
        }
        remediation_id = _stable_id("JOR", remediation_identity)
        remediation_record = {
            "artifact_type": "judgment_operator_remediation_record",
            "artifact_id": remediation_id,
            "artifact_version": "1.1.0",
            "schema_version": "1.1.0",
            "standards_version": "1.0.97",
            "remediation_id": remediation_id,
            "source_escalation_record_id": escalation_record["artifact_id"],
            "source_action_id": action_id,
            "source_outcome_id": outcome_id,
            "remediation_reason": reason,
            "required_human_role": role,
            "required_evidence_artifacts": required_artifacts,
            "status": "open",
            "status_history": _initial_status_history(
                changed_at=created_at,
                changed_by_role="control_plane",
                rationale="remediation opened from deterministic enforcement outcome",
            ),
            "trace": {
                "trace_id": trace_id,
                "run_id": run_id,
                "source_escalation_record_id": escalation_record["artifact_id"],
                "action_id": action_id,
                "outcome_id": outcome_id,
            },
            "created_at": created_at,
        }
        try:
            validate_artifact(remediation_record, "judgment_operator_remediation_record")
        except Exception as exc:  # pragma: no cover
            raise JudgmentEnforcementError(f"invalid judgment_operator_remediation_record: {exc}") from exc

    traceability = evaluate_judgment_enforcement_traceability(
        escalation_record=escalation_record,
        action_record=action_record,
        outcome_record=outcome_record,
        remediation_record=remediation_record,
    )

    return {
        "judgment_enforcement_action_record": action_record,
        "judgment_enforcement_outcome_record": outcome_record,
        "judgment_operator_remediation_record": remediation_record,
        "progression_allowed": traceability["progression_allowed"],
        "blocking_reasons": traceability["blocking_reasons"],
    }


def evaluate_judgment_enforcement_traceability(
    *,
    escalation_record: dict[str, Any] | None,
    action_record: dict[str, Any] | None,
    outcome_record: dict[str, Any] | None,
    remediation_record: dict[str, Any] | None,
    closure_record: dict[str, Any] | None = None,
    reinstatement_record: dict[str, Any] | None = None,
    evidence_artifact_refs: Sequence[str] | None = None,
    threshold_checks: Mapping[str, bool] | None = None,
    policy_version: str | None = None,
) -> dict[str, Any]:
    """Fail-closed progression gate for escalation->action->outcome->remediation->closure->reinstatement."""
    blocking_reasons: list[str] = []

    if not isinstance(escalation_record, dict):
        return {
            "progression_allowed": False,
            "blocking_reasons": ["missing escalation artifact"],
        }
    try:
        validate_artifact(escalation_record, "judgment_control_escalation_record")
    except Exception:
        return {
            "progression_allowed": False,
            "blocking_reasons": ["invalid escalation artifact"],
        }

    decision = escalation_record["decision"]
    if not isinstance(action_record, dict):
        blocking_reasons.append("missing enforcement action artifact")
    else:
        try:
            validate_artifact(action_record, "judgment_enforcement_action_record")
        except Exception:
            blocking_reasons.append("invalid enforcement action artifact")

    outcome_required = decision in {"allow", "warn", "freeze", "block"}
    if outcome_required and not isinstance(outcome_record, dict):
        blocking_reasons.append("missing enforcement outcome artifact")
    elif isinstance(outcome_record, dict):
        try:
            validate_artifact(outcome_record, "judgment_enforcement_outcome_record")
        except Exception:
            blocking_reasons.append("invalid enforcement outcome artifact")

    remediation_required = decision in {"freeze", "block"}
    if decision == "warn" and isinstance(outcome_record, dict) and outcome_record.get("operator_action_required") is True:
        remediation_required = True

    if remediation_required and not isinstance(remediation_record, dict):
        blocking_reasons.append("missing required remediation artifact")
    elif isinstance(remediation_record, dict):
        try:
            validate_artifact(remediation_record, "judgment_operator_remediation_record")
        except Exception:
            blocking_reasons.append("invalid remediation artifact")

    reinstatement_required = False
    if remediation_required:
        if not isinstance(remediation_record, dict):
            return {
                "progression_allowed": False,
                "blocking_reasons": sorted(set(blocking_reasons)),
            }
        if remediation_record.get("status") != "closed":
            blocking_reasons.append("remediation not closed")
        if not isinstance(closure_record, dict):
            blocking_reasons.append("missing remediation closure artifact")
        else:
            try:
                validate_artifact(closure_record, "judgment_remediation_closure_record")
            except Exception:
                blocking_reasons.append("invalid remediation closure artifact")
            else:
                if closure_record.get("remediation_id") != remediation_record.get("remediation_id"):
                    blocking_reasons.append("closure artifact remediation linkage mismatch")
                if closure_record.get("closure_decision") != "approved":
                    blocking_reasons.append("remediation closure not approved")
                closure_checks = closure_record.get("replay_safe_checks")
                if not isinstance(closure_checks, list) or not closure_checks:
                    blocking_reasons.append("missing replay-safe closure checks")
                else:
                    evidence_refs = evidence_artifact_refs or ()
                    threshold_map = dict(threshold_checks or {})
                    if policy_version:
                        computed = evaluate_replay_safe_closure_checks(
                            remediation_record=remediation_record,
                            escalation_record=escalation_record,
                            outcome_record=outcome_record if isinstance(outcome_record, dict) else {},
                            evidence_artifact_refs=evidence_refs,
                            threshold_checks=threshold_map,
                            policy_version=policy_version,
                        )
                        for expected in computed["checks"]:
                            matched = next(
                                (
                                    row
                                    for row in closure_checks
                                    if isinstance(row, dict)
                                    and row.get("check_name") == expected["check_name"]
                                ),
                                None,
                            )
                            if not isinstance(matched, dict) or bool(matched.get("passed")) != bool(expected["passed"]):
                                blocking_reasons.append("replay-safe closure proof mismatch")
                                break
        if decision in {"freeze", "block"} or (decision == "warn" and remediation_required):
            reinstatement_required = True

    if reinstatement_required:
        if not isinstance(reinstatement_record, dict):
            blocking_reasons.append("missing progression reinstatement artifact")
        else:
            try:
                validate_artifact(reinstatement_record, "judgment_progression_reinstatement_record")
            except Exception:
                blocking_reasons.append("invalid progression reinstatement artifact")
            else:
                if isinstance(closure_record, dict) and reinstatement_record.get("source_closure_id") != closure_record.get("closure_id"):
                    blocking_reasons.append("reinstatement artifact closure linkage mismatch")
                expected_type = {
                    "freeze": "unfreeze",
                    "block": "unblock",
                    "warn": "warning_acknowledged_continue",
                }[decision]
                if reinstatement_record.get("reinstatement_type") != expected_type:
                    blocking_reasons.append("invalid reinstatement type for decision")

    progression_allowed = len(blocking_reasons) == 0 and (
        decision == "allow"
        or (decision == "warn" and not remediation_required)
        or (reinstatement_required and isinstance(reinstatement_record, dict))
    )
    return {
        "progression_allowed": progression_allowed,
        "blocking_reasons": sorted(set(blocking_reasons)),
    }
