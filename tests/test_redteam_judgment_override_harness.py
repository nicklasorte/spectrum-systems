from scripts.run_redteam_judgment_override import run

def test_harness_emits_findings() -> None:
    out=run()
    assert out["outputs"]["findings"]
