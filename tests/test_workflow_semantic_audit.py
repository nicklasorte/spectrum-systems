import pytest
from spectrum_systems.modules.runtime.workflow_semantic_audit import audit_workflow_semantics
from spectrum_systems.modules.runtime.bne_utils import BNEBlockError

def test_false_authority_blocks() -> None:
    with pytest.raises(BNEBlockError):
        audit_workflow_semantics(trace_id="t", has_reachable_refs=True, check_names_align=True, false_authority=True)
