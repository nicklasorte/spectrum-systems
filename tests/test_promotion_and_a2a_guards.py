from spectrum_systems.modules.runtime.downstream_a2a_guard import enforce_downstream_intake_guard
from spectrum_systems.modules.runtime.promotion_readiness_checkpoint import enforce_promotion_readiness


def test_promotion_readiness_hard_gate_fail_closed() -> None:
    ok, reasons = enforce_promotion_readiness(
        lineage={
            "tax_lineage": True,
            "bax_lineage": True,
            "cax_lineage": True,
            "cde_lineage": True,
            "replay_complete": True,
            "trace_complete": False,
            "required_eval_coverage": True,
            "context_preflight_success": True,
        }
    )
    assert ok is False
    assert "missing:trace_complete" in reasons


def test_downstream_a2a_intake_guard_blocks_missing_authority_lineage() -> None:
    ok, reasons = enforce_downstream_intake_guard(
        intake={"arbitration_lineage": True, "budget_compatible": False, "policy_permission": True}
    )
    assert ok is False
    assert reasons == ["missing:budget_compatible"]
