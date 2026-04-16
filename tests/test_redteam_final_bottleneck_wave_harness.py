from scripts.run_redteam_final_bottleneck_wave import run

def test_harness_emits_findings() -> None:
    out=run()
    assert out["outputs"]["findings"]
