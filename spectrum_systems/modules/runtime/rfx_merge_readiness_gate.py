"""RFX-N19 — RFX merge readiness gate.

Checks that all required proof artifacts, guard conditions, and test
evidence are present before a change is considered ready for merge. Missing
proof, guards, or tests cause the gate to emit a block signal.

This module is a non-owning phase-label support helper. Canonical
ownership of those surfaces is recorded in
``docs/architecture/system_registry.md``. This gate emits a readiness
signal as input to the canonical owners.

Failure prevented: merges that proceed with missing proof artifacts, absent
guard conditions, or incomplete test evidence.

Signal improved: merge-readiness confidence; proof/guard/test coverage rate.

Reason codes:
  rfx_merge_missing_proof       — required proof artifact not present
  rfx_merge_missing_guard       — required guard condition not present
  rfx_merge_missing_test        — required test evidence not present
  rfx_merge_missing_trace       — readiness record lacks trace reference
  rfx_merge_empty               — no readiness record supplied
"""

from __future__ import annotations

from typing import Any

_REQUIRED_PROOF_KEYS: tuple[str, ...] = (
    "rfx_proof_ref",
    "evl_evidence_ref",
    "lin_lineage_ref",
    "rep_replay_ref",
)

_REQUIRED_GUARD_KEYS: tuple[str, ...] = (
    "authority_shape_check",
    "authority_drift_check",
    "system_registry_check",
)

_REQUIRED_TEST_KEYS: tuple[str, ...] = (
    "pytest_passed",
    "red_team_coverage",
)


def check_rfx_merge_readiness(
    *,
    readiness_record: dict[str, Any] | None,
) -> dict[str, Any]:
    """Emit a merge readiness signal from the supplied readiness record.

    The record must contain presence/truth values for all required proof,
    guard, and test keys. Any absent or falsy required key causes a block.
    """
    reason: list[str] = []

    if not isinstance(readiness_record, dict) or not readiness_record:
        reason.append("rfx_merge_empty")
        return {
            "artifact_type": "rfx_merge_readiness_gate_result",
            "schema_version": "1.0.0",
            "missing_proofs": list(_REQUIRED_PROOF_KEYS),
            "missing_guards": list(_REQUIRED_GUARD_KEYS),
            "missing_tests": list(_REQUIRED_TEST_KEYS),
            "reason_codes_emitted": sorted(set(reason)),
            "status": "not_ready",
            "signals": {
                "proof_coverage": 0.0,
                "guard_coverage": 0.0,
                "test_coverage": 0.0,
            },
        }

    trace_ref = readiness_record.get("trace_ref") or readiness_record.get("trace_id")
    if not trace_ref:
        reason.append("rfx_merge_missing_trace")

    missing_proofs: list[str] = []
    for key in _REQUIRED_PROOF_KEYS:
        if not readiness_record.get(key):
            reason.append("rfx_merge_missing_proof")
            missing_proofs.append(key)

    missing_guards: list[str] = []
    for key in _REQUIRED_GUARD_KEYS:
        if readiness_record.get(key) is not True:
            reason.append("rfx_merge_missing_guard")
            missing_guards.append(key)

    missing_tests: list[str] = []
    for key in _REQUIRED_TEST_KEYS:
        if readiness_record.get(key) is not True:
            reason.append("rfx_merge_missing_test")
            missing_tests.append(key)

    proof_coverage = (len(_REQUIRED_PROOF_KEYS) - len(missing_proofs)) / len(_REQUIRED_PROOF_KEYS)
    guard_coverage = (len(_REQUIRED_GUARD_KEYS) - len(missing_guards)) / len(_REQUIRED_GUARD_KEYS)
    test_coverage = (len(_REQUIRED_TEST_KEYS) - len(missing_tests)) / len(_REQUIRED_TEST_KEYS)

    unique_reasons = sorted(set(reason))
    return {
        "artifact_type": "rfx_merge_readiness_gate_result",
        "schema_version": "1.0.0",
        "missing_proofs": missing_proofs,
        "missing_guards": missing_guards,
        "missing_tests": missing_tests,
        "trace_ref": trace_ref,
        "reason_codes_emitted": unique_reasons,
        "status": "ready" if not unique_reasons else "not_ready",
        "signals": {
            "proof_coverage": proof_coverage,
            "guard_coverage": guard_coverage,
            "test_coverage": test_coverage,
        },
    }
