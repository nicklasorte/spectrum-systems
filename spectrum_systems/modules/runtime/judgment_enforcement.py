"""Deterministic judgment escalation -> enforcement artifact wiring."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from spectrum_systems.contracts import validate_artifact


class JudgmentEnforcementError(ValueError):
    """Raised when judgment enforcement artifacts cannot be built or validated."""


_DECISION_ACTION_MAP: dict[str, str] = {
    "allow": "promote_or_continue",
    "warn": "continue_with_warning",
    "freeze": "freeze_pipeline_or_freeze_scope",
    "block": "block_artifact_or_block_progression",
}


def _stable_id(prefix: str, payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


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


def build_judgment_enforcement_artifacts(
    escalation_record: dict[str, Any],
    *,
    created_at: str,
) -> dict[str, Any]:
    """Emit deterministic action/outcome/remediation artifacts from escalation decisions."""
    if not isinstance(escalation_record, dict):
        raise JudgmentEnforcementError("escalation_record must be a dict")
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
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": "1.0.96",
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
            "judgment_policy_version": escalation_record["artifact_version"],
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
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": "1.0.96",
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
            "artifact_version": "1.0.0",
            "schema_version": "1.0.0",
            "standards_version": "1.0.96",
            "remediation_id": remediation_id,
            "source_escalation_record_id": escalation_record["artifact_id"],
            "source_action_id": action_id,
            "source_outcome_id": outcome_id,
            "remediation_reason": reason,
            "required_human_role": role,
            "required_evidence_artifacts": required_artifacts,
            "status": "open",
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
) -> dict[str, Any]:
    """Fail-closed progression gate for escalation -> action -> outcome -> remediation trace."""
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

    progression_allowed = len(blocking_reasons) == 0 and decision in {"allow", "warn"} and not remediation_required
    return {
        "progression_allowed": progression_allowed,
        "blocking_reasons": blocking_reasons,
    }
