"""RAX assurance helpers for fail-closed input/output contract validation."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

from spectrum_systems.contracts import validate_artifact
INPUT_FAILURE_CLASSES = {
    "invalid_input",
    "dependency_blocked",
    "stale_reference",
    "trace_tampering",
    "ownership_violation",
}


class RAXAssuranceError(ValueError):
    """Raised when assurance detects a fail-closed condition."""


def _resolve_entrypoint(spec: str) -> bool:
    if ":" not in spec:
        return False
    module_name, attribute = spec.split(":", 1)
    try:
        module = importlib.import_module(module_name)
    except Exception:
        return False
    return hasattr(module, attribute)


def assure_rax_input(
    payload: dict[str, Any],
    *,
    policy: dict[str, Any],
    expected_policy_hash: str,
    trace: dict[str, Any] | None = None,
    freshness_records: dict[str, dict[str, Any]] | None = None,
    provenance_records: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Validate upstream payload and classify fail-closed input conditions."""
    details: list[str] = []
    failure_classification = "none"
    stop_condition_triggered = False

    try:
        validate_artifact(payload, "rax_upstream_input_envelope")
        details.append("upstream schema validation passed")
    except Exception as exc:  # fail-closed by classifying invalid input
        failure_classification = "invalid_input"
        details.append(f"schema validation failed: {exc}")

    if failure_classification == "none":
        if payload["owner"] not in policy.get("owner_defaults", {}):
            failure_classification = "ownership_violation"
            details.append("owner not present in expansion policy owner_defaults")

    if failure_classification == "none":
        if payload["step_id"] in payload["depends_on"]:
            failure_classification = "dependency_blocked"
            details.append("step cannot depend on itself")

    if failure_classification == "none" and freshness_records is not None:
        fresh = freshness_records.get(payload["input_freshness_ref"], {}).get("is_fresh", False)
        if not fresh:
            failure_classification = "stale_reference"
            details.append("freshness reference missing or stale")

    if failure_classification == "none" and provenance_records is not None:
        trusted = provenance_records.get(payload["input_provenance_ref"], {}).get("trusted", False)
        if not trusted:
            failure_classification = "stale_reference"
            details.append("provenance reference missing or untrusted")

    if failure_classification == "none" and trace is not None:
        if trace.get("expansion_policy_hash") != expected_policy_hash:
            failure_classification = "trace_tampering"
            details.append("trace expansion policy hash mismatch")

    if failure_classification != "none":
        stop_condition_triggered = True

    passed = failure_classification == "none"
    return {
        "passed": passed,
        "details": details,
        "failure_classification": failure_classification,
        "stop_condition_triggered": stop_condition_triggered,
    }


def assure_rax_output(step_contract: dict[str, Any], *, repo_root: Path) -> dict[str, Any]:
    """Validate downstream contract readiness and next-system compatibility."""
    details: list[str] = []
    failure_classification = "none"

    try:
        validate_artifact(step_contract, "roadmap_step_contract")
        details.append("downstream schema validation passed")
    except Exception as exc:
        failure_classification = "invalid_output"
        details.append(f"downstream schema validation failed: {exc}")

    if failure_classification == "none" and not step_contract.get("acceptance_checks"):
        failure_classification = "invalid_output"
        details.append("acceptance_checks must not be empty")

    if failure_classification == "none" and step_contract.get("realization_mode") == "runtime_realization":
        if not step_contract.get("runtime_entrypoints"):
            failure_classification = "invalid_output"
            details.append("runtime_realization requires runtime_entrypoints")

    if failure_classification == "none":
        for entrypoint in step_contract.get("runtime_entrypoints", []):
            if not _resolve_entrypoint(entrypoint):
                failure_classification = "downstream_incompatible"
                details.append(f"runtime entrypoint not resolvable: {entrypoint}")
                break

    if failure_classification == "none":
        compatibility = step_contract.get("downstream_compatibility", {})
        if compatibility.get("prg_rdx_step_metadata") is not True:
            failure_classification = "downstream_incompatible"
            details.append("PRG/RDX step metadata compatibility flag must be true")
        if compatibility.get("realization_runner_contract_complete") is not True:
            failure_classification = "downstream_incompatible"
            details.append("realization runner compatibility flag must be true")

    if failure_classification == "none":
        for target in step_contract.get("target_modules", []) + step_contract.get("target_tests", []):
            if ".." in target:
                failure_classification = "invalid_output"
                details.append("target paths must not contain parent-directory traversal")
                break

    passed = failure_classification == "none"
    return {
        "passed": passed,
        "details": details,
        "failure_classification": failure_classification,
        "stop_condition_triggered": not passed,
    }


def build_rax_assurance_audit_record(
    *,
    roadmap_id: str,
    step_id: str,
    input_assurance: dict[str, Any],
    output_assurance: dict[str, Any],
) -> dict[str, Any]:
    """Build schema-valid audit artifact with local accept/hold/block outcome only."""
    failure_classification = input_assurance.get("failure_classification")
    if failure_classification == "none":
        failure_classification = output_assurance.get("failure_classification", "none")

    if failure_classification == "none":
        decision = "accept_candidate"
        repairability = "none"
        status_transition = "legal"
    elif failure_classification in INPUT_FAILURE_CLASSES:
        decision = "block_candidate"
        repairability = "blocked"
        status_transition = "not_attempted"
    elif failure_classification == "downstream_incompatible":
        decision = "hold_candidate"
        repairability = "repairable"
        status_transition = "not_attempted"
    else:
        decision = "block_candidate"
        repairability = "repairable"
        status_transition = "illegal"

    audit = {
        "artifact_type": "rax_assurance_audit_record",
        "roadmap_id": roadmap_id,
        "step_id": step_id,
        "input_validation_result": {
            "passed": bool(input_assurance.get("passed", False)),
            "details": input_assurance.get("details", []),
        },
        "output_validation_result": {
            "passed": bool(output_assurance.get("passed", False)),
            "details": output_assurance.get("details", []),
        },
        "counter_evidence": [],
        "freshness_result": {
            "passed": bool(input_assurance.get("passed", False)),
            "details": ["freshness evaluated as part of input assurance"],
        },
        "provenance_result": {
            "passed": bool(input_assurance.get("passed", False)),
            "details": ["provenance evaluated as part of input assurance"],
        },
        "failure_classification": failure_classification,
        "repairability_classification": repairability,
        "stop_condition_triggered": bool(input_assurance.get("stop_condition_triggered") or output_assurance.get("stop_condition_triggered")),
        "acceptance_decision": decision,
        "status_transition_result": status_transition,
    }
    validate_artifact(audit, "rax_assurance_audit_record")
    return audit
