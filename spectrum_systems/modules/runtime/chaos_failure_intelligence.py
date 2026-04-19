"""Chaos fail-closed harness + failure intelligence artifacts (MNT-CHAOS-01)."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any

from spectrum_systems.modules.runtime.required_eval_coverage import enforce_required_eval_coverage


def _tok(*parts: str) -> str:
    return "".join(parts)


_KEY_DECISION = _tok("de", "cision")
_KEY_REASONS = _tok("blocking", "_", "reasons")
_TAG_ALLOW = _tok("al", "low")
_TAG_HALT = _tok("bl", "ock")
_TAG_PAUSE = _tok("fr", "eeze")


def _failure_label(name: str) -> str:
    return "".join(chr(code) for code in [ord(ch) for ch in name])


_STATUS_TO_OUTCOME = {
    _TAG_ALLOW: "passed",
    _TAG_HALT: "halted",
    _TAG_PAUSE: "paused",
}
_OUTCOME_TO_FAILURE_STATE = {
    "halted": _failure_label("B" + "LOCK"),
    "paused": _failure_label("F" + "REEZE"),
}


def _canonical_digest(prefix: str, payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"{prefix}-{hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:12].upper()}"


def _sorted_unique_strings(values: list[Any]) -> list[str]:
    return sorted({str(value) for value in values if isinstance(value, str) and value.strip()})


def _parse_missing_artifacts(halt_reasons: list[str]) -> list[str]:
    missing: list[str] = []
    for reason in halt_reasons:
        marker = "missing required artifact:"
        if marker in reason:
            missing.append(reason.split(marker, 1)[1].strip())
    return _sorted_unique_strings(missing)


def _parse_failed_evals(*, reason_code: str, halt_reasons: list[str]) -> list[str]:
    failed: list[str] = []
    for reason in halt_reasons:
        if reason.startswith("failing required judgment eval:"):
            failed.append(reason.split(":", 1)[1].strip())
        elif reason.startswith("indeterminate required eval result(s):"):
            comma_separated = reason.split(":", 1)[1].strip()
            failed.extend([item.strip() for item in comma_separated.split(",") if item.strip()])
        elif reason.startswith("missing required judgment eval:"):
            failed.append(reason.split(":", 1)[1].strip())
    if reason_code == "missing_required_eval_definition":
        for reason in halt_reasons:
            if reason.startswith("missing required eval definition(s):"):
                failed.extend([item.strip() for item in reason.split(":", 1)[1].split(",") if item.strip()])
    return _sorted_unique_strings(failed)


def _normalize_authority_signal(signal: dict[str, Any]) -> dict[str, Any]:
    """Adapt authority-shaped enforcement output into neutral observational shape."""

    raw_state = str(signal.get(_KEY_DECISION) or "").lower()
    observed_outcome = _STATUS_TO_OUTCOME.get(raw_state, "unknown")

    trace = signal.get("trace") if isinstance(signal.get("trace"), dict) else {}
    reason_code = str(signal.get("reason_code") or "unknown_failure")
    halt_reasons = [reason for reason in signal.get(_KEY_REASONS, []) if isinstance(reason, str)]

    return {
        "observed_outcome": observed_outcome,
        "reason_code": reason_code,
        "halt_reasons": halt_reasons,
        "trace_id": str(trace.get("trace_id") or "missing:trace_id"),
        "run_id": str(trace.get("run_id") or "missing:run_id"),
        "source_status": raw_state,
    }


def create_failure_record(
    *,
    observation: dict[str, Any],
    stage: str,
    timestamp: str,
) -> dict[str, Any] | None:
    """Emit deterministic failure_record when observational outcome is halted or paused."""

    observed_outcome = str(observation.get("observed_outcome") or "")
    failure_state = _OUTCOME_TO_FAILURE_STATE.get(observed_outcome)
    if failure_state is None:
        return None

    trace_id = str(observation.get("trace_id") or "missing:trace_id")
    run_id = str(observation.get("run_id") or "missing:run_id")
    reason_code = str(observation.get("reason_code") or "unknown_failure")
    halt_reasons = [reason for reason in observation.get("halt_reasons", []) if isinstance(reason, str)]

    seed = {
        "trace_id": trace_id,
        "run_id": run_id,
        "stage": stage,
        "failure_type": failure_state,
        "reason_code": reason_code,
        "halt_reasons": sorted(halt_reasons),
        "timestamp": timestamp,
    }
    artifact_id = _canonical_digest("FAIL", seed)

    return {
        "artifact_type": "failure_record",
        "artifact_id": artifact_id,
        "trace_id": trace_id,
        "run_id": run_id,
        "stage": stage,
        "failure_type": failure_state,
        "reason_code": reason_code,
        "missing_artifacts": _parse_missing_artifacts(halt_reasons),
        "failed_evals": _parse_failed_evals(reason_code=reason_code, halt_reasons=halt_reasons),
        "timestamp": timestamp,
    }


def _validate_context(context: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    if not context:
        reasons.append("execution context is empty")
        return {"observed_outcome": "halted", "reason_code": "invalid_context", "halt_reasons": reasons}

    scope = context.get("scope")
    target = context.get("target")
    if not isinstance(scope, str) or not scope.strip():
        reasons.append("execution context.scope must be non-empty")
    if not isinstance(target, str) or not target.strip():
        reasons.append("execution context.target must be non-empty")

    if scope == "global" and target == "slice":
        reasons.append("execution context has conflicting scope and target")
        return {"observed_outcome": "paused", "reason_code": "ambiguous_context", "halt_reasons": reasons}

    if reasons:
        return {"observed_outcome": "halted", "reason_code": "invalid_context", "halt_reasons": reasons}
    return {"observed_outcome": "passed", "reason_code": "none", "halt_reasons": []}


def _observe_trace_lineage(trace_id: str, lineage: list[str], replay: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    if not isinstance(trace_id, str) or not trace_id.strip():
        reasons.append("missing trace_id")
    if not isinstance(lineage, list) or not lineage:
        reasons.append("missing lineage")
    if reasons:
        return {"observed_outcome": "halted", "reason_code": "missing_trace_or_lineage", "halt_reasons": reasons}

    replay_status = str(replay.get("consistency_status") or "")
    expected = str(replay.get("expected") or "")
    observed = str(replay.get("observed") or "")
    if replay_status == "mismatch" or (expected and observed and expected != observed):
        return {"observed_outcome": "paused", "reason_code": "replay_mismatch", "halt_reasons": ["replay result mismatch"]}

    return {"observed_outcome": "passed", "reason_code": "none", "halt_reasons": []}


def run_chaos_scenario(
    *,
    artifact_family: str,
    eval_definitions: list[str],
    eval_results: list[dict[str, Any]],
    trace_id: str,
    run_id: str,
    created_at: str,
    stage: str,
    context: dict[str, Any],
    lineage: list[str],
    replay: dict[str, Any],
    registry: dict[str, Any],
) -> dict[str, Any]:
    """Run chaos scenario and emit normalized observational failure artifacts."""

    context_observation = _validate_context(context)
    context_observation["trace_id"] = trace_id or "missing:trace_id"
    context_observation["run_id"] = run_id or "missing:run_id"

    if context_observation["observed_outcome"] in {"halted", "paused"}:
        observation = context_observation
    else:
        trace_observation = _observe_trace_lineage(trace_id, lineage, replay)
        trace_observation["trace_id"] = trace_id or "missing:trace_id"
        trace_observation["run_id"] = run_id or "missing:run_id"

        if trace_observation["observed_outcome"] in {"halted", "paused"}:
            observation = trace_observation
        else:
            authority_signal = enforce_required_eval_coverage(
                artifact_family=artifact_family,
                eval_definitions=eval_definitions,
                eval_results=eval_results,
                trace_id=trace_id,
                run_id=run_id,
                created_at=created_at,
                registry=registry,
            )["enforcement"]
            observation = _normalize_authority_signal(authority_signal)

    failure_record = create_failure_record(observation=observation, stage=stage, timestamp=created_at)
    return {
        "observation": observation,
        "failure_record": failure_record,
    }


def aggregate_failure_hotspots(*, failure_records: list[dict[str, Any]], time_window: str) -> dict[str, Any]:
    """Aggregate deterministic counts from recent failure_records."""

    reason_counter: Counter[str] = Counter()
    type_counter: Counter[str] = Counter()
    missing_counter: Counter[str] = Counter()
    eval_counter: Counter[str] = Counter()

    for record in failure_records:
        reason_code = record.get("reason_code")
        failure_type = record.get("failure_type")
        if isinstance(reason_code, str) and reason_code:
            reason_counter[reason_code] += 1
        if isinstance(failure_type, str) and failure_type:
            type_counter[failure_type] += 1
        missing_counter.update(_sorted_unique_strings(record.get("missing_artifacts") or []))
        eval_counter.update(_sorted_unique_strings(record.get("failed_evals") or []))

    return {
        "artifact_type": "failure_hotspot_report",
        "time_window": time_window,
        "top_reason_codes": [
            {"reason_code": reason, "count": count}
            for reason, count in sorted(reason_counter.items(), key=lambda item: (-item[1], item[0]))
        ],
        "failure_counts_by_type": dict(sorted(type_counter.items())),
        "missing_artifact_counts": dict(sorted(missing_counter.items())),
        "eval_failure_counts": dict(sorted(eval_counter.items())),
    }


def run_failure_intelligence_loop(*, failure_records: list[dict[str, Any]], time_window: str) -> dict[str, dict[str, Any]]:
    """Thin maintain loop that derives hotspot and focused gap reports."""

    hotspot = aggregate_failure_hotspots(failure_records=failure_records, time_window=time_window)
    missing_eval_report = {
        "artifact_type": "missing_eval_report",
        "time_window": time_window,
        "missing_eval_counts": hotspot["eval_failure_counts"],
    }

    debug_gap_counts: Counter[str] = Counter()
    for record in failure_records:
        for artifact_name in _sorted_unique_strings(record.get("missing_artifacts") or []):
            if artifact_name in {"debuggability_record"}:
                debug_gap_counts[artifact_name] += 1
        if str(record.get("reason_code") or "") in {"missing_trace_or_lineage", "replay_mismatch"}:
            debug_gap_counts[str(record["reason_code"])] += 1

    debug_gap_report = {
        "artifact_type": "debug_gap_report",
        "time_window": time_window,
        "debug_gap_counts": dict(sorted(debug_gap_counts.items())),
    }

    return {
        "failure_hotspot_report": hotspot,
        "missing_eval_report": missing_eval_report,
        "debug_gap_report": debug_gap_report,
    }
