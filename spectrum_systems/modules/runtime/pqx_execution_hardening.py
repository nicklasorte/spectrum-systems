"""PQX bounded execution hardening foundation (PQX-01..PQX-09)."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Mapping

from spectrum_systems.contracts import validate_artifact


class PQXExecutionHardeningError(ValueError):
    """Raised when PQX hardening checks fail closed."""


_ALLOWED_TRANSITIONS = {
    "queued": {"running", "blocked"},
    "running": {"completed", "failed", "blocked", "review_required"},
    "review_required": {"completed", "failed", "blocked"},
    "failed": {"running", "blocked"},
    "blocked": set(),
    "completed": set(),
}
_TERMINAL_STATES = {"completed", "failed", "blocked"}


def _stable_hash(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _require_non_empty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PQXExecutionHardeningError(f"{field} must be a non-empty string")
    return value.strip()


def _freshness_status(wrapper: Mapping[str, Any], *, max_age_hours: int = 24) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    freshness = wrapper.get("freshness")
    if not isinstance(freshness, Mapping):
        return False, ["wrapper_freshness_missing"]
    status = str(freshness.get("status") or "")
    age_hours = freshness.get("age_hours")
    if status in {"stale", "expired", "mismatch"}:
        reasons.append("wrapper_stale")
    if not isinstance(age_hours, (int, float)):
        reasons.append("wrapper_age_missing")
    elif float(age_hours) > float(max_age_hours):
        reasons.append("wrapper_age_exceeded")
    return len(reasons) == 0, reasons


def enforce_execution_transition(*, prior_state: str, next_state: str) -> dict[str, Any]:
    allowed = _ALLOWED_TRANSITIONS.get(prior_state)
    if allowed is None:
        raise PQXExecutionHardeningError(f"unknown prior_state: {prior_state}")
    if next_state not in allowed:
        raise PQXExecutionHardeningError(f"invalid transition {prior_state}->{next_state}")
    reason = "terminal_outcome_reached" if next_state in _TERMINAL_STATES else "progression_accepted"
    return {
        "prior_state": prior_state,
        "next_state": next_state,
        "reason_code": reason,
        "terminal": next_state in _TERMINAL_STATES,
    }


def build_pqx_execution_eval_result(
    *,
    run_id: str,
    trace_id: str,
    slice_id: str,
    wrapper: Mapping[str, Any],
    tpa_slice_artifact: Mapping[str, Any],
    top_level_conductor_run_artifact: Mapping[str, Any],
    execution_result: Mapping[str, Any],
    review_handoff: Mapping[str, Any] | None,
    prior_attempts: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    _require_non_empty_string(run_id, "run_id")
    _require_non_empty_string(trace_id, "trace_id")
    _require_non_empty_string(slice_id, "slice_id")

    fail_reasons: list[str] = []
    checks: dict[str, bool] = {}

    checks["wrapper_present"] = isinstance(wrapper, Mapping) and wrapper.get("artifact_type") == "codex_pqx_task_wrapper"
    checks["tpa_slice_present"] = isinstance(tpa_slice_artifact, Mapping) and tpa_slice_artifact.get("artifact_type") == "tpa_slice_artifact"
    checks["tlc_present"] = isinstance(top_level_conductor_run_artifact, Mapping) and top_level_conductor_run_artifact.get("artifact_type") == "top_level_conductor_run_artifact"

    lineage = list(wrapper.get("lineage_path") or []) if isinstance(wrapper, Mapping) else []
    checks["lineage_valid"] = lineage == ["AEX", "TLC", "TPA", "PQX"]

    scope_allowlist = set(
        tpa_slice_artifact.get("allowed_scope", []) if isinstance(tpa_slice_artifact.get("allowed_scope"), list) else []
    )
    changed_paths = execution_result.get("changed_paths", []) if isinstance(execution_result.get("changed_paths"), list) else []
    if not changed_paths:
        checks["scope_compliant"] = True
    elif scope_allowlist:
        checks["scope_compliant"] = set(changed_paths).issubset(scope_allowlist)
    else:
        checks["scope_compliant"] = False

    budget = tpa_slice_artifact.get("complexity_budget") if isinstance(tpa_slice_artifact.get("complexity_budget"), Mapping) else {}
    max_units = int(budget.get("max_units", 0) or 0)
    consumed_units = int(execution_result.get("complexity_units", 0) or 0)
    checks["budget_compliant"] = max_units > 0 and consumed_units <= max_units

    checks["artifact_completeness"] = all(
        isinstance(execution_result.get(key), str) and str(execution_result.get(key)).strip()
        for key in ("slice_execution_record_ref", "audit_bundle_ref", "replay_result_ref")
    )
    checks["trace_completeness"] = isinstance(execution_result.get("trace_refs"), list) and len(execution_result.get("trace_refs", [])) >= 2
    checks["execution_path_correctness"] = execution_result.get("execution_path") in {"bounded", "bounded_fix", "bounded_replay"}
    checks["candidate_only_readiness"] = not bool(execution_result.get("closure_authority_requested"))

    fresh, freshness_reasons = _freshness_status(wrapper)
    checks["wrapper_fresh"] = fresh

    expected_fix_ref = str(review_handoff.get("fix_slice_ref") or "") if isinstance(review_handoff, Mapping) else ""
    actual_fix_ref = str(wrapper.get("fix_slice_ref") or "") if isinstance(wrapper, Mapping) else ""
    checks["review_to_execution_integrity"] = (not expected_fix_ref) or expected_fix_ref == actual_fix_ref

    checks["no_op_success_guard"] = not (
        execution_result.get("execution_status") == "success"
        and int(execution_result.get("meaningful_output_count", 0) or 0) <= 0
    )

    prior = prior_attempts or []
    retries = [item for item in prior if item.get("slice_id") == slice_id]
    no_improve = len(retries) >= 2 and len({str(item.get("result_fingerprint") or "") for item in retries[-2:]}) == 1
    checks["retry_loop_guard"] = not no_improve

    for key, ok in checks.items():
        if not ok:
            fail_reasons.append(key)
    fail_reasons.extend(freshness_reasons)

    status = "pass" if not fail_reasons else "fail"
    eval_id = f"pqx-eval-{_stable_hash([run_id, trace_id, slice_id, checks])[:12]}"
    artifact = {
        "artifact_type": "pqx_execution_eval_result",
        "schema_version": "1.0.0",
        "eval_id": eval_id,
        "run_id": run_id,
        "trace_id": trace_id,
        "slice_id": slice_id,
        "status": status,
        "checks": checks,
        "fail_reasons": sorted(set(fail_reasons)),
        "generated_at": _iso_now(),
    }
    validate_artifact(artifact, "pqx_execution_eval_result")
    return artifact


def build_pqx_execution_readiness_record(*, eval_result: Mapping[str, Any]) -> dict[str, Any]:
    readiness_id = f"pqx-readiness-{_stable_hash(eval_result)[:12]}"
    artifact = {
        "artifact_type": "pqx_execution_readiness_record",
        "schema_version": "1.0.0",
        "readiness_id": readiness_id,
        "eval_result_ref": f"pqx_execution_eval_result:{eval_result.get('eval_id')}",
        "status": "candidate_ready" if eval_result.get("status") == "pass" else "not_ready",
        "non_authority_assertions": [
            "no_closure_authority",
            "no_promotion_authority",
            "no_enforcement_authority",
        ],
        "generated_at": _iso_now(),
    }
    validate_artifact(artifact, "pqx_execution_readiness_record")
    return artifact


def validate_execution_replay(*, baseline: Mapping[str, Any], replay: Mapping[str, Any]) -> dict[str, Any]:
    basis = {
        "wrapper": baseline.get("wrapper_fingerprint"),
        "tpa": baseline.get("tpa_fingerprint"),
        "result": baseline.get("result_fingerprint"),
        "terminal_state": baseline.get("terminal_state"),
    }
    replay_basis = {
        "wrapper": replay.get("wrapper_fingerprint"),
        "tpa": replay.get("tpa_fingerprint"),
        "result": replay.get("result_fingerprint"),
        "terminal_state": replay.get("terminal_state"),
    }
    return {
        "is_match": basis == replay_basis,
        "baseline_fingerprint": _stable_hash(basis),
        "replay_fingerprint": _stable_hash(replay_basis),
        "reason_codes": [] if basis == replay_basis else ["replay_mismatch_detected"],
    }


def build_pqx_execution_conflict_record(*, eval_result: Mapping[str, Any]) -> dict[str, Any]:
    conflict_id = f"pqx-conflict-{_stable_hash(eval_result)[:12]}"
    artifact = {
        "artifact_type": "pqx_execution_conflict_record",
        "schema_version": "1.0.0",
        "conflict_id": conflict_id,
        "eval_result_ref": f"pqx_execution_eval_result:{eval_result.get('eval_id')}",
        "conflict_type": "execution_integrity_violation",
        "reason_codes": list(eval_result.get("fail_reasons") or []),
        "materiality": "material",
        "generated_at": _iso_now(),
    }
    validate_artifact(artifact, "pqx_execution_conflict_record")
    return artifact


def build_execution_effectiveness_record(*, execution_result: Mapping[str, Any], eval_result: Mapping[str, Any]) -> dict[str, Any]:
    artifact = {
        "artifact_type": "pqx_execution_effectiveness_record",
        "schema_version": "1.0.0",
        "record_id": f"pqx-effectiveness-{_stable_hash([execution_result, eval_result])[:12]}",
        "slice_id": execution_result.get("slice_id"),
        "intended_outcome_ref": execution_result.get("intended_outcome_ref"),
        "outcome_status": "effective" if eval_result.get("status") == "pass" else "ineffective",
        "fallout_level": "low" if eval_result.get("status") == "pass" else "elevated",
        "generated_at": _iso_now(),
    }
    validate_artifact(artifact, "pqx_execution_effectiveness_record")
    return artifact


def build_execution_recurrence_record(*, run_id: str, history: list[Mapping[str, Any]]) -> dict[str, Any]:
    motifs: Counter[str] = Counter()
    for row in history:
        for reason in row.get("fail_reasons", []):
            motifs[f"failure:{reason}"] += 1
        if row.get("retry_loop_detected"):
            motifs["retry_loop"] += 1
        if "wrapper_stale" in row.get("fail_reasons", []):
            motifs["stale_fixture"] += 1
    grouped = [{"motif": key, "count": count} for key, count in sorted(motifs.items())]
    artifact = {
        "artifact_type": "pqx_execution_recurrence_record",
        "schema_version": "1.0.0",
        "record_id": f"pqx-recurrence-{_stable_hash([run_id, grouped])[:12]}",
        "run_id": run_id,
        "motif_groups": grouped,
        "generated_at": _iso_now(),
    }
    validate_artifact(artifact, "pqx_execution_recurrence_record")
    return artifact


def build_execution_bundle(
    *,
    run_id: str,
    trace_id: str,
    wrapper_ref: str,
    tpa_ref: str,
    tlc_ref: str,
    eval_result: Mapping[str, Any],
    readiness_record: Mapping[str, Any],
    replay_validation: Mapping[str, Any],
    effectiveness_record: Mapping[str, Any],
    recurrence_record: Mapping[str, Any],
) -> dict[str, Any]:
    artifact = {
        "artifact_type": "pqx_execution_bundle",
        "schema_version": "1.0.0",
        "bundle_id": f"pqx-exec-bundle-{_stable_hash([run_id, trace_id, wrapper_ref, tpa_ref, tlc_ref])[:12]}",
        "run_id": run_id,
        "trace_id": trace_id,
        "wrapper_ref": wrapper_ref,
        "tpa_slice_artifact_ref": tpa_ref,
        "top_level_conductor_run_artifact_ref": tlc_ref,
        "eval_result_ref": f"pqx_execution_eval_result:{eval_result.get('eval_id')}",
        "readiness_ref": f"pqx_execution_readiness_record:{readiness_record.get('readiness_id')}",
        "replay_validation": deepcopy(dict(replay_validation)),
        "effectiveness_ref": f"pqx_execution_effectiveness_record:{effectiveness_record.get('record_id')}",
        "recurrence_ref": f"pqx_execution_recurrence_record:{recurrence_record.get('record_id')}",
        "generated_at": _iso_now(),
    }
    validate_artifact(artifact, "pqx_execution_bundle")
    return artifact


def run_boundary_redteam_round(*, round_id: str, base_fixture: Mapping[str, Any]) -> dict[str, Any]:
    fixtures = []
    base = deepcopy(dict(base_fixture))
    fixtures.append(("baseline", base))

    lineage_bypass = deepcopy(base)
    lineage_bypass.setdefault("wrapper", {})["lineage_path"] = ["AEX", "TPA", "PQX"]
    fixtures.append(("lineage_bypass", lineage_bypass))

    stale_wrapper = deepcopy(base)
    stale_wrapper.setdefault("wrapper", {})["freshness"] = {"status": "stale", "age_hours": 72}
    fixtures.append(("stale_wrapper", stale_wrapper))

    artifact_omission = deepcopy(base)
    artifact_omission.setdefault("execution_result", {}).pop("audit_bundle_ref", None)
    fixtures.append(("artifact_omission", artifact_omission))

    no_op = deepcopy(base)
    no_op.setdefault("execution_result", {})["meaningful_output_count"] = 0
    fixtures.append(("noop_success", no_op))

    outcomes: list[dict[str, Any]] = []
    exploits: list[dict[str, Any]] = []
    for fixture_id, fixture in fixtures:
        eval_result = build_pqx_execution_eval_result(
            run_id=str(fixture["run_id"]),
            trace_id=str(fixture["trace_id"]),
            slice_id=str(fixture["slice_id"]),
            wrapper=dict(fixture["wrapper"]),
            tpa_slice_artifact=dict(fixture["tpa_slice_artifact"]),
            top_level_conductor_run_artifact=dict(fixture["top_level_conductor_run_artifact"]),
            execution_result=dict(fixture["execution_result"]),
            review_handoff=fixture.get("review_handoff"),
            prior_attempts=list(fixture.get("prior_attempts") or []),
        )
        outcomes.append({"fixture_id": fixture_id, "status": eval_result["status"], "fail_reasons": eval_result["fail_reasons"]})
        if fixture_id != "baseline" and eval_result["status"] == "pass":
            exploits.append({"fixture_id": fixture_id, "exploit": "unexpected_pass"})

    return {
        "artifact_type": "pqx_redteam_round",
        "round_id": round_id,
        "status": "pass" if not exploits else "fail",
        "outcomes": outcomes,
        "exploits": exploits,
    }
