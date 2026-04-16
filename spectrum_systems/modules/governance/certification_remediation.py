from __future__ import annotations
from typing import Dict
from spectrum_systems.modules.runtime.bne_utils import BNEBlockError, ensure_contract


def build_certification_remediation(*, trace_id: str, certification_verdict: str, blockers: list[str]) -> Dict[str, any]:
    if certification_verdict in {"NEEDS_FIXES", "FREEZE"} and not blockers:
        raise BNEBlockError("certification block without remediation record")
    return ensure_contract({"artifact_type":"certification_remediation_record","schema_version":"1.0.0","trace_id":trace_id,"outputs":{"certification_verdict":certification_verdict,"blockers":blockers,"next_actions":[f'remediate:{b}' for b in blockers]}}, "certification_remediation_record")
