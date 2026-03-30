"""Deterministic, read-only cycle status and backlog observability builders."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema


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
    manifest = _load_json(manifest_path)
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


def build_cycle_backlog_snapshot(manifest_paths: list[str | Path], *, generated_at: str | None = None) -> dict[str, Any]:
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

    created = generated_at or datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")
    snapshot = {
        "artifact_type": "cycle_backlog_snapshot",
        "schema_version": "1.0.0",
        "generated_at": created,
        "cycle_count": len(statuses),
        "queues": {
            "active_cycles": sorted(active_cycles),
            "blocked_cycles": sorted(blocked_cycles),
            "certification_pending_cycles": sorted(certification_pending_cycles),
            "awaiting_review_cycles": sorted(awaiting_review_cycles),
            "awaiting_pqx_execution_cycles": sorted(awaiting_pqx_execution_cycles),
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
        "",
        "## Metrics",
        f"- count_by_state: `{json.dumps(metrics['count_by_state'], sort_keys=True)}`",
        f"- blocked_by_reason: `{json.dumps(metrics['blocked_by_reason'], sort_keys=True)}`",
        f"- average_execution_seconds: `{metrics['average_execution_seconds']}` (n={metrics['average_execution_seconds_sample_size']})",
        f"- open_critical_findings: {metrics['open_critical_findings']}",
        f"- open_blocker_findings: {metrics['open_blocker_findings']}",
        f"- certification_pass_count: {metrics['certification_pass_count']}",
        f"- certification_fail_count: {metrics['certification_fail_count']}",
    ]
    return "\n".join(lines) + "\n"
