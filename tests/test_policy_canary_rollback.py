import pytest
from spectrum_systems.modules.governance.policy_regression import evaluate_policy_regression
from spectrum_systems.modules.runtime.bne_utils import BNEBlockError

def test_policy_regression_block() -> None:
    with pytest.raises(BNEBlockError):
        evaluate_policy_regression(trace_id="t", canary_block_rate=0.4, current_block_rate=0.1)
