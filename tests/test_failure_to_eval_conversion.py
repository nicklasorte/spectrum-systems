from spectrum_systems.modules.runtime.failure_to_eval import convert_failure_to_eval_case

def test_conversion_record_present() -> None:
    out=convert_failure_to_eval_case(trace_id="t", source_finding_id="F-2", failure_class="c", expected_behavior="b", blocking_severity="HIGH")
    assert out["record"]["outputs"]["status"]=="converted"
