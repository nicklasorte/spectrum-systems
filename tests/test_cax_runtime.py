from spectrum_systems.modules.runtime.cax import apply_arbitration_precedence, build_arbitration_inputs


def test_cax_precedence_tpa_reject_dominates() -> None:
    outcome, _ = apply_arbitration_precedence(
        inputs=build_arbitration_inputs(
            tax_decision="complete",
            bax_decision="allow",
            tpa_decision="reject",
            required_signals_present=True,
            trace_complete=True,
            replay_blocking=False,
            drift_blocking=False,
        )
    )
    assert outcome == "block_required"


def test_cax_warn_complete_candidate_when_tax_complete_bax_warn() -> None:
    outcome, _ = apply_arbitration_precedence(
        inputs=build_arbitration_inputs(
            tax_decision="complete",
            bax_decision="warn",
            tpa_decision="allow",
            required_signals_present=True,
            trace_complete=True,
            replay_blocking=False,
            drift_blocking=False,
        )
    )
    assert outcome == "warn_complete_candidate"
