from spectrum_systems.modules.runtime.bne02_full_wave import compute_eval_coverage_artifact


def test_eval_coverage_blocks_when_required_eval_missing() -> None:
    artifact = compute_eval_coverage_artifact(
        trace_id="trace-1",
        artifact_family="wpg",
        stage="readiness",
        required_eval_ids=["eval.a", "eval.b"],
        observed_eval_ids=["eval.a"],
    )
    assert artifact["gate_status"] == "fail"
    assert artifact["missing_eval_ids"] == ["eval.b"]
    assert artifact["coverage_ratio"] == 0.5


def test_eval_coverage_allows_when_full() -> None:
    artifact = compute_eval_coverage_artifact(
        trace_id="trace-2",
        artifact_family="wpg",
        stage="readiness",
        required_eval_ids=["eval.a"],
        observed_eval_ids=["eval.a"],
    )
    assert artifact["gate_status"] == "pass"
    assert artifact["missing_eval_ids"] == []
