from spectrum_systems.modules.runtime.rfx_calibration_policy_handoff import build_rfx_calibration_policy_handoff


def test_rt_h09_hardcoded_threshold_blocked_then_revalidate():
    bad=build_rfx_calibration_policy_handoff(calibration_input={'threshold_source':'hardcoded'})
    assert 'rfx_calibration_threshold_hardcoded' in bad['reason_codes_emitted']
    good=build_rfx_calibration_policy_handoff(calibration_input={'threshold_source':'policy','policy_ref':'POL:1','eval_ref':'EVL:1','needs_change':True,'handoff_ref':'POL-H'})
    assert good['status']=='valid'
