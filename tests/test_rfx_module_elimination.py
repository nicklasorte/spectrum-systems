from spectrum_systems.modules.runtime.rfx_module_elimination import evaluate_rfx_module_elimination


def test_rt_h12_unjustified_module_recommended_then_revalidate():
    bad=evaluate_rfx_module_elimination(modules=[{'module':'m'}])
    assert 'rfx_module_unjustified' in bad['reason_codes_emitted']
    good=evaluate_rfx_module_elimination(modules=[{'module':'m','impacts':['signal_loss']}])
    assert any(x['recommendation']=='keep' for x in good['recommendations'])
