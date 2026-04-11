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


class RoadmapRealizationRuntimeError(ValueError):
    """Raised when realization checks violate fail-closed runtime rules."""


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
        if dependency in attempted:
            if attempted.index(dependency) >= step_index:
                raise RoadmapRealizationRuntimeError(
                    f"dependency order violated: {step_id} cannot run before {dependency}"
                )
        dependency_status = status_by_step.get(dependency)
        if dependency_status not in {"runtime_realized", "verified"}:
            raise RoadmapRealizationRuntimeError(
                f"dependency {dependency} not runtime realized for {step_id}"
            )


def next_realization_status(
    *,
    current_status: str,
    forbidden_patterns_absent: bool,
    runtime_entrypoints_exist: bool,
    behavioral_tests_passed: bool,
    verification_checks_passed: bool,
) -> str:
    if current_status not in ALLOWED_STATUSES:
        raise RoadmapRealizationRuntimeError(f"unknown realization status: {current_status}")

    if not (forbidden_patterns_absent and runtime_entrypoints_exist and behavioral_tests_passed):
        return current_status

    runtime_status = "runtime_realized"
    if verification_checks_passed:
        return "verified"
    return runtime_status
