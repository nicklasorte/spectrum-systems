from scripts.run_rfx_super_check import run_rfx_super_check,REQUIRED_STEPS


def test_rt_h15_integrity_and_steps_present():
    result=run_rfx_super_check()
    assert result['status']=='pass'
    assert set(REQUIRED_STEPS)==set(result['checks'])
