"""Deterministic normalization for contract preflight failures."""

from __future__ import annotations

from typing import Any


def normalize_preflight_failure(report: dict[str, Any]) -> dict[str, Any]:
    """Convert raw preflight report into deterministic failure signal."""

    signals = {
        "has_schema_failures": bool(report.get("schema_example_failures")),
        "has_test_failures": bool(
            report.get("producer_failures")
            or report.get("consumer_failures")
            or report.get("fixture_failures")
        ),
        "has_missing_surface": bool(report.get("missing_required_surface")),
        "has_invariant_violations": bool(report.get("invariant_violations")),
        "has_control_surface_gap": bool(report.get("control_surface_gap_blocking")),
        "has_pytest_execution_gap": bool(
            {
                "PR_PYTEST_EXECUTION_REQUIRED",
                "PREFLIGHT_PASS_WITHOUT_PYTEST_EXECUTION",
                "PR_PYTEST_EXECUTION_RECORD_REQUIRED",
                "PR_PYTEST_EXECUTION_REF_NON_CANONICAL",
                "PR_PYTEST_SELECTION_REF_NON_CANONICAL",
                "PR_PYTEST_EXECUTION_PROVENANCE_MISSING",
                "PR_PYTEST_SELECTION_PROVENANCE_MISSING",
                "PR_PYTEST_PROVENANCE_LINK_MISMATCH",
                "PR_PYTEST_PROVENANCE_HASH_MISMATCH",
                "PR_PYTEST_PROVENANCE_COMMIT_MISMATCH",
            }
            & set(report.get("invariant_violations", []))
        ),
        "has_pytest_selection_gap": bool(
            {
                "PYTEST_SELECTION_EMPTY",
                "PYTEST_REQUIRED_TARGETS_MISSING",
                "PYTEST_SELECTION_THRESHOLD_NOT_MET",
                "PYTEST_SELECTION_ARTIFACT_MISSING",
                "PYTEST_SELECTION_ARTIFACT_INVALID",
                "PYTEST_SELECTION_MISMATCH",
                "PYTEST_SELECTION_FILTERING_DETECTED",
                "PR_PYTEST_SELECTION_INTEGRITY_REQUIRED",
                "DEGRADED_REF_RESOLUTION_PR_BLOCK",
                "NON_EXHAUSTIVE_GOVERNED_PATH_RESOLUTION",
                "GOVERNED_SURFACE_DIFF_INCOMPLETE",
            }
            & set(report.get("invariant_violations", []))
        ),
        "has_test_inventory_failure": (
            report.get("test_inventory_integrity", {}).get("failure_class") not in {None, "success"}
        ),
    }

    if signals["has_schema_failures"]:
        failure_class = "schema_violation"
    elif signals["has_missing_surface"]:
        failure_class = "contract_mismatch"
    elif signals["has_test_inventory_failure"]:
        failure_class = "test_inventory_regression"
    elif signals["has_pytest_selection_gap"]:
        failure_class = "test_inventory_regression"
    elif signals["has_control_surface_gap"]:
        failure_class = "control_surface_gap"
    elif signals["has_pytest_execution_gap"]:
        failure_class = "test_inventory_regression"
    elif signals["has_test_failures"]:
        failure_class = "downstream_test_failure"
    elif signals["has_invariant_violations"]:
        failure_class = "internal_preflight_error"
    else:
        failure_class = "internal_preflight_error"

    return {
        "failure_class": failure_class,
        "signals": signals,
        "repairable": failure_class
        in {
            "schema_violation",
            "contract_mismatch",
            "test_inventory_regression",
            "control_surface_gap",
        },
    }


__all__ = ["normalize_preflight_failure"]
