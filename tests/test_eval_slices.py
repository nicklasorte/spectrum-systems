from spectrum_systems.modules.runtime.bne02_full_wave import build_eval_slice_summary


def test_eval_slice_summary_is_slice_aware() -> None:
    summary = build_eval_slice_summary(
        eval_cases=[
            {"agency": "A1", "risk": "high", "topic": "policy", "status": "pass"},
            {"agency": "A1", "risk": "high", "topic": "policy", "status": "fail"},
            {"agency": "A2", "risk": "low", "topic": "lineage", "status": "pass"},
        ]
    )

    assert summary["total_cases"] == 3
    assert summary["failing_cases"] == 1
    assert summary["slices"]["agency"] == {"A1": 2, "A2": 1}
    assert summary["slices"]["risk"] == {"high": 2, "low": 1}
    assert summary["slices"]["topic"] == {"policy": 2, "lineage": 1}
    assert summary["gate_status"] == "fail"
