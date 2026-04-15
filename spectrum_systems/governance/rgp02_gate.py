"""RGP-02 bounded-family governance gate helpers.

This module provides a deterministic, fail-closed validation surface for
`governed_prompt_queue` readiness input artifacts.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping

from jsonschema.exceptions import ValidationError

from spectrum_systems.contracts import validate_artifact


REQUIRED_CONTRACTS: tuple[str, ...] = (
    "context_preflight_result",
    "tool_output_envelope",
    "routing_decision_record",
    "eval_slice_summary",
    "lineage_completeness_report",
    "replay_integrity_record",
    "observability_contract_record",
    "evidence_sufficiency_result",
)


@dataclass(frozen=True)
class GateResult:
    passed: bool
    reason_codes: tuple[str, ...]


def validate_bounded_family_inputs(artifacts: Mapping[str, Dict[str, Any]], *, required: Iterable[str] = REQUIRED_CONTRACTS) -> GateResult:
    """Validate readiness inputs for the bounded family in a fail-closed manner.

    Args:
        artifacts: map of contract name to artifact payload.
        required: required contract names.

    Returns:
        GateResult with pass/fail and deterministic sorted reason codes.
    """
    reason_codes: set[str] = set()

    for contract_name in sorted(set(required)):
        payload = artifacts.get(contract_name)
        if payload is None:
            reason_codes.add(f"missing:{contract_name}")
            continue
        try:
            validate_artifact(payload, contract_name)
        except (ValidationError, FileNotFoundError, TypeError):
            reason_codes.add(f"invalid:{contract_name}")

    return GateResult(passed=not reason_codes, reason_codes=tuple(sorted(reason_codes)))
