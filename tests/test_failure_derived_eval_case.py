from spectrum_systems.modules.runtime.failure_to_eval import convert_failure_to_eval_case


def test_failure_derived_eval_case() -> None:
    out = convert_failure_to_eval_case(
        trace_id="t",
        source_finding_id="F-1",
        failure_class="c",
        expected_behavior="b",
        blocking_severity="HIGH",
    )
    assert out["case"]["payload"]["source_id"] == "F-1"
