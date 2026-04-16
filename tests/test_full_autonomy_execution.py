from __future__ import annotations

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.full_autonomy_execution import (
    AutonomyPosture,
    cde_authorize,
    load_fae_contract_examples,
    run_continuous_loop,
)


def test_fae_contract_examples_validate() -> None:
    for name, example in load_fae_contract_examples().items():
        validate_artifact(example, name)


def test_cde_authority_fail_closed_when_budget_exhausted() -> None:
    posture = AutonomyPosture(0.91, 0.0, 0.3, 0.3, False)
    decision = cde_authorize(posture, run_id="FAE-001-TEST-001")
    assert decision["artifact_type"] == "cde_autonomous_execution_authorization_decision"
    assert decision["details"]["authorized"] is False
    assert decision["status"] == "suspend"


def test_continuous_loop_runs_200_step_window_when_authorized() -> None:
    posture = AutonomyPosture(0.92, 0.8, 0.7, 0.4, False)
    result = run_continuous_loop(run_id="FAE-001-TEST-200", steps=200, posture=posture)
    assert result["authorized"] is True
    assert result["executed_steps"] == 200
    assert result["owner_records"]["cde"][0]["details"]["authorized"] is True


def test_continuous_loop_stops_when_safety_blocking_true() -> None:
    posture = AutonomyPosture(0.95, 0.9, 0.9, 0.2, True)
    result = run_continuous_loop(run_id="FAE-001-TEST-STOP", steps=200, posture=posture)
    assert result["authorized"] is False
    assert result["executed_steps"] == 0


def test_redteam_fix_and_final_proofs_all_emitted() -> None:
    posture = AutonomyPosture(0.9, 0.6, 0.6, 0.3, False)
    result = run_continuous_loop(run_id="FAE-001-TEST-RT", steps=20, posture=posture)
    integration_types = [record["artifact_type"] for record in result["owner_records"]["integration"]]

    expected = [
        "ril_autonomy_illusion_red_team_report",
        "fre_tpa_sel_pqx_fix_pack_a1",
        "ril_overconfidence_false_continue_red_team_report",
        "fre_tpa_sel_pqx_fix_pack_a2",
        "ril_runaway_learning_policy_drift_red_team_report",
        "fre_tpa_sel_pqx_fix_pack_a3",
        "ril_hidden_coupling_dependency_drift_red_team_report",
        "fre_tpa_sel_pqx_fix_pack_a4",
        "ril_human_bottleneck_escalation_overload_red_team_report",
        "fre_tpa_sel_pqx_fix_pack_a5",
        "ril_entropy_accumulation_long_horizon_decay_red_team_report",
        "fre_tpa_sel_pqx_fix_pack_a6",
        "final_fully_autonomous_run_record",
        "final_failure_recovery_proof_record",
        "final_long_horizon_stability_proof_record",
        "final_explainability_audit_record",
    ]
    for name in expected:
        assert name in integration_types
