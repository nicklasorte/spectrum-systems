from spectrum_systems.modules.governance.artifact_eval_requirements import evaluate_required_evals


def test_missing_required_eval_blocks() -> None:
    profile={"artifact_type":"artifact_eval_requirement_profile","schema_version":"1.0.0","trace_id":"t","outputs":{"requirements":[{"eval_id":"e1","stages":["s"],"artifact_families":["wpg"],"blocking":True}]}}
    res=evaluate_required_evals(profile, [], "wpg", "s", "t")
    assert res["status"]=="blocked"
