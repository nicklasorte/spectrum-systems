"""Trace + Correlation Layer (BK–BM).

Provides OpenTelemetry-style traceability across the full execution path:

    run → validators → SLO evaluation → enforcement → execution → artifacts

Every decision and artifact must be traceable, inspectable, and
reconstructable.

Design principles
-----------------
- Fail closed:  missing ``trace_id``, missing span context, or malformed trace
  structures block execution rather than silently passing.
- Deterministic IDs:  all IDs are UUID-4 strings.
- Thread-safe:  the in-process store is protected by a threading lock.
- No free text in events:  payloads are structured dicts, not log strings.
- Zero external dependencies:  only stdlib + jsonschema (already required).

Trace model
-----------
Trace:
  trace_id        – unique trace identifier
  root_span_id    – ID of the first span created
  spans           – list of Span dicts in creation order
  artifacts       – list of attached artifact references
  start_time      – ISO-8601 UTC
  end_time        – ISO-8601 UTC or None

Span:
  span_id         – unique span identifier
  trace_id        – owning trace
  parent_span_id  – parent span ID or None (root span)
  name            – human-readable operation name
  status          – "ok" | "error" | "blocked"
  start_time      – ISO-8601 UTC
  end_time        – ISO-8601 UTC or None
  events          – list of Event dicts

Event:
  event_type      – governed string (e.g. "validator_result")
  timestamp       – ISO-8601 UTC
  payload         – structured dict

Public API
----------
start_trace(context)                   → trace_id
start_span(trace_id, name, parent)     → span_id
end_span(span_id, status)              → None
record_event(span_id, event_type, payload) → None
attach_artifact(trace_id, artifact_id, artifact_type) → None
get_trace(trace_id)                    → Trace dict (deep copy)
summarize_trace(trace_id)              → str
validate_trace_context(trace_id, span_id) → List[str]  (empty = valid)
"""

from __future__ import annotations

import threading
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TypedDict

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SPAN_STATUS_OK = "ok"
SPAN_STATUS_ERROR = "error"
SPAN_STATUS_BLOCKED = "blocked"

_VALID_STATUSES = frozenset({SPAN_STATUS_OK, SPAN_STATUS_ERROR, SPAN_STATUS_BLOCKED})

SCHEMA_VERSION: str = "1.0.0"

# ---------------------------------------------------------------------------
# In-process store
# ---------------------------------------------------------------------------

_store_lock: threading.Lock = threading.Lock()

# trace_id → full Trace dict
_traces: Dict[str, Dict[str, Any]] = {}

# span_id → (trace_id, Span dict)
_span_index: Dict[str, tuple] = {}  # span_id → (trace_id, span_dict)


class TraceStore(TypedDict):
    """Isolated trace-store container for dependency-injected trace operations."""

    lock: threading.Lock
    traces: Dict[str, Dict[str, Any]]
    span_index: Dict[str, tuple]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


def _find_span(span_id: str, span_index: Dict[str, tuple]) -> Optional[Dict[str, Any]]:
    """Return the Span dict for *span_id* or ``None``."""
    entry = span_index.get(span_id)
    if entry is None:
        return None
    return entry[1]


def create_trace_store() -> TraceStore:
    """Create an isolated in-memory trace store.

    This enables callers (e.g. chaos validation) to run trace checks without
    mutating the process-global trace registry.
    """
    return {
        "lock": threading.Lock(),
        "traces": {},
        "span_index": {},
    }


def _resolve_store(store: Optional[TraceStore]) -> tuple[threading.Lock, Dict[str, Dict[str, Any]], Dict[str, tuple]]:
    if store is None:
        return _store_lock, _traces, _span_index
    return store["lock"], store["traces"], store["span_index"]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def start_trace(context: Optional[Dict[str, Any]] = None, *, store: Optional[TraceStore] = None) -> str:
    """Create a new Trace and return its ``trace_id``.

    Parameters
    ----------
    context:
        Optional metadata attached to the trace (e.g. stage, run_id).
        All values must be JSON-serialisable.

    Returns
    -------
    str
        A new ``trace_id`` (UUID-4).
    """
    ctx = dict(context or {})
    explicit_trace_id = ctx.get("trace_id")
    deterministic_seed = ctx.get("deterministic_seed")
    if isinstance(explicit_trace_id, str) and explicit_trace_id:
        trace_id = explicit_trace_id
    elif isinstance(deterministic_seed, str) and deterministic_seed:
        trace_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"trace::{deterministic_seed}"))
    else:
        trace_id = _new_id()
    now = _now_iso()
    trace: Dict[str, Any] = {
        "trace_id": trace_id,
        "root_span_id": None,
        "spans": [],
        "artifacts": [],
        "start_time": now,
        "end_time": None,
        "context": ctx,
        "schema_version": SCHEMA_VERSION,
    }
    store_lock, traces, _ = _resolve_store(store)
    with store_lock:
        existing = traces.get(trace_id)
        if existing is not None:
            if existing.get("context") != ctx:
                raise TraceConflictError(
                    f"start_trace: trace_id '{trace_id}' already exists with conflicting context"
                )
            raise TraceConflictError(
                f"start_trace: trace_id '{trace_id}' already exists"
            )
        traces[trace_id] = trace
    return trace_id


def start_span(
    trace_id: str,
    name: str,
    parent_span_id: Optional[str] = None,
    *,
    store: Optional[TraceStore] = None,
) -> str:
    """Create a new Span inside *trace_id* and return its ``span_id``.

    Fail-closed rules
    -----------------
    - ``trace_id`` not found → raises ``TraceNotFoundError``
    - ``parent_span_id`` provided but not found in this trace → raises
      ``SpanNotFoundError``

    Parameters
    ----------
    trace_id:
        Owning trace.
    name:
        Human-readable operation name (e.g. ``"enforcement"``,
        ``"validator:validate_bundle_contract"``).
    parent_span_id:
        Optional parent span ID.  When ``None`` this becomes the root span.

    Returns
    -------
    str
        A new ``span_id`` (UUID-4).
    """
    if not isinstance(name, str) or not name:
        raise ValueError("start_span: name must be a non-empty string")

    store_lock, traces, span_index = _resolve_store(store)
    with store_lock:
        trace = traces.get(trace_id)
        if trace is None:
            raise TraceNotFoundError(f"start_span: trace_id '{trace_id}' not found")

        if parent_span_id is not None:
            parent_entry = span_index.get(parent_span_id)
            if parent_entry is None or parent_entry[0] != trace_id:
                raise SpanNotFoundError(
                    f"start_span: parent_span_id '{parent_span_id}' not found in trace '{trace_id}'"
                )

        span_id = _new_id()
        now = _now_iso()
        span: Dict[str, Any] = {
            "span_id": span_id,
            "trace_id": trace_id,
            "parent_span_id": parent_span_id,
            "name": name,
            "status": None,  # Set by end_span
            "start_time": now,
            "end_time": None,
            "events": [],
        }
        trace["spans"].append(span)
        span_index[span_id] = (trace_id, span)

        # First span created becomes the root span
        if trace["root_span_id"] is None:
            trace["root_span_id"] = span_id

    return span_id


def end_span(
    span_id: str,
    status: str = SPAN_STATUS_OK,
    *,
    store: Optional[TraceStore] = None,
) -> None:
    """Close a Span and record its status.

    Fail-closed: invalid span_id or unrecognised status → raises.

    Parameters
    ----------
    span_id:
        Target span.
    status:
        ``"ok"``, ``"error"``, or ``"blocked"``.
    """
    if status not in _VALID_STATUSES:
        raise ValueError(
            f"end_span: status '{status}' is not valid; must be one of {sorted(_VALID_STATUSES)}"
        )
    store_lock, _, span_index = _resolve_store(store)
    with store_lock:
        span = _find_span(span_id, span_index)
        if span is None:
            raise SpanNotFoundError(f"end_span: span_id '{span_id}' not found")
        span["status"] = status
        span["end_time"] = _now_iso()


def record_event(
    span_id: str,
    event_type: str,
    payload: Optional[Dict[str, Any]] = None,
    *,
    store: Optional[TraceStore] = None,
) -> None:
    """Append a structured Event to a Span.

    Fail-closed: invalid span_id → raises.

    Parameters
    ----------
    span_id:
        Owning span.
    event_type:
        Governed event type string (e.g. ``"validator_result"``,
        ``"slo_evaluation"``, ``"enforcement_decision"``).
    payload:
        Structured dict.  No free-text values where governed keys exist.
    """
    if not isinstance(event_type, str) or not event_type:
        raise ValueError("record_event: event_type must be a non-empty string")

    store_lock, _, span_index = _resolve_store(store)
    with store_lock:
        span = _find_span(span_id, span_index)
        if span is None:
            raise SpanNotFoundError(f"record_event: span_id '{span_id}' not found")
        event: Dict[str, Any] = {
            "event_type": event_type,
            "timestamp": _now_iso(),
            "payload": dict(payload or {}),
        }
        span["events"].append(event)


def attach_artifact(
    trace_id: str,
    artifact_id: str,
    artifact_type: str,
    span_id: Optional[str] = None,
    *,
    store: Optional[TraceStore] = None,
) -> None:
    """Link an artifact to a Trace.

    Every artifact produced in the execution path must be attached so that
    the trace provides full artifact provenance.

    Parameters
    ----------
    trace_id:
        Owning trace.
    artifact_id:
        Unique artifact identifier (e.g. decision_id, execution_id).
    artifact_type:
        Governed type string (e.g. ``"control_chain_decision"``,
        ``"validator_execution_result"``).
    span_id:
        Optional span that produced the artifact; records ``parent_span_id``
        in the attachment record.
    """
    store_lock, traces, _ = _resolve_store(store)
    with store_lock:
        trace = traces.get(trace_id)
        if trace is None:
            raise TraceNotFoundError(f"attach_artifact: trace_id '{trace_id}' not found")
        attachment: Dict[str, Any] = {
            "artifact_id": artifact_id,
            "artifact_type": artifact_type,
            "attached_at": _now_iso(),
            "parent_span_id": span_id,
        }
        trace["artifacts"].append(attachment)


def get_trace(trace_id: str, *, store: Optional[TraceStore] = None) -> Dict[str, Any]:
    """Return a deep copy of the full Trace dict.

    Fail-closed: unknown trace_id → raises ``TraceNotFoundError``.
    """
    store_lock, traces, _ = _resolve_store(store)
    with store_lock:
        trace = traces.get(trace_id)
        if trace is None:
            raise TraceNotFoundError(f"get_trace: trace_id '{trace_id}' not found")
        return deepcopy(trace)


def summarize_trace(trace_id: str, *, store: Optional[TraceStore] = None) -> str:
    """Return an operator-readable summary of a Trace.

    Shows:
    - full span tree with statuses
    - first failure span
    - linked artifacts

    Fail-closed: unknown trace_id → raises ``TraceNotFoundError``.
    """
    trace = get_trace(trace_id, store=store)
    lines: List[str] = [
        "Trace Summary (BK–BM)",
        "---------------------",
        f"  trace_id   : {trace['trace_id']}",
        f"  start_time : {trace['start_time']}",
        f"  end_time   : {trace.get('end_time') or '(open)'}",
        "",
        "Span Tree:",
    ]

    spans = trace.get("spans") or []
    # Build parent → children map
    children: Dict[Optional[str], List[Dict[str, Any]]] = {}
    for span in spans:
        pid = span.get("parent_span_id")
        children.setdefault(pid, []).append(span)

    # Walk span tree depth-first
    first_failure_span: Optional[str] = None

    def _walk(span_id: Optional[str], depth: int = 0) -> None:
        nonlocal first_failure_span
        for span in children.get(span_id, []):
            indent = "  " * (depth + 1)
            status = span.get("status") or "(open)"
            lines.append(
                f"{indent}[{status}] {span['name']} (span_id={span['span_id'][:8]}…)"
            )
            if status in (SPAN_STATUS_ERROR, SPAN_STATUS_BLOCKED) and first_failure_span is None:
                first_failure_span = span["span_id"]
            for event in span.get("events") or []:
                lines.append(f"{indent}  event: {event['event_type']} @ {event['timestamp']}")
            _walk(span["span_id"], depth + 1)

    _walk(None)

    lines.append("")
    lines.append(f"  first_failure_span : {first_failure_span or '(none)'}")
    lines.append("")
    lines.append("Artifacts:")
    for art in trace.get("artifacts") or []:
        lines.append(
            f"  [{art['artifact_type']}] id={art['artifact_id']} "
            f"span={art.get('parent_span_id', '(none)')}"
        )
    if not trace.get("artifacts"):
        lines.append("  (none)")

    return "\n".join(lines)


def validate_trace_context(
    trace_id: Optional[str],
    span_id: Optional[str] = None,
    *,
    store: Optional[TraceStore] = None,
) -> List[str]:
    """Validate that a trace context is complete and well-formed.

    Used by integration points to enforce fail-closed rules.

    Returns
    -------
    list of str
        Empty if valid.  Non-empty list of error messages if invalid.
        Callers MUST block execution when the list is non-empty.
    """
    errors: List[str] = []

    if not trace_id:
        errors.append("validate_trace_context: trace_id is missing or empty")
        return errors  # Cannot proceed without trace_id

    store_lock, traces, span_index = _resolve_store(store)
    with store_lock:
        trace = traces.get(trace_id)

    if trace is None:
        errors.append(f"validate_trace_context: trace_id '{trace_id}' not found in store")
        return errors

    # Verify structural integrity
    if "spans" not in trace:
        errors.append(f"validate_trace_context: trace '{trace_id}' is missing 'spans' field")
    if "artifacts" not in trace:
        errors.append(f"validate_trace_context: trace '{trace_id}' is missing 'artifacts' field")
    if "start_time" not in trace:
        errors.append(f"validate_trace_context: trace '{trace_id}' is missing 'start_time' field")

    if span_id is not None:
        with store_lock:
            entry = span_index.get(span_id)
        if entry is None or entry[0] != trace_id:
            errors.append(
                f"validate_trace_context: span_id '{span_id}' not found in trace '{trace_id}'"
            )

    return errors


def get_all_trace_ids(*, store: Optional[TraceStore] = None) -> List[str]:
    """Return a list of all trace IDs currently in the store.

    Useful for diagnostics and test teardown.
    """
    store_lock, traces, _ = _resolve_store(store)
    with store_lock:
        return list(traces.keys())


def clear_trace_store(*, store: Optional[TraceStore] = None) -> None:
    """Remove all traces from the in-process store.

    For use in testing only.  Not safe to call in production.
    """
    store_lock, traces, span_index = _resolve_store(store)
    with store_lock:
        traces.clear()
        span_index.clear()


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class TraceEngineError(Exception):
    """Base class for all trace engine errors."""


class TraceNotFoundError(TraceEngineError):
    """Raised when a trace_id cannot be found in the store."""


class SpanNotFoundError(TraceEngineError):
    """Raised when a span_id cannot be found in the store."""


class TraceConflictError(TraceEngineError):
    """Raised when start_trace attempts to reuse an existing trace_id."""
