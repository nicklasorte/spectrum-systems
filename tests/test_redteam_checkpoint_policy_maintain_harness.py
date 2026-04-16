from scripts.run_redteam_checkpoint_policy_maintain import run

def test_harness_emits_findings() -> None:
    out=run()
    assert out["outputs"]["findings"]
