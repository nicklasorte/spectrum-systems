"""Certification prerequisite checks (NX-25) — non-owner support seam.

This module is a deterministic, fail-closed prerequisite check that
certification evidence packages must satisfy before the canonical
governance authority (recorded in docs/architecture/system_registry.md)
issues certification. It does not issue certification itself.

Required evidence streams:

  - all required evals passed
  - lineage completeness asserted
  - replay readiness signal present
  - control_signal record present
  - enforcement_signal record present (when state-changing)
  - no active registry violations
  - authority-shape preflight signal status pass

Canonical certification ownership remains with the governance authority
declared in the canonical registry; this seam only asserts evidence is
present and well-formed.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional


CANONICAL_CERTIFICATION_REASON_CODES = {
    "CERT_OK",
    "CERT_MISSING_EVAL_PASS",
    "CERT_MISSING_LINEAGE",
    "CERT_MISSING_REPLAY_READINESS",
    "CERT_MISSING_CONTROL_DECISION",
    "CERT_MISSING_ENFORCEMENT_RECORD",
    "CERT_REGISTRY_VIOLATION_PRESENT",
    "CERT_MISSING_AUTHORITY_SHAPE_PREFLIGHT",
}


class CertificationPrerequisiteError(ValueError):
    """Raised when prerequisites cannot be deterministically asserted."""


def assert_certification_prerequisites(
    *,
    eval_summary: Optional[Mapping[str, Any]],
    lineage_summary: Optional[Mapping[str, Any]],
    replay_summary: Optional[Mapping[str, Any]],
    control_decision: Optional[Mapping[str, Any]],
    enforcement_record: Optional[Mapping[str, Any]],
    registry_violations: Optional[List[Any]] = None,
    state_changing: bool = True,
    authority_shape_preflight_signal: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Assert that all certification evidence is present and passing.

    Returns
    -------
    {"decision": "allow"|"block",
     "reason_code": canonical,
     "blocking_reasons": [str,...]}
    """
    blocking: List[str] = []
    reason_code = "CERT_OK"

    def _maybe(name: str, val: Any) -> None:
        nonlocal reason_code
        if reason_code == "CERT_OK":
            reason_code = name

    if not isinstance(eval_summary, Mapping):
        blocking.append("eval summary missing")
        _maybe("CERT_MISSING_EVAL_PASS", None)
    else:
        status = str(
            eval_summary.get("status")
            or eval_summary.get("coverage_completeness_status")
            or ""
        ).lower()
        if status not in {"healthy", "complete", "pass"}:
            blocking.append(f"eval summary status not healthy: {status!r}")
            _maybe("CERT_MISSING_EVAL_PASS", None)

    if not isinstance(lineage_summary, Mapping):
        blocking.append("lineage summary missing")
        _maybe("CERT_MISSING_LINEAGE", None)
    else:
        status = str(lineage_summary.get("status") or "").lower()
        if status != "healthy":
            blocking.append(f"lineage summary status not healthy: {status!r}")
            _maybe("CERT_MISSING_LINEAGE", None)

    if not isinstance(replay_summary, Mapping):
        blocking.append("replay summary missing")
        _maybe("CERT_MISSING_REPLAY_READINESS", None)
    else:
        status = str(replay_summary.get("status") or "").lower()
        if status not in {"healthy", "ok", "match"}:
            blocking.append(f"replay summary status not healthy: {status!r}")
            _maybe("CERT_MISSING_REPLAY_READINESS", None)

    if not isinstance(control_decision, Mapping):
        blocking.append("control decision missing")
        _maybe("CERT_MISSING_CONTROL_DECISION", None)
    else:
        decision = str(control_decision.get("decision") or "").lower()
        if decision != "allow":
            blocking.append(f"control decision not allow: {decision!r}")
            _maybe("CERT_MISSING_CONTROL_DECISION", None)

    if state_changing and not isinstance(enforcement_record, Mapping):
        blocking.append("enforcement record required for state-changing path")
        _maybe("CERT_MISSING_ENFORCEMENT_RECORD", None)

    violations = registry_violations or []
    if violations:
        blocking.append(
            f"registry has {len(violations)} active violation(s); promotion blocked"
        )
        reason_code = "CERT_REGISTRY_VIOLATION_PRESENT"

    # Authority-shape preflight pass signal is required for promotion.
    # GOV does not decide policy here — it only refuses to package
    # certification evidence when the upstream preflight signal is
    # missing or failing.
    if not isinstance(authority_shape_preflight_signal, Mapping):
        blocking.append("authority-shape preflight signal missing")
        _maybe("CERT_MISSING_AUTHORITY_SHAPE_PREFLIGHT", None)
    else:
        signal_status = str(
            authority_shape_preflight_signal.get("status")
            or authority_shape_preflight_signal.get("preflight_status")
            or ""
        ).lower()
        if signal_status != "pass":
            blocking.append(
                f"authority-shape preflight signal status not pass: {signal_status!r}"
            )
            _maybe("CERT_MISSING_AUTHORITY_SHAPE_PREFLIGHT", None)

    return {
        "decision": "allow" if not blocking else "block",
        "reason_code": "CERT_OK" if not blocking else reason_code,
        "blocking_reasons": blocking,
    }


__all__ = [
    "CANONICAL_CERTIFICATION_REASON_CODES",
    "CertificationPrerequisiteError",
    "assert_certification_prerequisites",
]
