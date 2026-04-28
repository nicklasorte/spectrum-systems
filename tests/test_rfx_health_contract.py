from spectrum_systems.modules.runtime.rfx_health_contract import build_rfx_health_contract


def test_rt_h01_missing_module_detected_then_revalidate():
    bad=build_rfx_health_contract(modules=[{'module':'','reason_codes':['a'],'artifact_types':['x'],'owner_refs':['EVL'],'test_refs':['t']}])
    assert 'rfx_health_module_missing' in bad['reason_codes_emitted']
    good=build_rfx_health_contract(modules=[{'module':'m','reason_codes':['a'],'artifact_types':['x'],'owner_refs':['EVL'],'test_refs':['t'],'debug_bundle_available':True}])
    assert good['status']=='healthy'
