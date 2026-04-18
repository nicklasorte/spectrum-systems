from spectrum_systems.modules.runtime.bne02_full_wave import evaluate_promotion_gate


def test_promotion_gate_blocks_when_requirements_missing() -> None:
    result = evaluate_promotion_gate(
        trace_id="trace-1",
        run_id="run-1",
        eval_pass=True,
        lineage_complete=False,
        judgment_present=False,
        policy_aligned=True,
    )
    assert result["decision"] == "BLOCK"
    assert set(result["reason_codes"]) == {"missing_lineage_complete", "missing_judgment_present"}


def test_promotion_gate_allows_when_all_requirements_present() -> None:
    result = evaluate_promotion_gate(
        trace_id="trace-2",
        run_id="run-2",
        eval_pass=True,
        lineage_complete=True,
        judgment_present=True,
        policy_aligned=True,
    )
    assert result["decision"] == "ALLOW"
    assert result["reason_codes"] == []
