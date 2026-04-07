"""Deterministic repair prompt generation from failure diagnosis artifacts (BATCH-FRE-02)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema


class RepairPromptGenerationError(ValueError):
    """Raised when a deterministic repair prompt cannot be generated safely."""


_ALWAYS_CONSTRAINTS = [
    "Do NOT weaken schema constraints or required fields.",
    "Do NOT bypass contract preflight, enforcement, or control gates.",
    "Do NOT redesign system architecture beyond the diagnosed root cause.",
    "Only implement the smallest safe fix scope described below.",
    "Preserve deterministic and replayable behavior.",
]

_TEMPLATE_LIBRARY: dict[str, dict[str, Any]] = {
    "schema_mismatch": {
        "intent": "Realign schema and example so contract and golden-path example are consistent.",
        "description": "Apply the smallest alignment between schema and example based on diagnosed drift evidence.",
        "actions": [
            "Identify mismatch field(s) from diagnosis evidence and confirm authoritative source of truth.",
            "Update only the incorrect side (schema or example) to restore exact alignment.",
            "Keep contract strictness unchanged while restoring schema/example parity.",
            "Validate updated example against schema through contract enforcement checks.",
        ],
        "success": ["Schema and example validate without drift-related errors."],
    },
    "contract_registration_missing": {
        "intent": "Restore contract registration/manifest alignment for governed artifacts and consumers.",
        "description": "Correct registration taxonomy or consumer-pin mismatches in standards/registry surfaces only.",
        "actions": [
            "Locate mismatched manifest or registry entries identified in diagnosis evidence.",
            "Update artifact_class/intended_consumers (or equivalent registry fields) to authoritative values.",
            "Keep unrelated contract entries unchanged.",
            "Run contract enforcement checks to verify registration alignment.",
        ],
        "success": ["Contract registration mismatch findings are resolved."],
    },
    "branch_policy_violation": {
        "intent": "Restore branch/governance policy compliance without bypasses.",
        "description": "Fix the policy violation root path so governed branch constraints hold under normal execution.",
        "actions": [
            "Trace the violated policy condition to producer/validator logic.",
            "Implement minimal correction that restores policy compliance.",
            "Do not add suppression, allow-list bypass, or post-hoc masking logic.",
            "Run policy and preflight checks for the same scenario.",
        ],
        "success": ["Diagnosed branch policy violation no longer reproduces."],
    },
    "dependency_graph_violation": {
        "intent": "Restore deterministic dependency wiring across producer/consumer/runtime seams.",
        "description": "Repair dependency graph breakage while preserving bounded runtime module interfaces.",
        "actions": [
            "Locate dependency seam named by diagnosis evidence.",
            "Restore minimal producer/consumer wiring needed for governed artifact flow.",
            "Ensure mapped inputs/outputs use contract-defined fields only.",
            "Run targeted producer/consumer tests validating dependency path correctness.",
        ],
        "success": ["Dependency graph violation is eliminated on the diagnosed path."],
    },
    "test_expectation_drift": {
        "intent": "Align tests with authoritative governed behavior or restore behavior if tests are authoritative.",
        "description": "Apply minimal correction based on diagnosis evidence indicating expectation drift origin.",
        "actions": [
            "Inspect diagnosed failing assertions and corresponding governed behavior.",
            "If behavior is authoritative, update mismatched test expectations only.",
            "If implementation regressed, fix implementation and keep tests authoritative.",
            "Run targeted pytest cases proving expectation/behavior alignment.",
        ],
        "success": ["Diagnosed test expectation drift is eliminated."],
    },
    "unknown_failure": {
        "intent": "Produce governed manual triage instructions for unresolved deterministic classification.",
        "description": "Generate bounded triage instructions that preserve loop continuity without speculative code fixes.",
        "actions": [
            "Treat diagnosis as non-auto-repairable until additional governed evidence is captured.",
            "Capture minimal reproducer evidence and classify candidate causes using canonical registry classes only.",
            "Prepare follow-up diagnosis proposal with authoritative evidence refs; avoid speculative implementation edits.",
            "Run baseline validation commands to preserve replay continuity.",
        ],
        "success": ["Manual triage packet is prepared with authoritative evidence references."],
    },
}


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _canonical_hash(payload: Any) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _validate(instance: dict[str, Any], schema_name: str, *, label: str) -> None:
    validator = Draft202012Validator(load_schema(schema_name), format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda err: list(err.absolute_path))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise RepairPromptGenerationError(f"{label} failed schema validation ({schema_name}): {details}")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_source_refs(diagnosis_artifact: dict[str, Any]) -> list[str]:
    refs = diagnosis_artifact.get("source_artifact_refs") or []
    candidates: set[str] = set()
    for ref in refs:
        if isinstance(ref, str) and ref.strip():
            candidates.add(ref.strip())
    for row in diagnosis_artifact.get("evidence") or []:
        artifact_ref = row.get("artifact_ref")
        if isinstance(artifact_ref, str) and artifact_ref.strip():
            candidates.add(artifact_ref.strip())
    return sorted(candidates)


def _default_validation_commands(diagnosis_artifact: dict[str, Any], root_cause: str) -> list[str]:
    commands = [
        cmd.strip()
        for cmd in diagnosis_artifact.get("expected_validation_commands", [])
        if isinstance(cmd, str) and cmd.strip()
    ]
    if not commands:
        commands.append("pytest tests/test_repair_prompt_generator.py -q")

    if root_cause in {
        "schema_mismatch",
        "contract_registration_missing",
        "dependency_graph_violation",
        "test_expectation_drift",
    } and "python scripts/run_contract_enforcement.py" not in commands:
        commands.append("python scripts/run_contract_enforcement.py")

    if root_cause in {"branch_policy_violation"} and (
        "python scripts/run_contract_preflight.py --output-dir outputs/contract_preflight" not in commands
    ):
        commands.append("python scripts/run_contract_preflight.py --output-dir outputs/contract_preflight")

    return sorted(dict.fromkeys(commands))


def _resolve_template(root_cause: str) -> dict[str, Any]:
    template = _TEMPLATE_LIBRARY.get(root_cause)
    if template is None:
        raise RepairPromptGenerationError(
            f"unsupported primary_root_cause '{root_cause}'; no deterministic repair template available"
        )
    return template


def generate_repair_prompt(
    diagnosis_artifact: dict[str, Any],
    *,
    emitted_at: str | None = None,
    run_id: str = "run-fre-02",
    trace_id: str = "trace-fre-02",
) -> dict[str, Any]:
    """Generate deterministic repair prompt artifact from a valid diagnosis artifact."""
    if not isinstance(diagnosis_artifact, dict):
        raise RepairPromptGenerationError("diagnosis_artifact must be an object")

    _validate(diagnosis_artifact, "failure_diagnosis_artifact", label="diagnosis_artifact")

    primary_root_cause = diagnosis_artifact["primary_root_cause"]
    template = _resolve_template(primary_root_cause)

    diagnosis_id = diagnosis_artifact["diagnosis_id"]
    evidence_ids = sorted(
        row["evidence_id"]
        for row in diagnosis_artifact["evidence"]
        if isinstance(row, dict) and isinstance(row.get("evidence_id"), str)
    )
    if not evidence_ids:
        raise RepairPromptGenerationError("diagnosis_artifact must include at least one evidence entry with evidence_id")

    target_files_or_surfaces = _normalize_source_refs(diagnosis_artifact)
    if not target_files_or_surfaces:
        raise RepairPromptGenerationError("diagnosis_artifact must include non-empty source/evidence artifact references")

    resolved_emitted_at = emitted_at or diagnosis_artifact.get("emitted_at") or _utc_now()
    template_key = {
        "primary_root_cause": primary_root_cause,
        "smallest_safe_fix_class": diagnosis_artifact["smallest_safe_fix_class"],
        "recommended_repair_area": diagnosis_artifact["recommended_repair_area"],
        "target_files_or_surfaces": target_files_or_surfaces,
        "evidence_ids": evidence_ids,
    }
    hash_prefix = _canonical_hash(template_key)[:20]

    step_by_step_actions = [
        f"Locate diagnosed repair surfaces: {', '.join(target_files_or_surfaces)}.",
        f"Constrain edits to repair area: {diagnosis_artifact['recommended_repair_area']}.",
        *template["actions"],
        "Run the listed validation commands and confirm all success criteria are met.",
    ]

    validation_commands = _default_validation_commands(diagnosis_artifact, primary_root_cause)

    success_criteria = [
        "Targeted validation commands complete successfully.",
        *template["success"],
        "No unrelated files or behaviors outside diagnosed scope were changed.",
    ]

    repair_prompt_artifact = {
        "artifact_type": "repair_prompt_artifact",
        "artifact_version": "1.1.0",
        "schema_version": "1.1.0",
        "standards_version": diagnosis_artifact["standards_version"],
        "repair_prompt_id": f"RPR-{hash_prefix}",
        "diagnosis_ref": diagnosis_id,
        "target_files_or_surfaces": target_files_or_surfaces,
        "repair_intent": template["intent"],
        "smallest_safe_fix_description": template["description"],
        "step_by_step_actions": step_by_step_actions,
        "validation_commands": validation_commands,
        "constraints": list(_ALWAYS_CONSTRAINTS),
        "success_criteria": success_criteria,
        "repair_prompt_text": "\n".join(
            [
                "You are Codex executing a bounded repair from a diagnosed failure.",
                f"Diagnosis reference: {diagnosis_id}",
                f"Primary root cause: {primary_root_cause}",
                f"Repair intent: {template['intent']}",
                "",
                "Step-by-step actions:",
                *[f"{idx}. {step}" for idx, step in enumerate(step_by_step_actions, start=1)],
                "",
                "Validation commands:",
                *[f"- {cmd}" for cmd in validation_commands],
                "",
                "Constraints:",
                *[f"- {c}" for c in _ALWAYS_CONSTRAINTS],
                "",
                "Success criteria:",
                *[f"- {criterion}" for criterion in success_criteria],
            ]
        ),
        "emitted_at": resolved_emitted_at,
        "trace": {
            "run_id": run_id,
            "trace_id": trace_id,
            "policy_id": "FRE-004.repair_prompt_generator.v1",
            "governing_ref": "docs/roadmaps/system_roadmap.md#batch-fre-02",
            "diagnosis_hash": _canonical_hash(diagnosis_artifact),
            "template_id": primary_root_cause,
        },
    }

    _validate(repair_prompt_artifact, "repair_prompt_artifact", label="repair_prompt_artifact")
    return repair_prompt_artifact
