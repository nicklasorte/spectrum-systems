from spectrum_systems.modules.governance.promotion_requirements import evaluate_promotion_requirements

def test_promotion_prereq_block() -> None:
    profile={"artifact_type":"promotion_requirement_profile","schema_version":"1.0.0","trace_id":"t","outputs":{"families":{"FAQ":{"eval_classes":["e"],"review_artifacts":[],"critique_state":[],"certification_dependencies":[]}}}}
    out=evaluate_promotion_requirements(trace_id="t", profile=profile, artifact_family="FAQ", provided={"eval_classes":[]})
    assert out["outputs"]["decision"]=="BLOCK"
