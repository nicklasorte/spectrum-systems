"""RAX assurance helpers for fail-closed input/output contract validation."""

from __future__ import annotations

import importlib
import json
import re
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

_TRACE_REQUIRED_FIELDS = {
    "target_modules",
    "target_tests",
    "acceptance_checks",
    "forbidden_patterns",
    "downstream_compatibility",
}

_OWNER_INTENT_FORBIDDEN_PHRASES = {
    "PRG": ("runtime execution", "execute runtime", "directly execute", "runtime entrypoint"),
    "PQX": ("promotion decision", "closure decision", "readiness decision"),
    "RIL": ("enforce policy", "execute runtime", "repair plan generation"),
    "SEL": ("repair plan generation", "program prioritization"),
}

_WEAK_ACCEPTANCE_LANGUAGE = (
    "todo",
    "tbd",
    "placeholder",
    "maybe",
    "etc",
    "nice to have",
    "if possible",
)

_VERIFICATION_TERMS = ("must", "verify", "validated", "enforce", "deterministic", "fail", "prove")
_NON_OPERATIONAL_ACCEPTANCE_PHRASES = (
    "non-operational",
    "non operational",
    "non-falsifiable",
    "non falsifiable",
    "formatting consistency",
    "documentation only",
)
_DEPENDENCY_ID_PATTERN = re.compile(r"^RAX-INTERFACE-\d{2}-\d{2}$")

_COUNTER_EVIDENCE_PLACEHOLDERS = {
    "n/a",
    "none",
    "unknown",
    "placeholder",
    "generic",
    "tbd",
    "todo",
}

_ENTRY_REQUIRED_FIELDS = {
    "artifact_type",
    "step_id",
    "owner",
    "intent",
    "depends_on",
    "roadmap_group",
    "source_authority_ref",
    "source_version",
    "input_freshness_ref",
    "input_provenance_ref",
}


_DEFAULT_SOURCE_VERSION_AUTHORITY = {
    "docs/roadmaps/system_roadmap.md#RAX-INTERFACE-24-01": "1.3.112",
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


def _is_semantically_sufficient_intent(intent: str) -> bool:
    normalized = " ".join(intent.lower().split())
    tokens = [piece for piece in normalized.replace("-", " ").split(" ") if piece]
    if len(tokens) < 4:
        return False

    generic_placeholders = {"todo", "tbd", "placeholder", "generic", "misc", "none", "n/a", "lorem", "ipsum", "asdf"}
    if normalized in generic_placeholders:
        return False
    if len(set(tokens)) == 1:
        return False
    if all(token in generic_placeholders for token in tokens):
        return False

    meaningful_tokens = [token for token in tokens if len(token) >= 4 and token not in generic_placeholders]
    return len(meaningful_tokens) >= 3


def _validate_owner_intent_semantics(owner: str, intent: str) -> str | None:
    lowered = intent.lower()
    for phrase in _OWNER_INTENT_FORBIDDEN_PHRASES.get(owner, ()):
        if phrase in lowered:
            return f"owner-intent contradiction: owner={owner} cannot claim '{phrase}'"
    return None


def _validate_expansion_trace(trace: dict[str, Any], *, expected_policy_hash: str, step_id: str) -> list[str]:
    issues: list[str] = []
    try:
        validate_artifact(trace, "roadmap_expansion_trace")
    except Exception as exc:
        issues.append(f"trace schema validation failed: {exc}")
        return issues

    if trace.get("expansion_policy_hash") != expected_policy_hash:
        issues.append("trace expansion policy hash mismatch")

    if trace.get("step_id") != step_id:
        issues.append("trace step_id mismatch")

    field_trace = trace.get("field_trace", [])
    traced_fields = {entry.get("field_name") for entry in field_trace if isinstance(entry, dict)}
    missing_fields = sorted(_TRACE_REQUIRED_FIELDS - traced_fields)
    if missing_fields:
        issues.append(f"trace missing required derived field coverage: {', '.join(missing_fields)}")
    return issues


def _load_authoritative_source_versions(repo_root: Path) -> dict[str, str]:
    authority = dict(_DEFAULT_SOURCE_VERSION_AUTHORITY)
    example_path = repo_root / "contracts" / "examples" / "rax_upstream_input_envelope.example.json"
    if not example_path.exists():
        return authority
    try:
        example = json.loads(example_path.read_text(encoding="utf-8"))
    except Exception:
        return authority

    source_ref = example.get("source_authority_ref")
    source_version = example.get("source_version")
    if isinstance(source_ref, str) and isinstance(source_version, str):
        authority[source_ref] = source_version
    return authority


def assure_rax_input(
    payload: dict[str, Any],
    *,
    policy: dict[str, Any],
    expected_policy_hash: str,
    trace: dict[str, Any] | None = None,
    freshness_records: dict[str, dict[str, Any]] | None = None,
    provenance_records: dict[str, dict[str, Any]] | None = None,
    repo_root: Path | None = None,
    source_version_authority: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Validate upstream payload and classify fail-closed input conditions."""
    details: list[str] = []
    failure_classification = "none"

    missing_required_fields = sorted(field for field in _ENTRY_REQUIRED_FIELDS if field not in payload)
    if missing_required_fields:
        failure_classification = "invalid_input"
        details.append(f"entry_contract_missing_required_fields: {missing_required_fields}")

    if failure_classification == "none" and payload.get("artifact_type") != "rax_upstream_input_envelope":
        failure_classification = "invalid_input"
        details.append("entry_contract_invalid_artifact_type")

    if failure_classification == "none":
        try:
            validate_artifact(payload, "rax_upstream_input_envelope")
            details.append("upstream schema validation passed")
        except Exception as exc:  # fail-closed by classifying invalid input
            failure_classification = "invalid_input"
            details.append(f"schema validation failed: {exc}")

    if failure_classification == "none":
        intent = payload["intent"]
        if not _is_semantically_sufficient_intent(intent):
            failure_classification = "invalid_input"
            details.append("semantic_intent_insufficient: intent content is placeholder-like or too weak")

    if failure_classification == "none":
        owner_contradiction = _validate_owner_intent_semantics(payload["owner"], payload["intent"])
        if owner_contradiction:
            failure_classification = "ownership_violation"
            details.append(f"owner_intent_contradiction: {owner_contradiction}")

    if failure_classification == "none":
        if payload["owner"] not in policy.get("owner_defaults", {}):
            failure_classification = "ownership_violation"
            details.append("owner not present in expansion policy owner_defaults")

    if failure_classification == "none":
        if payload["step_id"] in payload["depends_on"]:
            failure_classification = "dependency_blocked"
            details.append("step cannot depend on itself")

    if failure_classification == "none":
        normalized_dependencies = [dep.strip() for dep in payload["depends_on"]]
        if len(normalized_dependencies) != len(set(normalized_dependencies)):
            failure_classification = "invalid_input"
            details.append("normalization_ambiguity: depends_on would collapse during canonical normalization")

    if failure_classification == "none":
        invalid_dependencies = [dep for dep in payload["depends_on"] if not _DEPENDENCY_ID_PATTERN.match(dep.strip())]
        if invalid_dependencies:
            failure_classification = "dependency_blocked"
            details.append(f"dependency_graph_corruption: invalid depends_on entries {sorted(invalid_dependencies)}")

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

    if failure_classification == "none":
        root = repo_root or Path(__file__).resolve().parents[3]
        authoritative_versions = _load_authoritative_source_versions(root)
        if source_version_authority is not None:
            immutable_version = authoritative_versions.get(payload["source_authority_ref"])
            supplied_version = source_version_authority.get(payload["source_authority_ref"])
            if immutable_version and supplied_version and supplied_version != immutable_version:
                failure_classification = "stale_reference"
                details.append("forged_authority_override_detected")
                details.append(f"source_version_drift: supplied_authority={supplied_version} immutable_authority={immutable_version}")
        expected_source_version = authoritative_versions.get(payload["source_authority_ref"])
        if expected_source_version is None:
            failure_classification = "stale_reference"
            details.append("source_version authority record missing for source_authority_ref")
        elif payload["source_version"] != expected_source_version:
            failure_classification = "stale_reference"
            details.append(
                f"source_version_drift: payload={payload['source_version']} authority={expected_source_version}"
            )

    if failure_classification == "none":
        if trace is None:
            failure_classification = "trace_tampering"
            details.append("missing_required_expansion_trace")
            details.append("entry_contract_trace_presence_required")
        else:
            trace_issues = _validate_expansion_trace(trace, expected_policy_hash=expected_policy_hash, step_id=payload["step_id"])
            if trace_issues:
                failure_classification = "trace_tampering"
                details.extend(trace_issues)

    passed = failure_classification == "none"
    return {
        "passed": passed,
        "details": details,
        "failure_classification": failure_classification,
        "stop_condition_triggered": not passed,
    }


def _check_acceptance_strength(step_contract: dict[str, Any], policy: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    checks = step_contract.get("acceptance_checks", [])
    owner = step_contract.get("owner")

    allowed_ids: set[str] = set(policy.get("acceptance_check_templates", {}).keys())
    owner_defaults = policy.get("owner_defaults", {}).get(owner, {})
    allowed_ids.update(owner_defaults.get("default_acceptance_check_templates", []))

    for index, check in enumerate(checks):
        check_id = str(check.get("check_id", ""))
        description = str(check.get("description", ""))
        description_lower = description.lower()

        check_id_is_recognized = check_id in allowed_ids or check_id.endswith("_valid") or check_id.endswith("_passes") or check_id.endswith("_resolvable")
        if not check_id_is_recognized:
            failures.append(f"weak_acceptance_check[{index}]: unapproved check_id '{check_id}'")

        if len(description.strip()) < 20:
            failures.append(f"weak_acceptance_check[{index}]: description too short")

        if any(term in description_lower for term in _WEAK_ACCEPTANCE_LANGUAGE):
            failures.append(f"weak_acceptance_check[{index}]: weak language detected")

        if not any(term in description_lower for term in _VERIFICATION_TERMS):
            failures.append(f"weak_acceptance_check[{index}]: missing verification semantics")

        if any(phrase in description_lower for phrase in _NON_OPERATIONAL_ACCEPTANCE_PHRASES):
            failures.append(f"weak_acceptance_check[{index}]: non-operational acceptance language detected")

        if check.get("required") is not True:
            failures.append(f"weak_acceptance_check[{index}]: check must be required=true")

    return failures


def _targets_within_allowed_prefixes(targets: list[str], allowed_prefixes: list[str]) -> bool:
    if not targets:
        return False
    return all(any(target.startswith(prefix) for prefix in allowed_prefixes) for target in targets)


def assure_rax_output(
    step_contract: dict[str, Any],
    *,
    repo_root: Path,
    policy: dict[str, Any] | None = None,
    prior_accepted_baseline: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate downstream contract readiness and next-system compatibility."""
    details: list[str] = []
    failure_classification = "none"
    policy = policy or {}

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

    if failure_classification == "none":
        owner_policy = policy.get("owner_defaults", {}).get(step_contract.get("owner"), {})
        allowed_module_prefixes = owner_policy.get("allowed_module_prefixes", [])
        allowed_test_prefixes = owner_policy.get("allowed_test_prefixes", [])

        if allowed_module_prefixes and not _targets_within_allowed_prefixes(step_contract.get("target_modules", []), allowed_module_prefixes):
            failure_classification = "downstream_incompatible"
            details.append("owner_target_contradiction: all target_modules must satisfy owner policy prefixes")

        if failure_classification == "none" and allowed_test_prefixes and not _targets_within_allowed_prefixes(
            step_contract.get("target_tests", []), allowed_test_prefixes
        ):
            failure_classification = "downstream_incompatible"
            details.append("owner_target_contradiction: all target_tests must satisfy owner policy prefixes")

    if failure_classification == "none":
        acceptance_failures = _check_acceptance_strength(step_contract, policy)
        if acceptance_failures:
            failure_classification = "invalid_output"
            details.extend(acceptance_failures)

    if failure_classification == "none" and prior_accepted_baseline is not None:
        baseline_checks = {check["check_id"] for check in prior_accepted_baseline.get("acceptance_checks", []) if "check_id" in check}
        current_checks = {check["check_id"] for check in step_contract.get("acceptance_checks", []) if "check_id" in check}
        missing_baseline = sorted(baseline_checks - current_checks)
        if missing_baseline:
            failure_classification = "downstream_incompatible"
            details.append(f"regression_detected: missing baseline acceptance checks {missing_baseline}")

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

    counter_evidence: list[str] = []
    if failure_classification != "none":
        counter_evidence.extend(str(item).strip() for item in input_assurance.get("details", []) if str(item).strip())
        counter_evidence.extend(str(item).strip() for item in output_assurance.get("details", []) if str(item).strip())
        counter_evidence = [item for item in counter_evidence if item.lower() not in _COUNTER_EVIDENCE_PLACEHOLDERS]
        if not counter_evidence:
            raise RAXAssuranceError("counter_evidence required and must be concrete when failures exist")

    stop_condition_triggered = failure_classification != "none"

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
        "counter_evidence": counter_evidence,
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
        "stop_condition_triggered": stop_condition_triggered,
        "acceptance_decision": decision,
        "status_transition_result": status_transition,
    }
    validate_artifact(audit, "rax_assurance_audit_record")
    return audit



def evaluate_rax_control_readiness(
    *,
    batch: str,
    target_ref: str,
    eval_summary: dict[str, Any],
    eval_results: list[dict[str, Any]],
    required_eval_coverage: dict[str, Any],
    assurance_audit: dict[str, Any] | None = None,
    trace_integrity_evidence: dict[str, Any] | None = None,
    lineage_provenance_evidence: dict[str, Any] | None = None,
    dependency_state: dict[str, Any] | None = None,
    authority_records: dict[str, Any] | None = None,
    replay_baseline_store: dict[str, Any] | None = None,
    replay_key: str | None = None,
) -> dict[str, Any]:
    """Build bounded RAX control-readiness artifact from governed eval artifacts."""
    from spectrum_systems.modules.runtime.rax_eval_runner import build_rax_control_readiness_record

    return build_rax_control_readiness_record(
        batch=batch,
        target_ref=target_ref,
        eval_summary=eval_summary,
        eval_results=eval_results,
        required_eval_coverage=required_eval_coverage,
        assurance_audit=assurance_audit,
        trace_integrity_evidence=trace_integrity_evidence,
        lineage_provenance_evidence=lineage_provenance_evidence,
        dependency_state=dependency_state,
        authority_records=authority_records,
        replay_baseline_store=replay_baseline_store,
        replay_key=replay_key,
    )
