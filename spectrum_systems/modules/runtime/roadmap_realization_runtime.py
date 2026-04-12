"""Runtime helpers for strict roadmap realization status control."""

from __future__ import annotations

from typing import Iterable


ALLOWED_STATUSES = [
    "planned_only",
    "artifact_materialized",
    "partially_realized",
    "runtime_realized",
    "verified",
]
RUNTIME_READY_DEPENDENCY_STATUSES = {"runtime_realized", "verified"}


class RoadmapRealizationRuntimeError(ValueError):
    """Raised when realization checks violate fail-closed runtime rules."""


def authoritative_start_status(status: str) -> str:
    """Normalize caller-provided status to an authoritative runtime baseline."""
    if status not in ALLOWED_STATUSES:
        raise RoadmapRealizationRuntimeError(f"unknown realization status: {status}")
    if status in {"runtime_realized", "verified"}:
        return "planned_only"
    return status


def enforce_realization_dependencies(
    *,
    step_id: str,
    depends_on: Iterable[str],
    attempted_steps: Iterable[str],
    status_by_step: dict[str, str],
) -> None:
    attempted = list(attempted_steps)
    if step_id not in attempted:
        raise RoadmapRealizationRuntimeError(f"step {step_id} not in attempted sequence")
    step_index = attempted.index(step_id)

    for dependency in depends_on:
        if dependency not in status_by_step:
            raise RoadmapRealizationRuntimeError(f"dependency {dependency} not found for {step_id}")
        if dependency in attempted and attempted.index(dependency) >= step_index:
            raise RoadmapRealizationRuntimeError(f"dependency order violated: {step_id} cannot run before {dependency}")
        dependency_status = status_by_step.get(dependency)
        if dependency_status not in RUNTIME_READY_DEPENDENCY_STATUSES:
            raise RoadmapRealizationRuntimeError(
                f"dependency {dependency} must be runtime_realized before {step_id}; found {dependency_status}"
            )


def next_realization_status(
    *,
    current_status: str,
    dependency_checks_passed: bool,
    ownership_checks_passed: bool,
    forbidden_patterns_absent: bool,
    runtime_entrypoints_exist: bool,
    behavioral_tests_passed: bool,
    verification_checks_passed: bool,
) -> str:
    if current_status not in ALLOWED_STATUSES:
        raise RoadmapRealizationRuntimeError(f"unknown realization status: {current_status}")

    runtime_gate_passed = all(
        (
            dependency_checks_passed,
            ownership_checks_passed,
            forbidden_patterns_absent,
            runtime_entrypoints_exist,
            behavioral_tests_passed,
        )
    )
    if not runtime_gate_passed:
        return current_status

    if current_status in {"planned_only", "artifact_materialized", "partially_realized"}:
        return "runtime_realized"

    if current_status == "runtime_realized" and verification_checks_passed:
        return "verified"

    return current_status
