from spectrum_systems.modules.runtime.rfx_bloat_budget import assess_rfx_bloat_budget


def test_rt_h07_budget_exceeded_emits_signal_then_revalidate():
    bad=assess_rfx_bloat_budget(measurement={'runtime_ms':99},budget={'max_runtime_ms':10})
    assert 'rfx_runtime_budget_exceeded' in bad['reason_codes_emitted']
    good=assess_rfx_bloat_budget(measurement={'runtime_ms':5},budget={'max_runtime_ms':10})
    assert good['status']=='within_budget'
