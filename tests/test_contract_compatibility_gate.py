import pytest
from spectrum_systems.modules.governance.contract_compatibility import evaluate_contract_compatibility
from spectrum_systems.modules.runtime.bne_utils import BNEBlockError

def test_breaking_without_version_bump_blocks() -> None:
    with pytest.raises(BNEBlockError):
        evaluate_contract_compatibility(trace_id="t", change_class="breaking", version_bumped=False, manifest_updated=True)
