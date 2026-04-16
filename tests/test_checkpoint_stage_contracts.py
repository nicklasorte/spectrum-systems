import pytest
from spectrum_systems.modules.runtime.checkpoint_stage_contracts import evaluate_checkpoint_transition
from spectrum_systems.modules.runtime.bne_utils import BNEBlockError

def test_illegal_transition_blocks() -> None:
    with pytest.raises(BNEBlockError):
        evaluate_checkpoint_transition(trace_id="t", current_state="HIBERNATED", action="COMPLETE")
