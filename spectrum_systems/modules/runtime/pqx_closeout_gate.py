"""PQX-10 closeout gate checks for operational readiness."""

from __future__ import annotations

from typing import Any


REQUIRED_HARDENING_ARTIFACTS = {
    "pqx_slice_execution_record",
    "pqx_bundle_execution_record",
    "pqx_execution_closure_record",
}


def evaluate_pqx_closeout_gate(*, emitted_artifact_types: list[str], ci_gate_consumers: list[str], downstream_consumers: list[str]) -> dict[str, Any]:
    emitted = set(emitted_artifact_types)
    missing = sorted(REQUIRED_HARDENING_ARTIFACTS.difference(emitted))
    fail_reasons: list[str] = []
    if missing:
        fail_reasons.append("missing_required_pqx_hardening_artifacts")
    if "pqx_hardening_bundle" not in ci_gate_consumers:
        fail_reasons.append("ci_gate_missing_pqx_hardening_bundle")
    if "SEL" not in downstream_consumers or "CDE" not in downstream_consumers:
        fail_reasons.append("downstream_consumption_incomplete")

    return {
        "artifact_type": "pqx_closeout_gate_record",
        "closeout_status": "pass" if not fail_reasons else "fail",
        "missing_artifacts": missing,
        "fail_reasons": fail_reasons,
        "execution_only_assertion": True,
    }
