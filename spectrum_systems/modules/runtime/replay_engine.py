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
import os
import uuid
import hashlib
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema
from spectrum_systems.modules.runtime.baseline_gating import (
    BaselineGatingError,
    build_baseline_gate_decision,
    load_baseline_gate_policy,
)
from spectrum_systems.modules.runtime.drift_detection import (
    DriftDetectionError as BaselineDriftDetectionError,
    build_drift_detection_result,
)
from spectrum_systems.modules.runtime.drift_detection_engine import detect_drift
from spectrum_systems.modules.runtime.alert_triggers import build_alert_trigger
from spectrum_systems.modules.runtime.error_budget import build_error_budget_status
from spectrum_systems.modules.runtime.observability_metrics import build_observability_metrics
from spectrum_systems.modules.runtime.trace_store import (
    TraceNotFoundError as StoreTraceNotFoundError,
    TraceStoreError,
    load_trace,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCHEMA_VERSION: str = "1.0.0"
ARTIFACT_TYPE: str = "replay_result"

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCHEMA_DIR = _REPO_ROOT / "contracts" / "schemas"
_REPLAY_RESULT_SCHEMA_PATH = _SCHEMA_DIR / "replay_result.schema.json"
_REPLAY_RESULTS_DIR = _REPO_ROOT / "data" / "replays"

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


def _stable_sha256(payload: Dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _canonical_timestamp_from_inputs(
    original_decision: Dict[str, Any],
    original_enforcement: Dict[str, Any],
) -> str:
    for field in ("timestamp", "created_at"):
        value = original_enforcement.get(field)
        if isinstance(value, str) and value.strip():
            return value
    for field in ("created_at", "timestamp"):
        value = original_decision.get(field)
        if isinstance(value, str) and value.strip():
            return value
    raise ReplayEngineError(
        "REPLAY_MISSING_PREREQUISITE_ARTIFACT: canonical replay timestamp "
        "must be derivable from original_decision/original_enforcement"
    )


def _load_replay_result_schema() -> Dict[str, Any]:
    return json.loads(_REPLAY_RESULT_SCHEMA_PATH.read_text(encoding="utf-8"))


def _replay_result_path(replay_id: str, base_dir: Optional[Path] = None) -> Path:
    if not replay_id or not isinstance(replay_id, str):
        raise ReplayEngineError("replay_id must be a non-empty string")
    target_dir = _REPLAY_RESULTS_DIR if base_dir is None else base_dir.parent / "replays"
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / f"{replay_id}.json"


def _persist_replay_result_immutable(
    replay_result: Dict[str, Any],
    base_dir: Optional[Path] = None,
) -> str:
    replay_id = replay_result.get("replay_id")
    if not isinstance(replay_id, str) or not replay_id:
        raise ReplayEngineError("replay_result persistence requires replay_id")
    path = _replay_result_path(replay_id, base_dir=base_dir)
    payload = json.dumps(replay_result, indent=2, ensure_ascii=False) + "\n"
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError as exc:
        raise ReplayEngineError(
            f"execute_replay: immutable replay persistence refused overwrite for '{path}'"
        ) from exc
    except OSError as exc:
        raise ReplayEngineError(
            f"execute_replay: failed to create replay artifact '{path}': {exc}"
        ) from exc

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
    except OSError as exc:
        raise ReplayEngineError(
            f"execute_replay: failed to persist replay artifact '{path}': {exc}"
        ) from exc
    return str(path)


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
    require_prerequisites: bool = False,
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
        Legacy execute_replay payloads are not canonical replay_result artifacts.
        Persistence is therefore fail-closed and this flag is not supported.
    run_decision_analysis:
        Legacy execute_replay payloads are not extended with governed analysis.
        Analysis must be run via ``run_replay_decision_analysis``.
    require_prerequisites:
        If ``True``, prerequisite failures raise ``ReplayPrerequisiteError``
        instead of returning a blocked legacy replay payload.

    Returns
    -------
    dict
        A legacy-shaped replay payload validated against the legacy replay
        compatibility schema.

    Raises
    ------
    ReplayPrerequisiteError
        If prerequisites are not met.
    ReplayEngineError
        If the replay result fails schema validation.
    """
    if persist_result:
        raise ReplayEngineError(
            "execute_replay: persist_result=True is not allowed for legacy replay payloads; "
            "use canonical run_replay persistence paths"
        )
    if run_decision_analysis:
        raise ReplayEngineError(
            "execute_replay: run_decision_analysis=True is not supported; "
            "run replay_decision_engine.run_replay_decision_analysis(...) separately"
        )

    replay_id = _new_id()
    replayed_at = _now_iso()

    # Validate prerequisites first
    prerequisite_errors = validate_replay_prerequisites(trace_id, base_dir=base_dir)
    prerequisites_valid = len(prerequisite_errors) == 0

    if not prerequisites_valid:
        if require_prerequisites:
            raise ReplayPrerequisiteError(
                f"execute_replay: prerequisites not met for trace '{trace_id}': "
                + "; ".join(prerequisite_errors)
            )
        result = _build_blocked_result(
            replay_id=replay_id,
            trace_id=trace_id,
            replayed_at=replayed_at,
            prerequisite_errors=prerequisite_errors,
            context=context,
        )
        errors = validate_replay_result_legacy(result)
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

    errors = validate_replay_result_legacy(result)
    if errors:
        raise ReplayEngineError(
            f"execute_replay: result failed schema validation: " + "; ".join(errors)
        )

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
    """Validate replay_result payloads against the canonical replay_result schema."""
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

    return [e.message for e in primary_errors]


def validate_replay_result_legacy(result: Dict[str, Any]) -> List[str]:
    """Validate legacy replay_result payloads against the legacy compatibility schema only."""
    if not isinstance(result, dict):
        return ["validate_replay_result_legacy: result must be a dict"]

    checker = FormatChecker()
    legacy_validator = Draft202012Validator(_LEGACY_REPLAY_RESULT_SCHEMA, format_checker=checker)
    legacy_errors = sorted(legacy_validator.iter_errors(result), key=lambda e: list(e.path))
    return [e.message for e in legacy_errors]


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
        span_id = span.get("span_id")
        if not isinstance(span_id, str) or not span_id.strip():
            raise ReplayEngineError(
                f"_execute_steps: span at index {idx} is missing required span_id"
            )
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


def _resolve_source_artifact_id(artifact: Dict[str, Any]) -> str:
    source_id = (
        artifact.get("eval_run_id")
        or artifact.get("eval_case_id")
        or artifact.get("run_id")
        or artifact.get("artifact_id")
    )
    if not isinstance(source_id, str) or not source_id.strip():
        raise ReplayEngineError(
            "REPLAY_MISSING_PREREQUISITE_ARTIFACT: source artifact must include one of "
            "eval_run_id, eval_case_id, run_id, or artifact_id"
        )
    if source_id.startswith("unknown-") or source_id == "unknown":
        raise ReplayEngineError(
            f"REPLAY_INVALID_LINEAGE: source artifact id contains forbidden placeholder {source_id!r}"
        )
    return source_id


def _validate_replay_lineage_or_raise(
    *,
    artifact: Dict[str, Any],
    original_decision: Dict[str, Any],
    original_enforcement: Dict[str, Any],
    trace_id: str,
) -> None:
    """Fail-closed lineage/trace continuity checks for governed replay."""
    source_artifact_type = artifact.get("artifact_type")
    source_artifact_id = _resolve_source_artifact_id(artifact)

    input_signal_ref = original_decision.get("input_signal_reference")
    if not isinstance(input_signal_ref, dict):
        raise ReplayEngineError(
            "REPLAY_INVALID_LINEAGE: original_decision.input_signal_reference must be present"
        )
    if input_signal_ref.get("signal_type") != source_artifact_type:
        raise ReplayEngineError(
            "REPLAY_INVALID_LINEAGE: original_decision.input_signal_reference.signal_type "
            f"{input_signal_ref.get('signal_type')!r} does not match replay source artifact_type "
            f"{source_artifact_type!r}"
        )
    if input_signal_ref.get("source_artifact_id") != source_artifact_id:
        raise ReplayEngineError(
            "REPLAY_INVALID_LINEAGE: original_decision.input_signal_reference.source_artifact_id "
            f"{input_signal_ref.get('source_artifact_id')!r} does not match replay source artifact id "
            f"{source_artifact_id!r}"
        )

    decision_id = original_decision.get("decision_id")
    if not isinstance(decision_id, str) or not decision_id.strip():
        raise ReplayEngineError(
            "REPLAY_MISSING_PREREQUISITE_ARTIFACT: original_decision.decision_id is required for lineage"
        )

    enf_input_ref = original_enforcement.get("input_decision_reference")
    if enf_input_ref != decision_id:
        raise ReplayEngineError(
            "REPLAY_INVALID_LINEAGE: original_enforcement.input_decision_reference does not "
            "match original_decision.decision_id"
        )

    artifact_trace_id = artifact.get("trace_id")
    decision_trace_id = original_decision.get("trace_id")
    enforcement_trace_id = original_enforcement.get("trace_id")
    trace_ids = [artifact_trace_id, decision_trace_id, enforcement_trace_id, trace_id]
    if any(not isinstance(value, str) or not value.strip() for value in trace_ids):
        raise ReplayEngineError(
            "REPLAY_INVALID_TRACE_LINKAGE: artifact, original_decision, original_enforcement, "
            "and replay trace context must all include non-empty trace_id values"
        )
    if len(set(trace_ids)) != 1:
        raise ReplayEngineError(
            "REPLAY_INVALID_TRACE_LINKAGE: trace_id mismatch across replay source chain "
            f"(artifact={artifact_trace_id!r}, original_decision={decision_trace_id!r}, "
            f"original_enforcement={enforcement_trace_id!r}, replay_trace={trace_id!r})"
        )


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


def _enforce_authoritative_replay_seam_or_raise(replay_result: Dict[str, Any]) -> None:
    """Fail-closed validation that replay_result is fully governed and non-bypassable."""
    required_embedded = ("observability_metrics", "error_budget_status", "alert_trigger")
    for field in required_embedded:
        value = replay_result.get(field)
        if not isinstance(value, dict):
            raise ReplayEngineError(
                f"REPLAY_MISSING_REQUIRED_GOVERNED_ARTIFACT: replay_result.{field} must be present"
            )

    _validate_schema_or_raise(replay_result["observability_metrics"], "observability_metrics", context="replay_result.observability_metrics")
    _validate_schema_or_raise(replay_result["error_budget_status"], "error_budget_status", context="replay_result.error_budget_status")
    _validate_schema_or_raise(replay_result["alert_trigger"], "alert_trigger", context="replay_result.alert_trigger")

    trace_id = replay_result.get("trace_id")
    if replay_result["observability_metrics"].get("trace_refs", {}).get("trace_id") != trace_id:
        raise ReplayEngineError("REPLAY_INVALID_TRACE_LINKAGE: observability_metrics.trace_refs.trace_id mismatch")
    if replay_result["error_budget_status"].get("trace_refs", {}).get("trace_id") != trace_id:
        raise ReplayEngineError("REPLAY_INVALID_TRACE_LINKAGE: error_budget_status.trace_refs.trace_id mismatch")
    if replay_result["alert_trigger"].get("trace_refs", {}).get("trace_id") != trace_id:
        raise ReplayEngineError("REPLAY_INVALID_TRACE_LINKAGE: alert_trigger.trace_refs.trace_id mismatch")

    if replay_result["error_budget_status"].get("observability_metrics_id") != replay_result["observability_metrics"].get("artifact_id"):
        raise ReplayEngineError(
            "REPLAY_INVALID_LINEAGE: error_budget_status.observability_metrics_id must reference embedded observability_metrics.artifact_id"
        )
    if replay_result["alert_trigger"].get("replay_result_id") != replay_result.get("replay_id"):
        raise ReplayEngineError("REPLAY_INVALID_LINEAGE: alert_trigger.replay_result_id must reference replay_result.replay_id")


def _build_replay_result(
    *,
    artifact: Dict[str, Any],
    original_decision: Dict[str, Any],
    original_enforcement: Dict[str, Any],
    replay_decision: Dict[str, Any],
    replay_enforcement: Dict[str, Any],
    trace_id: str,
    canonical_timestamp: str,
    consistency_status: str,
    failure_reason: Optional[str],
) -> Dict[str, Any]:
    def _require_non_empty_ref(value: Any, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ReplayEngineError(
                f"replay_result linkage requires non-empty {field_name}; placeholder/default values are forbidden"
            )
        if value.startswith("unknown-") or value == "unknown":
            raise ReplayEngineError(
                f"replay_result linkage field {field_name} contains forbidden placeholder value {value!r}"
            )
        return value

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

    source_id = _require_non_empty_ref(_resolve_source_artifact_id(artifact), "source_artifact_id")
    original_run_id = _require_non_empty_ref(original_decision.get("run_id"), "original_run_id")
    source_artifact_type = _require_non_empty_ref(
        artifact.get("artifact_type"),
        "source_artifact_type",
    )
    source_ref = f"{source_artifact_type}:{source_id}"
    deterministic_seed = f"{original_run_id}|{trace_id}|{source_ref}"
    replay_run_id = f"rplrun-{_stable_sha256({'seed': deterministic_seed})[:20]}"
    drift_detected = consistency_status == "mismatch"
    replay_decision_reference = f"ECD-{_stable_sha256({'seed': deterministic_seed, 'kind': 'decision'})[:24]}"
    replay_enforcement_reference = f"ENF-{_stable_sha256({'seed': deterministic_seed, 'kind': 'enforcement'})[:24]}"

    result = {
        "artifact_id": "",
        "artifact_type": "replay_result",
        "schema_version": "1.2.0",
        "replay_id": _stable_replay_id(original_run_id, trace_id, source_ref),
        "original_run_id": original_run_id,
        "replay_run_id": replay_run_id,
        "timestamp": canonical_timestamp,
        "trace_id": trace_id,
        "input_artifact_reference": source_ref,
        "original_decision_reference": _require_non_empty_ref(
            original_decision.get("decision_id"),
            "original_decision_reference",
        ),
        "original_enforcement_reference": _require_non_empty_ref(
            original_enforcement.get("enforcement_result_id"),
            "original_enforcement_reference",
        ),
        "replay_decision_reference": _require_non_empty_ref(
            replay_decision_reference,
            "replay_decision_reference",
        ),
        "replay_enforcement_reference": _require_non_empty_ref(
            replay_enforcement_reference,
            "replay_enforcement_reference",
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
        "provenance": {
            "source_artifact_type": source_artifact_type,
            "source_artifact_id": source_id,
            "trace_id": trace_id,
        },
    }
    preimage = dict(result)
    preimage.pop("artifact_id", None)
    result["artifact_id"] = _stable_sha256(preimage)
    return result


def run_replay(
    artifact: dict,
    original_decision: dict,
    original_enforcement: dict,
    trace_context: dict,
    *,
    baseline_artifact: dict | None = None,
    baseline_policy: dict | None = None,
    slo_definition: dict | None = None,
    error_budget_policy: dict | None = None,
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

    trace_id_value = trace_context_input.get("trace_id")
    if not isinstance(trace_id_value, str) or not trace_id_value.strip():
        raise ReplayEngineError(
            "REPLAY_INVALID_TRACE_LINKAGE: trace_context.trace_id is required for governed replay flows"
        )
    if trace_id_value.startswith("unknown-") or trace_id_value == "unknown":
        raise ReplayEngineError(
            f"REPLAY_INVALID_TRACE_LINKAGE: placeholder trace_id is forbidden ({trace_id_value!r})"
        )
    trace_id = trace_id_value
    if slo_definition is None:
        raise ReplayEngineError(
            "REPLAY_MISSING_REQUIRED_GOVERNED_ARTIFACT: slo_definition is required to produce "
            "authoritative error_budget_status and alert_trigger artifacts"
        )
    _validate_replay_lineage_or_raise(
        artifact=artifact_input,
        original_decision=original_decision_input,
        original_enforcement=original_enforcement_input,
        trace_id=trace_id,
    )

    try:
        from spectrum_systems.modules.runtime.control_loop import run_control_loop
        from spectrum_systems.modules.runtime.enforcement_engine import enforce_control_decision

        replay_decision = run_control_loop(artifact_input, trace_context_input)[
            "evaluation_control_decision"
        ]
        replay_enforcement = enforce_control_decision(replay_decision)
        canonical_timestamp = _canonical_timestamp_from_inputs(
            original_decision_input,
            original_enforcement_input,
        )
        consistency_status = _classify_consistency(replay_enforcement, original_enforcement_input)
        replay_result = _build_replay_result(
            artifact=artifact_input,
            original_decision=original_decision_input,
            original_enforcement=original_enforcement_input,
            replay_decision=replay_decision,
            replay_enforcement=replay_enforcement,
            trace_id=trace_id,
            canonical_timestamp=canonical_timestamp,
            consistency_status=consistency_status,
            failure_reason=None,
        )
        observability_sources = [replay_result]

        if baseline_artifact is not None:
            policy = baseline_policy if baseline_policy is not None else load_baseline_gate_policy()
            drift_detection_result = build_drift_detection_result(
                replay_result,
                baseline_artifact,
                policy,
                trace_id=trace_id,
                run_id=replay_result.get("replay_run_id"),
            )
            baseline_gate_decision = build_baseline_gate_decision(
                drift_detection_result,
                policy,
                trace_id=trace_id,
                run_id=replay_result.get("replay_run_id"),
            )
            replay_result["drift_detection_result"] = drift_detection_result
            replay_result["baseline_gate_decision"] = baseline_gate_decision
            observability_sources.extend([drift_detection_result, baseline_gate_decision])
            if baseline_gate_decision.get("enforcement_action") == "block_promotion":
                raise ReplayEngineError(
                    "BASELINE_GATE_BLOCKED:"
                    + baseline_gate_decision.get("decision_id", "unknown")
                )

        replay_result["observability_metrics"] = build_observability_metrics(
            observability_sources,
            slo_definition=slo_definition,
            trace_id=trace_id,
        )

        replay_result["error_budget_status"] = build_error_budget_status(
            replay_result["observability_metrics"],
            slo_definition,
            policy=error_budget_policy,
            trace_id=trace_id,
        )
        replay_result["drift_result"] = detect_drift(replay_result)
        replay_result["alert_trigger"] = build_alert_trigger(
            replay_result,
            trace_id=trace_id,
        )
        _enforce_authoritative_replay_seam_or_raise(replay_result)

        errors = validate_replay_result(replay_result)
        if errors:
            raise ReplayEngineError("replay_result failed validation: " + "; ".join(errors))
        return replay_result
    except (ReplayEngineError, BaselineDriftDetectionError, BaselineGatingError):
        raise
    except Exception as exc:  # noqa: BLE001
        raise ReplayEngineError(
            f"REPLAY_EXECUTION_FAILED:{exc.__class__.__name__}:{exc}"
        ) from exc
