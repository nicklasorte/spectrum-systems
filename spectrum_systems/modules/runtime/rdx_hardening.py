"""RDX bounded roadmap-governance hardening with deterministic selection, eval, replay, and red-team fix loops."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any, Mapping

from spectrum_systems.contracts import validate_artifact


class RDXHardeningError(ValueError):
    """Raised when RDX hardening checks fail closed."""


_FORBIDDEN_ACTION_PREFIXES = (
    "execute_work",
    "route_subsystem",
    "issue_closure",
    "issue_policy",
    "reinterpret_review",
    "generate_repair_plan",
    "enforce_runtime_action",
    "adoption_priority",
)


def _hash(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def enforce_rdx_boundary(*, consumed_inputs: list[str], emitted_outputs: list[str], claimed_actions: list[str]) -> list[str]:
    allowed_inputs = {
        "roadmap_artifact",
        "roadmap_signal_bundle",
        "trust_gap_signals",
        "dependency_graph",
        "batch_completion_evidence",
        "umbrella_completion_evidence",
        "execution_loop_readiness_inputs",
    }
    allowed_outputs = {
        "rdx_roadmap_selection_record",
        "rdx_batch_selection_record",
        "rdx_umbrella_selection_record",
        "rdx_execution_loop_readiness_handoff_record",
        "rdx_selection_eval_result",
        "rdx_selection_conflict_record",
        "rdx_selection_readiness_record",
        "rdx_selection_effectiveness_record",
        "rdx_rework_debt_record",
        "rdx_roadmap_governance_bundle",
    }
    failures: list[str] = []
    for name in consumed_inputs:
        if name not in allowed_inputs:
            failures.append(f"invalid_upstream_input:{name}")
    for name in emitted_outputs:
        if name not in allowed_outputs:
            failures.append(f"invalid_downstream_output:{name}")
    for action in claimed_actions:
        if action.startswith(_FORBIDDEN_ACTION_PREFIXES):
            failures.append(f"forbidden_owner_overlap:{action}")
    return sorted(set(failures))


def select_next_governed_batch(*, roadmap: Mapping[str, Any], trust_gap_priority: list[str], now: str) -> dict[str, Any]:
    batches = roadmap.get("batches")
    if not isinstance(batches, list) or not batches:
        raise RDXHardeningError("roadmap_batches_required")

    status_by_id = {str(b.get("batch_id")): str(b.get("status")) for b in batches if isinstance(b, Mapping)}
    eligible: list[dict[str, Any]] = []
    reasons: list[str] = []

    for batch in batches:
        if not isinstance(batch, Mapping):
            continue
        batch_id = str(batch.get("batch_id") or "")
        if not batch_id or str(batch.get("status")) != "not_started":
            continue
        deps = batch.get("depends_on", [])
        if not isinstance(deps, list):
            raise RDXHardeningError(f"depends_on_list_required:{batch_id}")
        unmet = [dep for dep in deps if status_by_id.get(str(dep)) != "completed"]
        if unmet:
            reasons.append(f"dependency_unmet:{batch_id}:{','.join(sorted(str(d) for d in unmet))}")
            continue
        trust_tag = str(batch.get("trust_gap_tag") or "")
        priority_rank = trust_gap_priority.index(trust_tag) if trust_tag in trust_gap_priority else len(trust_gap_priority) + 99
        eligible.append(
            {
                "batch_id": batch_id,
                "umbrella_id": str(batch.get("umbrella_id") or "UNKNOWN"),
                "priority_rank": priority_rank,
                "base_priority": int(batch.get("priority") or 9999),
                "trust_gap_tag": trust_tag,
            }
        )

    if not eligible:
        raise RDXHardeningError("no_eligible_batch")

    selected = sorted(eligible, key=lambda row: (row["priority_rank"], row["base_priority"], row["batch_id"]))[0]
    record = {
        "artifact_type": "rdx_batch_selection_record",
        "record_id": f"rbs-{_hash([roadmap.get('roadmap_id'), selected['batch_id'], now])[:16]}",
        "roadmap_id": str(roadmap.get("roadmap_id") or "unknown"),
        "selected_batch_id": selected["batch_id"],
        "selected_umbrella_id": selected["umbrella_id"],
        "reason_codes": ["dependency_satisfied", "trust_gap_priority_applied", "deterministic_tie_break_applied"],
        "trust_gap_tag": selected["trust_gap_tag"],
        "evaluated_at": now,
        "lineage_ref": str(roadmap.get("lineage_ref") or "lineage:unknown"),
    }
    validate_artifact(record, "rdx_batch_selection_record")
    return record


def build_roadmap_selection_record(*, roadmap: Mapping[str, Any], selected_umbrella_id: str, reason_codes: list[str], evaluated_at: str) -> dict[str, Any]:
    record = {
        "artifact_type": "rdx_roadmap_selection_record",
        "record_id": f"rrs-{_hash([roadmap.get('roadmap_id'), selected_umbrella_id, evaluated_at])[:16]}",
        "roadmap_id": str(roadmap.get("roadmap_id") or "unknown"),
        "selected_umbrella_id": selected_umbrella_id,
        "reason_codes": sorted(set(reason_codes)),
        "evaluated_at": evaluated_at,
        "lineage_ref": str(roadmap.get("lineage_ref") or "lineage:unknown"),
    }
    validate_artifact(record, "rdx_roadmap_selection_record")
    return record


def build_umbrella_selection_record(*, roadmap: Mapping[str, Any], selected_umbrella_id: str, evaluated_at: str) -> dict[str, Any]:
    umbrellas = [u for u in roadmap.get("umbrellas", []) if isinstance(u, Mapping)]
    row = next((u for u in umbrellas if str(u.get("umbrella_id")) == selected_umbrella_id), None)
    if not row:
        raise RDXHardeningError("selected_umbrella_not_found")
    batch_ids = row.get("batch_ids", [])
    if not isinstance(batch_ids, list) or len(batch_ids) < 2:
        raise RDXHardeningError("selected_umbrella_invalid_cardinality")
    record = {
        "artifact_type": "rdx_umbrella_selection_record",
        "record_id": f"rus-{_hash([roadmap.get('roadmap_id'), selected_umbrella_id, evaluated_at])[:16]}",
        "roadmap_id": str(roadmap.get("roadmap_id") or "unknown"),
        "selected_umbrella_id": selected_umbrella_id,
        "batch_ids": [str(v) for v in batch_ids],
        "reason_codes": ["umbrella_active", "minimum_cardinality_satisfied"],
        "evaluated_at": evaluated_at,
        "lineage_ref": str(roadmap.get("lineage_ref") or "lineage:unknown"),
    }
    validate_artifact(record, "rdx_umbrella_selection_record")
    return record


def build_execution_loop_readiness_handoff(*, trace_id: str, selected_batch_id: str, selected_umbrella_id: str, lineage_ref: str, readiness_status: str, created_at: str) -> dict[str, Any]:
    record = {
        "artifact_type": "rdx_execution_loop_readiness_handoff_record",
        "record_id": f"reh-{_hash([trace_id, selected_batch_id, created_at])[:16]}",
        "trace_id": trace_id,
        "selected_batch_id": selected_batch_id,
        "selected_umbrella_id": selected_umbrella_id,
        "lineage_ref": lineage_ref,
        "readiness_status": readiness_status,
        "non_authority_assertions": ["candidate_only_non_authoritative", "rdx_not_execution_authority"],
        "created_at": created_at,
    }
    validate_artifact(record, "rdx_execution_loop_readiness_handoff_record")
    return record


def evaluate_selection(*, roadmap: Mapping[str, Any], selection_record: Mapping[str, Any], owner: str, trust_gap_priority: list[str], evaluated_at: str) -> dict[str, Any]:
    checks = {
        "required_evidence_present": bool(roadmap.get("dependency_graph_ref")) and bool(roadmap.get("trust_signal_ref")),
        "dependency_valid": True,
        "owner_valid": owner == "RDX",
        "trust_gap_priority_aligned": True,
        "hierarchy_valid": True,
    }
    fail_reasons: list[str] = []
    selected = str(selection_record.get("selected_batch_id") or "")
    batches = [b for b in roadmap.get("batches", []) if isinstance(b, Mapping)]
    by_id = {str(b.get("batch_id")): b for b in batches}
    batch = by_id.get(selected)
    if not batch:
        checks["dependency_valid"] = False
        checks["hierarchy_valid"] = False
        fail_reasons.append("selected_batch_missing")
    else:
        deps = batch.get("depends_on", [])
        if not isinstance(deps, list):
            checks["dependency_valid"] = False
            fail_reasons.append("selected_batch_depends_on_invalid")
        else:
            unmet = [d for d in deps if str(by_id.get(str(d), {}).get("status")) != "completed"]
            if unmet:
                checks["dependency_valid"] = False
                fail_reasons.append("selected_batch_dependency_unmet")

        selected_tag = str(batch.get("trust_gap_tag") or "")
        unresolved_tags = sorted(
            {
                str(row.get("trust_gap_tag"))
                for row in batches
                if str(row.get("status")) == "not_started" and isinstance(row.get("trust_gap_tag"), str)
            }
        )
        expected_top = next((tag for tag in trust_gap_priority if tag in unresolved_tags), None)
        if expected_top and selected_tag != expected_top:
            checks["trust_gap_priority_aligned"] = False
            fail_reasons.append("trust_gap_priority_inverted")

    umbrellas = roadmap.get("umbrellas", [])
    if not isinstance(umbrellas, list):
        checks["hierarchy_valid"] = False
        fail_reasons.append("umbrellas_missing")
    else:
        for umb in umbrellas:
            if not isinstance(umb, Mapping):
                checks["hierarchy_valid"] = False
                fail_reasons.append("umbrella_row_invalid")
                continue
            batch_ids = umb.get("batch_ids", [])
            if not isinstance(batch_ids, list) or len(batch_ids) < 2:
                checks["hierarchy_valid"] = False
                fail_reasons.append("invalid_single_batch_umbrella")
            if isinstance(batch_ids, list) and len(batch_ids) == 1 and str(batch_ids[0]) == str(umb.get("umbrella_id")):
                checks["hierarchy_valid"] = False
                fail_reasons.append("pass_through_wrapper_detected")

    for batch_row in batches:
        slice_ids = batch_row.get("slice_ids", [])
        if isinstance(slice_ids, list) and len(slice_ids) < 2:
            checks["hierarchy_valid"] = False
            fail_reasons.append("invalid_single_slice_batch")

    eval_result = {
        "artifact_type": "rdx_selection_eval_result",
        "eval_id": f"rse-{_hash([selection_record.get('record_id'), checks, evaluated_at])[:16]}",
        "selection_ref": f"rdx_batch_selection_record:{selection_record.get('record_id')}",
        "evaluated_at": evaluated_at,
        "evaluation_status": "pass" if not fail_reasons else "fail",
        "checks": checks,
        "fail_reasons": sorted(set(fail_reasons)),
        "trace_id": str(roadmap.get("trace_id") or "trace:unknown"),
    }
    validate_artifact(eval_result, "rdx_selection_eval_result")
    return eval_result


def validate_selection_replay(*, prior_input: Mapping[str, Any], replay_input: Mapping[str, Any], prior_selection: Mapping[str, Any], replay_selection: Mapping[str, Any], prior_eval: Mapping[str, Any], replay_eval: Mapping[str, Any]) -> tuple[bool, list[str]]:
    failures: list[str] = []
    if _hash(prior_input) != _hash(replay_input):
        failures.append("replay_input_drift")
    if prior_selection.get("selected_batch_id") != replay_selection.get("selected_batch_id"):
        failures.append("replay_selected_batch_mismatch")
    if prior_selection.get("reason_codes") != replay_selection.get("reason_codes"):
        failures.append("replay_reason_code_mismatch")
    if prior_eval.get("fail_reasons") != replay_eval.get("fail_reasons"):
        failures.append("replay_eval_mismatch")
    if not prior_input.get("dependency_graph_ref") or not replay_input.get("dependency_graph_ref"):
        failures.append("replay_evidence_incomplete")
    return (not failures, sorted(set(failures)))


def validate_progression_vs_closure(*, progression_refs: list[str], closure_refs: list[str], non_authority_assertions: list[str]) -> list[str]:
    failures: list[str] = []
    if any(ref.startswith("closure_decision_artifact:") for ref in progression_refs):
        failures.append("progression_contains_closure_artifact")
    if any(ref.startswith("promotion_readiness_decision:") for ref in progression_refs):
        failures.append("progression_contains_promotion_artifact")
    if any(ref.startswith("rdx_") for ref in closure_refs):
        failures.append("closure_flow_consumes_rdx_progression_artifact")
    if "rdx_not_closure_authority" not in non_authority_assertions:
        failures.append("missing_non_authority_assertion")
    return sorted(set(failures))


def detect_pass_through_wrappers(*, roadmap: Mapping[str, Any]) -> list[str]:
    fails: list[str] = []
    for batch in roadmap.get("batches", []):
        if isinstance(batch, Mapping):
            batch_id = str(batch.get("batch_id") or "")
            slice_ids = batch.get("slice_ids", [])
            if isinstance(slice_ids, list) and len(slice_ids) == 1:
                only = str(slice_ids[0])
                if only == batch_id or only.startswith("BATCH-"):
                    fails.append(f"batch_pass_through_wrapper:{batch_id}")
    for umb in roadmap.get("umbrellas", []):
        if isinstance(umb, Mapping):
            umbrella_id = str(umb.get("umbrella_id") or "")
            batch_ids = umb.get("batch_ids", [])
            if isinstance(batch_ids, list) and len(batch_ids) == 1:
                only = str(batch_ids[0])
                if only == umbrella_id or only.startswith("UMB-"):
                    fails.append(f"umbrella_pass_through_wrapper:{umbrella_id}")
    return sorted(set(fails))


def build_rework_debt_record(*, selection_history: list[Mapping[str, Any]], created_at: str, trace_id: str) -> dict[str, Any]:
    counter: Counter[str] = Counter()
    for row in selection_history:
        for batch_id in row.get("deferred_batch_ids", []):
            counter[str(batch_id)] += 1
    repeated = sorted([batch for batch, count in counter.items() if count >= 3])
    artifact = {
        "artifact_type": "rdx_rework_debt_record",
        "debt_id": f"rrd-{_hash([trace_id, sorted(counter.items())])[:16]}",
        "trace_id": trace_id,
        "created_at": created_at,
        "deferred_counts": {k: int(v) for k, v in sorted(counter.items())},
        "repeat_rework_batch_ids": repeated,
        "debt_status": "elevated" if repeated else "normal",
    }
    validate_artifact(artifact, "rdx_rework_debt_record")
    return artifact


def validate_selection_to_tlc_integrity(*, handoff_record: Mapping[str, Any], tlc_input: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    if handoff_record.get("selected_batch_id") != tlc_input.get("selected_batch_id"):
        failures.append("selected_batch_drift")
    if handoff_record.get("selected_umbrella_id") != tlc_input.get("selected_umbrella_id"):
        failures.append("selected_umbrella_drift")
    if handoff_record.get("lineage_ref") != tlc_input.get("lineage_ref"):
        failures.append("lineage_drift")
    if tlc_input.get("execution_authority"):
        failures.append("handoff_smuggles_execution_authority")
    return sorted(set(failures))


def detect_progression_artifact_misuse(*, consumer_artifacts: list[Mapping[str, Any]]) -> list[str]:
    failures: list[str] = []
    for artifact in consumer_artifacts:
        source = str(artifact.get("source_ref") or "")
        use = str(artifact.get("used_for") or "")
        if source.startswith("rdx_") and use in {"closure_evidence", "promotion_evidence"}:
            failures.append(f"progression_artifact_misused:{artifact.get('artifact_id', 'unknown')}")
    return sorted(set(failures))


def build_selection_readiness(*, eval_result: Mapping[str, Any], dependency_failures: list[str], created_at: str, trace_id: str) -> dict[str, Any]:
    fail_reasons = sorted(set([*eval_result.get("fail_reasons", []), *dependency_failures]))
    record = {
        "artifact_type": "rdx_selection_readiness_record",
        "readiness_id": f"rsr-{_hash([trace_id, fail_reasons])[:16]}",
        "trace_id": trace_id,
        "created_at": created_at,
        "readiness_status": "candidate_only" if not fail_reasons else "blocked",
        "fail_reasons": fail_reasons,
        "non_authority_assertions": [
            "candidate_only_non_authoritative",
            "rdx_not_closure_authority",
            "rdx_not_policy_authority",
            "rdx_not_execution_authority",
        ],
    }
    validate_artifact(record, "rdx_selection_readiness_record")
    return record


def build_selection_effectiveness(*, outcomes: list[Mapping[str, Any]], window_id: str, created_at: str) -> dict[str, Any]:
    if not outcomes:
        raise RDXHardeningError("selection_effectiveness_requires_outcomes")
    total = len(outcomes)
    trust_gap_closed = sum(1 for row in outcomes if row.get("trust_gap_closed") is True)
    dependency_violations = sum(1 for row in outcomes if row.get("dependency_violation") is True)
    rework = sum(1 for row in outcomes if row.get("rework") is True)
    status = "improving" if trust_gap_closed / total >= 0.6 and dependency_violations == 0 and rework / total <= 0.3 else "degraded"
    artifact = {
        "artifact_type": "rdx_selection_effectiveness_record",
        "effectiveness_id": f"rseff-{_hash([window_id, total, trust_gap_closed, dependency_violations, rework])[:16]}",
        "window_id": window_id,
        "created_at": created_at,
        "runs_evaluated": total,
        "trust_gap_closure_rate": trust_gap_closed / total,
        "dependency_violation_rate": dependency_violations / total,
        "rework_rate": rework / total,
        "value_status": status,
    }
    validate_artifact(artifact, "rdx_selection_effectiveness_record")
    return artifact


def build_governance_bundle(*, roadmap_selection: Mapping[str, Any], batch_selection: Mapping[str, Any], umbrella_selection: Mapping[str, Any], handoff: Mapping[str, Any], eval_result: Mapping[str, Any], readiness: Mapping[str, Any], effectiveness: Mapping[str, Any], rework_debt: Mapping[str, Any], created_at: str, trace_id: str) -> dict[str, Any]:
    bundle = {
        "artifact_type": "rdx_roadmap_governance_bundle",
        "bundle_id": f"rgb-{_hash([trace_id, roadmap_selection.get('record_id'), batch_selection.get('record_id')])[:16]}",
        "trace_id": trace_id,
        "created_at": created_at,
        "record_refs": [
            f"rdx_roadmap_selection_record:{roadmap_selection.get('record_id')}",
            f"rdx_batch_selection_record:{batch_selection.get('record_id')}",
            f"rdx_umbrella_selection_record:{umbrella_selection.get('record_id')}",
            f"rdx_execution_loop_readiness_handoff_record:{handoff.get('record_id')}",
            f"rdx_selection_eval_result:{eval_result.get('eval_id')}",
            f"rdx_selection_readiness_record:{readiness.get('readiness_id')}",
            f"rdx_selection_effectiveness_record:{effectiveness.get('effectiveness_id')}",
            f"rdx_rework_debt_record:{rework_debt.get('debt_id')}",
        ],
        "non_authority_assertions": [
            "bundle_controls_progression_only",
            "does_not_replace_cde_closure_authority",
            "does_not_replace_tpa_policy_authority",
        ],
    }
    validate_artifact(bundle, "rdx_roadmap_governance_bundle")
    return bundle


def run_rdx_boundary_redteam(*, fixtures: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [dict(row) for row in fixtures if row.get("should_fail_closed") and row.get("observed") != "blocked"]


def run_rdx_semantic_redteam(*, fixtures: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for row in fixtures:
        if row.get("semantic_risk") is True and row.get("observed") != "blocked":
            findings.append(dict(row))
    return findings


def build_selection_conflict_record(*, trace_id: str, created_at: str, conflict_codes: list[str]) -> dict[str, Any]:
    record = {
        "artifact_type": "rdx_selection_conflict_record",
        "conflict_id": f"rconf-{_hash([trace_id, sorted(set(conflict_codes))])[:16]}",
        "trace_id": trace_id,
        "created_at": created_at,
        "conflict_codes": sorted(set(conflict_codes)),
    }
    validate_artifact(record, "rdx_selection_conflict_record")
    return record


def verify_hnx_closeout_dependency_gate(*, hnx_closeout_status: str, replay_match: bool, stop_guard_ok: bool, checkpoint_resume_ok: bool) -> dict[str, Any]:
    checks = {
        "hnx_closeout_closed": hnx_closeout_status == "closed",
        "replay_valid": replay_match,
        "stop_condition_integrity": stop_guard_ok,
        "checkpoint_resume_integrity": checkpoint_resume_ok,
    }
    fail_reasons = [name for name, ok in checks.items() if not ok]
    return {
        "closeout_status": "closed" if not fail_reasons else "open",
        "checks": checks,
        "fail_reasons": fail_reasons,
    }
