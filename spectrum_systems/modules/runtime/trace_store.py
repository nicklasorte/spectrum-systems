"""Trace Persistence Layer (BN).

Provides durable, file-backed storage for trace artifacts produced by the
BK–BM Trace + Correlation Layer.  Extends in-memory explainability to
audit-grade, replayable execution records.

Design principles
-----------------
- Fail closed:  any missing or inconsistent state raises rather than silently
  degrading.
- Schema-governed:  every persisted trace is validated against
  ``persisted_trace.schema.json`` before being written and after being read.
- Storage-path conventions:  all traces are stored under
  ``data/traces/<trace_id>.json`` relative to the repository root.
- No hidden re-derivation:  what is written is exactly what is read back.
- Thread-safe + immutable: each write is create-only and fails if the destination already exists.

Public API
----------
persist_trace(trace)                → storage_path (str)
load_trace(trace_id)                → persisted_trace_envelope (dict)
list_traces()                       → list[str]  (trace_ids)
delete_trace(trace_id)              → None (blocked; store is append-only)
validate_persisted_trace(envelope)  → list[str]  (errors; empty = valid)
"""

from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from jsonschema import Draft202012Validator, FormatChecker

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ENVELOPE_VERSION: str = "1.0.0"

_REPO_ROOT = Path(__file__).resolve().parents[3]
_TRACES_DIR = _REPO_ROOT / "data" / "traces"
_SCHEMA_DIR = _REPO_ROOT / "contracts" / "schemas"
_ENVELOPE_SCHEMA_PATH = _SCHEMA_DIR / "persisted_trace.schema.json"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _load_envelope_schema() -> Dict[str, Any]:
    """Load and return the persisted_trace envelope JSON Schema."""
    return json.loads(_ENVELOPE_SCHEMA_PATH.read_text(encoding="utf-8"))


def _ensure_traces_dir(base_dir: Optional[Path] = None) -> Path:
    """Return the traces storage directory, creating it if necessary."""
    target = base_dir if base_dir is not None else _TRACES_DIR
    target.mkdir(parents=True, exist_ok=True)
    return target


def _trace_path(trace_id: str, base_dir: Optional[Path] = None) -> Path:
    """Return the canonical path for storing *trace_id*."""
    if not trace_id or not isinstance(trace_id, str):
        raise TraceStoreError("trace_id must be a non-empty string")
    storage_dir = _ensure_traces_dir(base_dir)
    return storage_dir / f"{trace_id}.json"


def _relative_storage_path(full_path: Path) -> str:
    """Return a repo-root-relative path string for *full_path*."""
    try:
        return str(full_path.relative_to(_REPO_ROOT))
    except ValueError:
        return str(full_path)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def persist_trace(
    trace: Dict[str, Any],
    base_dir: Optional[Path] = None,
) -> str:
    """Persist a trace object to the file-backed store.

    The trace is wrapped in a governed envelope, validated against
    ``persisted_trace.schema.json``, and written atomically.

    Parameters
    ----------
    trace:
        A full Trace dict as returned by
        ``spectrum_systems.modules.runtime.trace_engine.get_trace``.
    base_dir:
        Override the storage directory (primarily for testing).

    Returns
    -------
    str
        The repo-root-relative path where the trace was written.

    Raises
    ------
    TraceStoreError
        If *trace* is missing required fields or schema validation fails.
    TraceStorePersistenceError
        If the file cannot be written.
    """
    if not isinstance(trace, dict):
        raise TraceStoreError("persist_trace: trace must be a dict")

    trace_id = trace.get("trace_id")
    if not trace_id:
        raise TraceStoreError("persist_trace: trace is missing 'trace_id'")

    dest_path = _trace_path(trace_id, base_dir)
    storage_path = _relative_storage_path(dest_path)

    envelope: Dict[str, Any] = {
        "envelope_version": ENVELOPE_VERSION,
        "persisted_at": _now_iso(),
        "storage_path": storage_path,
        "trace": deepcopy(trace),
    }

    errors = validate_persisted_trace(envelope)
    if errors:
        raise TraceStoreError(
            f"persist_trace: envelope validation failed for trace '{trace_id}': "
            + "; ".join(errors)
        )

    _atomic_write(dest_path, envelope)
    return storage_path


def load_trace(
    trace_id: str,
    base_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Load and return a persisted trace envelope from disk.

    Parameters
    ----------
    trace_id:
        The trace to load.
    base_dir:
        Override the storage directory (primarily for testing).

    Returns
    -------
    dict
        The full persisted trace envelope (including the inner ``trace``
        dict and all envelope metadata).

    Raises
    ------
    TraceNotFoundError
        If no persisted trace for *trace_id* exists.
    TraceStoreError
        If the stored file is corrupt or fails schema validation.
    """
    path = _trace_path(trace_id, base_dir)
    if not path.exists():
        raise TraceNotFoundError(
            f"load_trace: no persisted trace found for trace_id '{trace_id}'"
        )

    try:
        raw = path.read_text(encoding="utf-8")
        envelope = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise TraceStoreError(
            f"load_trace: failed to read trace '{trace_id}' from '{path}': {exc}"
        ) from exc

    errors = validate_persisted_trace(envelope)
    if errors:
        raise TraceStoreError(
            f"load_trace: stored trace '{trace_id}' failed schema validation: "
            + "; ".join(errors)
        )

    stored_trace_id = ((envelope.get("trace") or {}).get("trace_id"))
    if stored_trace_id != trace_id:
        raise TraceStoreError(
            "load_trace: trace identity mismatch between request and payload "
            f"(requested={trace_id!r}, stored={stored_trace_id!r})"
        )

    expected_storage_path = _relative_storage_path(path)
    stored_storage_path = envelope.get("storage_path")
    if stored_storage_path != expected_storage_path:
        raise TraceStoreError(
            "load_trace: storage_path mismatch for persisted trace "
            f"'{trace_id}' (expected={expected_storage_path!r}, "
            f"stored={stored_storage_path!r})"
        )

    return envelope


def list_traces(base_dir: Optional[Path] = None) -> List[str]:
    """Return a sorted list of all persisted trace IDs.

    Parameters
    ----------
    base_dir:
        Override the storage directory (primarily for testing).

    Returns
    -------
    list[str]
        Sorted list of trace IDs (filename stems) found in the storage
        directory.  Returns an empty list if the directory does not yet exist.
    """
    storage_dir = base_dir if base_dir is not None else _TRACES_DIR
    if not storage_dir.exists():
        return []
    return sorted(p.stem for p in storage_dir.glob("*.json"))


def delete_trace(
    trace_id: str,
    base_dir: Optional[Path] = None,
) -> None:
    """Block deletion for governed trace artifacts.

    Governed traces are append-only and must not be physically deleted.
    """
    _ = _trace_path(trace_id, base_dir)
    raise TraceStoreError(
        "delete_trace: physical deletion is forbidden for governed traces; "
        "trace_store is append-only"
    )


def validate_persisted_trace(envelope: Dict[str, Any]) -> List[str]:
    """Validate *envelope* against the ``persisted_trace.schema.json`` contract.

    Parameters
    ----------
    envelope:
        The persisted trace envelope dict to validate.

    Returns
    -------
    list[str]
        Empty list if valid.  Non-empty list of error messages if invalid.
        Callers MUST treat any non-empty result as a hard failure.
    """
    if not isinstance(envelope, dict):
        return ["validate_persisted_trace: envelope must be a dict"]

    try:
        schema = _load_envelope_schema()
    except (OSError, json.JSONDecodeError) as exc:
        return [f"validate_persisted_trace: could not load envelope schema: {exc}"]

    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(envelope), key=lambda e: list(e.path))
    return [e.message for e in errors]


# ---------------------------------------------------------------------------
# Internal write helper
# ---------------------------------------------------------------------------


def _atomic_write(dest: Path, data: Dict[str, Any]) -> None:
    """Write *data* as JSON to *dest* exactly once (immutable create-only)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2, ensure_ascii=False) + "\n"

    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        fd = os.open(dest, flags, 0o644)
    except FileExistsError as exc:
        raise TraceStorePersistenceError(
            f"_atomic_write: refused overwrite for existing governed artifact '{dest}'"
        ) from exc
    except OSError as exc:
        raise TraceStorePersistenceError(
            f"_atomic_write: failed to create '{dest}': {exc}"
        ) from exc

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
    except OSError as exc:
        raise TraceStorePersistenceError(
            f"_atomic_write: failed to write to '{dest}': {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class TraceStoreError(Exception):
    """Base class for all trace store errors."""


class TraceNotFoundError(TraceStoreError):
    """Raised when a trace_id cannot be found in the persistent store."""


class TraceStorePersistenceError(TraceStoreError):
    """Raised when a file-system operation fails during trace persistence."""
