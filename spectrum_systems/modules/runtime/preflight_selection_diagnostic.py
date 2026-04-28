"""Pytest selection diagnostic surface for governed preflight diagnosis.

This module is non-authoritative WFL/preflight observation infrastructure. It
produces an observation payload that names the changed paths a preflight
runner could not map to a pytest selection, the surface_rules it attempted
from the canonical policy registry, and the registry locations a future
operator should update to repair the mapping.

The payload carries no authority. It only records observations and
recommended inputs for canonical owner systems to consume.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

PYTEST_SELECTION_OBSERVATION_FAILURE_CLASSES: frozenset[str] = frozenset(
    {
        "pytest_selection_missing",
        "pytest_selection_mismatch",
        "pytest_selection_filtering",
        "pytest_selection_threshold",
    }
)

_RECOMMENDED_MAPPING_LOCATIONS: tuple[str, ...] = (
    "docs/governance/pytest_pr_selection_integrity_policy.json#surface_rules",
    "docs/governance/preflight_required_surface_test_overrides.json",
    "scripts/run_contract_preflight.py:_REQUIRED_SURFACE_TEST_OVERRIDES",
    "scripts/run_contract_preflight.py:_is_forced_evaluation_surface",
)


def _string_iterable(value: Any) -> Iterable[str]:
    if not isinstance(value, list):
        return ()
    return (str(item).strip() for item in value if isinstance(item, str) and str(item).strip())


def _load_policy_surface_rules(policy_path: Path) -> list[dict[str, Any]]:
    if not policy_path.is_file():
        return []
    try:
        payload = json.loads(policy_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, dict):
        return []
    rules: list[dict[str, Any]] = []
    for rule in payload.get("surface_rules") or []:
        if not isinstance(rule, dict):
            continue
        prefix = str(rule.get("path_prefix") or "").strip()
        if not prefix:
            continue
        targets = list(_string_iterable(rule.get("required_test_targets")))
        rules.append({"path_prefix": prefix, "required_test_targets": targets})
    return rules


def build_pytest_selection_observation(
    *,
    report: dict[str, Any],
    policy_path: Path,
) -> dict[str, Any]:
    """Build the diagnostic observation surface for a preflight report.

    The returned payload conforms to the optional ``pytest_selection_diagnostic``
    field of ``preflight_block_diagnosis_record``. The field is observation-only
    and carries no authority — canonical owners consume it as a recommended
    input.
    """
    detection = report.get("changed_path_detection") or {}
    changed_paths = list(_string_iterable(detection.get("changed_paths_resolved")))

    selection_observation = report.get("pytest_selection_integrity") or {}
    selected = set(_string_iterable(selection_observation.get("selected_test_targets")))
    missing_required = set(_string_iterable(selection_observation.get("missing_required_targets")))

    no_op_paths = {
        str(entry.get("path") or "").strip()
        for entry in (report.get("evaluation_classification") or [])
        if isinstance(entry, dict)
        and str(entry.get("classification") or "") == "no_applicable_contract_surface"
    }

    unmatched: set[str] = set()
    for path in changed_paths:
        if path in no_op_paths:
            unmatched.add(path)
            continue
        if path.startswith("tests/") and path.endswith(".py") and path not in selected:
            unmatched.add(path)
    for target in missing_required:
        if target not in selected:
            unmatched.add(target)

    return {
        "unmatched_changed_paths": sorted(unmatched),
        "attempted_surface_rules": _load_policy_surface_rules(policy_path),
        "recommended_mapping_locations": list(_RECOMMENDED_MAPPING_LOCATIONS),
    }


def is_pytest_selection_observation_class(failure_class: str | None) -> bool:
    if not failure_class:
        return False
    return failure_class in PYTEST_SELECTION_OBSERVATION_FAILURE_CLASSES


__all__ = [
    "PYTEST_SELECTION_OBSERVATION_FAILURE_CLASSES",
    "build_pytest_selection_observation",
    "is_pytest_selection_observation_class",
]
