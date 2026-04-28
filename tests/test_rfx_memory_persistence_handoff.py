from spectrum_systems.modules.runtime.rfx_memory_persistence_handoff import build_rfx_memory_persistence_handoff


def test_rt_h10_untraced_write_blocked_then_revalidate():
    bad=build_rfx_memory_persistence_handoff(request={'direct_write':True,'target_owner_ref':'REP'})
    assert 'rfx_untraced_memory_write' in bad['reason_codes_emitted']
    good=build_rfx_memory_persistence_handoff(request={'direct_write':True,'trace_ref':'T','target_owner_ref':'REP','lineage_refs':['L1']})
    assert good['status']=='valid'
