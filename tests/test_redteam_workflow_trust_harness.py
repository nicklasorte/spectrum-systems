from scripts.run_redteam_workflow_trust import run

def test_harness_emits_findings() -> None:
    out=run()
    assert out["outputs"]["findings"]
