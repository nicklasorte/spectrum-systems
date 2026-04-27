"""Proof bundle size validation support for GOV/PRA certification evidence.

This module reads proof bundle size policy inputs and emits validation
evidence for certification packaging.

TPA remains the canonical policy authority.

This module does not define policy, override policy, or authorize promotion.
It only validates supplied artifacts against policy inputs and returns
fail-closed size validation results for downstream packaging.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from spectrum_systems.modules.governance.trust_compression import enforce_proof_size_budget


class ProofBundleSizeError(ValueError):
    """Raised when proof bundle size validation inputs are malformed."""


def validate_proof_bundle_size(
    *,
    proof_bundle: Mapping[str, Any],
    evidence_index: Optional[Mapping[str, Any]] = None,
    one_page_trace: str = "",
) -> Dict[str, Any]:
    """Return fail-closed proof size validation evidence for packaging seams."""
    if not isinstance(proof_bundle, Mapping):
        raise ProofBundleSizeError("proof_bundle must be a mapping")
    if evidence_index is not None and not isinstance(evidence_index, Mapping):
        raise ProofBundleSizeError("evidence_index must be a mapping when provided")
    if not isinstance(one_page_trace, str):
        raise ProofBundleSizeError("one_page_trace must be a string")

    result = enforce_proof_size_budget(
        proof_bundle=proof_bundle,
        evidence_index=evidence_index,
        one_page_trace=one_page_trace,
    )
    return {
        "artifact_type": "proof_bundle_size_validation_result",
        "decision": result["decision"],
        "reason_codes": result["reason_codes"],
        "overflow_behavior": result["overflow_behavior"],
        "external_reference_field": result["external_reference_field"],
    }


__all__ = ["ProofBundleSizeError", "validate_proof_bundle_size"]
