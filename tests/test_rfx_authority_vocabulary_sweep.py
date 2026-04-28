from spectrum_systems.modules.runtime.rfx_authority_vocabulary_sweep import run_rfx_authority_vocabulary_sweep


def test_rt_h19_forbidden_literal_caught_then_revalidate(tmp_path):
    badf=tmp_path/'bad.py';badf.write_text('this module decides outputs')
    bad=run_rfx_authority_vocabulary_sweep(paths=[str(badf)])
    assert 'rfx_authority_vocab_violation' in bad['reason_codes_emitted']
    goodf=tmp_path/'good.py';goodf.write_text('this module emits signal outputs')
    good=run_rfx_authority_vocabulary_sweep(paths=[str(goodf)])
    assert good['status']=='clean'
