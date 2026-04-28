from spectrum_systems.modules.runtime.rfx_golden_loop import build_rfx_golden_loop_record


def test_rt_h05_missing_link_blocks_then_revalidate():
    bad=build_rfx_golden_loop_record(loop={'failure_ref':'f'})
    assert 'rfx_golden_loop_missing_eval' in bad['reason_codes_emitted']
    good=build_rfx_golden_loop_record(loop={'failure_ref':'f','eval_ref':'e','fix_proof_ref':'p','trend_ref':'t','recommendation_ref':'r'})
    assert good['status']=='complete'
