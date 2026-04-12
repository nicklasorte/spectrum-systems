"""SEL bounded enforcement foundation (SEL-01..SEL-08 + RT hardening).

SEL consumes governed CDE decision artifacts and evidence bundles only,
and emits bounded enforcement artifacts only.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

from spectrum_systems.contracts import validate_artifact


class SELEnforcementError(ValueError):
    """Raised when SEL boundary rules fail closed."""


_ALLOWED_ACTIONS = {
    "continue_repair_path",
    "quarantine",
    "require_human_review",
    "halt",
    "none",
}

_ALLOWED_UPSTREAM_TYPES = {
    "continuation_decision_record",
    "decision_bundle",
    "decision_evidence_pack",
}

_DECISION_ACTION_MAP = {
    "continue_repair_bounded": "continue_repair_path",
    "human_review_required": "require_human_review",
    "block": "halt",
}


def _digest(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def _required_str(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SELEnforcementError(f"{field} must be a non-empty string")
    return value.strip()


def _clean_refs(values: Any, *, field: str, min_items: int = 1) -> list[str]:
    if not isinstance(values, list):
        raise SELEnforcementError(f"{field} must be a list")
    refs = sorted({str(v).strip() for v in values if isinstance(v, str) and v.strip()})
    if len(refs) < min_items:
        raise SELEnforcementError(f"{field} must include at least {min_items} refs")
    return refs


def verify_sel_boundary_inputs(*, decision_record: Mapping[str, Any], decision_bundle: Mapping[str, Any], evidence_bundle: Mapping[str, Any]) -> None:
    validate_artifact(dict(decision_record), "continuation_decision_record")
    validate_artifact(dict(decision_bundle), "decision_bundle")

    artifact_type = _required_str(evidence_bundle.get("artifact_type"), field="artifact_type")
    if artifact_type not in _ALLOWED_UPSTREAM_TYPES:
        raise SELEnforcementError("SEL upstream boundary rejected non-governed artifact")
    if "decision_outcome" in evidence_bundle and artifact_type != "continuation_decision_record":
        raise SELEnforcementError("SEL fail-closed: mixed decision payloads are not allowed in evidence_bundle")


def build_enforcement_action_record(
    *,
    decision_record: Mapping[str, Any],
    decision_bundle: Mapping[str, Any],
    evidence_refs: Sequence[str],
    requested_action: str | None = None,
) -> dict[str, Any]:
    validate_artifact(dict(decision_record), "continuation_decision_record")
    validate_artifact(dict(decision_bundle), "decision_bundle")

    expected = _DECISION_ACTION_MAP.get(decision_record["decision_outcome"], "none")
    action = (requested_action or expected).strip()
    if action not in _ALLOWED_ACTIONS:
        raise SELEnforcementError("requested_action must be one of bounded SEL actions")

    record = {
        "artifact_type": "enforcement_action_record",
        "schema_version": "1.0.0",
        "action_id": f"sel-act-{_digest([decision_record['decision_id'], action, list(evidence_refs)])[:16]}",
        "trace_id": decision_record["trace_id"],
        "continuation_decision_record_ref": f"continuation_decision_record:{decision_record['decision_id']}",
        "decision_bundle_ref": f"decision_bundle:{decision_bundle['bundle_id']}",
        "action": action,
        "action_reason_codes": sorted(set(decision_record.get("reason_codes", []))),
        "evidence_refs": _clean_refs(list(evidence_refs), field="evidence_refs"),
        "non_authority_assertions": [
            "sel_enforcement_only",
            "sel_must_not_reinterpret_cde",
            "sel_must_not_issue_new_decisions",
        ],
    }
    validate_artifact(record, "enforcement_action_record")
    return record


def evaluate_enforcement_action(
    *,
    decision_record: Mapping[str, Any],
    action_record: Mapping[str, Any],
    evidence_bundle: Mapping[str, Any],
) -> dict[str, Any]:
    validate_artifact(dict(decision_record), "continuation_decision_record")
    validate_artifact(dict(action_record), "enforcement_action_record")

    fail_reasons: list[str] = []
    expected_action = _DECISION_ACTION_MAP.get(decision_record["decision_outcome"], "none")

    if action_record.get("action") != expected_action:
        fail_reasons.append("decision_action_mismatch")
    if len(action_record.get("evidence_refs", [])) < 1:
        fail_reasons.append("evidence_incomplete")
    if not str(action_record.get("decision_bundle_ref", "")).startswith("decision_bundle:"):
        fail_reasons.append("scope_compliance_failed")
    if not str(evidence_bundle.get("artifact_type", "")).startswith("decision_") and evidence_bundle.get("artifact_type") != "continuation_decision_record":
        fail_reasons.append("policy_compliance_failed")
    if "sel_must_not_issue_new_decisions" not in action_record.get("non_authority_assertions", []):
        fail_reasons.append("non_decision_assertion_missing")

    result = {
        "artifact_type": "enforcement_eval_result",
        "schema_version": "1.0.0",
        "eval_id": f"sel-eval-{_digest([action_record['action_id'], fail_reasons])[:16]}",
        "trace_id": decision_record["trace_id"],
        "enforcement_action_record_ref": f"enforcement_action_record:{action_record['action_id']}",
        "scope_compliance_passed": "scope_compliance_failed" not in fail_reasons,
        "decision_alignment_passed": "decision_action_mismatch" not in fail_reasons,
        "policy_compliance_passed": "policy_compliance_failed" not in fail_reasons,
        "evidence_completeness_passed": "evidence_incomplete" not in fail_reasons,
        "non_decision_assertion_passed": "non_decision_assertion_missing" not in fail_reasons,
        "result": "pass" if not fail_reasons else "fail",
        "fail_reasons": sorted(set(fail_reasons)),
    }
    validate_artifact(result, "enforcement_eval_result")
    return result


def build_enforcement_readiness(
    *,
    decision_record: Mapping[str, Any],
    action_record: Mapping[str, Any],
    eval_result: Mapping[str, Any],
) -> dict[str, Any]:
    validate_artifact(dict(decision_record), "continuation_decision_record")
    validate_artifact(dict(action_record), "enforcement_action_record")
    validate_artifact(dict(eval_result), "enforcement_eval_result")

    blocking_reasons: list[str] = []
    if eval_result.get("result") != "pass":
        blocking_reasons.append("enforcement_eval_not_pass")
    if action_record.get("action") == "none":
        blocking_reasons.append("no_op_not_ready")

    readiness = {
        "artifact_type": "enforcement_readiness_record",
        "schema_version": "1.0.0",
        "readiness_id": f"sel-ready-{_digest([action_record['action_id'], eval_result['eval_id'], blocking_reasons])[:16]}",
        "trace_id": decision_record["trace_id"],
        "enforcement_action_record_ref": f"enforcement_action_record:{action_record['action_id']}",
        "enforcement_eval_result_ref": f"enforcement_eval_result:{eval_result['eval_id']}",
        "candidate_ready": len(blocking_reasons) == 0,
        "blocking_reasons": sorted(set(blocking_reasons)),
        "non_authority_assertions": [
            "candidate_only",
            "cannot_create_new_decision_authority",
            "promotion_requires_separate_gate",
        ],
    }
    validate_artifact(readiness, "enforcement_readiness_record")
    return readiness


def build_enforcement_conflict_record(*, decision_record: Mapping[str, Any], action_record: Mapping[str, Any], eval_result: Mapping[str, Any]) -> dict[str, Any]:
    validate_artifact(dict(decision_record), "continuation_decision_record")
    validate_artifact(dict(action_record), "enforcement_action_record")
    validate_artifact(dict(eval_result), "enforcement_eval_result")

    expected_action = _DECISION_ACTION_MAP.get(decision_record["decision_outcome"], "none")
    conflict_refs: list[str] = []
    if action_record["action"] != expected_action:
        conflict_refs.append("decision_action_mismatch")
    if eval_result["result"] != "pass":
        conflict_refs.extend(eval_result.get("fail_reasons", []))

    record = {
        "artifact_type": "enforcement_conflict_record",
        "schema_version": "1.0.0",
        "conflict_id": f"sel-conf-{_digest([decision_record['decision_id'], action_record['action_id'], conflict_refs])[:16]}",
        "trace_id": decision_record["trace_id"],
        "continuation_decision_record_ref": f"continuation_decision_record:{decision_record['decision_id']}",
        "enforcement_action_record_ref": f"enforcement_action_record:{action_record['action_id']}",
        "conflict_refs": sorted(set(conflict_refs)),
        "integrity_passed": len(conflict_refs) == 0,
        "result": "pass" if len(conflict_refs) == 0 else "fail",
    }
    validate_artifact(record, "enforcement_conflict_record")
    return record


def build_enforcement_result_record(
    *,
    decision_record: Mapping[str, Any],
    action_record: Mapping[str, Any],
    eval_result: Mapping[str, Any],
    readiness_record: Mapping[str, Any],
    conflict_record: Mapping[str, Any],
) -> dict[str, Any]:
    validate_artifact(dict(decision_record), "continuation_decision_record")
    validate_artifact(dict(action_record), "enforcement_action_record")
    validate_artifact(dict(eval_result), "enforcement_eval_result")
    validate_artifact(dict(readiness_record), "enforcement_readiness_record")
    validate_artifact(dict(conflict_record), "enforcement_conflict_record")

    blocked = eval_result["result"] != "pass" or conflict_record["result"] != "pass" or not readiness_record["candidate_ready"]
    result_record = {
        "artifact_type": "enforcement_result_record",
        "schema_version": "1.0.0",
        "result_id": f"sel-res-{_digest([action_record['action_id'], eval_result['eval_id'], conflict_record['conflict_id']])[:16]}",
        "trace_id": decision_record["trace_id"],
        "enforcement_action_record_ref": f"enforcement_action_record:{action_record['action_id']}",
        "enforcement_eval_result_ref": f"enforcement_eval_result:{eval_result['eval_id']}",
        "enforcement_readiness_record_ref": f"enforcement_readiness_record:{readiness_record['readiness_id']}",
        "enforcement_conflict_record_ref": f"enforcement_conflict_record:{conflict_record['conflict_id']}",
        "enforcement_status": "blocked" if blocked else "enforced",
        "reason_codes": sorted(set(eval_result.get("fail_reasons", []) + conflict_record.get("conflict_refs", []) + (["candidate_not_ready"] if not readiness_record["candidate_ready"] else []))),
    }
    validate_artifact(result_record, "enforcement_result_record")
    return result_record


def build_enforcement_bundle(
    *,
    action_record: Mapping[str, Any],
    result_record: Mapping[str, Any],
    eval_result: Mapping[str, Any],
    readiness_record: Mapping[str, Any],
    conflict_record: Mapping[str, Any],
) -> dict[str, Any]:
    validate_artifact(dict(action_record), "enforcement_action_record")
    validate_artifact(dict(result_record), "enforcement_result_record")
    validate_artifact(dict(eval_result), "enforcement_eval_result")
    validate_artifact(dict(readiness_record), "enforcement_readiness_record")
    validate_artifact(dict(conflict_record), "enforcement_conflict_record")

    bundle = {
        "artifact_type": "enforcement_bundle",
        "schema_version": "1.0.0",
        "bundle_id": f"sel-bundle-{_digest([action_record['action_id'], result_record['result_id'], eval_result['eval_id']])[:16]}",
        "trace_id": action_record["trace_id"],
        "enforcement_action_record_ref": f"enforcement_action_record:{action_record['action_id']}",
        "enforcement_result_record_ref": f"enforcement_result_record:{result_record['result_id']}",
        "enforcement_eval_result_ref": f"enforcement_eval_result:{eval_result['eval_id']}",
        "enforcement_readiness_record_ref": f"enforcement_readiness_record:{readiness_record['readiness_id']}",
        "enforcement_conflict_record_ref": f"enforcement_conflict_record:{conflict_record['conflict_id']}",
        "lineage_complete": True,
    }
    validate_artifact(bundle, "enforcement_bundle")
    return bundle


def validate_enforcement_replay(*, decision_record: Mapping[str, Any], action_record: Mapping[str, Any], first_result: Mapping[str, Any], replay_result: Mapping[str, Any], evidence_refs: Sequence[str]) -> dict[str, Any]:
    validate_artifact(dict(decision_record), "continuation_decision_record")
    validate_artifact(dict(action_record), "enforcement_action_record")
    validate_artifact(dict(first_result), "enforcement_result_record")
    validate_artifact(dict(replay_result), "enforcement_result_record")

    refs = _clean_refs(list(evidence_refs), field="evidence_refs")
    first_fp = _digest(first_result)
    replay_fp = _digest(replay_result)
    deterministic_match = first_fp == replay_fp

    record = {
        "artifact_type": "enforcement_conflict_record",
        "schema_version": "1.0.0",
        "conflict_id": f"sel-conf-{_digest([decision_record['decision_id'], action_record['action_id'], refs, first_fp, replay_fp])[:16]}",
        "trace_id": decision_record["trace_id"],
        "continuation_decision_record_ref": f"continuation_decision_record:{decision_record['decision_id']}",
        "enforcement_action_record_ref": f"enforcement_action_record:{action_record['action_id']}",
        "conflict_refs": [] if deterministic_match else ["enforcement_replay_mismatch"],
        "integrity_passed": deterministic_match,
        "result": "pass" if deterministic_match else "fail",
    }
    validate_artifact(record, "enforcement_conflict_record")
    return record


def build_enforcement_effectiveness_record(*, decision_record: Mapping[str, Any], action_record: Mapping[str, Any], result_record: Mapping[str, Any], observed_outcome: str, observed_outcome_ref: str) -> dict[str, Any]:
    validate_artifact(dict(decision_record), "continuation_decision_record")
    validate_artifact(dict(action_record), "enforcement_action_record")
    validate_artifact(dict(result_record), "enforcement_result_record")

    outcome = _required_str(observed_outcome, field="observed_outcome")
    mapping = {
        ("continue_repair_path", "improved"): ("effective", True),
        ("halt", "contained"): ("effective", True),
        ("require_human_review", "awaiting_review"): ("pending", False),
        ("none", "unchanged"): ("ineffective", False),
    }
    state, success = mapping.get((action_record["action"], outcome), ("ineffective", False))

    record = {
        "artifact_type": "enforcement_effectiveness_record",
        "schema_version": "1.0.0",
        "record_id": f"sel-eff-{_digest([decision_record['decision_id'], action_record['action_id'], result_record['result_id'], outcome])[:16]}",
        "trace_id": decision_record["trace_id"],
        "continuation_decision_record_ref": f"continuation_decision_record:{decision_record['decision_id']}",
        "enforcement_action_record_ref": f"enforcement_action_record:{action_record['action_id']}",
        "enforcement_result_record_ref": f"enforcement_result_record:{result_record['result_id']}",
        "observed_outcome_ref": _required_str(observed_outcome_ref, field="observed_outcome_ref"),
        "effectiveness_state": state,
        "success": success,
    }
    validate_artifact(record, "enforcement_effectiveness_record")
    return record
