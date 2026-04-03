"""Deterministic control authorization for roadmap-selected batch execution (RDX-003)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema


class RoadmapAuthorizationError(ValueError):
    """Raised when roadmap execution authorization cannot be computed safely."""


_DECISIONS = ("allow", "warn", "freeze", "block")

_REASON_AUTHORIZED = "AUTHORIZED"
_REASON_WARN = "AUTHORIZED_WITH_WARNINGS"
_REASON_NO_SELECTED = "NO_SELECTED_BATCH"
_REASON_BATCH_NOT_READY = "BATCH_NOT_READY"
_REASON_MISSING_SIGNAL = "MISSING_REQUIRED_SIGNAL"
_REASON_HARD_GATE = "HARD_GATE_UNMET"
_REASON_CERT_REQUIRED = "CERTIFICATION_REQUIRED"
_REASON_REVIEW_REQUIRED = "REVIEW_REQUIRED"
_REASON_EVAL_REQUIRED = "EVAL_REQUIRED"
_REASON_INVALID_ROADMAP = "INVALID_ROADMAP_ARTIFACT"
_REASON_INVALID_SELECTION = "INVALID_SELECTION_RESULT"
_REASON_TRACE_MISSING = "MISSING_TRACE_LINKAGE"
_REASON_REPLAY_MISMATCH = "REPLAY_MISMATCH"
_REASON_FREEZE = "CONTROL_FREEZE_CONDITION"
_REASON_BLOCK = "CONTROL_BLOCK_CONDITION"
_REASON_AMBIGUOUS = "AMBIGUOUS_INPUT"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _deterministic_authorization_id(payload: dict[str, Any]) -> str:
    digest = _canonical_hash(payload)[:12].upper()
    return f"REA-{digest}"


def _validate_schema(instance: dict[str, Any], schema_name: str, *, label: str) -> None:
    schema = load_schema(schema_name)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda err: list(err.absolute_path))
    if errors:
        reason = "; ".join(error.message for error in errors)
        raise RoadmapAuthorizationError(f"{label} failed schema validation ({schema_name}): {reason}")


def _coerce_signal_state(value: Any, *, allowed: set[str], field: str) -> str:
    text = str(value or "").strip().lower()
    if text not in allowed:
        raise RoadmapAuthorizationError(f"system_signals.{field} must be one of: {', '.join(sorted(allowed))}")
    return text


def _ensure_signal_payload(system_signals: Any) -> dict[str, Any]:
    if not isinstance(system_signals, dict):
        raise RoadmapAuthorizationError("system_signals must be an object")
    return dict(system_signals)


def _resolve_selected_batch(roadmap_artifact: dict[str, Any], selected_batch_id: str | None) -> dict[str, Any] | None:
    if selected_batch_id is None:
        return None
    batches = roadmap_artifact.get("batches", [])
    for batch in batches:
        if isinstance(batch, dict) and batch.get("batch_id") == selected_batch_id:
            return batch
    return None


def authorize_selected_batch(
    roadmap_artifact: dict[str, Any],
    roadmap_selection_result: dict[str, Any],
    system_signals: dict[str, Any],
    *,
    evaluated_at: str | None = None,
) -> dict[str, Any]:
    """Authorize or deny execution for a selected roadmap batch using governed control semantics."""
    reasons: set[str] = set()
    blockers: set[str] = set()
    followups: set[str] = set()
    warnings: list[str] = []

    roadmap_valid = True
    try:
        _validate_schema(roadmap_artifact, "roadmap_artifact", label="roadmap_artifact")
    except RoadmapAuthorizationError as exc:
        roadmap_valid = False
        reasons.add(_REASON_INVALID_ROADMAP)
        blockers.add(str(exc))
        followups.add("repair_invalid_artifact")

    selection_valid = True
    try:
        _validate_schema(roadmap_selection_result, "roadmap_selection_result", label="roadmap_selection_result")
    except RoadmapAuthorizationError as exc:
        selection_valid = False
        reasons.add(_REASON_INVALID_SELECTION)
        blockers.add(str(exc))
        followups.add("repair_invalid_artifact")

    signals = _ensure_signal_payload(system_signals)
    trace_id = str(signals.get("trace_id") or "").strip()
    if not trace_id:
        reasons.add(_REASON_TRACE_MISSING)
        blockers.add("system_signals.trace_id is required")
        followups.add("repair_trace_linkage")
    elif not trace_id.startswith("trace-"):
        reasons.add(_REASON_TRACE_MISSING)
        blockers.add("system_signals.trace_id must start with 'trace-'")
        followups.add("repair_trace_linkage")

    selected_batch_id = roadmap_selection_result.get("selected_batch_id") if selection_valid else None
    selected_batch = _resolve_selected_batch(roadmap_artifact, selected_batch_id if isinstance(selected_batch_id, str) else None)
    selected_batch_title = selected_batch.get("title") if isinstance(selected_batch, dict) else None

    if selection_valid and selected_batch_id is None:
        reasons.add(_REASON_NO_SELECTED)
        blockers.add("roadmap_selection_result.selected_batch_id is null")
        followups.add("refresh_roadmap_selection")

    if selection_valid and isinstance(selected_batch_id, str) and selected_batch is None:
        reasons.add(_REASON_INVALID_SELECTION)
        blockers.add("selected_batch_id not present in roadmap_artifact.batches")
        followups.add("repair_invalid_artifact")

    if selection_valid and roadmap_selection_result.get("ready_to_run") is False:
        reasons.add(_REASON_BATCH_NOT_READY)
        blockers.add("roadmap_selection_result.ready_to_run=false")

    raw_reason_codes = roadmap_selection_result.get("reason_codes") if selection_valid else []
    if isinstance(raw_reason_codes, list) and "REQUIRED_SIGNAL_MISSING" in raw_reason_codes:
        reasons.add(_REASON_MISSING_SIGNAL)
        blockers.add("selection reports REQUIRED_SIGNAL_MISSING")
        followups.add("provide_missing_signal")

    try:
        required_signals_satisfied = bool(signals["required_signals_satisfied"])
    except KeyError:
        reasons.add(_REASON_MISSING_SIGNAL)
        reasons.add(_REASON_AMBIGUOUS)
        blockers.add("system_signals.required_signals_satisfied is required")
        followups.add("provide_missing_signal")
        required_signals_satisfied = False
    if not required_signals_satisfied:
        reasons.add(_REASON_MISSING_SIGNAL)
        blockers.add("required signals are not satisfied")
        followups.add("provide_missing_signal")

    try:
        hard_gate_state = _coerce_signal_state(
            signals.get("hard_gate_state"), allowed={"pass", "fail", "unknown"}, field="hard_gate_state"
        )
    except RoadmapAuthorizationError as exc:
        hard_gate_state = "unknown"
        reasons.add(_REASON_AMBIGUOUS)
        blockers.add(str(exc))
    if hard_gate_state != "pass":
        reasons.add(_REASON_HARD_GATE)
        blockers.add(f"hard gate state is {hard_gate_state}")
        followups.add("resolve_hard_gate")

    def _consume_state(field: str, reason: str, followup: str) -> None:
        try:
            state = _coerce_signal_state(signals.get(field), allowed={"complete", "required", "unknown"}, field=field)
        except RoadmapAuthorizationError as exc:
            reasons.add(_REASON_AMBIGUOUS)
            blockers.add(str(exc))
            followups.add(followup)
            return
        if state != "complete":
            reasons.add(reason)
            blockers.add(f"{field} state is {state}")
            followups.add(followup)

    _consume_state("certification_state", _REASON_CERT_REQUIRED, "complete_certification")
    _consume_state("review_state", _REASON_REVIEW_REQUIRED, "complete_review")
    _consume_state("eval_state", _REASON_EVAL_REQUIRED, "complete_eval")

    try:
        replay_consistency = _coerce_signal_state(
            signals.get("replay_consistency"), allowed={"match", "mismatch", "indeterminate"}, field="replay_consistency"
        )
    except RoadmapAuthorizationError as exc:
        replay_consistency = "indeterminate"
        reasons.add(_REASON_AMBIGUOUS)
        blockers.add(str(exc))
    if replay_consistency in {"mismatch", "indeterminate"}:
        reasons.add(_REASON_REPLAY_MISMATCH)
        reasons.add(_REASON_FREEZE)
        blockers.add(f"replay consistency is {replay_consistency}")
        followups.add("resolve_replay_mismatch")

    freeze_condition = bool(signals.get("control_freeze_condition", False))
    if freeze_condition:
        reasons.add(_REASON_FREEZE)
        blockers.add("explicit control_freeze_condition=true")

    block_condition = bool(signals.get("control_block_condition", False))
    if block_condition:
        reasons.add(_REASON_BLOCK)
        blockers.add("explicit control_block_condition=true")

    warning_states = signals.get("warning_states", [])
    if isinstance(warning_states, list):
        warnings = sorted(str(item) for item in warning_states if str(item).strip())
    elif warning_states is not None:
        reasons.add(_REASON_AMBIGUOUS)
        blockers.add("system_signals.warning_states must be a list when provided")

    has_block = bool(
        reasons.intersection(
            {
                _REASON_NO_SELECTED,
                _REASON_BATCH_NOT_READY,
                _REASON_MISSING_SIGNAL,
                _REASON_HARD_GATE,
                _REASON_CERT_REQUIRED,
                _REASON_REVIEW_REQUIRED,
                _REASON_EVAL_REQUIRED,
                _REASON_INVALID_ROADMAP,
                _REASON_INVALID_SELECTION,
                _REASON_TRACE_MISSING,
                _REASON_BLOCK,
            }
        )
    )
    has_freeze = bool(reasons.intersection({_REASON_REPLAY_MISMATCH, _REASON_FREEZE, _REASON_AMBIGUOUS}))

    if has_block:
        decision = "block"
        authorized_to_run = False
    elif has_freeze:
        decision = "freeze"
        authorized_to_run = False
    elif warnings:
        decision = "warn"
        authorized_to_run = True
        reasons.add(_REASON_WARN)
        blockers.update(f"warning state: {item}" for item in warnings)
    else:
        decision = "allow"
        authorized_to_run = True
        reasons.add(_REASON_AUTHORIZED)

    if not followups:
        followups.add("none")
    elif "none" in followups and len(followups) > 1:
        followups.remove("none")

    timestamp = evaluated_at or _utc_now()
    input_payload = {
        "roadmap_artifact": roadmap_artifact,
        "roadmap_selection_result": roadmap_selection_result,
        "system_signals": signals,
    }
    input_hash = _canonical_hash(input_payload)

    source_refs_raw = signals.get("source_refs")
    if isinstance(source_refs_raw, list) and source_refs_raw:
        source_refs = sorted(str(item) for item in source_refs_raw if str(item).strip())
    else:
        source_refs = [
            "roadmap_artifact:inline",
            "roadmap_selection_result:inline",
        ]

    normalized_roadmap_id = roadmap_artifact.get("roadmap_id")
    if not isinstance(normalized_roadmap_id, str) or not normalized_roadmap_id:
        normalized_roadmap_id = roadmap_selection_result.get("roadmap_id")
    if not isinstance(normalized_roadmap_id, str) or not normalized_roadmap_id:
        normalized_roadmap_id = "INVALID-ROADMAP"

    artifact_seed = {
        "roadmap_id": normalized_roadmap_id,
        "selected_batch_id": selected_batch_id,
        "control_decision": decision,
        "authorized_to_run": authorized_to_run,
        "reason_codes": sorted(reasons),
        "blocking_conditions": sorted(blockers),
        "required_followups": sorted(followups),
        "evaluated_at": timestamp,
        "input_hash": input_hash,
        "trace_id": trace_id,
    }

    result = {
        "authorization_id": _deterministic_authorization_id(artifact_seed),
        "schema_version": "1.0.0",
        "roadmap_id": normalized_roadmap_id,
        "selected_batch_id": selected_batch_id if isinstance(selected_batch_id, str) else None,
        "selected_batch_title": selected_batch_title if isinstance(selected_batch_title, str) else None,
        "control_decision": decision,
        "authorized_to_run": authorized_to_run,
        "reason_codes": sorted(reasons),
        "blocking_conditions": sorted(blockers),
        "required_followups": sorted(followups),
        "evaluated_at": timestamp,
        "input_hash": input_hash,
        "trace_id": trace_id or "trace-missing",
        "source_refs": source_refs,
    }

    _validate_schema(result, "roadmap_execution_authorization", label="roadmap_execution_authorization")
    return result


def validate_roadmap_execution_authorization(payload: dict[str, Any]) -> None:
    _validate_schema(payload, "roadmap_execution_authorization", label="roadmap_execution_authorization")


def write_roadmap_execution_authorization(payload: dict[str, Any], output_path: Path) -> Path:
    validate_roadmap_execution_authorization(payload)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def read_roadmap_execution_authorization(path: Path) -> dict[str, Any]:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RoadmapAuthorizationError(f"roadmap_execution_authorization artifact not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RoadmapAuthorizationError(f"roadmap_execution_authorization artifact is not valid JSON: {path}") from exc

    if not isinstance(loaded, dict):
        raise RoadmapAuthorizationError("roadmap_execution_authorization artifact root must be a JSON object")
    validate_roadmap_execution_authorization(loaded)
    return loaded


__all__ = [
    "RoadmapAuthorizationError",
    "authorize_selected_batch",
    "read_roadmap_execution_authorization",
    "validate_roadmap_execution_authorization",
    "write_roadmap_execution_authorization",
]
