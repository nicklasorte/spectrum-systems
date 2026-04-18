from spectrum_systems.modules.runtime.failure_to_eval import convert_failure_to_eval_case, convert_failures_to_eval_cases


def test_conversion_from_redteam_finding_creates_regression_case() -> None:
    out = convert_failure_to_eval_case(
        trace_id="t",
        source_type="redteam_finding",
        source_record={
            "finding_id": "F-2",
            "failure_class": "contradiction_miss",
            "expected_behavior": "block contradictory answers",
            "severity": "HIGH",
        },
    )
    assert out["record"]["outputs"]["status"] == "converted"
    assert out["regression_eval_case"]["artifact_type"] == "regression_eval_case"


def test_batch_conversion_warns_when_failure_missing_source() -> None:
    out = convert_failures_to_eval_cases(
        trace_id="trace-x",
        failures=[
            {"source_type": "redteam_finding", "source_record": {"finding_id": "finding-1"}},
            {"source_type": "", "source_record": {}},
        ],
    )
    assert out["outputs"]["conversion_count"] == 1
    assert "missing_conversion_for_failure" in out["outputs"]["warnings"]
