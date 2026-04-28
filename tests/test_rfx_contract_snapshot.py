from spectrum_systems.modules.runtime.rfx_contract_snapshot import compare_rfx_contract_snapshot


def test_rt_h17_contract_change_without_note_fails_then_revalidate():
    current=[{'module':'m','artifact_type':'new','fields':['a'],'reason_codes':['r1']}];manifest={'contracts':{'m':{'artifact_type':'old','fields':['a','b'],'reason_codes':['r1','r2']}}}
    bad=compare_rfx_contract_snapshot(current=current,manifest=manifest,migration_note=None)
    assert 'rfx_contract_migration_missing' in bad['reason_codes_emitted']
    good=compare_rfx_contract_snapshot(current=current,manifest={'contracts':{}},migration_note='v2 note')
    assert good['status']=='match'
