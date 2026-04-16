from spectrum_systems.modules.governance.policy_regression import evaluate_policy_regression

def test_policy_regression_clean() -> None:
    out=evaluate_policy_regression(trace_id="t", canary_block_rate=0.1, current_block_rate=0.1)
    assert out["report"]["outputs"]["unacceptable"] is False
