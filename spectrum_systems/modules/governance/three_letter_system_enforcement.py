"""Deterministic audit for 3-letter-system ownership and gate expectations."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.governance.system_registry_guard import RegistryModel


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def evaluate_three_letter_system_enforcement(
    *,
    repo_root: Path,
    changed_files: list[str],
    policy: dict[str, Any],
    registry_model: RegistryModel,
    generated_at: str | None = None,
) -> dict[str, Any]:
    changed_paths = sorted(set(path for path in changed_files if path))

    systems = policy.get("systems") if isinstance(policy.get("systems"), dict) else {}
    path_prefixes = tuple(str(item) for item in (policy.get("system_like_path_prefixes") or []) if str(item).strip())
    reserved_prefixes = tuple(str(item) for item in (policy.get("reserved_or_transitional_paths") or []) if str(item).strip())

    ambiguous_paths: set[str] = set()
    unowned_paths: set[str] = set()
    fully_covered_systems: set[str] = set()
    ownership_drift_findings: list[dict[str, Any]] = []
    missing_gate_expectations: list[dict[str, Any]] = []
    violations: set[str] = set()

    owners_by_path: dict[str, list[str]] = {}

    for acronym, row in systems.items():
        if not isinstance(row, dict):
            continue
        owned = [str(item) for item in (row.get("owned_paths") or []) if str(item).strip()]
        tests = [str(item) for item in (row.get("minimum_required_tests") or []) if str(item).strip()]

        if len(str(acronym)) != 3:
            violations.add("INVALID_SYSTEM_ACRONYM")
            continue
        if str(acronym).upper() not in registry_model.systems:
            violations.add("POLICY_SYSTEM_NOT_IN_REGISTRY")
        if not tests:
            violations.add("MISSING_MINIMUM_REQUIRED_TESTS")

        for owned_path in owned:
            owners_by_path.setdefault(owned_path, []).append(str(acronym).upper())

        if tests and owned:
            fully_covered_systems.add(str(acronym).upper())

    for path, owners in sorted(owners_by_path.items()):
        uniq = sorted(set(owners))
        if len(uniq) > 1:
            ownership_drift_findings.append({"path": path, "owners": uniq, "reason": "duplicate ownership declaration"})
            violations.add("OWNERSHIP_DRIFT")

    for changed in changed_paths:
        if changed == "docs/architecture/system_registry.md":
            continue
        if changed.startswith(reserved_prefixes):
            continue
        if not changed.startswith(path_prefixes):
            continue

        matched_systems: list[str] = []
        for acronym, row in systems.items():
            if not isinstance(row, dict):
                continue
            owned = [str(item) for item in (row.get("owned_paths") or []) if str(item).strip()]
            if any(changed == prefix or changed.startswith(prefix) for prefix in owned):
                matched_systems.append(str(acronym).upper())

        if not matched_systems:
            unowned_paths.add(changed)
            violations.add("UNOWNED_SYSTEM_LIKE_PATH")
            continue

        if len(set(matched_systems)) > 1:
            ambiguous_paths.add(changed)
            violations.add("AMBIGUOUS_SYSTEM_OWNERSHIP")

        for system in sorted(set(matched_systems)):
            row = systems.get(system, {}) if isinstance(systems.get(system), dict) else {}
            missing: list[str] = []
            if bool(row.get("artifact_boundary_coverage_mandatory")) and "tests/test_artifact_boundary_workflow_pytest_enforcement.py" not in row.get("minimum_required_tests", []):
                missing.append("artifact_boundary_test_expectation")
            if bool(row.get("pytest_visibility_mandatory")) and "tests/test_pytest_trust_gap_audit.py" not in row.get("minimum_required_tests", []):
                missing.append("pytest_visibility_test_expectation")
            if bool(row.get("system_registry_review_mandatory")) and "tests/test_system_registry_guard.py" not in row.get("minimum_required_tests", []):
                missing.append("system_registry_review_test_expectation")
            if missing:
                missing_gate_expectations.append({"system": system, "path": changed, "missing_requirements": sorted(set(missing))})
                violations.add("MISSING_REQUIRED_GATES")

    final_decision = "PASS" if not violations else "FAIL"

    result = {
        "artifact_type": "three_letter_system_enforcement_audit_result",
        "schema_version": "1.0.0",
        "policy_version": str(policy.get("policy_version") or "unknown"),
        "systems_evaluated": len([key for key in systems if len(str(key)) == 3]),
        "fully_covered_systems": sorted(fully_covered_systems),
        "ambiguous_paths": sorted(ambiguous_paths),
        "unowned_system_like_paths": sorted(unowned_paths),
        "ownership_drift_findings": ownership_drift_findings,
        "missing_gate_expectations": missing_gate_expectations,
        "violations": sorted(violations),
        "final_decision": final_decision,
        "generated_at": generated_at or _utc_now(),
    }
    validate_artifact(result, "three_letter_system_enforcement_audit_result")
    return result


__all__ = ["evaluate_three_letter_system_enforcement"]
