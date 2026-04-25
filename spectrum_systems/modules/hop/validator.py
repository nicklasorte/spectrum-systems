"""Pre-eval interface validation for harness candidates.

A candidate is *only* admitted to evaluation if it passes:

1. **schema validation** — the ``hop_harness_candidate`` payload conforms to
   ``contracts/schemas/hop/harness_candidate.schema.json``.
2. **import + smoke** — the declared module imports without error and exposes
   the declared entrypoint as a callable.
3. **method existence** — every name in ``declared_methods`` is a callable
   attribute on the imported module.

Any failure produces a structured ``hop_harness_failure_hypothesis`` artifact
with ``stage = "validation"`` and ``severity = "reject"``. Rejected candidates
never reach the evaluator.
"""

from __future__ import annotations

import importlib
from datetime import datetime, timezone
from typing import Any

from spectrum_systems.modules.hop.artifacts import finalize_artifact, make_trace
from spectrum_systems.modules.hop.schemas import (
    HopSchemaError,
    validate_hop_artifact,
)


class HopValidatorError(Exception):
    """Raised when validator-level invariants cannot be evaluated."""


def _utcnow() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _build_failure(
    *,
    candidate_id: str,
    failure_class: str,
    evidence: list[dict[str, str]],
    trace_id: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "artifact_type": "hop_harness_failure_hypothesis",
        "schema_ref": "hop/harness_failure_hypothesis.schema.json",
        "schema_version": "1.0.0",
        "trace": make_trace(primary=trace_id),
        "hypothesis_id": f"v_{failure_class}_{candidate_id}",
        "candidate_id": candidate_id,
        "run_id": None,
        "stage": "validation",
        "failure_class": failure_class,
        "severity": "reject",
        "evidence": evidence,
        "detected_at": _utcnow(),
        "release_block_signal": True,
    }
    finalize_artifact(payload, id_prefix="hop_failure_")
    return payload


def validate_candidate(
    candidate_payload: dict[str, Any],
    *,
    trace_id: str = "hop_validator",
) -> tuple[bool, list[dict[str, Any]]]:
    """Validate a candidate. Returns ``(ok, failures)``.

    ``ok`` is True only when every gate passes. ``failures`` is the list of
    ``hop_harness_failure_hypothesis`` artifacts produced; never None.
    """
    failures: list[dict[str, Any]] = []
    candidate_id = candidate_payload.get("candidate_id") or "unknown"

    # 1. schema validation
    try:
        validate_hop_artifact(candidate_payload, "hop_harness_candidate")
    except HopSchemaError as exc:
        failures.append(
            _build_failure(
                candidate_id=str(candidate_id),
                failure_class="schema_violation",
                evidence=[{"kind": "schema_path", "detail": str(exc)}],
                trace_id=trace_id,
            )
        )
        return False, failures

    candidate_id = candidate_payload["candidate_id"]
    module_name = candidate_payload["code_module"]
    entrypoint = candidate_payload["code_entrypoint"]
    declared_methods = candidate_payload["declared_methods"]

    # 2. import smoke test
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:  # pragma: no cover - import errors covered by tests
        failures.append(
            _build_failure(
                candidate_id=candidate_id,
                failure_class="import_error",
                evidence=[
                    {"kind": "code_path", "detail": module_name},
                    {"kind": "exception", "detail": f"{type(exc).__name__}: {exc}"},
                ],
                trace_id=trace_id,
            )
        )
        return False, failures

    # 3. entrypoint must exist and be callable
    entry = getattr(module, entrypoint, None)
    if entry is None or not callable(entry):
        failures.append(
            _build_failure(
                candidate_id=candidate_id,
                failure_class="missing_method",
                evidence=[
                    {"kind": "code_path", "detail": f"{module_name}.{entrypoint}"},
                    {"kind": "snippet", "detail": "entrypoint_not_callable"},
                ],
                trace_id=trace_id,
            )
        )
        return False, failures

    # 4. declared methods must each be callable on the module
    missing = [name for name in declared_methods if not callable(getattr(module, name, None))]
    if missing:
        failures.append(
            _build_failure(
                candidate_id=candidate_id,
                failure_class="missing_method",
                evidence=[
                    {"kind": "code_path", "detail": module_name},
                    {"kind": "snippet", "detail": "missing_methods=" + ",".join(missing)},
                ],
                trace_id=trace_id,
            )
        )
        return False, failures

    return True, failures
