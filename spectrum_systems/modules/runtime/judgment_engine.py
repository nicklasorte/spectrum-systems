"""Deterministic judgment policy + precedent + application engine for autonomous cycle control."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
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




def _canonical_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _parse_iso8601(timestamp: str) -> datetime:
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


def _as_judgment_ref(value: str) -> str:
    return value if value.startswith("judgment_record:") else f"judgment_record:{value}"


def build_judgment_lifecycle_record(
    *,
    judgment_record_ref: str,
    lifecycle_state: str,
    activation_status: str,
    prior_judgment_ref: str | None,
    supersedes_refs: list[str],
    superseded_by_ref: str | None,
    retirement_reason: str | None,
    effective_at: str | None,
    retired_at: str | None,
    created_at: str,
    trace_id: str,
) -> dict[str, Any]:
    seed = {
        "judgment_record_ref": judgment_record_ref,
        "lifecycle_state": lifecycle_state,
        "supersedes_refs": sorted(supersedes_refs),
        "superseded_by_ref": superseded_by_ref,
        "trace_id": trace_id,
    }
    record = {
        "judgment_lifecycle_id": f"JLC-{_canonical_hash(seed)[:12].upper()}",
        "judgment_record_ref": judgment_record_ref,
        "lifecycle_state": lifecycle_state,
        "prior_judgment_ref": prior_judgment_ref,
        "supersedes_refs": sorted(set(supersedes_refs)),
        "superseded_by_ref": superseded_by_ref,
        "activation_status": activation_status,
        "retirement_reason": retirement_reason,
        "effective_at": effective_at,
        "retired_at": retired_at,
        "created_at": created_at,
        "trace_id": trace_id,
    }
    validate_artifact(record, "judgment_lifecycle_record")
    return record


def validate_judgment_active_set(*, lifecycle_records: list[dict[str, Any]], allow_multiple_active: bool = False) -> list[str]:
    active_by_scope: dict[str, list[str]] = {}
    for row in lifecycle_records:
        validate_artifact(row, "judgment_lifecycle_record")
        if row["activation_status"] != "active":
            continue
        ref = str(row["judgment_record_ref"])
        scope = ref.split(":", 1)[-1].split("@", 1)[0]
        active_by_scope.setdefault(scope, []).append(ref)

    conflicts: list[str] = []
    for scope, refs in sorted(active_by_scope.items()):
        if len(refs) > 1 and not allow_multiple_active:
            conflicts.append(f"ambiguous_active_set:{scope}:{','.join(sorted(refs))}")
    return conflicts


def supersede_judgment(
    *,
    prior_record: dict[str, Any],
    new_judgment_ref: str,
    created_at: str,
    trace_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    prior_ref = str(prior_record["judgment_record_ref"])
    next_ref = _as_judgment_ref(new_judgment_ref)
    updated_prior = build_judgment_lifecycle_record(
        judgment_record_ref=prior_ref,
        lifecycle_state="superseded",
        activation_status="inactive",
        prior_judgment_ref=prior_record.get("prior_judgment_ref"),
        supersedes_refs=list(prior_record.get("supersedes_refs", [])),
        superseded_by_ref=next_ref,
        retirement_reason="superseded_by_new_active_judgment",
        effective_at=prior_record.get("effective_at"),
        retired_at=created_at,
        created_at=created_at,
        trace_id=trace_id,
    )
    new_record = build_judgment_lifecycle_record(
        judgment_record_ref=next_ref,
        lifecycle_state="active",
        activation_status="active",
        prior_judgment_ref=prior_ref,
        supersedes_refs=[prior_ref],
        superseded_by_ref=None,
        retirement_reason=None,
        effective_at=created_at,
        retired_at=None,
        created_at=created_at,
        trace_id=trace_id,
    )
    return updated_prior, new_record


def retire_judgment(*, lifecycle_record: dict[str, Any], reason: str, created_at: str, trace_id: str) -> dict[str, Any]:
    return build_judgment_lifecycle_record(
        judgment_record_ref=str(lifecycle_record["judgment_record_ref"]),
        lifecycle_state="retired",
        activation_status="inactive",
        prior_judgment_ref=lifecycle_record.get("prior_judgment_ref"),
        supersedes_refs=list(lifecycle_record.get("supersedes_refs", [])),
        superseded_by_ref=lifecycle_record.get("superseded_by_ref"),
        retirement_reason=reason,
        effective_at=lifecycle_record.get("effective_at"),
        retired_at=created_at,
        created_at=created_at,
        trace_id=trace_id,
    )


def resolve_precedent_precedence(*, candidates: list[dict[str, Any]], precedence_order: list[str]) -> list[dict[str, Any]]:
    rank = {name: idx for idx, name in enumerate(precedence_order)}
    return sorted(
        candidates,
        key=lambda item: (
            rank.get(str(item.get("precedence_tier", "override")), len(rank)),
            -float(item.get("score", 0.0)),
            str(item.get("record_ref", "")),
        ),
    )


def detect_precedent_conflicts(*, candidates: list[dict[str, Any]], target_judgment_ref: str, created_at: str, trace_id: str) -> dict[str, Any] | None:
    if len(candidates) < 2:
        return None
    winners = [c for c in candidates if float(c.get("score", 0.0)) == float(candidates[0].get("score", 0.0))]
    if len(winners) < 2:
        return None
    refs = sorted(_as_judgment_ref(str(item.get("record_ref", ""))) for item in winners[:2])
    seed = {"target": target_judgment_ref, "refs": refs, "trace_id": trace_id}
    conflict = {
        "precedent_conflict_id": f"PCF-{_canonical_hash(seed)[:12].upper()}",
        "target_judgment_ref": target_judgment_ref,
        "conflicting_precedent_refs": refs,
        "conflict_type": "scope_overlap_conflict",
        "severity": "high",
        "precedence_resolution": "deterministic_tie_break_by_record_ref",
        "blocking": True,
        "required_followup": ["governance_review:precedent_conflict"],
        "created_at": created_at,
        "trace_id": trace_id,
    }
    validate_artifact(conflict, "precedent_conflict_record")
    return conflict


def select_precedent_for_judgment(
    *,
    target_judgment_ref: str,
    precedents: list[dict[str, Any]],
    created_at: str,
    trace_id: str,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    ordered = resolve_precedent_precedence(
        candidates=precedents,
        precedence_order=["global_invariants", "domain_policy", "active_local_judgment", "override"],
    )
    selected = _as_judgment_ref(str(ordered[0]["record_ref"])) if ordered else None
    candidates = [_as_judgment_ref(str(item["record_ref"])) for item in ordered]
    rejected = [ref for ref in candidates if ref != selected]
    seed = {"target": target_judgment_ref, "selected": selected, "trace_id": trace_id, "candidates": candidates}
    selection = {
        "precedent_selection_id": f"PSL-{_canonical_hash(seed)[:12].upper()}",
        "target_judgment_ref": target_judgment_ref,
        "candidate_precedent_refs": candidates,
        "selected_precedent_ref": selected,
        "rejected_precedent_refs": rejected,
        "similarity_basis": sorted({basis for item in ordered for basis in item.get("basis", [])}) or ["none"],
        "scope_match_signals": ["active_only", "non_retired", "non_revoked", "deterministic_order"],
        "precedence_rule_applied": "global invariants > domain policy > active local judgment > override",
        "conflict_detected": False,
        "supporting_artifact_refs": sorted(set(candidates + [target_judgment_ref])),
        "created_at": created_at,
        "trace_id": trace_id,
    }
    conflict = detect_precedent_conflicts(candidates=ordered, target_judgment_ref=target_judgment_ref, created_at=created_at, trace_id=trace_id)
    selection["conflict_detected"] = conflict is not None
    validate_artifact(selection, "precedent_selection_record")
    return selection, conflict


def build_override_governance_record(
    *,
    override_record_ref: str,
    owner: str,
    justification: str,
    scope: str,
    issued_at: str,
    expires_at: str,
    review_due_at: str,
    linked_decision_refs: list[str],
    linked_artifact_refs: list[str],
    created_at: str,
    trace_id: str,
    outcome_tracking_status: str = "pending",
    escalation_state: str = "none",
    active: bool = True,
) -> dict[str, Any]:
    if not owner.strip() or not justification.strip():
        raise JudgmentEngineError("override governance requires owner and justification")
    seed = {"override_record_ref": override_record_ref, "scope": scope, "issued_at": issued_at, "trace_id": trace_id}
    record = {
        "override_governance_id": f"OVG-{_canonical_hash(seed)[:12].upper()}",
        "override_record_ref": override_record_ref,
        "owner": owner,
        "justification": justification,
        "scope": scope,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "review_due_at": review_due_at,
        "outcome_tracking_status": outcome_tracking_status,
        "linked_decision_refs": sorted(set(linked_decision_refs)),
        "linked_artifact_refs": sorted(set(linked_artifact_refs)),
        "escalation_state": escalation_state,
        "active": active,
        "created_at": created_at,
        "trace_id": trace_id,
    }
    validate_artifact(record, "override_governance_record")
    return record


def validate_override_expiry(*, record: dict[str, Any], now: str, max_age_days: int = 30) -> dict[str, Any]:
    validate_artifact(record, "override_governance_record")
    issued = _parse_iso8601(record["issued_at"])
    expires = _parse_iso8601(record["expires_at"])
    current = _parse_iso8601(now)
    age_days = (current - issued).days
    expired = current >= expires
    escalation = str(record["escalation_state"])
    active = bool(record["active"])
    status = str(record["outcome_tracking_status"])
    if expired and active:
        escalation = "freeze_candidate" if age_days <= max_age_days else "block"
        active = False
        status = "expired"
    return record | {"escalation_state": escalation, "active": active, "outcome_tracking_status": status}


def evaluate_override_backlog(*, records: list[dict[str, Any]], warning_threshold: int = 2, block_threshold: int = 5) -> str:
    active_count = sum(1 for rec in records if rec.get("active") is True)
    if active_count >= block_threshold:
        return "block"
    if active_count >= warning_threshold:
        return "warning"
    return "none"


def escalate_override_governance(*, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    backlog_state = evaluate_override_backlog(records=records)
    escalated: list[dict[str, Any]] = []
    for rec in records:
        row = dict(rec)
        if backlog_state == "block" and row.get("active") is True:
            row["escalation_state"] = "block"
        elif backlog_state == "warning" and row.get("active") is True and row.get("escalation_state") == "none":
            row["escalation_state"] = "warning"
        validate_artifact(row, "override_governance_record")
        escalated.append(row)
    return escalated
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
    governed_runtime: bool = False,
) -> tuple[dict[str, Any], list[str]]:
    if not policy_paths:
        raise JudgmentEngineError("no judgment policies configured")

    strict_lifecycle = governed_runtime or lifecycle_records is not None
    strict_rollout = governed_runtime or rollout_records is not None
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

    def _matching_canary_rollouts(policy: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            rec for rec in rollout_records
            if rec.get("policy_id") == policy["artifact_id"]
            and rec.get("policy_version") == policy["artifact_version"]
            and rec.get("rollout_type") == "canary"
            and rec.get("rollout_status") == "active"
        ]

    def _canary_rollout_allows(policy: dict[str, Any]) -> tuple[bool, str | None]:
        if policy["status"] != "canary":
            return True, None
        matching_rollouts = _matching_canary_rollouts(policy)
        if not matching_rollouts:
            return False, None
        if trace_id is None:
            return False, None
        for rollout in sorted(matching_rollouts, key=lambda rec: str(rec.get("artifact_id") or "")):
            try:
                if is_trace_in_canary_cohort(trace_id=trace_id, cohort=rollout.get("cohort", {}), environment=environment):
                    return True, str(rollout.get("rollout_id") or rollout.get("artifact_id") or "")
            except JudgmentPolicyLifecycleError:
                continue
        return False, None

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
        rollout_allowed, selected_rollout_id = _canary_rollout_allows(policy)
        if not rollout_allowed:
            continue
        matched.append((path, policy | {"_selected_rollout_id": selected_rollout_id}))

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
    governed_runtime: bool = False,
) -> dict[str, dict[str, Any]]:
    selected_policy, matched_paths = select_policy(
        policy_paths=policy_paths,
        judgment_type=judgment_type,
        scope=scope,
        environment=environment,
        trace_id=trace_id,
        lifecycle_records=lifecycle_records,
        rollout_records=rollout_records,
        governed_runtime=governed_runtime,
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
        "artifact_version": "1.1.0",
        "schema_version": "1.1.0",
        "standards_version": "1.0.93",
        "judgment_record_ref": f"judgment_record::{cycle_id}",
        "selected_policy_ref": selected_policy["_path"],
        "selected_policy_id": selected_policy["artifact_id"],
        "selected_policy_version": selected_policy["artifact_version"],
        "policy_lifecycle_status": selected_policy["status"],
        "policy_rollout_id": selected_policy.get("_selected_rollout_id"),
        "policy_trace": {
            "trace_id": trace_id or cycle_id,
            "cycle_id": cycle_id,
        },
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

    trace_key = trace_id or cycle_id
    target_ref = _as_judgment_ref(judgment_record["artifact_id"])
    lifecycle_record = build_judgment_lifecycle_record(
        judgment_record_ref=target_ref,
        lifecycle_state="active",
        activation_status="active",
        prior_judgment_ref=None,
        supersedes_refs=[],
        superseded_by_ref=None,
        retirement_reason=None,
        effective_at=created_at,
        retired_at=None,
        created_at=created_at,
        trace_id=trace_key,
    )
    active_conflicts = validate_judgment_active_set(lifecycle_records=[lifecycle_record])
    if active_conflicts:
        raise JudgmentEngineError("ambiguous active-set detected for judgment lifecycle")

    decorated_precedents = []
    for item in precedents:
        decorated_precedents.append(
            dict(item)
            | {
                "precedence_tier": "active_local_judgment",
                "record_ref": _as_judgment_ref(str(item["record_ref"]).replace("::", ":")),
            }
        )
    selection_record, conflict_record = select_precedent_for_judgment(
        target_judgment_ref=target_ref,
        precedents=decorated_precedents,
        created_at=created_at,
        trace_id=trace_key,
    )
    if conflict_record is not None and conflict_record["blocking"] and conflict_record["severity"] in {"high", "critical"} and governed_runtime:
        raise JudgmentEngineError("unresolved high-severity precedent conflict on governed path")

    override_record = None
    override_input = context.get("override_governance")
    if override_input is not None:
        if not isinstance(override_input, dict):
            raise JudgmentEngineError("override_governance context must be an object when provided")
        override_record = build_override_governance_record(
            override_record_ref=str(override_input.get("override_record_ref", "")),
            owner=str(override_input.get("owner", "")),
            justification=str(override_input.get("justification", "")),
            scope=str(override_input.get("scope", "")),
            issued_at=str(override_input.get("issued_at", created_at)),
            expires_at=str(override_input.get("expires_at", "")),
            review_due_at=str(override_input.get("review_due_at", "")),
            linked_decision_refs=list(override_input.get("linked_decision_refs", [f"judgment_application_record:{application_record['artifact_id']}"])),
            linked_artifact_refs=list(override_input.get("linked_artifact_refs", [target_ref])),
            created_at=created_at,
            trace_id=trace_key,
        )
        override_record = validate_override_expiry(record=override_record, now=created_at)
        if override_record["escalation_state"] == "block" and governed_runtime:
            raise JudgmentEngineError("expired override on active governed path")

    return {
        "judgment_record": judgment_record,
        "judgment_application_record": application_record,
        "judgment_eval_result": eval_result,
        "judgment_lifecycle_record": lifecycle_record,
        "precedent_selection_record": selection_record,
        "precedent_conflict_record": conflict_record,
        "override_governance_record": override_record,
    }
