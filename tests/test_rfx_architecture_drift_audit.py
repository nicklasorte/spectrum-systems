from spectrum_systems.modules.runtime.rfx_architecture_drift_audit import run_rfx_architecture_drift_audit


def test_rt_h16_hidden_authority_detected_then_revalidate():
    bad=run_rfx_architecture_drift_audit(modules=[{'flags':{'hidden_authority':True}}])
    assert 'rfx_hidden_authority_detected' in bad['reason_codes_emitted']
    good=run_rfx_architecture_drift_audit(modules=[{'flags':{}}])
    assert good['status']=='clean'
