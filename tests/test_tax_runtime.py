from spectrum_systems.modules.runtime.tax import decide_termination


def _base_signals() -> dict:
    return {
        "required_artifacts_present": True,
        "required_evals_present": True,
        "required_evals_passed": True,
        "trace_complete": True,
        "blocking_contradiction_present": False,
        "human_review_outstanding": False,
        "replay_consistent": True,
        "policy_rejected": False,
        "bax_decision": "allow",
    }


def test_tax_complete_only_with_full_signal_satisfaction() -> None:
    decision, reasons = decide_termination(signals=_base_signals())
    assert decision == "complete"
    assert reasons == ["termination_conditions_satisfied"]


def test_tax_blocks_on_missing_required_artifacts() -> None:
    signals = _base_signals()
    signals["required_artifacts_present"] = False
    decision, _ = decide_termination(signals=signals)
    assert decision == "block_required"


def test_tax_repairs_on_indeterminate_or_failed_required_evals() -> None:
    signals = _base_signals()
    signals["required_evals_passed"] = False
    decision, _ = decide_termination(signals=signals)
    assert decision == "repair_required"
