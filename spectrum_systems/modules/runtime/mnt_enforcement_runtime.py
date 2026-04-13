"""MNT-25..MNT-29 enforcement coverage/runtime checks."""
from __future__ import annotations

from typing import Any, Mapping

from spectrum_systems.contracts import validate_artifact


REQUIRED_PROMOTION_ENTRYPOINTS = {
    "promotion_gate",
    "release_gate",
    "control_loop_certification",
}


def audit_promotion_entrypoints(*, observed_entrypoints: set[str], created_at: str) -> dict[str, Any]:
    uncovered = sorted(REQUIRED_PROMOTION_ENTRYPOINTS - observed_entrypoints)
    rec = {
        "artifact_type": "mnt_promotion_entrypoint_coverage_report",
        "artifact_id": "mnt-entrypoint-audit-001",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": "1.3.130",
        "created_at": created_at,
        "entrypoints": sorted(observed_entrypoints),
        "uncovered_entrypoints": uncovered,
        "status": "pass" if not uncovered else "fail",
    }
    validate_artifact(rec, "mnt_promotion_entrypoint_coverage_report")
    return rec


def consistency_check(*, gate_results: Mapping[str, str], created_at: str) -> dict[str, Any]:
    inconsistent = sorted([gate for gate, state in gate_results.items() if state not in {"pass", "freeze", "block"}])
    rec = {
        "artifact_type": "mnt_enforcement_consistency_result",
        "artifact_id": "mnt-consistency-001",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": "1.3.130",
        "created_at": created_at,
        "checked_gates": sorted(gate_results.keys()),
        "inconsistent_gates": inconsistent,
        "status": "pass" if not inconsistent else "fail",
    }
    validate_artifact(rec, "mnt_enforcement_consistency_result")
    return rec
