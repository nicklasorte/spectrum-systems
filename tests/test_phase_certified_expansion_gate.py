from spectrum_systems.modules.governance.phase_certified_expansion_gate import evaluate_phase_certified_expansion_gate

def test_expansion_blocked_if_missing() -> None:
    out=evaluate_phase_certified_expansion_gate(trace_id="t", eval_coverage_complete=False, readiness_clean=True, mandatory_rtx_fix_closure=True, checkpoint_complete=True, certification_acceptable=True)
    assert out["outputs"]["decision"]=="BLOCK"
