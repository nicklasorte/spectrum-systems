from scripts.run_redteam_readiness_promotion import run

def test_harness_emits_findings() -> None:
    out=run()
    assert out["outputs"]["findings"]
