"""Deterministic fail-closed governed PQX required-context enforcement (CON-039)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from spectrum_systems.contracts import validate_artifact


class PQXRequiredContextEnforcementError(ValueError):
    """Raised when enforcement input is malformed."""


@dataclass(frozen=True)
class PQXRequiredContextEnforcementResult:
    classification: str
    execution_context: str
    wrapper_present: bool
    wrapper_context_valid: bool
    authority_context_valid: bool
    authority_state: str
    requires_pqx_execution: bool
    enforcement_decision: str
    status: str
    blocking_reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "classification": self.classification,
            "execution_context": self.execution_context,
            "wrapper_present": self.wrapper_present,
            "wrapper_context_valid": self.wrapper_context_valid,
            "authority_context_valid": self.authority_context_valid,
            "authority_state": self.authority_state,
            "requires_pqx_execution": self.requires_pqx_execution,
            "enforcement_decision": self.enforcement_decision,
            "status": self.status,
            "blocking_reasons": list(self.blocking_reasons),
        }


def _normalize_evidence_ref(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise PQXRequiredContextEnforcementError("authority_evidence_ref must be a non-empty string when provided")
    normalized = value.strip()
    if normalized.startswith("/"):
        raise PQXRequiredContextEnforcementError("authority_evidence_ref must be repository-relative")
    if ".." in normalized.split("/"):
        raise PQXRequiredContextEnforcementError("authority_evidence_ref must not traverse parent directories")
    return normalized


def _is_well_formed_governed_evidence_ref(value: str | None) -> bool:
    if not isinstance(value, str) or not value:
        return False
    return value.endswith(".pqx_slice_execution_record.json")


def _normalize_wrapper_payload(wrapper_payload: Any) -> dict[str, Any] | None:
    if wrapper_payload is None:
        return None
    if not isinstance(wrapper_payload, Mapping):
        raise PQXRequiredContextEnforcementError("pqx_task_wrapper must be an object when provided")
    return dict(wrapper_payload)


def enforce_pqx_required_context(
    *,
    classification: str,
    execution_context: str | None,
    changed_paths: Sequence[str] | None = None,
    pqx_task_wrapper: Mapping[str, Any] | None = None,
    authority_evidence_ref: str | None = None,
    preflight_mode: str = "execution_admission",
) -> PQXRequiredContextEnforcementResult:
    """Enforce governed wrapper/context posture without inferring from prose or ambient state."""

    normalized_context = str(execution_context or "unspecified").strip() or "unspecified"
    inspection_mode = preflight_mode == "commit_range_inspection"
    wrapper = _normalize_wrapper_payload(pqx_task_wrapper)

    normalized_authority_ref = _normalize_evidence_ref(authority_evidence_ref)
    if wrapper is not None and normalized_authority_ref is None:
        governance = wrapper.get("governance")
        if isinstance(governance, Mapping):
            normalized_authority_ref = _normalize_evidence_ref(governance.get("authority_evidence_ref"))

    governed = classification == "governed_pqx_required"
    blocking_reasons: list[str] = []
    wrapper_context_valid = False
    authority_context_valid = False
    requires_pqx_execution = governed

    if wrapper is not None:
        try:
            validate_artifact(wrapper, "codex_pqx_task_wrapper")
            wrapper_context_valid = True
        except Exception:
            blocking_reasons.append("MALFORMED_PQX_TASK_WRAPPER")

    if governed:
        if normalized_context != "pqx_governed":
            if inspection_mode and normalized_context == "unspecified":
                pass
            else:
                blocking_reasons.append("GOVERNED_REQUIRES_PQX_GOVERNED_CONTEXT")

        if normalized_context == "pqx_governed":
            if wrapper is None:
                blocking_reasons.append("GOVERNED_REQUIRES_PQX_TASK_WRAPPER")
            elif wrapper_context_valid:
                governance = wrapper.get("governance")
                execution_intent = wrapper.get("execution_intent")
                if not isinstance(governance, Mapping):
                    blocking_reasons.append("MALFORMED_PQX_TASK_WRAPPER")
                else:
                    if governance.get("pqx_required") is not True:
                        blocking_reasons.append("WRAPPER_GOVERNANCE_PQX_REQUIRED_FALSE")
                    if governance.get("classification") != "governed_pqx_required":
                        blocking_reasons.append("WRAPPER_CLASSIFICATION_MISMATCH")
                    if governance.get("authority_state") != "authoritative_governed_pqx":
                        blocking_reasons.append("WRAPPER_AUTHORITY_STATE_MISMATCH")

                if not isinstance(execution_intent, Mapping):
                    blocking_reasons.append("MALFORMED_PQX_TASK_WRAPPER")
                else:
                    if execution_intent.get("mode") != "governed":
                        blocking_reasons.append("WRAPPER_MODE_MISMATCH")
                    if execution_intent.get("execution_context") != "pqx_governed":
                        blocking_reasons.append("WRAPPER_EXECUTION_CONTEXT_MISMATCH")

                if changed_paths is not None:
                    wrapper_changed = wrapper.get("changed_paths")
                    if not isinstance(wrapper_changed, list):
                        blocking_reasons.append("WRAPPER_CHANGED_PATHS_MISSING")
                    else:
                        provided_set = {str(path) for path in changed_paths}
                        wrapper_set = {str(path) for path in wrapper_changed}
                        if not provided_set.issubset(wrapper_set):
                            blocking_reasons.append("WRAPPER_CHANGED_PATHS_MISMATCH")

        if normalized_authority_ref is not None and _is_well_formed_governed_evidence_ref(normalized_authority_ref):
            authority_context_valid = True

        if normalized_context == "pqx_governed":
            if not _is_well_formed_governed_evidence_ref(normalized_authority_ref):
                blocking_reasons.append("MALFORMED_OR_MISSING_GOVERNED_AUTHORITY_EVIDENCE_REF")
            else:
                authority_context_valid = True
        elif normalized_authority_ref is not None and not _is_well_formed_governed_evidence_ref(normalized_authority_ref):
            blocking_reasons.append("MALFORMED_OR_MISSING_GOVERNED_AUTHORITY_EVIDENCE_REF")

    else:
        authority_context_valid = True
        if wrapper is not None and wrapper_context_valid:
            governance = wrapper.get("governance")
            if isinstance(governance, Mapping) and governance.get("pqx_required") is True and normalized_context != "pqx_governed":
                blocking_reasons.append("NON_GOVERNED_WITH_GOVERNED_WRAPPER_POSTURE")

    status = "block" if blocking_reasons else "allow"
    if status == "allow" and wrapper is None:
        wrapper_context_valid = not governed

    authority_state = "non_authoritative_direct_run"
    if governed:
        if normalized_context == "pqx_governed":
            authority_state = "authoritative_governed_pqx"
        elif inspection_mode and normalized_context == "unspecified":
            authority_state = "unknown_pending_execution"
        else:
            authority_state = "non_authoritative_direct_run"

    return PQXRequiredContextEnforcementResult(
        classification=classification,
        execution_context=normalized_context,
        wrapper_present=wrapper is not None,
        wrapper_context_valid=wrapper_context_valid,
        authority_context_valid=authority_context_valid,
        authority_state=authority_state,
        requires_pqx_execution=requires_pqx_execution,
        enforcement_decision=status,
        status=status,
        blocking_reasons=tuple(sorted(set(blocking_reasons))),
    )
