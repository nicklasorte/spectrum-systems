"""Deterministic pytest selection integrity evaluation for contract preflight."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class PytestSelectionIntegrityError(ValueError):
    """Raised when policy or runtime inputs are malformed."""


@dataclass(frozen=True)
class SelectionIntegrityEvaluation:
    status: str
    decision: str
    blocking_reasons: list[str]
    payload: dict[str, Any]


def _load_policy(policy_path: Path) -> dict[str, Any]:
    if not policy_path.is_file():
        raise PytestSelectionIntegrityError(f"missing_selection_policy:{policy_path}")
    payload = json.loads(policy_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise PytestSelectionIntegrityError("selection policy must be a JSON object")
    return payload


def _required_targets_from_policy(*, changed_paths: list[str], policy: dict[str, Any]) -> list[str]:
    rules = policy.get("surface_rules")
    if not isinstance(rules, list):
        return []
    required: set[str] = set()
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        prefix = str(rule.get("path_prefix") or "").strip()
        targets = rule.get("required_test_targets") or []
        if not prefix or not isinstance(targets, list):
            continue
        if any(path.startswith(prefix) for path in changed_paths):
            required.update(str(target).strip() for target in targets if isinstance(target, str) and str(target).strip())
    return sorted(required)


def _collect_equivalence_groups(policy: dict[str, Any]) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    raw = policy.get("bounded_equivalence")
    if not isinstance(raw, list):
        return groups
    for item in raw:
        if not isinstance(item, dict):
            continue
        required_target = str(item.get("required_target") or "").strip()
        equivalents = item.get("equivalent_targets") or []
        if not required_target or not isinstance(equivalents, list):
            continue
        normalized = sorted({str(target).strip() for target in equivalents if isinstance(target, str) and str(target).strip()})
        if normalized:
            groups[required_target] = normalized
    return groups


def evaluate_pytest_selection_integrity(
    *,
    changed_paths: list[str],
    selected_test_targets: list[str],
    required_test_targets: list[str],
    pytest_execution_record: dict[str, Any] | None,
    policy_path: Path,
    generated_at: str,
) -> SelectionIntegrityEvaluation:
    """Evaluate fail-closed selection integrity evidence for preflight."""
    policy = _load_policy(policy_path)
    minimum_selection_threshold = int(policy.get("minimum_selection_threshold") or 1)
    if minimum_selection_threshold < 1:
        raise PytestSelectionIntegrityError("minimum_selection_threshold must be >= 1")

    governed_prefixes = [
        str(item).strip()
        for item in (policy.get("governed_surface_prefixes") or [])
        if isinstance(item, str) and str(item).strip()
    ]
    changed_paths_norm = sorted({str(path).strip() for path in changed_paths if isinstance(path, str) and str(path).strip()})
    selected_targets_norm = sorted({str(path).strip() for path in selected_test_targets if isinstance(path, str) and str(path).strip()})

    policy_required_targets = _required_targets_from_policy(changed_paths=changed_paths_norm, policy=policy)
    effective_required = sorted(set(required_test_targets) | set(policy_required_targets))

    impacted_governed_paths = [
        path for path in changed_paths_norm if any(path.startswith(prefix) for prefix in governed_prefixes)
    ]
    impacted_surface_count = len(impacted_governed_paths)

    reasons: list[str] = []
    missing_required_targets: list[str] = []

    executed = bool((pytest_execution_record or {}).get("executed", False))
    if not executed:
        reasons.append("PYTEST_SELECTION_ARTIFACT_MISSING")

    if not selected_targets_norm:
        reasons.append("PYTEST_SELECTION_EMPTY")

    if impacted_surface_count > 0 and not effective_required:
        reasons.append("PYTEST_REQUIRED_TARGETS_MISSING")

    equivalence_allowed = bool(policy.get("allow_bounded_equivalence", False))
    equivalence_groups = _collect_equivalence_groups(policy)
    selected_set = set(selected_targets_norm)
    for target in effective_required:
        if target in selected_set:
            continue
        equivalents = equivalence_groups.get(target, []) if equivalence_allowed else []
        if equivalents and selected_set.intersection(equivalents):
            continue
        missing_required_targets.append(target)

    if missing_required_targets:
        reasons.append("PYTEST_SELECTION_MISMATCH")

    threshold_satisfied = len(selected_targets_norm) >= minimum_selection_threshold
    if not threshold_satisfied:
        reasons.append("PYTEST_SELECTION_THRESHOLD_NOT_MET")

    reason_codes_from_execution = {
        str(code)
        for code in ((pytest_execution_record or {}).get("selection_reason_codes") or [])
        if isinstance(code, str)
    }
    if {"PR_PYTEST_SELECTED_TARGETS_EMPTY", "PR_PYTEST_FALLBACK_TARGETS_EMPTY"} & reason_codes_from_execution:
        reasons.append("PYTEST_SELECTION_FILTERING_DETECTED")

    reasons = sorted(set(reasons))
    decision = "ALLOW" if not reasons else "BLOCK"
    payload = {
        "artifact_type": "pytest_selection_integrity_result",
        "schema_version": "1.0.0",
        "changed_paths": changed_paths_norm,
        "required_test_targets": effective_required,
        "selected_test_targets": selected_targets_norm,
        "missing_required_targets": sorted(set(missing_required_targets)),
        "selection_count": len(selected_targets_norm),
        "minimum_selection_threshold": minimum_selection_threshold,
        "threshold_satisfied": threshold_satisfied,
        "impacted_surface_count": impacted_surface_count,
        "selection_integrity_decision": decision,
        "blocking_reasons": reasons,
        "generated_at": generated_at,
    }
    return SelectionIntegrityEvaluation(
        status="passed" if decision == "ALLOW" else "failed",
        decision=decision,
        blocking_reasons=reasons,
        payload=payload,
    )


__all__ = [
    "PytestSelectionIntegrityError",
    "SelectionIntegrityEvaluation",
    "evaluate_pytest_selection_integrity",
]
