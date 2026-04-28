from spectrum_systems.modules.runtime.rfx_reason_code_registry import build_rfx_reason_code_registry


def test_rt_h02_duplicate_or_ambiguous_blocked_then_revalidate():
    bad=build_rfx_reason_code_registry(entries=[{'code':'x','module':'m1','failure_prevented':'a','owner_context':'o','repair_hint':'h'},{'code':'x','module':'m2','failure_prevented':'b','owner_context':'o','repair_hint':'h'}])
    assert 'rfx_reason_code_duplicate' in bad['reason_codes_emitted']
    good=build_rfx_reason_code_registry(entries=[{'code':'x','module':'m1','failure_prevented':'a','owner_context':'o','repair_hint':'h'}],module_exports={'m1':['x']})
    assert good['status']=='valid'
