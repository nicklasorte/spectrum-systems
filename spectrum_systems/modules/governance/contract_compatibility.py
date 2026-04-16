from __future__ import annotations
from typing import Dict
from spectrum_systems.modules.runtime.bne_utils import BNEBlockError, ensure_contract


def evaluate_contract_compatibility(*, trace_id: str, change_class: str, version_bumped: bool, manifest_updated: bool) -> Dict[str, any]:
    breaking = change_class in {"breaking", "additive_required_field"}
    if breaking and not version_bumped:
        raise BNEBlockError("breaking/additive required-field changes without version bump")
    if not manifest_updated:
        raise BNEBlockError("manifest update missing for contract evolution")
    return ensure_contract({
        "artifact_type": "contract_compatibility_evaluation_record",
        "schema_version": "1.0.0",
        "trace_id": trace_id,
        "outputs": {"change_class": change_class, "version_bumped": version_bumped, "manifest_updated": manifest_updated, "decision": "ALLOW"},
    }, "contract_compatibility_evaluation_record")
