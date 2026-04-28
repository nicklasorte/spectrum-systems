from spectrum_systems.modules.runtime.rfx_operator_runbook import build_rfx_operator_runbook


def test_rt_h13_action_missing_blocks_then_revalidate():
    bad=build_rfx_operator_runbook(registry={'entries':[{'code':'x','module':'m','owner_context':'EVL'}]},debug_bundles=[])
    assert 'rfx_runbook_action_missing' in bad['reason_codes_emitted']
    good=build_rfx_operator_runbook(registry={'entries':[{'code':'x','module':'m','owner_context':'EVL','repair_hint':'do x','failure_prevented':'issue'}]},debug_bundles=[{'reason_code':'x','debug_ref':'D1'}])
    assert good['status']=='complete'
