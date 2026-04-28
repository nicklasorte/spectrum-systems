"""CL-07 / CL-09: PQX execution envelope — pure validator.

Every PQX run must surface a normalized execution envelope carrying:

  * ``run_id``                — deterministic run identifier;
  * ``trace_id``              — trace identifier shared with upstream;
  * ``input_refs``            — list of artifact ids consumed;
  * ``output_refs``           — list of artifact ids produced;
  * ``output_hash``           — content hash of the produced output;
  * ``status``                — ``ok | failed | skipped``;
  * ``replay_ref``            — replay record reference;
  * ``replayable``            — bool flag asserted by REP;
  * ``aex_admission_ref``     — back-reference to admission proof.

This validator does not own execution; PQX retains that authority. It
detects execution drift (missing trace_id, missing output_hash, missing
input refs, run_id mismatch with admission, unreplayable envelope) and
emits stable canonical reasons consumed by the primary reason policy
under the ``execution`` precedence class.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

REQUIRED_KEYS: Tuple[str, ...] = (
    "run_id",
    "trace_id",
    "input_refs",
    "output_refs",
    "output_hash",
    "status",
    "replay_ref",
    "replayable",
    "aex_admission_ref",
)

REASON_OK = "EXECUTION_ENVELOPE_OK"
REASON_ENVELOPE_MISSING = "EXECUTION_ENVELOPE_MISSING"
REASON_TRACE_ID_MISSING = "EXECUTION_TRACE_ID_MISSING"
REASON_RUN_ID_MISSING = "EXECUTION_RUN_ID_MISSING"
REASON_RUN_ID_MISMATCH = "EXECUTION_RUN_ID_MISMATCH"
REASON_OUTPUT_HASH_MISSING = "EXECUTION_OUTPUT_HASH_MISSING"
REASON_INPUT_REFS_MISSING = "EXECUTION_INPUT_REFS_MISSING"
REASON_OUTPUT_REFS_MISSING = "EXECUTION_OUTPUT_REFS_MISSING"
REASON_NOT_REPLAYABLE = "EXECUTION_NOT_REPLAYABLE"
REASON_BAD_STATUS = "EXECUTION_BAD_STATUS"
REASON_ADMISSION_REF_MISSING = "EXECUTION_ADMISSION_REF_MISSING"

ALLOWED_STATUS = ("ok", "failed", "skipped")


class ExecutionEnvelopeError(ValueError):
    """Raised only on programmer-misuse."""


def _violation(code: str, **details: Any) -> Dict[str, Any]:
    return {"reason_code": code, **details}


def _is_nonempty_str(v: Any) -> bool:
    return isinstance(v, str) and bool(v.strip())


def validate_execution_envelope(
    envelope: Optional[Mapping[str, Any]],
    *,
    expected_run_id: Optional[str] = None,
    expected_trace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Validate a PQX execution envelope.

    When ``expected_run_id`` / ``expected_trace_id`` are supplied (e.g. from
    AEX admission), a mismatch fails closed with ``EXECUTION_RUN_ID_MISMATCH``.
    """
    if envelope is None or not isinstance(envelope, Mapping):
        return {
            "ok": False,
            "violations": [_violation(REASON_ENVELOPE_MISSING)],
            "primary_reason": REASON_ENVELOPE_MISSING,
        }

    violations: List[Dict[str, Any]] = []

    trace_id = envelope.get("trace_id")
    if not _is_nonempty_str(trace_id):
        violations.append(_violation(REASON_TRACE_ID_MISSING))

    run_id = envelope.get("run_id")
    if not _is_nonempty_str(run_id):
        violations.append(_violation(REASON_RUN_ID_MISSING))
    elif expected_run_id and run_id != expected_run_id:
        violations.append(
            _violation(
                REASON_RUN_ID_MISMATCH, expected=expected_run_id, got=run_id
            )
        )

    if expected_trace_id and _is_nonempty_str(trace_id) and trace_id != expected_trace_id:
        violations.append(
            _violation(
                "EXECUTION_TRACE_ID_MISMATCH",
                expected=expected_trace_id,
                got=trace_id,
            )
        )

    output_hash = envelope.get("output_hash")
    if not _is_nonempty_str(output_hash):
        violations.append(_violation(REASON_OUTPUT_HASH_MISSING))

    input_refs = envelope.get("input_refs")
    if not isinstance(input_refs, Sequence) or not input_refs or any(
        not _is_nonempty_str(r) for r in input_refs
    ):
        violations.append(_violation(REASON_INPUT_REFS_MISSING))

    output_refs = envelope.get("output_refs")
    if not isinstance(output_refs, Sequence) or not output_refs or any(
        not _is_nonempty_str(r) for r in output_refs
    ):
        violations.append(_violation(REASON_OUTPUT_REFS_MISSING))

    status = envelope.get("status")
    if not _is_nonempty_str(status) or status not in ALLOWED_STATUS:
        violations.append(_violation(REASON_BAD_STATUS, got=status))

    replay_ref = envelope.get("replay_ref")
    replayable = envelope.get("replayable")
    if not _is_nonempty_str(replay_ref) or replayable is not True:
        violations.append(_violation(REASON_NOT_REPLAYABLE))

    if not _is_nonempty_str(envelope.get("aex_admission_ref")):
        violations.append(_violation(REASON_ADMISSION_REF_MISSING))

    primary_reason = REASON_OK
    if violations:
        primary_reason = violations[0]["reason_code"]

    return {
        "ok": not violations,
        "violations": violations,
        "primary_reason": primary_reason,
    }


def normalize_execution_envelope(
    *,
    run_id: str,
    trace_id: str,
    input_refs: Sequence[str],
    output_refs: Sequence[str],
    output_hash: str,
    status: str,
    replay_ref: str,
    replayable: bool,
    aex_admission_ref: str,
    artifact_ids: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Build a canonical normalized PQX execution envelope.

    Pure data construction — does not trigger execution.
    """
    return {
        "artifact_type": "pqx_core_loop_execution_envelope",
        "schema_version": "1.0.0",
        "run_id": run_id,
        "trace_id": trace_id,
        "input_refs": list(input_refs),
        "output_refs": list(output_refs),
        "output_hash": output_hash,
        "status": status,
        "replay_ref": replay_ref,
        "replayable": bool(replayable),
        "aex_admission_ref": aex_admission_ref,
        "artifact_ids": list(artifact_ids or output_refs),
    }


__all__ = [
    "REQUIRED_KEYS",
    "ALLOWED_STATUS",
    "ExecutionEnvelopeError",
    "REASON_OK",
    "REASON_ENVELOPE_MISSING",
    "REASON_TRACE_ID_MISSING",
    "REASON_RUN_ID_MISSING",
    "REASON_RUN_ID_MISMATCH",
    "REASON_OUTPUT_HASH_MISSING",
    "REASON_INPUT_REFS_MISSING",
    "REASON_OUTPUT_REFS_MISSING",
    "REASON_NOT_REPLAYABLE",
    "REASON_BAD_STATUS",
    "REASON_ADMISSION_REF_MISSING",
    "validate_execution_envelope",
    "normalize_execution_envelope",
]
