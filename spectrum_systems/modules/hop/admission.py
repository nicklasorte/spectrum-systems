"""HOP candidate admission — single chained gate before evaluation.

Composes ``validator.validate_candidate`` with ``safety_checks.scan_candidate``.
The result is fail-closed: a candidate is admitted ONLY when both gates
pass. The evaluator should call ``admit_candidate`` (or be invoked behind a
pipeline that has already done so); the integration test enforces this.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from spectrum_systems.modules.hop.safety_checks import scan_candidate
from spectrum_systems.modules.hop.validator import validate_candidate


def admit_candidate(
    candidate_payload: dict[str, Any],
    eval_cases: Iterable[Mapping[str, Any]],
    *,
    trace_id: str = "hop_admission",
) -> tuple[bool, list[dict[str, Any]]]:
    """Run the full pre-eval admission chain.

    Returns ``(ok, failures)``. ``ok`` is True only when every gate passes.
    ``failures`` is the union of validator + safety_check failures, never
    None.
    """
    failures: list[dict[str, Any]] = []
    ok_validator, validator_failures = validate_candidate(
        candidate_payload, trace_id=trace_id
    )
    failures.extend(validator_failures)
    if not ok_validator:
        return False, failures

    ok_safety, safety_failures = scan_candidate(
        candidate_payload, eval_cases, trace_id=trace_id
    )
    failures.extend(safety_failures)
    if not ok_safety:
        return False, failures

    return True, failures
