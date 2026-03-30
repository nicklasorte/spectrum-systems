"""Deterministic judgment policy + precedent + application engine for autonomous cycle control."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.judgment_eval_runner import run_judgment_evals
from spectrum_systems.modules.runtime.judgment_policy_lifecycle import (
    JudgmentPolicyLifecycleError,
    is_trace_in_canary_cohort,
)


class JudgmentEngineError(ValueError):
    """Raised when judgment policy selection or application cannot complete fail-closed."""


def _load_json(path: str) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise JudgmentEngineError(f"expected object artifact: {path}")
    return payload


def _semver_key(version: str) -> tuple[int, int, int]:
    parts = version.split(".")
    if len(parts) != 3 or any(not p.isdigit() for p in parts):
        raise JudgmentEngineError(f"invalid semantic version: {version}")
    return int(parts[0]), int(parts[1]), int(parts[2])


def select_policy(
    *,
    policy_paths: list[str],
    judgment_type: str,
    scope: str,
    environment: str,
    trace_id: str | None = None,
    lifecycle_records: list[dict[str, Any]] | None = None,
    rollout_records: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    if not policy_paths:
        raise JudgmentEngineError("no judgment policies configured")

    strict_lifecycle = lifecycle_records is not None
    strict_rollout = rollout_records is not None
    lifecycle_records = [dict(item) for item in (lifecycle_records or []) if isinstance(item, dict)]
    rollout_records = [dict(item) for item in (rollout_records or []) if isinstance(item, dict)]

    loaded: list[tuple[str, dict[str, Any]]] = []
    for path in sorted(policy_paths):
        policy = _load_json(path)
        validate_artifact(policy, "judgment_policy")
        loaded.append((path, policy))

    def _has_lifecycle_record(policy: dict[str, Any]) -> bool:
        if not strict_lifecycle:
            return True
        pid = policy["artifact_id"]
        version = policy["artifact_version"]
        status = policy["status"]
        expected_action = {
            "draft": "create_draft",
            "canary": "enter_canary",
            "active": "promote_active",
            "deprecated": "deprecate",
            "revoked": "revoke",
        }.get(status)
        if expected_action is None:
            return False
        return any(
            rec.get("policy_id") == pid
            and rec.get("to_version") == version
            and rec.get("lifecycle_action") == expected_action
            and rec.get("resulting_status") == status
            for rec in lifecycle_records
        )

    def _canary_rollout_allows(policy: dict[str, Any]) -> bool:
        if policy["status"] != "canary":
            return True
        matching_rollouts = [
            rec for rec in rollout_records
            if rec.get("policy_id") == policy["artifact_id"]
            and rec.get("policy_version") == policy["artifact_version"]
            and rec.get("rollout_type") == "canary"
            and rec.get("rollout_status") == "active"
        ]
        if not matching_rollouts:
            return False
        if trace_id is None:
            return False
        for rollout in sorted(matching_rollouts, key=lambda rec: str(rec.get("artifact_id") or "")):
            try:
                if is_trace_in_canary_cohort(trace_id=trace_id, cohort=rollout.get("cohort", {}), environment=environment):
                    return True
            except JudgmentPolicyLifecycleError:
                continue
        return False

    matched = []
    for path, policy in loaded:
        if policy["judgment_type"] != judgment_type or policy["scope"] != scope or environment not in policy["environments"]:
            continue
        if policy["status"] in {"deprecated", "revoked"}:
            continue
        if policy["status"] not in {"active", "canary"}:
            continue
        if strict_lifecycle and not _has_lifecycle_record(policy):
            continue
        if not _canary_rollout_allows(policy):
            continue
        matched.append((path, policy))

    if not matched:
        if strict_lifecycle or strict_rollout:
            raise JudgmentEngineError("no applicable governed judgment policy found for type/scope/environment")
        raise JudgmentEngineError("no applicable judgment policy found for type/scope/environment")

    status_rank = {"active": 0, "canary": 1}
    matched.sort(key=lambda item: (status_rank[item[1]["status"]], tuple(-x for x in _semver_key(item[1]["artifact_version"])), item[1]["artifact_id"]))
    selected_path, selected = matched[0]
    return selected | {"_path": selected_path}, [path for path, _ in matched]


def _read_value(context: dict[str, Any], field: str) -> Any:
    if field not in context:
        raise JudgmentEngineError(f"missing required policy input: {field}")
    return context[field]


def _match_condition(context: dict[str, Any], condition: dict[str, Any]) -> bool:
    lhs = _read_value(context, condition["field"])
    op = condition["operator"]
    rhs = condition["value"]
    if op == "eq":
        return lhs == rhs
    if op == "gte":
        return isinstance(lhs, (int, float)) and lhs >= rhs
    if op == "lte":
        return isinstance(lhs, (int, float)) and lhs <= rhs
    if op == "in":
        return lhs in rhs if isinstance(rhs, list) else False
    raise JudgmentEngineError(f"unsupported operator: {op}")


def _select_rule(context: dict[str, Any], rules: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    ordered = sorted(rules, key=lambda r: (r["priority"], r["rule_id"]))
    matched: list[dict[str, Any]] = []
    for rule in ordered:
        conditions = rule.get("all_conditions", [])
        if all(_match_condition(context, condition) for condition in conditions):
            matched.append(rule)
    if not matched:
        raise JudgmentEngineError("no policy rule matched inputs")
    return matched[0], matched


def retrieve_precedents(*, precedent_paths: list[str], retrieval: dict[str, Any], query_context: dict[str, Any]) -> list[dict[str, Any]]:
    for field in retrieval["query_fields"]:
        if field not in query_context:
            raise JudgmentEngineError(f"missing required precedent retrieval input: {field}")

    scored: list[tuple[float, str, list[str]]] = []
    for path in sorted(precedent_paths):
        try:
            record = _load_json(path)
            validate_artifact(record, "judgment_record")
        except Exception:
            continue
        matched_basis: list[str] = []
        for field in retrieval["query_fields"]:
            precedent_value = record.get("context_fingerprint", {}).get(field)
            if precedent_value == query_context[field]:
                matched_basis.append(field)
        score = len(matched_basis) / float(len(retrieval["query_fields"]))
        if score >= retrieval["threshold"]:
            scored.append((score, path, matched_basis))

    scored.sort(key=lambda item: (-item[0], item[1]))
    top = scored[: retrieval["top_k"]]
    return [{"record_ref": path, "score": score, "basis": basis} for score, path, basis in top]


def run_judgment(
    *,
    cycle_id: str,
    judgment_type: str,
    scope: str,
    environment: str,
    policy_paths: list[str],
    context: dict[str, Any],
    evidence_refs: list[str],
    precedent_paths: list[str],
    created_at: str,
    replay_reference: dict[str, Any] | None = None,
    replay_reference_source: str | None = None,
    trace_id: str | None = None,
    lifecycle_records: list[dict[str, Any]] | None = None,
    rollout_records: list[dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    selected_policy, matched_paths = select_policy(
        policy_paths=policy_paths,
        judgment_type=judgment_type,
        scope=scope,
        environment=environment,
        trace_id=trace_id,
        lifecycle_records=lifecycle_records,
        rollout_records=rollout_records,
    )

    for key in selected_policy["required_inputs"]:
        if key not in context:
            raise JudgmentEngineError(f"missing required policy input: {key}")

    retrieval_cfg = selected_policy["precedent_retrieval"]
    precedents = retrieve_precedents(precedent_paths=precedent_paths, retrieval=retrieval_cfg, query_context=context)
    if retrieval_cfg["required"] and not precedents:
        raise JudgmentEngineError("required precedent retrieval produced no qualifying precedents")

    winning_rule, matched_rules = _select_rule(context, selected_policy["decision_rules"])
    matched_outcomes = sorted({rule["outcome"] for rule in matched_rules})
    conflicts = [f"conflicting matched outcomes: {', '.join(matched_outcomes)}"] if len(matched_outcomes) > 1 else []
    deviations = []
    if not precedents:
        deviations.append("no precedent returned above configured threshold")

    claims_considered = [
        {
            "claim_id": "claim-001",
            "claim_text": "artifact release requires explicit evidence and policy evaluation",
            "is_material": True,
            "supported_by_evidence_ids": list(evidence_refs),
        },
        {
            "claim_id": "claim-002",
            "claim_text": "precedent consistency should be recorded for traceability",
            "is_material": True,
            "supported_by_evidence_ids": list(evidence_refs),
        },
    ]

    judgment_record = {
        "artifact_type": "judgment_record",
        "artifact_id": f"judgment-record-{cycle_id}",
        "artifact_version": "1.1.0",
        "schema_version": "1.1.0",
        "standards_version": "1.0.93",
        "judgment_type": judgment_type,
        "selected_outcome": winning_rule["outcome"],
        "cycle_id": cycle_id,
        "policy_ref": selected_policy["_path"],
        "claims_considered": claims_considered,
        "evidence_refs": evidence_refs,
        "rules_applied": [winning_rule["rule_id"]],
        "alternatives_considered": [rule["rule_id"] for rule in matched_rules[1:]],
        "uncertainties": ["precedent similarity below perfect match"] if any(x["score"] < 1.0 for x in precedents) else [],
        "conditions_under_which_decision_changes": [
            "required policy inputs change",
            "selected policy version/status changes",
            "precedent similarity drops below threshold",
        ],
        "precedent_retrieval": {
            "method_id": retrieval_cfg["method_id"],
            "method_version": retrieval_cfg["method_version"],
            "threshold": retrieval_cfg["threshold"],
            "top_k": retrieval_cfg["top_k"],
            "similarity_basis": retrieval_cfg["similarity_basis"],
            "scored_precedents": precedents,
        },
        "context_fingerprint": {field: context[field] for field in retrieval_cfg["query_fields"]},
        "rationale_summary": winning_rule["rationale_template"],
        "created_at": created_at,
    }
    validate_artifact(judgment_record, "judgment_record")

    application_record = {
        "artifact_type": "judgment_application_record",
        "artifact_id": f"judgment-application-{cycle_id}",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": "1.0.93",
        "judgment_record_ref": f"judgment_record::{cycle_id}",
        "selected_policy_ref": selected_policy["_path"],
        "matched_policy_refs": matched_paths,
        "conflicts": conflicts,
        "deviations": deviations,
        "final_outcome": winning_rule["outcome"],
        "created_at": created_at,
    }
    validate_artifact(application_record, "judgment_application_record")

    eval_result = run_judgment_evals(
        cycle_id=cycle_id,
        created_at=created_at,
        judgment_record=judgment_record,
        application_record=application_record,
        policy=selected_policy,
        replay_reference=replay_reference,
        replay_reference_source=replay_reference_source,
    )

    return {
        "judgment_record": judgment_record,
        "judgment_application_record": application_record,
        "judgment_eval_result": eval_result,
    }
