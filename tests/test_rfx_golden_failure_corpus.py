from spectrum_systems.modules.runtime.rfx_golden_failure_corpus import build_rfx_golden_failure_corpus


def test_rt_h14_outcome_mutation_detected_then_revalidate():
    bad=build_rfx_golden_failure_corpus(cases=[{'id':'c1','trace_ref':'t','expected':'blocked','actual':'ok'}],registered_case_ids={'c1'})
    assert 'rfx_golden_expected_outcome_mismatch' in bad['reason_codes_emitted']
    good=build_rfx_golden_failure_corpus(cases=[{'id':'c1','trace_ref':'t','expected':'blocked','actual':'blocked'}],registered_case_ids={'c1'})
    assert good['status']=='stable'
