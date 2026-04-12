"""Deterministic expansion from canonical RAX model to downstream roadmap step contract."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from spectrum_systems.modules.runtime.rax_model import CanonicalRoadmapStep


class RAXExpansionError(ValueError):
    """Raised when deterministic expansion policy requirements are not satisfied."""


def _policy_sha256(policy_path: Path) -> str:
    return hashlib.sha256(policy_path.read_bytes()).hexdigest()


def _acceptance_checks_from_templates(policy: dict[str, Any], template_ids: list[str]) -> list[dict[str, Any]]:
    templates = policy.get("acceptance_check_templates", {})
    checks: list[dict[str, Any]] = []
    for template_id in template_ids:
        description = templates.get(template_id)
        if not description:
            raise RAXExpansionError(f"missing acceptance_check_templates mapping for {template_id}")
        checks.append({"check_id": template_id, "description": description, "required": True})
    return checks


def expand_to_step_contract(
    canonical_step: CanonicalRoadmapStep,
    *,
    policy: dict[str, Any],
    policy_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Expand canonical step to strict downstream contract and expansion trace."""
    owner_defaults = policy.get("owner_defaults", {})
    owner_mapping = owner_defaults.get(canonical_step.owner)
    if not owner_mapping:
        raise RAXExpansionError(f"missing owner_defaults mapping for owner {canonical_step.owner}")

    module_prefixes = owner_mapping.get("allowed_module_prefixes", [])
    test_prefixes = owner_mapping.get("allowed_test_prefixes", [])
    contract_locations = owner_mapping.get("default_contract_locations", [])
    acceptance_templates = owner_mapping.get("default_acceptance_check_templates", [])
    if not module_prefixes or not test_prefixes or not contract_locations or not acceptance_templates:
        raise RAXExpansionError("owner mapping must include module/test/contract/acceptance defaults")

    expansion_version = policy.get("expansion_version") or policy.get("policy_version")
    if not expansion_version:
        raise RAXExpansionError("policy_version/expansion_version missing")

    policy_hash = _policy_sha256(policy_path)

    target_modules = sorted(f"{prefix}{canonical_step.step_id.lower().replace('-', '_')}.py" for prefix in module_prefixes)
    target_tests = sorted(f"{prefix}_rax_interface_assurance.py" for prefix in test_prefixes)
    target_contracts = sorted(
        {
            *contract_locations,
            "contracts/schemas/roadmap_step_contract.schema.json",
            "contracts/schemas/roadmap_expansion_trace.schema.json",
        }
    )

    acceptance_checks = _acceptance_checks_from_templates(policy, acceptance_templates)

    runtime_entrypoints = [
        "spectrum_systems.modules.runtime.rax_model:load_compact_roadmap_step",
        "spectrum_systems.modules.runtime.rax_expander:expand_to_step_contract",
        "spectrum_systems.modules.runtime.rax_assurance:assure_rax_output",
    ]

    step_contract = {
        "artifact_type": "roadmap_step_contract",
        "roadmap_id": canonical_step.roadmap_id,
        "roadmap_group": canonical_step.roadmap_group,
        "step_id": canonical_step.step_id,
        "owner": canonical_step.owner,
        "intent": canonical_step.intent,
        "depends_on": list(canonical_step.depends_on),
        "source_authority_ref": canonical_step.source_authority_ref,
        "source_version": canonical_step.source_version,
        "input_freshness_ref": canonical_step.input_freshness_ref,
        "input_provenance_ref": canonical_step.input_provenance_ref,
        "target_modules": target_modules,
        "target_contracts": target_contracts,
        "target_tests": target_tests,
        "runtime_entrypoints": runtime_entrypoints,
        "forbidden_patterns": policy.get("default_forbidden_patterns", []),
        "acceptance_checks": acceptance_checks,
        "realization_mode": "runtime_realization",
        "realization_status": "planned_only",
        "downstream_compatibility": policy.get(
            "default_downstream_compatibility",
            {"prg_rdx_step_metadata": True, "realization_runner_contract_complete": True},
        ),
        "expansion_version": expansion_version,
        "expansion_policy_hash": policy_hash,
        "expansion_trace_ref": f"contracts/examples/roadmap_expansion_trace.example.json#{canonical_step.step_id}",
    }

    field_trace = []
    for field_name, source_type, source_ref, rule_id, notes in (
        ("owner", "roadmap_artifact", canonical_step.source_authority_ref, "OWNER_FROM_UPSTREAM", "Owner copied from compact roadmap input."),
        (
            "target_modules",
            "expansion_policy",
            f"{policy_path.as_posix()}#owner_defaults.{canonical_step.owner}.allowed_module_prefixes",
            "MODULE_PREFIX_BY_OWNER",
            "Module targets derived from owner-bound policy prefixes.",
        ),
        (
            "target_tests",
            "expansion_policy",
            f"{policy_path.as_posix()}#owner_defaults.{canonical_step.owner}.allowed_test_prefixes",
            "TEST_PREFIX_BY_OWNER",
            "Test targets derived from owner-bound policy prefixes.",
        ),
        (
            "acceptance_checks",
            "expansion_policy",
            f"{policy_path.as_posix()}#acceptance_check_templates",
            "CHECK_TEMPLATE_EXPANSION",
            "Acceptance checks expanded from deterministic templates.",
        ),
        (
            "forbidden_patterns",
            "expansion_policy",
            f"{policy_path.as_posix()}#default_forbidden_patterns",
            "FORBIDDEN_PATTERN_DEFAULTS",
            "Default forbidden patterns carried from governed policy.",
        ),
        (
            "downstream_compatibility",
            "expansion_policy",
            f"{policy_path.as_posix()}#default_downstream_compatibility",
            "DOWNSTREAM_COMPATIBILITY_DEFAULT",
            "Downstream compatibility booleans set by policy default.",
        ),
    ):
        field_trace.append(
            {
                "field_name": field_name,
                "source_type": source_type,
                "source_ref": source_ref,
                "rule_id": rule_id,
                "notes": notes,
            }
        )

    trace = {
        "artifact_type": "roadmap_expansion_trace",
        "step_id": canonical_step.step_id,
        "expansion_version": expansion_version,
        "expansion_policy_hash": policy_hash,
        "field_trace": field_trace,
    }

    # enforce deterministic ordering on serialized forms
    json.dumps(step_contract, sort_keys=True)
    json.dumps(trace, sort_keys=True)
    return step_contract, trace
