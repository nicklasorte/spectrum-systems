from __future__ import annotations

import pytest

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.next24_serial_execution import (
    Next24ExecutionError,
    run_next24_serial_execution,
)


def _all_true_flags() -> dict[str, bool]:
    return {
        "judgment_artifact_required": True,
        "judgment_contracts_canonical": True,
        "judgment_eval_matrix_enforced": True,
        "judgment_precedence_enforced": True,
        "judgment_policy_lifecycle_governed": True,
        "precedent_retrieval_deterministic": True,
        "policy_conflict_arbitrated": True,
        "error_budget_artifact_emitted": True,
        "error_budget_burn_computed": True,
        "error_budget_control_enforced": True,
        "failure_eval_factory_active": True,
        "slice_coverage_audited": True,
        "certification_required": True,
        "certification_layers_expanded": True,
        "promotion_provenance_signed": True,
        "trace_completeness_required": True,
        "replay_integrity_hardened": True,
        "trust_posture_snapshot_published": True,
        "override_hotspot_published": True,
        "evidence_gap_hotspot_published": True,
        "policy_regression_report_published": True,
        "minimal_intelligence_slice_scoped": True,
        "slice_canary_plumbing_wired": True,
        "slice_champion_challenger_calibrated": True,
    }


def test_next24_execution_succeeds_with_all_required_gates() -> None:
    record = run_next24_serial_execution(
        trace_id="trace-next24-serial-01",
        created_at="2026-04-12T00:00:00Z",
        primary_artifact_family="artifact_release_readiness",
        gate_flags=_all_true_flags(),
    )

    assert record["record_id"].startswith("N24-")
    assert len(record["executed_steps"]) == 24
    assert [item["step_id"] for item in record["executed_steps"]][:4] == [
        "JUD-013A",
        "JUD-013B",
        "JUD-013C",
        "JUD-013D",
    ]
    assert record["executed_steps"][-1]["step_id"] == "SUB-03"
    validate_artifact(record, "next24_serial_execution_record")


def test_missing_required_gate_fails_closed() -> None:
    flags = _all_true_flags()
    flags["certification_required"] = False

    with pytest.raises(Next24ExecutionError, match="GOV-10A fail-closed"):
        run_next24_serial_execution(
            trace_id="trace-next24-serial-02",
            created_at="2026-04-12T00:00:00Z",
            primary_artifact_family="artifact_release_readiness",
            gate_flags=flags,
        )


def test_primary_slice_scope_is_fail_closed() -> None:
    with pytest.raises(Next24ExecutionError, match="only artifact_release_readiness"):
        run_next24_serial_execution(
            trace_id="trace-next24-serial-03",
            created_at="2026-04-12T00:00:00Z",
            primary_artifact_family="other_family",
            gate_flags=_all_true_flags(),
        )


def test_evidence_overrides_are_supported_but_required() -> None:
    record = run_next24_serial_execution(
        trace_id="trace-next24-serial-04",
        created_at="2026-04-12T00:00:00Z",
        primary_artifact_family="artifact_release_readiness",
        gate_flags=_all_true_flags(),
        evidence_overrides={"GOV-10C": ["promotion_provenance_bundle:sig-v1"]},
    )

    gov_step = [item for item in record["executed_steps"] if item["step_id"] == "GOV-10C"][0]
    assert gov_step["gate_evidence_refs"] == ["promotion_provenance_bundle:sig-v1"]
