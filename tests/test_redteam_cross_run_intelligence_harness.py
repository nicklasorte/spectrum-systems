from scripts.run_redteam_cross_run_intelligence import run

def test_harness_emits_findings() -> None:
    out=run()
    assert out["outputs"]["findings"]
