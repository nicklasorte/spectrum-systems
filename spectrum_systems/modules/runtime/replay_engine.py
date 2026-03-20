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

    Returns
    -------
    dict
        A fully validated ``replay_result`` artifact conforming to
        ``replay_result.schema.json``.

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
    """Validate *result* against the ``replay_result.schema.json`` contract.

    Parameters
    ----------
    result:
        The replay result dict to validate.

    Returns
    -------
    list[str]
        Empty list if valid.  Non-empty list of error messages if invalid.
        Callers MUST treat any non-empty result as a hard failure.
    """
    if not isinstance(result, dict):
        return ["validate_replay_result: result must be a dict"]

    try:
        schema = _load_replay_result_schema()
    except (OSError, json.JSONDecodeError) as exc:
        return [f"validate_replay_result: could not load replay result schema: {exc}"]

    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(result), key=lambda e: list(e.path))
    return [e.message for e in errors]


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
