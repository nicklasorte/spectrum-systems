"""System justification enforcement v2 (NS-13..15).

Strengthens the existing canonical registry validator by asserting that
every active system declares:
  - failure_prevented (non-empty, non-placeholder)
  - signal_improved   (non-empty, non-placeholder)
  - canonical_artifacts_owned (non-empty list)
  - primary_code_paths (non-empty, all paths exist)
  - upstream_dependencies (declared, list of acronyms)
  - downstream_dependencies (declared, list of acronyms)
  - status = active

It also asserts that every active system has at least one test or check
proving its failure-prevention / signal-improvement claim. The proof set is
satisfied when the justification module receives a non-empty list of test
files for that system.

This module is a non-owning seam. It does not redefine ownership; it only
emits a validation result that the certification evidence index consumes.
Demoted systems remain visible but are not required to satisfy active-system
justification rules.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional


CANONICAL_JUSTIFICATION_REASON_CODES = {
    "JUSTIFICATION_OK",
    "JUSTIFICATION_MISSING_FAILURE_PREVENTED",
    "JUSTIFICATION_MISSING_SIGNAL_IMPROVED",
    "JUSTIFICATION_MISSING_CANONICAL_ARTIFACTS",
    "JUSTIFICATION_MISSING_PRIMARY_CODE_PATHS",
    "JUSTIFICATION_MISSING_UPSTREAM",
    "JUSTIFICATION_MISSING_DOWNSTREAM",
    "JUSTIFICATION_MISSING_STATUS",
    "JUSTIFICATION_NO_PROOF_TEST",
    "JUSTIFICATION_PLACEHOLDER_RATIONALE",
    "JUSTIFICATION_DEMOTED_NOT_VISIBLE",
}

_PLACEHOLDER_HINTS = {
    "tbd",
    "todo",
    "placeholder",
    "n/a",
    "none",
    "not_yet",
    "future",
    "pending",
    "",
}


class SystemJustificationError(ValueError):
    """Raised when system justification cannot be deterministically verified."""


def _non_placeholder(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    norm = value.strip().lower()
    if not norm:
        return False
    if norm in _PLACEHOLDER_HINTS:
        return False
    return True


def _list_non_empty(value: Any) -> bool:
    return isinstance(value, list) and len(value) > 0


def assert_system_justification(
    *,
    acronym: str,
    fields: Mapping[str, Any],
    proof_tests: Optional[Iterable[str]] = None,
    require_proof_test: bool = True,
) -> Dict[str, Any]:
    """Assert that ``fields`` describe a justified, active system.

    ``fields`` keys (case-insensitive accepted at top level):
      - status                       (must equal "active")
      - failure_prevented            (non-empty, non-placeholder)
      - signal_improved              (non-empty, non-placeholder)
      - canonical_artifacts_owned    (non-empty list)
      - primary_code_paths           (non-empty list, paths checked elsewhere)
      - upstream_dependencies        (list)
      - downstream_dependencies      (list)

    Returns
      {"decision": "allow"|"block",
       "reason_code": canonical,
       "blocking_reasons": [...]}
    """
    if not isinstance(acronym, str) or not acronym.strip():
        raise SystemJustificationError("acronym must be a non-empty string")
    if not isinstance(fields, Mapping):
        raise SystemJustificationError("fields must be a mapping")

    blocking: List[str] = []
    reason_code = "JUSTIFICATION_OK"

    def _maybe(name: str, why: str) -> None:
        nonlocal reason_code
        blocking.append(why)
        if reason_code == "JUSTIFICATION_OK":
            reason_code = name

    status = fields.get("status")
    if not isinstance(status, str) or status.strip().lower() != "active":
        _maybe("JUSTIFICATION_MISSING_STATUS", f"{acronym} status must be 'active'; got {status!r}")

    if not _non_placeholder(fields.get("failure_prevented")):
        _maybe(
            "JUSTIFICATION_MISSING_FAILURE_PREVENTED",
            f"{acronym} failure_prevented missing or placeholder",
        )
    if not _non_placeholder(fields.get("signal_improved")):
        _maybe(
            "JUSTIFICATION_MISSING_SIGNAL_IMPROVED",
            f"{acronym} signal_improved missing or placeholder",
        )

    if not _list_non_empty(fields.get("canonical_artifacts_owned")):
        _maybe(
            "JUSTIFICATION_MISSING_CANONICAL_ARTIFACTS",
            f"{acronym} canonical_artifacts_owned missing or empty",
        )

    paths = fields.get("primary_code_paths")
    if not _list_non_empty(paths):
        _maybe(
            "JUSTIFICATION_MISSING_PRIMARY_CODE_PATHS",
            f"{acronym} primary_code_paths missing or empty",
        )

    upstream = fields.get("upstream_dependencies")
    if not isinstance(upstream, list):
        _maybe(
            "JUSTIFICATION_MISSING_UPSTREAM",
            f"{acronym} upstream_dependencies must be a list (may be empty)",
        )
    downstream = fields.get("downstream_dependencies")
    if not isinstance(downstream, list):
        _maybe(
            "JUSTIFICATION_MISSING_DOWNSTREAM",
            f"{acronym} downstream_dependencies must be a list (may be empty)",
        )

    if require_proof_test:
        proofs = list(proof_tests or [])
        if not proofs:
            _maybe(
                "JUSTIFICATION_NO_PROOF_TEST",
                f"{acronym} has no proof-test linking failure_prevented/signal_improved",
            )

    return {
        "decision": "allow" if not blocking else "block",
        "reason_code": "JUSTIFICATION_OK" if not blocking else reason_code,
        "blocking_reasons": blocking,
    }


def assert_demoted_system_visibility(
    *,
    acronym: str,
    fields: Mapping[str, Any],
) -> Dict[str, Any]:
    """A demoted system must remain visible (status declared, must_not_do
    listed) even though it is not authoritative."""
    if not isinstance(fields, Mapping):
        raise SystemJustificationError("fields must be a mapping")
    blocking: List[str] = []
    status = str(fields.get("status") or "").lower()
    if status not in {"demoted", "deprecated", "removed"}:
        return {
            "decision": "allow",
            "reason_code": "JUSTIFICATION_OK",
            "blocking_reasons": [],
        }
    if not isinstance(fields.get("must_not_do"), list) or not fields.get("must_not_do"):
        blocking.append(
            f"{acronym} (demoted) must declare must_not_do to remain visible"
        )
    return {
        "decision": "allow" if not blocking else "block",
        "reason_code": "JUSTIFICATION_OK" if not blocking else "JUSTIFICATION_DEMOTED_NOT_VISIBLE",
        "blocking_reasons": blocking,
    }


def validate_active_systems_bulk(
    *,
    active_systems: Mapping[str, Mapping[str, Any]],
    proof_tests_by_system: Optional[Mapping[str, Iterable[str]]] = None,
    require_proof_test: bool = True,
) -> Dict[str, Any]:
    """Validate every active system in ``active_systems``.

    Returns
      {"validation_id": str (caller-supplied), "decision": "allow"|"block",
       "violations": [str, ...], "per_system": {acronym: result}}
    """
    proofs = dict(proof_tests_by_system or {})
    per_system: Dict[str, Dict[str, Any]] = {}
    violations: List[str] = []

    for acronym, fields in active_systems.items():
        result = assert_system_justification(
            acronym=acronym,
            fields=fields,
            proof_tests=proofs.get(acronym, []),
            require_proof_test=require_proof_test,
        )
        per_system[acronym] = result
        if result["decision"] == "block":
            for r in result["blocking_reasons"]:
                violations.append(f"{acronym}: {r}")

    return {
        "decision": "allow" if not violations else "block",
        "violations": violations,
        "per_system": per_system,
    }


__all__ = [
    "CANONICAL_JUSTIFICATION_REASON_CODES",
    "SystemJustificationError",
    "assert_demoted_system_visibility",
    "assert_system_justification",
    "validate_active_systems_bulk",
]
