"""Deterministic, read-only cycle status and backlog observability builders."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema
from spectrum_systems.orchestration.cycle_manifest_validator import normalize_cycle_manifest


class CycleObservabilityError(ValueError):
    """Raised when cycle observability cannot be derived fail-closed."""


_BLOCKED_REASON_CATEGORIES = (
    "missing_required_artifact",
    "invalid_artifact_contract",
    "pqx_execution_failure",
    "review_missing",
    "review_invalid",
    "fix_generation_failure",
    "certification_missing",
    "certification_failed",
    "other",
)
def _load_json(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise CycleObservabilityError(f"expected object artifact: {path}")
    return payload


def _require_artifact(payload: dict[str, Any], schema_name: str) -> bool:
    try:
        _validate(payload, schema_name)
    except Exception:
        return False
    return True


def _safe_remediation_id(payload: dict[str, Any] | None) -> str:
    if not isinstance(payload, dict):
        return ""
    value = payload.get("remediation_id")
    return value if isinstance(value, str) else ""


def build_remediation_readiness_status(
    remediation_record: dict[str, Any] | None,
    *,
    evidence_artifact_refs: Sequence[str] | None = None,
    threshold_checks: Mapping[str, bool] | None = None,
    closure_record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Deterministic remediation closure readiness status builder."""
    remediation_valid = isinstance(remediation_record, dict) and _require_artifact(
        remediation_record, "judgment_operator_remediation_record"
    )
    remediation_id = _safe_remediation_id(remediation_record)
    lifecycle_state = (
        remediation_record.get("status")
        if remediation_valid and isinstance(remediation_record.get("status"), str)
        else "unknown"
    )
    required_evidence = sorted(
        set(remediation_record.get("required_evidence_artifacts", []))
    ) if remediation_valid else []
    provided_evidence = sorted(
        {
            ref
            for ref in (evidence_artifact_refs or [])
            if isinstance(ref, str) and ref.strip()
        }
    )
    missing_evidence = sorted(set(required_evidence) - set(provided_evidence))
    present_evidence = sorted(set(required_evidence) & set(provided_evidence))

    threshold_map = {
        key: bool(value)
        for key, value in dict(threshold_checks or {}).items()
        if isinstance(key, str) and key.strip()
    }
    required_thresholds = sorted(threshold_map.keys())
    thresholds_satisfied = sorted(key for key, passed in threshold_map.items() if passed)
    thresholds_not_satisfied = sorted(key for key, passed in threshold_map.items() if not passed)

    blocking_reasons: list[str] = []
    if not remediation_valid:
        blocking_reasons.append("invalid_artifact_contract")
    if lifecycle_state not in {"approved_for_closure"}:
        blocking_reasons.append("remediation_not_in_closure_state")
    if missing_evidence:
        blocking_reasons.append("missing_required_evidence")
    if not required_thresholds:
        blocking_reasons.append("missing_eval_result")
    if thresholds_not_satisfied:
        blocking_reasons.append("threshold_not_met")

    closure_eligible = remediation_valid and not blocking_reasons
    closure_valid = isinstance(closure_record, dict) and _require_artifact(
        closure_record, "judgment_remediation_closure_record"
    )
    trace = remediation_record.get("trace") if remediation_valid else {}
    trace_id = trace.get("trace_id") if isinstance(trace, dict) and isinstance(trace.get("trace_id"), str) else ""

    status = {
        "artifact_type": "judgment_remediation_readiness_status",
        "schema_version": "1.0.0",
        "remediation_id": remediation_id or "unknown",
        "current_lifecycle_state": lifecycle_state,
        "required_evidence_refs": required_evidence,
        "evidence_present_refs": present_evidence,
        "evidence_missing_refs": missing_evidence,
        "required_thresholds": required_thresholds,
        "thresholds_satisfied": thresholds_satisfied,
        "thresholds_not_satisfied": thresholds_not_satisfied,
        "closure_eligible": bool(closure_eligible),
        "blocking_reasons": sorted(set(blocking_reasons)),
        "trace": {
            "trace_id": trace_id,
            "remediation_record_id": remediation_record.get("artifact_id") if remediation_valid else "",
            "closure_record_id": closure_record.get("artifact_id") if closure_valid else "",
            "reinstatement_record_id": "",
        },
    }
    _validate(status, "judgment_remediation_readiness_status")
    return status


def build_reinstatement_readiness_status(
    remediation_record: dict[str, Any] | None,
    *,
    closure_record: dict[str, Any] | None = None,
    reinstatement_record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Deterministic reinstatement readiness status builder."""
    remediation_valid = isinstance(remediation_record, dict) and _require_artifact(
        remediation_record, "judgment_operator_remediation_record"
    )
    closure_valid = isinstance(closure_record, dict) and _require_artifact(
        closure_record, "judgment_remediation_closure_record"
    )
    reinstatement_valid = isinstance(reinstatement_record, dict) and _require_artifact(
        reinstatement_record, "judgment_progression_reinstatement_record"
    )

    remediation_id = _safe_remediation_id(remediation_record) or _safe_remediation_id(closure_record)
    lifecycle_state = remediation_record.get("status") if remediation_valid else "unknown"
    closure_approved = bool(closure_valid and closure_record.get("closure_decision") == "approved")
    remediation_closed = bool(remediation_valid and lifecycle_state == "closed")
    required_gates = ["remediation_closed", "closure_approved", "reinstatement_artifact_present"]
    gates_satisfied = [
        gate
        for gate, ok in (
            ("remediation_closed", remediation_closed),
            ("closure_approved", closure_approved),
            ("reinstatement_artifact_present", reinstatement_valid),
        )
        if ok
    ]
    gates_not_satisfied = sorted(set(required_gates) - set(gates_satisfied))
    resulting_eligible_state = (
        reinstatement_record.get("reinstatement_type")
        if reinstatement_valid and isinstance(reinstatement_record.get("reinstatement_type"), str)
        else (
            "unfreeze"
            if closure_valid and closure_record.get("resulting_system_effect") == "remain_frozen"
            else "unblock"
            if closure_valid and closure_record.get("resulting_system_effect") == "remain_blocked"
            else "continue"
        )
    )

    blocking_reasons: list[str] = []
    if not remediation_valid:
        blocking_reasons.append("invalid_artifact_contract")
    if not closure_valid:
        blocking_reasons.append("missing_closure_artifact")
    if not reinstatement_valid:
        blocking_reasons.append("missing_reinstatement_artifact")
    if not remediation_closed:
        blocking_reasons.append("remediation_not_closed")
    if closure_valid and not closure_approved:
        blocking_reasons.append("threshold_not_met")

    trace = remediation_record.get("trace") if remediation_valid else {}
    trace_id = trace.get("trace_id") if isinstance(trace, dict) and isinstance(trace.get("trace_id"), str) else ""
    status = {
        "artifact_type": "judgment_reinstatement_readiness_status",
        "schema_version": "1.0.0",
        "remediation_id": remediation_id or "unknown",
        "closure_artifact_present": bool(closure_valid),
        "closure_artifact_valid": bool(closure_valid),
        "reinstatement_artifact_present": bool(reinstatement_valid),
        "reinstatement_artifact_valid": bool(reinstatement_valid),
        "required_gates_satisfied": sorted(gates_satisfied),
        "required_gates_not_satisfied": gates_not_satisfied,
        "reinstatement_eligible": len(blocking_reasons) == 0,
        "blocking_reasons": sorted(set(blocking_reasons)),
        "resulting_eligible_state": resulting_eligible_state,
        "trace": {
            "trace_id": trace_id,
            "remediation_record_id": remediation_record.get("artifact_id") if remediation_valid else "",
            "closure_record_id": closure_record.get("artifact_id") if closure_valid else "",
            "reinstatement_record_id": reinstatement_record.get("artifact_id") if reinstatement_valid else "",
        },
    }
    _validate(status, "judgment_reinstatement_readiness_status")
    return status


def _validate(payload: dict[str, Any], schema_name: str) -> None:
    schema = load_schema(schema_name)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(payload)


def _require_string(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CycleObservabilityError(f"missing required field: {field}")
    return value


def _normalize_blocked_reason(reason: str) -> dict[str, str]:
    text = reason.strip()
    lowered = text.lower()

    if "missing required artifact" in lowered:
        category = "missing_required_artifact"
    elif "failed schema validation" in lowered or "invalid" in lowered and "artifact" in lowered:
        category = "invalid_artifact_contract"
    elif "pqx handoff failed" in lowered or "pqx fix re-entry failed" in lowered:
        category = "pqx_execution_failure"
    elif "dual implementation reviews required" in lowered or "roadmap approval required" in lowered:
        category = "review_missing"
    elif "implementation_review_artifact" in lowered or "roadmap_review_artifact" in lowered:
        category = "review_invalid"
    elif "fix roadmap generation failed" in lowered:
        category = "fix_generation_failure"
    elif "certification handoff requires" in lowered or "certification handoff missing" in lowered:
        category = "certification_missing"
    elif "done certification" in lowered:
        category = "certification_failed"
    else:
        category = "other"

    return {
        "reason_code": category,
        "reason_category": category,
        "detail": text,
    }


def _parse_iso8601(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _required_refs(manifest: dict[str, Any]) -> dict[str, str | list[str] | None]:
    return {
        "roadmap_artifact_ref": manifest.get("roadmap_artifact_path"),
        "roadmap_review_refs": manifest.get("roadmap_review_artifact_paths", []),
        "execution_report_refs": manifest.get("execution_report_paths", []),
        "implementation_review_refs": manifest.get("implementation_review_paths", []),
        "fix_roadmap_ref": manifest.get("fix_roadmap_path"),
        "fix_roadmap_markdown_ref": manifest.get("fix_roadmap_markdown_path"),
        "fix_execution_report_refs": manifest.get("fix_execution_report_paths", []),
        "certification_ref": manifest.get("certification_record_path"),
    }


def _build_phase_durations(manifest: dict[str, Any]) -> dict[str, Any]:
    started = _parse_iso8601(manifest.get("execution_started_at"))
    completed = _parse_iso8601(manifest.get("execution_completed_at"))
    updated = _parse_iso8601(manifest.get("updated_at"))

    execution_seconds: float | None = None
    if started and completed:
        execution_seconds = round((completed - started).total_seconds(), 3)

    if execution_seconds is None and (started or completed):
        raise CycleObservabilityError("incomplete timing data: execution_started_at and execution_completed_at are required together")

    return {
        "execution_seconds": execution_seconds,
        "has_complete_timing": execution_seconds is not None,
        "updated_at": updated.isoformat().replace("+00:00", "Z") if updated else manifest.get("updated_at"),
    }


def build_cycle_status(manifest_path: str | Path) -> dict[str, Any]:
    """Build schema-backed status summary for one cycle manifest."""
    manifest = normalize_cycle_manifest(_load_json(manifest_path))
    _validate(manifest, "cycle_manifest")

    cycle_id = _require_string(manifest.get("cycle_id"), field="cycle_id")
    current_state = _require_string(manifest.get("current_state"), field="current_state")
    next_action = _require_string(manifest.get("next_action"), field="next_action")
    updated_at = _require_string(manifest.get("updated_at"), field="updated_at")

    blocking_issues = manifest.get("blocking_issues", [])
    if not isinstance(blocking_issues, list) or not all(isinstance(item, str) for item in blocking_issues):
        raise CycleObservabilityError("blocking_issues must be a list of strings")

    if current_state == "blocked" and not blocking_issues:
        raise CycleObservabilityError("blocked state requires blocking_issues details")

    blocked_reasons = [_normalize_blocked_reason(issue) for issue in blocking_issues]
    blocked_reason_counts = dict(Counter(reason["reason_category"] for reason in blocked_reasons))

    refs = _required_refs(manifest)
    timing = _build_phase_durations(manifest)

    status = {
        "artifact_type": "cycle_status_artifact",
        "schema_version": "1.0.0",
        "cycle_id": cycle_id,
        "current_state": current_state,
        "next_action": next_action,
        "blocking_issues": blocking_issues,
        "blocked_reason_summary": {
            "counts_by_category": blocked_reason_counts,
            "reasons": blocked_reasons,
        },
        "artifact_refs": refs,
        "phase_metrics": {
            "execution_seconds": timing["execution_seconds"],
            "has_complete_timing": timing["has_complete_timing"],
            "execution_report_count": len(refs["execution_report_refs"] or []),
            "fix_execution_report_count": len(refs["fix_execution_report_refs"] or []),
        },
        "last_updated": updated_at,
        "status_markdown": render_cycle_status_markdown(
            cycle_id=cycle_id,
            current_state=current_state,
            next_action=next_action,
            blocking_issues=blocking_issues,
            blocked_reason_counts=blocked_reason_counts,
            refs=refs,
            last_updated=updated_at,
        ),
    }
    _validate(status, "cycle_status_artifact")
    return status


def render_cycle_status_markdown(
    *,
    cycle_id: str,
    current_state: str,
    next_action: str,
    blocking_issues: list[str],
    blocked_reason_counts: dict[str, int],
    refs: dict[str, Any],
    last_updated: str,
) -> str:
    """Render deterministic concise markdown summary for one cycle."""
    reason_line = (
        ", ".join(f"{key}={blocked_reason_counts[key]}" for key in sorted(blocked_reason_counts))
        if blocked_reason_counts
        else "none"
    )
    lines = [
        f"# Cycle Status — {cycle_id}",
        f"- current_state: `{current_state}`",
        f"- next_action: `{next_action}`",
        f"- blocked_reasons: {reason_line}",
        f"- blocking_issues_count: {len(blocking_issues)}",
        f"- last_updated: `{last_updated}`",
        "",
        "## Artifact refs",
        f"- roadmap: `{refs['roadmap_artifact_ref']}`",
        f"- roadmap_reviews: {len(refs['roadmap_review_refs'])}",
        f"- execution_reports: {len(refs['execution_report_refs'])}",
        f"- implementation_reviews: {len(refs['implementation_review_refs'])}",
        f"- fix_roadmap: `{refs['fix_roadmap_ref']}`",
        f"- fix_execution_reports: {len(refs['fix_execution_report_refs'])}",
        f"- certification: `{refs['certification_ref']}`",
    ]
    return "\n".join(lines) + "\n"


def _load_review_findings(manifest: dict[str, Any]) -> tuple[int, int]:
    critical = 0
    blocker = 0
    for path in manifest.get("implementation_review_paths", []):
        if not isinstance(path, str) or not path:
            continue
        artifact = _load_json(path)
        _validate(artifact, "implementation_review_artifact")
        findings = artifact.get("findings", [])
        if not isinstance(findings, list):
            continue
        for finding in findings:
            if not isinstance(finding, dict):
                continue
            severity = str(finding.get("severity", "")).lower()
            if severity == "critical":
                critical += 1
            if severity == "blocker":
                blocker += 1
    return critical, blocker


def build_cycle_backlog_snapshot(
    manifest_paths: list[str | Path],
    *,
    generated_at: str | None = None,
    remediation_records: Sequence[dict[str, Any]] | None = None,
    remediation_evidence_refs_by_id: Mapping[str, Sequence[str]] | None = None,
    remediation_threshold_checks_by_id: Mapping[str, Mapping[str, bool]] | None = None,
    closure_records: Sequence[dict[str, Any]] | None = None,
    reinstatement_records: Sequence[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build deterministic backlog snapshot + rollups over cycle manifests."""
    if not manifest_paths:
        raise CycleObservabilityError("at least one manifest path is required")

    statuses = [build_cycle_status(path) for path in sorted(str(path) for path in manifest_paths)]

    state_counter = Counter(status["current_state"] for status in statuses)
    blocked_counter = Counter()
    total_execution_seconds = 0.0
    execution_samples = 0
    cert_pass = 0
    cert_fail = 0
    critical_findings = 0
    blocker_findings = 0

    active_cycles: list[str] = []
    blocked_cycles: list[str] = []
    certification_pending_cycles: list[str] = []
    awaiting_review_cycles: list[str] = []
    awaiting_pqx_execution_cycles: list[str] = []
    open_remediations: list[str] = []
    remediations_ready_for_closure: list[str] = []
    remediations_blocked_on_missing_evidence: list[str] = []
    remediations_pending_review: list[str] = []
    reinstatement_ready_items: list[str] = []
    frozen_or_blocked_with_unresolved_remediation: list[str] = []

    for status, path in zip(statuses, sorted(str(path) for path in manifest_paths)):
        cycle_id = status["cycle_id"]
        state = status["current_state"]
        manifest = _load_json(path)

        if state != "certified_done":
            active_cycles.append(cycle_id)
        if state == "blocked":
            blocked_cycles.append(cycle_id)
        if state == "certification_pending":
            certification_pending_cycles.append(cycle_id)
        if state in {"roadmap_under_review", "execution_complete_unreviewed"}:
            awaiting_review_cycles.append(cycle_id)
        if state in {"execution_ready", "fix_roadmap_ready"}:
            awaiting_pqx_execution_cycles.append(cycle_id)

        for category, count in status["blocked_reason_summary"]["counts_by_category"].items():
            blocked_counter[category] += int(count)

        seconds = status["phase_metrics"]["execution_seconds"]
        if isinstance(seconds, (int, float)):
            total_execution_seconds += float(seconds)
            execution_samples += 1

        cert_status = manifest.get("certification_status")
        if cert_status == "passed":
            cert_pass += 1
        elif cert_status == "failed":
            cert_fail += 1

        c_count, b_count = _load_review_findings(manifest)
        critical_findings += c_count
        blocker_findings += b_count

    closure_by_remediation = {
        row.get("remediation_id"): row
        for row in (closure_records or [])
        if isinstance(row, dict) and isinstance(row.get("remediation_id"), str)
    }
    reinstatement_by_remediation = {
        row.get("trace", {}).get("remediation_id"): row
        for row in (reinstatement_records or [])
        if isinstance(row, dict)
        and isinstance(row.get("trace"), dict)
        and isinstance(row.get("trace", {}).get("remediation_id"), str)
    }

    for remediation in sorted(
        (row for row in (remediation_records or []) if isinstance(row, dict)),
        key=lambda row: str(row.get("remediation_id", "")),
    ):
        remediation_id = str(remediation.get("remediation_id") or "")
        if not remediation_id:
            continue
        closure = closure_by_remediation.get(remediation_id)
        reinstatement = reinstatement_by_remediation.get(remediation_id)
        readiness = build_remediation_readiness_status(
            remediation,
            evidence_artifact_refs=(remediation_evidence_refs_by_id or {}).get(remediation_id, []),
            threshold_checks=(remediation_threshold_checks_by_id or {}).get(remediation_id, {}),
            closure_record=closure,
        )
        reinstatement_status = build_reinstatement_readiness_status(
            remediation,
            closure_record=closure,
            reinstatement_record=reinstatement,
        )
        status = remediation.get("status")
        if status != "closed":
            open_remediations.append(remediation_id)
        if readiness["closure_eligible"]:
            remediations_ready_for_closure.append(remediation_id)
        if "missing_required_evidence" in readiness["blocking_reasons"]:
            remediations_blocked_on_missing_evidence.append(remediation_id)
        if status == "pending_review":
            remediations_pending_review.append(remediation_id)
        if reinstatement_status["reinstatement_eligible"]:
            reinstatement_ready_items.append(remediation_id)
        if not reinstatement_status["reinstatement_eligible"]:
            frozen_or_blocked_with_unresolved_remediation.append(remediation_id)

    created = generated_at or datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")
    snapshot = {
        "artifact_type": "cycle_backlog_snapshot",
        "schema_version": "1.1.0",
        "generated_at": created,
        "cycle_count": len(statuses),
        "queues": {
            "active_cycles": sorted(active_cycles),
            "blocked_cycles": sorted(blocked_cycles),
            "certification_pending_cycles": sorted(certification_pending_cycles),
            "awaiting_review_cycles": sorted(awaiting_review_cycles),
            "awaiting_pqx_execution_cycles": sorted(awaiting_pqx_execution_cycles),
            "open_remediations": sorted(open_remediations),
            "remediations_ready_for_closure": sorted(remediations_ready_for_closure),
            "remediations_blocked_on_missing_evidence": sorted(remediations_blocked_on_missing_evidence),
            "remediations_pending_review": sorted(remediations_pending_review),
            "reinstatement_ready_items": sorted(reinstatement_ready_items),
            "frozen_or_blocked_with_unresolved_remediation": sorted(frozen_or_blocked_with_unresolved_remediation),
        },
        "metrics": {
            "count_by_state": dict(sorted(state_counter.items())),
            "blocked_by_reason": dict(sorted(blocked_counter.items())),
            "average_execution_seconds": round(total_execution_seconds / execution_samples, 3) if execution_samples else None,
            "average_execution_seconds_sample_size": execution_samples,
            "open_critical_findings": critical_findings,
            "open_blocker_findings": blocker_findings,
            "certification_pass_count": cert_pass,
            "certification_fail_count": cert_fail,
            "open_remediation_count": len(open_remediations),
            "remediation_ready_for_closure_count": len(remediations_ready_for_closure),
            "remediation_blocked_missing_evidence_count": len(remediations_blocked_on_missing_evidence),
            "remediation_pending_review_count": len(remediations_pending_review),
            "reinstatement_ready_count": len(reinstatement_ready_items),
            "frozen_or_blocked_unresolved_remediation_count": len(frozen_or_blocked_with_unresolved_remediation),
        },
        "cycle_status_refs": [str(path) for path in sorted(str(path) for path in manifest_paths)],
        "summary_markdown": render_backlog_markdown(
            cycle_count=len(statuses),
            queues={
                "active_cycles": sorted(active_cycles),
                "blocked_cycles": sorted(blocked_cycles),
                "certification_pending_cycles": sorted(certification_pending_cycles),
                "awaiting_review_cycles": sorted(awaiting_review_cycles),
                "awaiting_pqx_execution_cycles": sorted(awaiting_pqx_execution_cycles),
                "open_remediations": sorted(open_remediations),
                "remediations_ready_for_closure": sorted(remediations_ready_for_closure),
                "remediations_blocked_on_missing_evidence": sorted(remediations_blocked_on_missing_evidence),
                "remediations_pending_review": sorted(remediations_pending_review),
                "reinstatement_ready_items": sorted(reinstatement_ready_items),
                "frozen_or_blocked_with_unresolved_remediation": sorted(frozen_or_blocked_with_unresolved_remediation),
            },
            metrics={
                "count_by_state": dict(sorted(state_counter.items())),
                "blocked_by_reason": dict(sorted(blocked_counter.items())),
                "average_execution_seconds": round(total_execution_seconds / execution_samples, 3) if execution_samples else None,
                "average_execution_seconds_sample_size": execution_samples,
                "open_critical_findings": critical_findings,
                "open_blocker_findings": blocker_findings,
                "certification_pass_count": cert_pass,
                "certification_fail_count": cert_fail,
                "open_remediation_count": len(open_remediations),
                "remediation_ready_for_closure_count": len(remediations_ready_for_closure),
                "remediation_blocked_missing_evidence_count": len(remediations_blocked_on_missing_evidence),
                "remediation_pending_review_count": len(remediations_pending_review),
                "reinstatement_ready_count": len(reinstatement_ready_items),
                "frozen_or_blocked_unresolved_remediation_count": len(frozen_or_blocked_with_unresolved_remediation),
            },
            generated_at=created,
        ),
    }
    _validate(snapshot, "cycle_backlog_snapshot")
    return snapshot


def render_backlog_markdown(*, cycle_count: int, queues: dict[str, list[str]], metrics: dict[str, Any], generated_at: str) -> str:
    """Render deterministic concise markdown summary for backlog snapshot."""
    lines = [
        "# Cycle Backlog Snapshot",
        f"- generated_at: `{generated_at}`",
        f"- cycle_count: {cycle_count}",
        f"- active_cycles: {len(queues['active_cycles'])}",
        f"- blocked_cycles: {len(queues['blocked_cycles'])}",
        f"- certification_pending_cycles: {len(queues['certification_pending_cycles'])}",
        f"- awaiting_review_cycles: {len(queues['awaiting_review_cycles'])}",
        f"- awaiting_pqx_execution_cycles: {len(queues['awaiting_pqx_execution_cycles'])}",
        f"- open_remediations: {len(queues['open_remediations'])}",
        f"- remediations_ready_for_closure: {len(queues['remediations_ready_for_closure'])}",
        f"- remediations_blocked_on_missing_evidence: {len(queues['remediations_blocked_on_missing_evidence'])}",
        f"- remediations_pending_review: {len(queues['remediations_pending_review'])}",
        f"- reinstatement_ready_items: {len(queues['reinstatement_ready_items'])}",
        f"- frozen_or_blocked_with_unresolved_remediation: {len(queues['frozen_or_blocked_with_unresolved_remediation'])}",
        "",
        "## Metrics",
        f"- count_by_state: `{json.dumps(metrics['count_by_state'], sort_keys=True)}`",
        f"- blocked_by_reason: `{json.dumps(metrics['blocked_by_reason'], sort_keys=True)}`",
        f"- average_execution_seconds: `{metrics['average_execution_seconds']}` (n={metrics['average_execution_seconds_sample_size']})",
        f"- open_critical_findings: {metrics['open_critical_findings']}",
        f"- open_blocker_findings: {metrics['open_blocker_findings']}",
        f"- certification_pass_count: {metrics['certification_pass_count']}",
        f"- certification_fail_count: {metrics['certification_fail_count']}",
        f"- open_remediation_count: {metrics['open_remediation_count']}",
        f"- remediation_ready_for_closure_count: {metrics['remediation_ready_for_closure_count']}",
        f"- remediation_blocked_missing_evidence_count: {metrics['remediation_blocked_missing_evidence_count']}",
        f"- remediation_pending_review_count: {metrics['remediation_pending_review_count']}",
        f"- reinstatement_ready_count: {metrics['reinstatement_ready_count']}",
        f"- frozen_or_blocked_unresolved_remediation_count: {metrics['frozen_or_blocked_unresolved_remediation_count']}",
    ]
    return "\n".join(lines) + "\n"
