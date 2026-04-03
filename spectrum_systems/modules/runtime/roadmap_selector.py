"""Deterministic roadmap batch selection and readiness validation (RDX-002)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema
from spectrum_systems.modules.runtime.roadmap_stop_reasons import (
    STOP_REASON_MISSING_REQUIRED_SIGNAL,
    STOP_REASON_NO_ELIGIBLE_BATCH,
)


class RoadmapSelectionError(ValueError):
    """Raised when roadmap selection cannot be computed safely."""


_REASON_READY = "READY_TO_RUN"
_REASON_NO_ELIGIBLE = "NO_ELIGIBLE_BATCH"
_REASON_DEP_INCOMPLETE = "DEPENDENCY_INCOMPLETE"
_REASON_SIGNAL_MISSING = "REQUIRED_SIGNAL_MISSING"
_REASON_HARD_GATE = "HARD_GATE_VIOLATED"
_REASON_EVAL_MISSING = "CONTROL_LOOP_EVAL_MISSING"
_REASON_TRACE_MISSING = "CONTROL_LOOP_TRACE_MISSING"
_REASON_SCHEMA_INVALID = "CONTROL_LOOP_SCHEMA_INVALID"
_REASON_AMBIGUOUS = "AMBIGUOUS_STATE"
_REASON_INVALID_ROADMAP = "INVALID_ROADMAP_STRUCTURE"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _validate_schema(instance: dict[str, Any], schema_name: str, *, label: str) -> None:
    schema = load_schema(schema_name)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda err: list(err.absolute_path))
    if errors:
        reason = "; ".join(error.message for error in errors)
        raise RoadmapSelectionError(f"{label} failed schema validation ({schema_name}): {reason}")


def _require_signal_set(system_signals: Any) -> set[str]:
    if not isinstance(system_signals, dict):
        raise RoadmapSelectionError("system_signals must be an object")
    raw = system_signals.get("signals", [])
    if not isinstance(raw, list):
        raise RoadmapSelectionError("system_signals.signals must be a list")
    if any(not isinstance(item, str) or not item.strip() for item in raw):
        raise RoadmapSelectionError("system_signals.signals entries must be non-empty strings")
    return {item.strip() for item in raw}


def _require_control_loop(system_signals: dict[str, Any]) -> dict[str, bool]:
    loop = system_signals.get("control_loop")
    if not isinstance(loop, dict):
        raise RoadmapSelectionError("system_signals.control_loop must be an object")

    required_keys = ("eval_present", "trace_present", "schema_valid")
    missing = [key for key in required_keys if key not in loop]
    if missing:
        missing_joined = ", ".join(sorted(missing))
        raise RoadmapSelectionError(f"system_signals.control_loop missing required keys: {missing_joined}")

    normalized: dict[str, bool] = {}
    for key in required_keys:
        value = loop[key]
        if not isinstance(value, bool):
            raise RoadmapSelectionError(f"system_signals.control_loop.{key} must be boolean")
        normalized[key] = value
    return normalized


def _collect_prior_hard_gates(prior_batches: list[dict[str, Any]], hard_gates: dict[str, Any]) -> list[str]:
    violations: list[str] = []
    for prior in prior_batches:
        if not prior.get("hard_gate_after"):
            continue
        batch_id = prior.get("batch_id")
        if not isinstance(batch_id, str) or not batch_id:
            violations.append("prior batch has invalid batch_id for hard gate evaluation")
            continue
        gate_state = hard_gates.get(batch_id, "pass")
        if gate_state not in {"pass", "fail"}:
            violations.append(f"hard gate state ambiguous for {batch_id}")
            continue
        if gate_state == "fail":
            violations.append(f"prior hard gate failed after {batch_id}")
    return violations


def validate_batch_readiness(batch: dict[str, Any], system_signals: dict[str, Any]) -> dict[str, Any]:
    """Validate whether a dependency-eligible batch is safe and ready to run."""
    reasons: list[str] = []
    blockers: list[str] = []

    if not isinstance(batch, dict):
        return {
            "ready_to_run": False,
            "readiness_reason_codes": [_REASON_AMBIGUOUS],
            "blocking_conditions": ["batch must be an object"],
        }

    dependency_status = batch.get("dependency_status")
    if not isinstance(dependency_status, dict):
        return {
            "ready_to_run": False,
            "readiness_reason_codes": [_REASON_AMBIGUOUS],
            "blocking_conditions": ["dependency_status mapping missing"],
        }

    incomplete_dependencies = sorted(dep for dep, status in dependency_status.items() if status != "completed")
    if incomplete_dependencies:
        reasons.append(_REASON_DEP_INCOMPLETE)
        blockers.append(f"incomplete dependencies: {', '.join(incomplete_dependencies)}")

    try:
        provided_signals = _require_signal_set(system_signals)
    except RoadmapSelectionError as exc:
        reasons.append(_REASON_AMBIGUOUS)
        blockers.append(str(exc))
        provided_signals = set()

    required_signals = batch.get("required_signals", [])
    if not isinstance(required_signals, list) or any(not isinstance(item, str) or not item.strip() for item in required_signals):
        reasons.append(_REASON_AMBIGUOUS)
        blockers.append("batch.required_signals must be a list of non-empty strings")
        required_signals = []

    missing_signals = sorted(signal for signal in required_signals if signal not in provided_signals)
    if missing_signals:
        reasons.append(_REASON_SIGNAL_MISSING)
        blockers.append(f"missing required signals: {', '.join(missing_signals)}")

    prior_batches = batch.get("prior_batches", [])
    hard_gates = system_signals.get("hard_gates", {}) if isinstance(system_signals, dict) else {}
    if not isinstance(prior_batches, list) or any(not isinstance(item, dict) for item in prior_batches):
        reasons.append(_REASON_AMBIGUOUS)
        blockers.append("prior_batches context missing or invalid")
    elif not isinstance(hard_gates, dict):
        reasons.append(_REASON_AMBIGUOUS)
        blockers.append("system_signals.hard_gates must be an object")
    else:
        violations = _collect_prior_hard_gates(prior_batches, hard_gates)
        if violations:
            reasons.append(_REASON_HARD_GATE)
            blockers.extend(violations)

    try:
        control_loop = _require_control_loop(system_signals)
    except RoadmapSelectionError as exc:
        reasons.append(_REASON_AMBIGUOUS)
        blockers.append(str(exc))
    else:
        if not control_loop["eval_present"]:
            reasons.append(_REASON_EVAL_MISSING)
            blockers.append("control loop invariant failed: eval missing")
        if not control_loop["trace_present"]:
            reasons.append(_REASON_TRACE_MISSING)
            blockers.append("control loop invariant failed: trace missing")
        if not control_loop["schema_valid"]:
            reasons.append(_REASON_SCHEMA_INVALID)
            blockers.append("control loop invariant failed: schema invalid")

    deduped_reasons = sorted(set(reasons))
    deduped_blockers = sorted(set(blockers))
    return {
        "ready_to_run": not deduped_reasons,
        "readiness_reason_codes": deduped_reasons,
        "blocking_conditions": deduped_blockers,
    }


def _build_batch_context(roadmap_artifact: dict[str, Any], candidate_index: int) -> dict[str, Any]:
    batches = roadmap_artifact["batches"]
    candidate = dict(batches[candidate_index])

    indexed_status = {
        entry["batch_id"]: entry["status"]
        for entry in batches
        if isinstance(entry, dict) and isinstance(entry.get("batch_id"), str)
    }
    dependency_status = {dep: indexed_status.get(dep, "missing") for dep in candidate.get("depends_on", [])}
    candidate["dependency_status"] = dependency_status
    candidate["prior_batches"] = [dict(row) for row in batches[:candidate_index]]
    return candidate


def select_next_batch(roadmap_artifact: dict[str, Any], system_signals: dict[str, Any]) -> str | None:
    """Select the next roadmap batch allowed to run, or ``None`` when no batch is eligible."""
    _validate_schema(roadmap_artifact, "roadmap_artifact", label="roadmap_artifact")

    batches = roadmap_artifact.get("batches", [])
    if not isinstance(batches, list):
        raise RoadmapSelectionError("roadmap_artifact.batches must be a list")

    for index, batch in enumerate(batches):
        if batch.get("status") != "not_started":
            continue

        candidate = _build_batch_context(roadmap_artifact, index)
        dependency_status = candidate["dependency_status"]
        if any(state != "completed" for state in dependency_status.values()):
            continue

        readiness = validate_batch_readiness(candidate, system_signals)
        if readiness["ready_to_run"]:
            return str(candidate["batch_id"])

        # Fail closed: first dependency-eligible batch blocks progression.
        return None

    return None


def build_roadmap_selection_result(
    roadmap_artifact: dict[str, Any],
    system_signals: dict[str, Any],
    *,
    evaluated_at: str | None = None,
) -> dict[str, Any]:
    """Create a deterministic ``roadmap_selection_result`` artifact."""
    _validate_schema(roadmap_artifact, "roadmap_artifact", label="roadmap_artifact")

    if not isinstance(system_signals, dict):
        raise RoadmapSelectionError("system_signals must be an object")

    batch_id = select_next_batch(roadmap_artifact, system_signals)

    reasons: list[str] = []
    blockers: list[str] = []

    batches = roadmap_artifact.get("batches", [])
    dependency_eligible_index: int | None = None
    for index, batch in enumerate(batches):
        if batch.get("status") != "not_started":
            continue
        candidate = _build_batch_context(roadmap_artifact, index)
        if all(state == "completed" for state in candidate["dependency_status"].values()):
            dependency_eligible_index = index
            readiness = validate_batch_readiness(candidate, system_signals)
            reasons = readiness["readiness_reason_codes"]
            blockers = readiness["blocking_conditions"]
            break

    stop_reason: str | None = None

    if batch_id is not None:
        ready_to_run = True
        reasons = [_REASON_READY]
        blockers = []
    elif dependency_eligible_index is None:
        ready_to_run = False
        reasons = [_REASON_NO_ELIGIBLE]
        blockers = ["no not_started batch has all dependencies completed"]
        stop_reason = STOP_REASON_NO_ELIGIBLE_BATCH
    else:
        ready_to_run = False
        if not reasons:
            reasons = [_REASON_AMBIGUOUS]
            blockers = ["dependency-eligible batch failed readiness with no reason codes"]
            stop_reason = STOP_REASON_NO_ELIGIBLE_BATCH
        elif _REASON_SIGNAL_MISSING in reasons:
            stop_reason = STOP_REASON_MISSING_REQUIRED_SIGNAL
        else:
            stop_reason = STOP_REASON_NO_ELIGIBLE_BATCH

    timestamp = evaluated_at or _utc_now()
    stop_reason_codes = [stop_reason] if isinstance(stop_reason, str) else []
    result = {
        "roadmap_id": roadmap_artifact["roadmap_id"],
        "selected_batch_id": batch_id,
        "ready_to_run": ready_to_run,
        "stop_reason": stop_reason,
        "stop_reason_codes": stop_reason_codes,
        "reason_codes": reasons,
        "blocking_conditions": blockers,
        "evaluated_at": timestamp,
        "input_hash": _canonical_hash(
            {
                "roadmap_artifact": roadmap_artifact,
                "system_signals": system_signals,
            }
        ),
    }

    _validate_schema(result, "roadmap_selection_result", label="roadmap_selection_result")
    return result


__all__ = [
    "RoadmapSelectionError",
    "build_roadmap_selection_result",
    "select_next_batch",
    "validate_batch_readiness",
]
