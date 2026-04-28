from spectrum_systems.modules.runtime.rfx_debug_bundle import build_rfx_debug_bundle


def test_rt_h03_hint_and_repro_required_then_revalidate():
    bad=build_rfx_debug_bundle(failure={'reason_codes':['r'],'source_refs':['s'],'owner_context':'EVL'})
    assert 'rfx_debug_repair_hint_missing' in bad['reason_codes_emitted']
    assert 'rfx_debug_repro_payload_missing' in bad['reason_codes_emitted']
    good=build_rfx_debug_bundle(failure={'reason_codes':['r'],'source_refs':['s'],'owner_context':'EVL','repair_hint':'do x','repro_payload':{'i':1}})
    assert good['status']=='complete'
