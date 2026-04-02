"""Deterministic default PQX execution policy for governed changed-path sets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

_GOVERNED_PREFIXES = (
    "spectrum_systems/",
    "contracts/",
    "spectrum_systems/modules/runtime/",
    "spectrum_systems/orchestration/",
)

_GOVERNED_EXACT_PATHS = {
    "scripts/run_contract_preflight.py",
    "scripts/pqx_runner.py",
    "scripts/run_contract_enforcement.py",
    "tests/test_contract_preflight.py",
    "tests/test_pqx_slice_runner.py",
    "tests/test_done_certification.py",
    "tests/test_sequence_transition_policy.py",
    "tests/test_contracts.py",
    "tests/test_contract_enforcement.py",
}

_ALLOWED_EXECUTION_CONTEXTS = {
    "pqx_governed",
    "exploration",
    "debugging",
    "draft_planning",
    "non_governed_notes",
    "direct",
    "unspecified",
}


class PQXExecutionPolicyError(ValueError):
    """Raised when policy inputs are malformed and must fail closed."""


@dataclass(frozen=True)
class PQXExecutionPolicyDecision:
    policy_version: str
    classification: str
    execution_context: str
    pqx_required: bool
    status: str
    authority_state: str
    blocking_reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "policy_version": self.policy_version,
            "classification": self.classification,
            "execution_context": self.execution_context,
            "pqx_required": self.pqx_required,
            "status": self.status,
            "authority_state": self.authority_state,
            "blocking_reasons": list(self.blocking_reasons),
        }


def _normalize_changed_paths(changed_paths: Iterable[str]) -> list[str]:
    normalized: list[str] = []
    for index, value in enumerate(changed_paths):
        if not isinstance(value, str):
            raise PQXExecutionPolicyError(f"changed_paths[{index}] must be a string")
        path = value.strip()
        if not path:
            raise PQXExecutionPolicyError(f"changed_paths[{index}] must be non-empty")
        if path.startswith("/"):
            raise PQXExecutionPolicyError(f"changed_paths[{index}] must be repository-relative")
        if ".." in path.split("/"):
            raise PQXExecutionPolicyError(f"changed_paths[{index}] must not traverse parent directories")
        normalized.append(path)
    return sorted(set(normalized))


def classify_changed_paths(changed_paths: Iterable[str]) -> dict[str, object]:
    paths = _normalize_changed_paths(changed_paths)
    governed_paths = sorted(
        path
        for path in paths
        if path in _GOVERNED_EXACT_PATHS or any(path.startswith(prefix) for prefix in _GOVERNED_PREFIXES)
    )
    classification = "governed_pqx_required" if governed_paths else "exploration_only_or_non_governed"
    return {
        "classification": classification,
        "governed_paths": governed_paths,
        "non_governed_paths": sorted(path for path in paths if path not in governed_paths),
    }


def evaluate_pqx_execution_policy(
    *,
    changed_paths: Iterable[str],
    execution_context: str | None,
    policy_version: str = "1.0.0",
) -> PQXExecutionPolicyDecision:
    normalized_context = str(execution_context or "unspecified").strip() or "unspecified"
    if normalized_context not in _ALLOWED_EXECUTION_CONTEXTS:
        return PQXExecutionPolicyDecision(
            policy_version=policy_version,
            classification="governed_pqx_required",
            execution_context=normalized_context,
            pqx_required=True,
            status="block",
            authority_state="non_authoritative_direct_run",
            blocking_reasons=("INVALID_EXECUTION_CONTEXT",),
        )

    classification_result = classify_changed_paths(changed_paths)
    classification = str(classification_result["classification"])
    governed = classification == "governed_pqx_required"

    if governed and normalized_context != "pqx_governed":
        return PQXExecutionPolicyDecision(
            policy_version=policy_version,
            classification=classification,
            execution_context=normalized_context,
            pqx_required=True,
            status="block",
            authority_state="non_authoritative_direct_run",
            blocking_reasons=("GOVERNED_CHANGES_REQUIRE_PQX_CONTEXT",),
        )

    if governed:
        return PQXExecutionPolicyDecision(
            policy_version=policy_version,
            classification=classification,
            execution_context=normalized_context,
            pqx_required=True,
            status="allow",
            authority_state="authoritative_governed_pqx",
            blocking_reasons=(),
        )

    authority_state = "non_authoritative_direct_run" if normalized_context != "pqx_governed" else "authoritative_governed_pqx"
    return PQXExecutionPolicyDecision(
        policy_version=policy_version,
        classification=classification,
        execution_context=normalized_context,
        pqx_required=False,
        status="allow",
        authority_state=authority_state,
        blocking_reasons=(),
    )
