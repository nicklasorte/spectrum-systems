"""Trace Replay Engine (BP).

Provides deterministic replay of prior execution traces for debugging,
audit, and learning workflows.

Design principles
-----------------
- Fail closed:  missing or inconsistent prerequisites block replay rather than
  silently proceeding with degraded state.
- Schema-governed:  the replay result artifact is validated against
  ``replay_result.schema.json`` before being returned.
- Deterministic where possible:  all IDs derived from the original trace;
  non-deterministic elements are explicitly recorded in ``determinism_notes``.
- No hidden re-derivation:  replay operates from the recorded trace state, not
  from inferred or re-computed inputs.
- No database:  integrates with the file-backed ``trace_store`` for loading
  persisted traces.

Replay model
------------
A replay record is built from:
  - The persisted trace (via trace_store.load_trace)
  - The list of spans in original execution order

Each span in the original trace is replayed as a discrete step.  Steps are
executed sequentially.  The overall replay status is determined by the
aggregate step outcomes.

The replay result artifact records:
  - Which steps were executed and their outcomes
  - A comparison of replay span statuses against original span statuses
  - Any non-deterministic elements encountered

Public API
----------
build_replay_record(trace_id, ...)               → replay_record (dict)
validate_replay_prerequisites(trace_id, ...)     → list[str]  (empty = valid)
execute_replay(trace_id, ...)                    → replay_result (dict)
compare_replay_outputs(original, replayed)       → output_comparison (dict)
validate_replay_result(result)                   → list[str]  (empty = valid)
"""

from __future__ import annotations

import json
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema
from spectrum_systems.modules.runtime.drift_detection_engine import detect_drift
from spectrum_systems.modules.runtime.provenance import (
    build_canonical_provenance,
    revalidate_mutated_artifact,
)
from spectrum_systems.modules.runtime.trace_store import (
    TraceNotFoundError as StoreTraceNotFoundError,
    TraceStoreError,
    load_trace,
    persist_trace,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCHEMA_VERSION: str = "1.0.0"
ARTIFACT_TYPE: str = "replay_result"

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCHEMA_DIR = _REPO_ROOT / "contracts" / "schemas"
_REPLAY_RESULT_SCHEMA_PATH = _SCHEMA_DIR / "replay_result.schema.json"

# Known non-deterministic span fields (timestamps are always non-deterministic)
_NON_DETERMINISTIC_FIELDS = frozenset({"start_time", "end_time"})
_SUPPORTED_GOVERNED_ARTIFACT_TYPES = frozenset({"eval_summary", "failure_eval_case"})


_LEGACY_REPLAY_RESULT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "artifact_type",
        "schema_version",
        "replay_id",
        "source_trace_id",
        "replayed_at",
        "status",
        "prerequisites_valid",
        "prerequisite_errors",
        "steps_executed",
        "output_comparison",
        "determinism_notes",
        "context",
    ],
    "properties": {
        "artifact_type": {"const": "replay_result"},
        "schema_version": {"const": "1.0.0"},
        "replay_id": {"type": "string", "minLength": 1},
        "source_trace_id": {"type": "string", "minLength": 1},
        "replayed_at": {"type": "string", "format": "date-time"},
        "status": {"type": "string"},
        "prerequisites_valid": {"type": "boolean"},
        "prerequisite_errors": {"type": "array"},
        "steps_executed": {"type": "array"},
        "output_comparison": {"type": "object"},
        "determinism_notes": {"type": "array"},
        "context": {"type": "object"},
    },
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


def _load_replay_result_schema() -> Dict[str, Any]:
    return json.loads(_REPLAY_RESULT_SCHEMA_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_replay_record(
    trace_id: str,
    base_dir: Optional[Path] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a replay record from a persisted trace.

    Loads the trace from the file-backed store and assembles a replay record
    containing the full span list in execution order.

    Parameters
    ----------
    trace_id:
        The trace to replay.
    base_dir:
        Override the trace store directory (primarily for testing).
    context:
        Optional caller-supplied context metadata (e.g. triggered_by).

    Returns
    -------
    dict
        A replay record with keys:
        - ``trace_id``: the source trace ID
        - ``spans``: ordered list of span dicts from the original trace
        - ``artifacts``: artifact attachments from the original trace
        - ``context``: merged context (trace + caller)
        - ``envelope``: the raw persisted envelope (for auditability)

    Raises
    ------
    ReplayPrerequisiteError
        If the trace cannot be loaded or is structurally incomplete.
    """
    errors = validate_replay_prerequisites(trace_id, base_dir=base_dir)
    if errors:
        raise ReplayPrerequisiteError(
            f"build_replay_record: prerequisites not met for trace '{trace_id}': "
            + "; ".join(errors)
        )

    envelope = load_trace(trace_id, base_dir=base_dir)
    inner_trace = envelope["trace"]

    merged_context = dict(inner_trace.get("context") or {})
    if context:
        merged_context.update(context)

    return {
        "trace_id": trace_id,
        "spans": deepcopy(inner_trace.get("spans") or []),
        "artifacts": deepcopy(inner_trace.get("artifacts") or []),
        "context": merged_context,
        "envelope": envelope,
    }


def validate_replay_prerequisites(
    trace_id: str,
    base_dir: Optional[Path] = None,
) -> List[str]:
    """Validate that all prerequisites for replaying *trace_id* are met.

    Prerequisites
    -------------
    1. ``trace_id`` must be a non-empty string.
    2. A persisted trace for ``trace_id`` must exist in the store.
    3. The stored envelope must pass schema validation.
    4. The inner trace must contain at least one span.

    Parameters
    ----------
    trace_id:
        The trace to validate.
    base_dir:
        Override the trace store directory (primarily for testing).

    Returns
    -------
    list[str]
        Empty if all prerequisites are satisfied.  Non-empty list of error
        messages if any prerequisite fails.  Callers MUST block execution when
        the list is non-empty.
    """
    errors: List[str] = []

    if not trace_id or not isinstance(trace_id, str):
        errors.append("validate_replay_prerequisites: trace_id must be a non-empty string")
        return errors  # Cannot proceed without a valid trace_id

    try:
        envelope = load_trace(trace_id, base_dir=base_dir)
    except StoreTraceNotFoundError:
        errors.append(
            f"validate_replay_prerequisites: no persisted trace found for trace_id '{trace_id}'"
        )
        return errors
    except TraceStoreError as exc:
        errors.append(
            f"validate_replay_prerequisites: trace store error for '{trace_id}': {exc}"
        )
        return errors

    inner_trace = envelope.get("trace", {})

    if not inner_trace.get("spans"):
        errors.append(
            f"validate_replay_prerequisites: trace '{trace_id}' has no spans — nothing to replay"
        )

    if not inner_trace.get("trace_id"):
        errors.append(
            f"validate_replay_prerequisites: inner trace is missing 'trace_id'"
        )

    return errors


def execute_replay(
    trace_id: str,
    base_dir: Optional[Path] = None,
    context: Optional[Dict[str, Any]] = None,
    persist_result: bool = False,
    run_decision_analysis: bool = False,
) -> Dict[str, Any]:
    """Execute a replay of the trace identified by *trace_id*.

    The replay walks each span in the original trace in creation order,
    treating the span as a discrete replay step.  The outcome of each step
    mirrors the original span status.  Timestamps and IDs are non-deterministic
    and recorded as such in ``determinism_notes``.

    Parameters
    ----------
    trace_id:
        The trace to replay.
    base_dir:
        Override the trace store directory (primarily for testing).
    context:
        Optional caller-supplied replay context metadata.
    persist_result:
        If ``True``, persist the replay result trace via ``trace_store``.
    run_decision_analysis:
        If ``True``, invoke the BQ Replay Decision Integrity Engine after the
        replay completes and attach the result under the
        ``decision_analysis`` key.  Decision analysis failures are recorded
        but do not cause this function to raise — the replay result is still
        returned.

    Returns
    -------
    dict
        A fully validated ``replay_result`` artifact conforming to
        ``replay_result.schema.json``.  When ``run_decision_analysis`` is
        ``True`` an additional ``decision_analysis`` key is present containing
        the governed analysis artifact (or ``None`` on failure).

    Raises
    ------
    ReplayPrerequisiteError
        If prerequisites are not met.
    ReplayEngineError
        If the replay result fails schema validation.
    """
    replay_id = _new_id()
    replayed_at = _now_iso()

    # Validate prerequisites first
    prerequisite_errors = validate_replay_prerequisites(trace_id, base_dir=base_dir)
    prerequisites_valid = len(prerequisite_errors) == 0

    if not prerequisites_valid:
        result = _build_blocked_result(
            replay_id=replay_id,
            trace_id=trace_id,
            replayed_at=replayed_at,
            prerequisite_errors=prerequisite_errors,
            context=context,
        )
        errors = validate_replay_result(result)
        if errors:
            raise ReplayEngineError(
                f"execute_replay: blocked result failed schema validation: "
                + "; ".join(errors)
            )
        return result

    # Load replay record
    record = build_replay_record(trace_id, base_dir=base_dir, context=context)
    spans = record["spans"]

    # Execute steps
    steps_executed, determinism_notes = _execute_steps(spans)

    # Determine overall status
    status = _compute_overall_status(steps_executed)

    # Compare outputs
    output_comparison = compare_replay_outputs(
        original_spans=spans,
        replay_steps=steps_executed,
    )

    result: Dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "schema_version": SCHEMA_VERSION,
        "replay_id": replay_id,
        "source_trace_id": trace_id,
        "replayed_at": replayed_at,
        "status": status,
        "prerequisites_valid": True,
        "prerequisite_errors": [],
        "steps_executed": steps_executed,
        "output_comparison": output_comparison,
        "determinism_notes": determinism_notes,
        "context": dict(context or {}),
    }

    errors = validate_replay_result(result)
    if errors:
        raise ReplayEngineError(
            f"execute_replay: result failed schema validation: " + "; ".join(errors)
        )

    if run_decision_analysis:
        # Import lazily to avoid a circular import at module load time.
        from spectrum_systems.modules.runtime.replay_decision_engine import (  # noqa: PLC0415
            ReplayDecisionError,
            run_replay_decision_analysis,
        )
        try:
            analysis = run_replay_decision_analysis(
                trace_id,
                base_dir=base_dir,
                replay_context=context,
            )
            result["decision_analysis"] = analysis
        except ReplayDecisionError:
            result["decision_analysis"] = None

    return result


def compare_replay_outputs(
    original_spans: List[Dict[str, Any]],
    replay_steps: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Compare replay step outcomes against original span outcomes.

    Compares the ``status`` field of each original span against the
    corresponding replay step.  Timestamps are explicitly excluded from
    comparison as they are always non-deterministic.

    Parameters
    ----------
    original_spans:
        The span list from the original trace.
    replay_steps:
        The step list produced by ``execute_replay``.

    Returns
    -------
    dict
        An ``output_comparison`` dict with keys:
        - ``compared`` (bool)
        - ``matched`` (bool | None)
        - ``differences`` (list of difference dicts)
    """
    if not original_spans or not replay_steps:
        return {"compared": False, "matched": None, "differences": []}

    differences: List[Dict[str, Any]] = []

    for step in replay_steps:
        original_span_id = step.get("original_span_id")
        # Find the matching original span by span_id
        orig_span = next(
            (s for s in original_spans if s.get("span_id") == original_span_id),
            None,
        )
        if orig_span is None:
            differences.append(
                {
                    "field": f"spans[{original_span_id}]",
                    "original_value": None,
                    "replay_value": step.get("status"),
                }
            )
            continue

        orig_status = orig_span.get("status")
        replay_status = step.get("status")
        if orig_status != replay_status:
            differences.append(
                {
                    "field": f"span[{original_span_id}].status",
                    "original_value": orig_status,
                    "replay_value": replay_status,
                }
            )

    matched = len(differences) == 0
    return {
        "compared": True,
        "matched": matched,
        "differences": differences,
    }


def validate_replay_result(result: Dict[str, Any]) -> List[str]:
    """Validate replay_result payloads across BAG and legacy BP surfaces."""
    if not isinstance(result, dict):
        return ["validate_replay_result: result must be a dict"]

    try:
        primary_schema = _load_replay_result_schema()
    except (OSError, json.JSONDecodeError) as exc:
        return [f"validate_replay_result: could not load replay result schema: {exc}"]

    checker = FormatChecker()
    primary_validator = Draft202012Validator(primary_schema, format_checker=checker)
    primary_errors = sorted(primary_validator.iter_errors(result), key=lambda e: list(e.path))
    if not primary_errors:
        return []

    legacy_validator = Draft202012Validator(_LEGACY_REPLAY_RESULT_SCHEMA, format_checker=checker)
    legacy_errors = sorted(legacy_validator.iter_errors(result), key=lambda e: list(e.path))
    if not legacy_errors:
        return []

    return [e.message for e in primary_errors]


# ---------------------------------------------------------------------------
# Internal step execution helpers
# ---------------------------------------------------------------------------


def _execute_steps(
    spans: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Walk each span and build the list of executed replay steps.

    Returns
    -------
    tuple[list[dict], list[str]]
        A tuple of (steps_executed, determinism_notes).
    """
    steps: List[Dict[str, Any]] = []
    determinism_notes: List[str] = [
        "Span start_time and end_time are non-deterministic (wall-clock timestamps differ on replay).",
        "Span IDs are preserved from the original trace; new spans are not generated.",
    ]

    for idx, span in enumerate(spans):
        span_id = span.get("span_id", f"unknown-{idx}")
        original_status = span.get("status")
        span_name = span.get("name") or f"<unnamed-span-{idx}>"

        # Map original status to replay step status
        # Open spans (status=None) are replayed as 'ok' with a determinism note
        if original_status is None:
            replay_status = "ok"
            determinism_notes.append(
                f"Span '{span_name}' (id={span_id}) had no recorded "
                f"status in the original trace (was open); replayed as 'ok'."
            )
        elif original_status in ("ok", "error", "blocked"):
            replay_status = original_status
        else:
            replay_status = "skipped"
            determinism_notes.append(
                f"Span '{span_name}' (id={span_id}) had unrecognized "
                f"status '{original_status}'; replayed as 'skipped'."
            )

        step: Dict[str, Any] = {
            "step_index": idx,
            "span_name": span_name,
            "original_span_id": span_id,
            "status": replay_status,
            "replayed_at": _now_iso(),
            "error_message": None,
        }
        steps.append(step)

    return steps, determinism_notes


def _compute_overall_status(steps: List[Dict[str, Any]]) -> str:
    """Derive overall replay status from step outcomes."""
    if not steps:
        return "failed"
    statuses = {s["status"] for s in steps}
    if "blocked" in statuses:
        return "partial"
    if "error" in statuses:
        return "partial"
    if "skipped" in statuses:
        return "partial"
    return "success"


def _build_blocked_result(
    replay_id: str,
    trace_id: str,
    replayed_at: str,
    prerequisite_errors: List[str],
    context: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build a replay result artifact for a blocked (prerequisites-failed) replay."""
    return {
        "artifact_type": ARTIFACT_TYPE,
        "schema_version": SCHEMA_VERSION,
        "replay_id": replay_id,
        "source_trace_id": trace_id,
        "replayed_at": replayed_at,
        "status": "blocked",
        "prerequisites_valid": False,
        "prerequisite_errors": prerequisite_errors,
        "steps_executed": [],
        "output_comparison": {
            "compared": False,
            "matched": None,
            "differences": [],
        },
        "determinism_notes": [],
        "context": dict(context or {}),
    }


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ReplayEngineError(Exception):
    """Base class for all replay engine errors."""


class ReplayPrerequisiteError(ReplayEngineError):
    """Raised when replay prerequisites are not satisfied."""


def validate_replay_execution_record(record: Dict[str, Any]) -> List[str]:
    """Validate a replay execution record artifact against contract schema."""
    if not isinstance(record, dict):
        return ["validate_replay_execution_record: record must be an object"]
    try:
        schema = load_schema("replay_execution_record")
    except (OSError, FileNotFoundError, ValueError) as exc:
        return [f"validate_replay_execution_record: schema unavailable: {exc}"]

    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(record), key=lambda e: list(e.path))
    return [e.message for e in errors]


def replay_run(bundle_path: str, original_decision: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministically replay run-bundle control-plane execution.

    Replays the same pipeline used for original execution:
    validation -> monitor record -> summary -> budget decision -> enforcement.
    Returns a schema-valid replay_execution_record with lineage and consistency
    check outcomes. Fail-closed behavior is applied for invalid inputs or
    malformed comparison surfaces.
    """
    replay_id = _new_id()
    timestamp = _now_iso()
    compared_artifacts = [
        "decision",
        "enforcement_action",
        "final_status",
    ]

    def _indeterminate(reason: str, replay_run_id: str = "unknown", replay_trace_id: str = "unknown") -> Dict[str, Any]:
        base = {
            "replay_id": replay_id,
            "original_run_id": str((original_decision or {}).get("run_id") or "unknown"),
            "replay_run_id": replay_run_id,
            "original_trace_id": str((original_decision or {}).get("trace_id") or "unknown"),
            "replay_trace_id": replay_trace_id,
            "timestamp": timestamp,
            "replay_status": "indeterminate",
            "consistency_check_passed": False,
            "compared_artifacts": compared_artifacts,
            "reasons": [reason],
        }
        schema_errors = validate_replay_execution_record(base)
        if schema_errors:
            base["reasons"].extend([f"schema_validation_failed: {e}" for e in schema_errors])
        return base

    if not isinstance(bundle_path, str) or not bundle_path.strip():
        return _indeterminate("invalid replay input: bundle_path must be a non-empty string")

    if not isinstance(original_decision, dict):
        return _indeterminate("original decision malformed: must be an object")

    required_original_keys = {"run_id", "trace_id"}
    missing = sorted(k for k in required_original_keys if not original_decision.get(k))
    if missing:
        return _indeterminate(f"original decision malformed: missing required fields {missing}")

    try:
        from spectrum_systems.modules.runtime.control_loop import run_control_loop
        from spectrum_systems.modules.runtime.enforcement_engine import enforce_control_decision
        from spectrum_systems.modules.runtime.evaluation_monitor import (
            build_validation_monitor_record,
            summarize_validation_monitor_records,
        )
        from spectrum_systems.modules.runtime.run_bundle_validator import validate_and_emit_decision
    except Exception as exc:  # noqa: BLE001
        raise ReplayEngineError(
            f"REPLAY_EXECUTION_FAILED:{exc.__class__.__name__}:{exc}"
        ) from exc

    try:
        replay_validation_decision = validate_and_emit_decision(bundle_path)
        replay_monitor = build_validation_monitor_record(replay_validation_decision)
        replay_summary = summarize_validation_monitor_records([replay_monitor])

        replay_trace_id = str(replay_validation_decision.get("trace_id") or "")
        try:
            uuid.UUID(replay_trace_id)
        except (TypeError, ValueError):
            replay_trace_id = str(uuid.uuid5(uuid.NAMESPACE_URL, replay_trace_id or "unknown-trace"))

        success_rate = float(
            (replay_summary.get("aggregated_slis") or {}).get("bundle_validation_success_rate", 0.0)
        )
        reproducibility_score = float(
            (replay_summary.get("aggregated_slis") or {}).get("provenance_required_rate", 0.0)
        )
        replay_eval_summary = {
            "artifact_type": "eval_summary",
            "schema_version": "1.0.0",
            "trace_id": replay_trace_id,
            "eval_run_id": str(replay_validation_decision.get("run_id") or "unknown-run"),
            "pass_rate": success_rate,
            "failure_rate": max(0.0, min(1.0, 1.0 - success_rate)),
            "drift_rate": max(0.0, min(1.0, 1.0 - success_rate)),
            "reproducibility_score": reproducibility_score,
            "system_status": (
                "healthy"
                if success_rate >= 0.95
                else "degraded"
                if success_rate > 0.0
                else "failing"
            ),
        }

        replay_decision = run_control_loop(
            replay_eval_summary,
            {
                "trace_id": replay_trace_id,
                "run_id": replay_eval_summary["eval_run_id"],
                "replay_id": replay_id,
            },
        )["evaluation_control_decision"]
        replay_enforcement = enforce_control_decision(replay_decision)
    except Exception as exc:  # noqa: BLE001
        raise ReplayEngineError(
            f"REPLAY_EXECUTION_FAILED:{exc.__class__.__name__}:{exc}"
        ) from exc

    replay_run_id = str(replay_decision.get("run_id") or replay_validation_decision.get("run_id") or "unknown")
    replay_trace_id = str(replay_decision.get("trace_id") or replay_validation_decision.get("trace_id") or "unknown")

    reasons: List[str] = []
    consistency_check_passed = True
    replay_status = "success"

    original_decision_status = str(original_decision.get("decision") or "")
    if not original_decision_status:
        mapped_response = {
            "allow": "allow",
            "warn": "require_review",
            "freeze": "deny",
            "block": "deny",
        }.get(str(original_decision.get("system_response") or ""), "")
        original_decision_status = mapped_response
    replay_decision_status = str(replay_decision.get("decision"))
    if original_decision_status != replay_decision_status:
        consistency_check_passed = False
        replay_status = "failed"
        reasons.append(
            f"decision mismatch: original={original_decision_status} replay={replay_decision_status}"
        )

    original_enforcement_action = str(original_decision.get("enforcement_action") or "")
    legacy_action_map = {
        "allow": "allow_execution",
        "warn": "require_manual_review",
        "freeze": "deny_execution",
        "block": "deny_execution",
    }
    if original_enforcement_action in legacy_action_map:
        original_enforcement_action = legacy_action_map[original_enforcement_action]
    if not original_enforcement_action:
        original_enforcement_action = {
            "allow": "allow_execution",
            "warn": "require_manual_review",
            "freeze": "deny_execution",
            "block": "deny_execution",
        }.get(str(original_decision.get("system_response") or ""), "deny_execution")
    replay_enforcement_action = str(replay_enforcement.get("enforcement_action"))
    if original_enforcement_action != replay_enforcement_action:
        consistency_check_passed = False
        replay_status = "failed"
        reasons.append(
            "enforcement_action mismatch: "
            f"original={original_enforcement_action} replay={replay_enforcement_action}"
        )

    original_validation_status = str(original_decision.get("final_status") or original_decision_status)
    replay_validation_status = str(replay_enforcement.get("final_status"))
    if original_validation_status != replay_validation_status:
        consistency_check_passed = False
        replay_status = "failed"
        reasons.append(
            f"validation_status mismatch: original={original_validation_status} replay={replay_validation_status}"
        )

    if not reasons:
        reasons.append("replay matched original control-plane outputs")

    record = {
        "replay_id": replay_id,
        "original_run_id": str(original_decision.get("run_id")),
        "replay_run_id": replay_run_id,
        "original_trace_id": str(original_decision.get("trace_id")),
        "replay_trace_id": replay_trace_id,
        "timestamp": timestamp,
        "replay_status": replay_status,
        "consistency_check_passed": consistency_check_passed,
        "compared_artifacts": compared_artifacts,
        "reasons": reasons,
    }

    schema_errors = validate_replay_execution_record(record)
    if schema_errors:
        return _indeterminate(
            "comparison cannot be performed: replay_execution_record schema validation failed",
            replay_run_id=replay_run_id,
            replay_trace_id=replay_trace_id,
        )
    return record

# ---------------------------------------------------------------------------
# BAG replay engine (canonical trust-loop replay)
# ---------------------------------------------------------------------------


def _validate_schema_or_raise(payload: Dict[str, Any], schema_name: str, *, context: str) -> None:
    schema = load_schema(schema_name)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.path))
    if errors:
        details = "; ".join(e.message for e in errors)
        raise ReplayEngineError(f"{context} failed validation: {details}")


def _validate_governed_artifact_or_raise(artifact: Dict[str, Any]) -> None:
    artifact_type = artifact.get("artifact_type")
    if not isinstance(artifact_type, str) or not artifact_type:
        raise ReplayEngineError("REPLAY_INVALID_INPUT_ARTIFACT: missing artifact_type")
    if artifact_type not in _SUPPORTED_GOVERNED_ARTIFACT_TYPES:
        raise ReplayEngineError(
            "REPLAY_UNSUPPORTED_INPUT_ARTIFACT: artifact_type must be one of "
            f"{tuple(sorted(_SUPPORTED_GOVERNED_ARTIFACT_TYPES))}, got {artifact_type!r}"
        )
    try:
        _validate_schema_or_raise(artifact, artifact_type, context="input artifact")
    except FileNotFoundError as exc:
        raise ReplayEngineError(
            f"REPLAY_UNSUPPORTED_INPUT_ARTIFACT: schema not found for artifact_type={artifact_type}"
        ) from exc


def _stable_replay_id(original_run_id: str, trace_id: str, source_ref: str) -> str:
    seed = f"{original_run_id}|{trace_id}|{source_ref}"
    return f"RPL-{uuid.uuid5(uuid.NAMESPACE_URL, seed).hex[:12]}"


def _classify_consistency(
    replay_enforcement: Dict[str, Any],
    original_enforcement: Dict[str, Any],
) -> str:
    replay_action = replay_enforcement.get("enforcement_action")
    original_action = original_enforcement.get("enforcement_action")
    replay_status = replay_enforcement.get("final_status")
    original_status = original_enforcement.get("final_status")
    if replay_action == original_action and replay_status == original_status:
        return "match"
    return "mismatch"


def _build_replay_result(
    *,
    artifact: Dict[str, Any],
    original_decision: Dict[str, Any],
    original_enforcement: Dict[str, Any],
    replay_decision: Dict[str, Any],
    replay_enforcement: Dict[str, Any],
    trace_id: str,
    consistency_status: str,
    failure_reason: Optional[str],
) -> Dict[str, Any]:
    replay_decision_value = replay_decision.get("decision")
    if replay_decision_value not in {"allow", "deny", "require_review"}:
        raise ReplayEngineError(
            f"replay_decision contains unsupported decision value: {replay_decision_value!r}"
        )

    replay_action = replay_enforcement.get("enforcement_action")
    replay_status = replay_enforcement.get("final_status")
    original_action = original_enforcement.get("enforcement_action")
    original_status = original_enforcement.get("final_status")
    if replay_action not in {"allow_execution", "deny_execution", "require_manual_review"}:
        raise ReplayEngineError(
            f"replay_enforcement contains unsupported enforcement_action: {replay_action!r}"
        )
    if original_action not in {"allow_execution", "deny_execution", "require_manual_review"}:
        raise ReplayEngineError(
            f"original_enforcement contains unsupported enforcement_action: {original_action!r}"
        )
    if replay_status not in {"allow", "deny", "require_review"}:
        raise ReplayEngineError(
            f"replay_enforcement contains unsupported final_status: {replay_status!r}"
        )
    if original_status not in {"allow", "deny", "require_review"}:
        raise ReplayEngineError(
            f"original_enforcement contains unsupported final_status: {original_status!r}"
        )

    source_id = str(
        artifact.get("eval_run_id")
        or artifact.get("eval_case_id")
        or artifact.get("run_id")
        or artifact.get("artifact_id")
        or trace_id
    )
    original_run_id = str(original_decision.get("run_id") or source_id)
    replay_run_id = str(replay_decision.get("run_id") or source_id)
    source_ref = f"{artifact.get('artifact_type', 'unknown')}:{source_id}"
    drift_detected = consistency_status == "mismatch"

    result_id = _stable_replay_id(original_run_id, trace_id, source_ref)
    result_timestamp = _now_iso()
    result = {
        "artifact_type": "replay_result",
        "schema_version": "1.1.1",
        "replay_id": result_id,
        "original_run_id": original_run_id,
        "replay_run_id": replay_run_id,
        "timestamp": result_timestamp,
        "trace_id": trace_id,
        "input_artifact_reference": source_ref,
        "original_decision_reference": str(original_decision.get("decision_id") or "unknown-decision"),
        "original_enforcement_reference": str(
            original_enforcement.get("enforcement_result_id") or "unknown-enforcement"
        ),
        "replay_decision_reference": str(replay_decision.get("decision_id") or "unknown-replay-decision"),
        "replay_enforcement_reference": str(
            replay_enforcement.get("enforcement_result_id") or "unknown-replay-enforcement"
        ),
        "replay_decision": replay_decision_value,
        "replay_enforcement_action": replay_action,
        "replay_final_status": replay_status,
        "original_enforcement_action": original_action,
        "original_final_status": original_status,
        "consistency_status": consistency_status,
        "drift_detected": drift_detected,
        "failure_reason": failure_reason,
        "replay_path": "bag_replay_engine",
        "provenance": build_canonical_provenance(
            run_id=replay_run_id,
            trace_id=trace_id,
            span_id=str(result_id),
            parent_span_id=str(replay_decision.get("decision_id") or ""),
            source_artifacts=[
                {
                    "artifact_type": str(artifact.get("artifact_type") or ""),
                    "artifact_id": source_id,
                }
            ],
            generator_name="runtime.replay_engine.run_replay",
            generator_version="1.2.0",
            artifact_type="replay_result",
            artifact_id=str(result_id),
            schema_version="1.1.1",
            timestamp=result_timestamp,
        ),
    }
    errors = validate_replay_result(result)
    if errors:
        raise ReplayEngineError("replay_result failed validation: " + "; ".join(errors))
    return result


def _require_trace_context(trace_context: Dict[str, Any]) -> Tuple[str, str, str]:
    trace_id = str(trace_context.get("trace_id") or "").strip()
    span_id = str(trace_context.get("span_id") or "").strip()
    parent_span_id = str(trace_context.get("parent_span_id") or "").strip()
    missing = [
        field
        for field, value in (
            ("trace_id", trace_id),
            ("span_id", span_id),
            ("parent_span_id", parent_span_id),
        )
        if not value
    ]
    if missing:
        raise ReplayEngineError(
            "REPLAY_MISSING_TRACE_CONTEXT: trace_context missing required fields: " + ", ".join(missing)
        )
    return trace_id, span_id, parent_span_id


def run_replay(
    artifact: dict,
    original_decision: dict,
    original_enforcement: dict,
    trace_context: dict,
) -> dict:
    """Replay canonical trust-loop execution deterministically for a governed artifact.

    Canonical path only:
        artifact -> run_control_loop(...) -> enforce_control_decision(...)
    """
    if not isinstance(artifact, dict):
        raise ReplayEngineError("REPLAY_INVALID_ARTIFACT: artifact must be a dict")
    if not isinstance(original_decision, dict):
        raise ReplayEngineError("REPLAY_MISSING_ORIGINAL_DECISION: original_decision must be a dict")
    if not isinstance(original_enforcement, dict):
        raise ReplayEngineError("REPLAY_MISSING_ORIGINAL_ENFORCEMENT: original_enforcement must be a dict")
    if not isinstance(trace_context, dict):
        raise ReplayEngineError("REPLAY_INVALID_TRACE_CONTEXT: trace_context must be a dict")

    artifact_input = deepcopy(artifact)
    original_decision_input = deepcopy(original_decision)
    original_enforcement_input = deepcopy(original_enforcement)
    trace_context_input = deepcopy(trace_context)

    _validate_governed_artifact_or_raise(artifact_input)
    _validate_schema_or_raise(
        original_decision_input,
        "evaluation_control_decision",
        context="original_decision",
    )
    _validate_schema_or_raise(
        original_enforcement_input,
        "enforcement_result",
        context="original_enforcement",
    )

    trace_id, _trace_span_id, _trace_parent_span_id = _require_trace_context(trace_context_input)

    try:
        from spectrum_systems.modules.runtime.control_loop import run_control_loop
        from spectrum_systems.modules.runtime.enforcement_engine import enforce_control_decision

        replay_decision = run_control_loop(artifact_input, trace_context_input)[
            "evaluation_control_decision"
        ]
        replay_enforcement = enforce_control_decision(replay_decision)
        consistency_status = _classify_consistency(replay_enforcement, original_enforcement_input)
        replay_result = _build_replay_result(
            artifact=artifact_input,
            original_decision=original_decision_input,
            original_enforcement=original_enforcement_input,
            replay_decision=replay_decision,
            replay_enforcement=replay_enforcement,
            trace_id=trace_id,
            consistency_status=consistency_status,
            failure_reason=None,
        )
        replay_result["drift_result"] = detect_drift(replay_result)
        return revalidate_mutated_artifact(
            replay_result,
            schema_validator=validate_replay_result,
            artifact_label="replay_result",
        )
    except ReplayEngineError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ReplayEngineError(
            f"REPLAY_EXECUTION_FAILED:{exc.__class__.__name__}:{exc}"
        ) from exc
