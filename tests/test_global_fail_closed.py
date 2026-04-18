from spectrum_systems.modules.runtime.bne02_full_wave import enforce_global_invariants


def test_global_fail_closed_blocks_missing_eval_control_lineage_and_schema() -> None:
    result = enforce_global_invariants(
        gate="pipeline_exit",
        trace_id="trace-1",
        run_id="run-1",
        artifact={"critical_eval_status": "pass", "schema_valid": False},
    )
    assert result["gate_status"] == "fail"
    assert set(result["blocking_reasons"]) == {
        "missing_eval",
        "missing_control_signal",
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
            "control_signal": {"status": "ok"},
            "lineage": {"upstream": ["a"]},
            "schema_valid": True,
            "critical_eval_status": "indeterminate",
        },
    )
    assert result["gate_status"] == "indeterminate"
    assert "critical_eval_indeterminate" in result["blocking_reasons"]


def test_global_fail_closed_fails_unknown_critical_eval_status() -> None:
    result = enforce_global_invariants(
        gate="phase_transition",
        trace_id="trace-3",
        run_id="run-3",
        artifact={
            "eval": {"status": "pass"},
            "control_signal": {"status": "ok"},
            "lineage": {"upstream": ["a"]},
            "schema_valid": True,
            "critical_eval_status": "unknown",
        },
    )
    assert result["gate_status"] == "fail"
    assert "critical_eval_status_unknown" in result["blocking_reasons"]
