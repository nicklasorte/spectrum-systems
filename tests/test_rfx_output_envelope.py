from spectrum_systems.modules.runtime.rfx_output_envelope import build_rfx_output_envelope


def test_rt_h04_malformed_envelope_rejected_then_revalidate():
    bad=build_rfx_output_envelope(artifact_type='',producer_module='',status='weird',reason_codes=[],trace_refs=[],source_refs=[])
    assert 'rfx_envelope_invalid_status' in bad['reason_codes_emitted']
    good=build_rfx_output_envelope(artifact_type='x',producer_module='m',status='ok',reason_codes=['a'],trace_refs=['t'],source_refs=['s'])
    assert good['reason_codes_emitted']==[]
