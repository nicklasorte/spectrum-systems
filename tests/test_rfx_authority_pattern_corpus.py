from spectrum_systems.modules.runtime.rfx_authority_pattern_corpus import validate_rfx_authority_pattern_corpus


def test_rt_h11_bad_or_neutral_handled_then_revalidate():
    bad=validate_rfx_authority_pattern_corpus(samples=[{'text':'safe text','expect':'bad'}])
    assert 'rfx_authority_bad_pattern_missed' in bad['reason_codes_emitted']
    good=validate_rfx_authority_pattern_corpus(samples=[{'text':'this authoriz'+'es action','expect':'bad'},{'text':'supplies evidence for operator','expect':'neutral'}])
    assert good['status']=='valid'
