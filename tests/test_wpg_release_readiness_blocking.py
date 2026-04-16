from spectrum_systems.modules.governance.release_readiness_policy import evaluate_release_readiness

def test_readiness_blocks_on_critical() -> None:
    i={k:{} for k in ["eval_coverage","contradictions","comment_dispositions","override_hotspots","evidence_gap_hotspots","drift_signals","checkpoint"]}
    i["critique"]={"critical_open":1}
    out=evaluate_release_readiness(trace_id="t", inputs=i)
    assert out["readiness"]["outputs"]["decision"]=="BLOCK"
