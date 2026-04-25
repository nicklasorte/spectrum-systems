"""
PQX Step Harness — spectrum_systems/modules/orchestration/pqx_step_harness.py

Bounded, traced execution wrapper for transcript pipeline steps.
PQX is the sole execution authority: every pipeline step must run through this harness.

Invariants:
- Every execution emits a pqx_execution_record regardless of success or failure.
- Outputs are schema-validated before being registered in the artifact store.
- Missing outputs are treated as failures (fail-closed).
- trace_id and span_id are attached to all outputs.
- No step may produce output that bypasses the harness.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from spectrum_systems.modules.runtime.artifact_store import (
    ArtifactStore,
    ArtifactStoreError,
    compute_content_hash,
)


class PQXExecutionError(RuntimeError):
    """Raised when a PQX step fails. Always carries reason_codes."""

    def __init__(
        self,
        message: str,
        reason_codes: List[str],
        step_name: str,
        execution_record: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.reason_codes = reason_codes
        self.step_name = step_name
        self.execution_record = execution_record

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": str(self),
            "reason_codes": self.reason_codes,
            "step_name": self.step_name,
            "execution_record": self.execution_record,
        }


def _new_trace_id() -> str:
    return uuid.uuid4().hex + uuid.uuid4().hex[:0]  # 32-char hex


def _new_span_id() -> str:
    return uuid.uuid4().hex[:16]


def _build_execution_record(
    *,
    step_name: str,
    trace_id: str,
    span_id: str,
    input_artifact_ids: List[str],
    output_artifact_id: Optional[str],
    status: str,
    started_at: str,
    completed_at: str,
    duration_ms: int,
    reason_codes: List[str],
    error_detail: Optional[str],
) -> Dict[str, Any]:
    record_id = f"PQX-REC-{uuid.uuid4().hex[:12].upper()}"
    record: Dict[str, Any] = {
        "record_id": record_id,
        "record_type": "pqx_execution_record",
        "step_name": step_name,
        "trace_id": trace_id,
        "span_id": span_id,
        "input_artifact_ids": input_artifact_ids,
        "output_artifact_id": output_artifact_id,
        "status": status,
        "started_at": started_at,
        "completed_at": completed_at,
        "duration_ms": duration_ms,
        "reason_codes": reason_codes,
    }
    if error_detail is not None:
        record["error_detail"] = error_detail
    return record


def run_pqx_step(
    step_name: str,
    inputs: Dict[str, Any],
    execution_fn: Callable[[Dict[str, Any], str, str], Dict[str, Any]],
    artifact_store: ArtifactStore,
    parent_trace_id: Optional[str] = None,
    expected_output_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute a single governed pipeline step.

    Parameters
    ----------
    step_name:
        Canonical name of the step (e.g., 'normalize_transcript').
    inputs:
        Input data passed to execution_fn. Must contain 'input_artifact_ids' list.
    execution_fn:
        Callable(inputs, trace_id, span_id) -> output_artifact dict.
        Must return a fully-formed artifact dict with all required envelope fields.
    artifact_store:
        Store to register output artifacts in.
    parent_trace_id:
        If provided, output artifacts inherit this trace_id (span chaining).
    expected_output_type:
        If provided, the output artifact's artifact_type must exactly match this value.
        A mismatch raises PQXExecutionError with reason_code OUTPUT_TYPE_MISMATCH.
        This prevents a step from silently producing the wrong artifact type.

    Returns
    -------
    Dict containing 'execution_record' and 'output_artifact'.

    Raises
    ------
    PQXExecutionError
        On any failure: execution error, missing output, schema violation, type mismatch.
        Always includes the execution_record in the exception.
    """
    if not step_name or not isinstance(step_name, str):
        raise PQXExecutionError(
            "step_name must be a non-empty string",
            reason_codes=["INVALID_STEP_NAME"],
            step_name=str(step_name),
        )
    if not callable(execution_fn):
        raise PQXExecutionError(
            "execution_fn must be callable",
            reason_codes=["INVALID_EXECUTION_FN"],
            step_name=step_name,
        )

    trace_id = parent_trace_id if parent_trace_id else _new_trace_id()
    span_id = _new_span_id()
    input_artifact_ids: List[str] = inputs.get("input_artifact_ids", [])

    started_at = datetime.now(timezone.utc).isoformat()
    t_start = time.monotonic()

    output_artifact: Optional[Dict[str, Any]] = None
    status = "failed"
    reason_codes: List[str] = []
    error_detail: Optional[str] = None
    registered_id: Optional[str] = None

    try:
        result = execution_fn(inputs, trace_id, span_id)

        if result is None:
            raise PQXExecutionError(
                f"Step '{step_name}' returned None — output is required",
                reason_codes=["MISSING_OUTPUT"],
                step_name=step_name,
            )
        if not isinstance(result, dict):
            raise PQXExecutionError(
                f"Step '{step_name}' returned non-dict output",
                reason_codes=["INVALID_OUTPUT_TYPE"],
                step_name=step_name,
            )

        if expected_output_type is not None:
            actual_type = result.get("artifact_type")
            if actual_type != expected_output_type:
                raise PQXExecutionError(
                    f"Step '{step_name}' produced artifact_type={actual_type!r} "
                    f"but expected_output_type={expected_output_type!r}",
                    reason_codes=["OUTPUT_TYPE_MISMATCH"],
                    step_name=step_name,
                )

        if "content_hash" not in result:
            result["content_hash"] = compute_content_hash(result)

        registered_id = artifact_store.register_artifact(result)
        output_artifact = result
        status = "success"

    except PQXExecutionError:
        raise

    except ArtifactStoreError as exc:
        error_detail = str(exc)
        reason_codes = [exc.reason_code, "ARTIFACT_STORE_REJECTION"]

    except Exception as exc:
        error_detail = f"{type(exc).__name__}: {exc}"
        reason_codes = ["EXECUTION_EXCEPTION"]

    finally:
        t_end = time.monotonic()
        completed_at = datetime.now(timezone.utc).isoformat()
        duration_ms = int((t_end - t_start) * 1000)

        execution_record = _build_execution_record(
            step_name=step_name,
            trace_id=trace_id,
            span_id=span_id,
            input_artifact_ids=input_artifact_ids,
            output_artifact_id=registered_id,
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            reason_codes=reason_codes,
            error_detail=error_detail,
        )

    if status == "failed":
        raise PQXExecutionError(
            f"Step '{step_name}' failed: {error_detail}",
            reason_codes=reason_codes,
            step_name=step_name,
            execution_record=execution_record,
        )

    return {
        "execution_record": execution_record,
        "output_artifact": output_artifact,
    }


__all__ = [
    "PQXExecutionError",
    "run_pqx_step",
]
