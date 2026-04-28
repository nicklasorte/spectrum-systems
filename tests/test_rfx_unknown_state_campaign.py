from spectrum_systems.modules.runtime.rfx_unknown_state_campaign import run_rfx_unknown_state_campaign


def test_rt_h18_unknown_states_block_then_revalidate():
    bad=run_rfx_unknown_state_campaign(states=[{}])
    assert 'rfx_unknown_owner' in bad['reason_codes_emitted']
    good=run_rfx_unknown_state_campaign(states=[{'owner_ref':'o','trace_ref':'t','source_artifact':'a','policy_posture':'p','eval_evidence':['e'],'replay_evidence':['r'],'lineage_evidence':['l'],'reason_codes':['x']}])
    assert good['status']=='clean'
