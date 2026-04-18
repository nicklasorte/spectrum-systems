from spectrum_systems.modules.runtime.bne02_full_wave import enforce_global_invariants


def test_global_fail_closed_blocks_missing_eval_control_lineage_and_schema() -> None:
    result = enforce_global_invariants(
        gate="pipeline_exit",
        trace_id="trace-1",
        run_id="run-1",
        artifact={"critical_eval_status": "pass", "schema_valid": False},
    )
    assert result["decision"] == "BLOCK"
    assert set(result["reason_codes"]) == {
        "missing_eval",
        "missing_control_decision",
        "missing_lineage",
        "schema_validation_failed",
    }


def test_global_fail_closed_freezes_indeterminate_critical_eval() -> None:
    result = enforce_global_invariants(
        gate="promotion_gate",
        trace_id="trace-2",
        run_id="run-2",
        artifact={
            "eval": {"status": "pass"},
            "control_decision": {"decision": "ALLOW"},
            "lineage": {"upstream": ["a"]},
            "schema_valid": True,
            "critical_eval_status": "indeterminate",
        },
    )
    assert result["decision"] == "FREEZE"
    assert "critical_eval_indeterminate" in result["reason_codes"]
