from spectrum_systems.modules.governance.phase_certified_expansion_gate import evaluate_phase_certified_expansion_gate

def test_final_seam_blocking() -> None:
    out=evaluate_phase_certified_expansion_gate(trace_id="t", eval_coverage_complete=True, readiness_clean=True, mandatory_rtx_fix_closure=False, checkpoint_complete=True, certification_acceptable=True)
    assert out["outputs"]["missing_prerequisites"]
