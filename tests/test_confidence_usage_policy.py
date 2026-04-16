import pytest
from spectrum_systems.modules.governance.confidence_usage import enforce_confidence_usage
from spectrum_systems.modules.runtime.bne_utils import BNEBlockError

def test_confidence_misuse_blocks() -> None:
    with pytest.raises(BNEBlockError):
        enforce_confidence_usage(trace_id="t", confidence=0.95, has_required_eval=False, policy_support=False)
