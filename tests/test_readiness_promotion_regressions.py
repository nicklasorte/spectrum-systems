from spectrum_systems.modules.governance.promotion_requirements import evaluate_promotion_requirements

def test_false_green_closed() -> None:
    p={"artifact_type":"promotion_requirement_profile","schema_version":"1.0.0","trace_id":"t","outputs":{"families":{"minutes":{"eval_classes":["x"],"review_artifacts":[],"critique_state":[],"certification_dependencies":[]}}}}
    out=evaluate_promotion_requirements(trace_id="t", profile=p, artifact_family="minutes", provided={"eval_classes":[]})
    assert out["outputs"]["missing_prerequisites"]
