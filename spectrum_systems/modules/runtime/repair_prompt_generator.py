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
    "missing_required_surface": {
        "intent": "Restore the missing required artifact/surface at the governed path and contract shape.",
        "description": "Create or restore the required artifact surface exactly as required by diagnosed consumers.",
        "actions": [
            "Locate missing required surfaces listed in diagnosis evidence details and source references.",
            "Create or restore each missing artifact at the governed path without introducing new artifact families.",
            "Ensure restored artifact(s) conform to the authoritative schema and expected required fields.",
            "Re-run targeted checks to confirm the required surface is present and discoverable.",
        ],
        "success": [
            "Previously missing governed artifact surface exists at expected path(s).",
            "Artifact validates against its authoritative contract.",
        ],
    },
    "schema_example_drift": {
        "intent": "Realign schema and example so contract and golden-path example are consistent.",
        "description": "Apply the smallest alignment between schema and example based on diagnosed drift evidence.",
        "actions": [
            "Identify mismatch field(s) from diagnosis evidence and confirm authoritative source of truth.",
            "Update only the incorrect side (schema or example) to restore exact alignment.",
            "Keep contract strictness unchanged while restoring schema/example parity.",
            "Validate updated example against schema through contract enforcement checks.",
        ],
        "success": [
            "Schema and example validate without drift-related errors.",
            "No schema weakening was introduced while resolving drift.",
        ],
    },
    "producer_wiring_gap": {
        "intent": "Restore producer-side emission of required artifact outputs.",
        "description": "Repair producer wiring so required artifacts are emitted in governed shape.",
        "actions": [
            "Locate producer boundary named by diagnosis and identify missing emit/write path.",
            "Add or restore minimal producer emission logic for required artifact(s).",
            "Ensure produced artifact structure matches contract-required fields.",
            "Run targeted tests validating producer output shape and presence.",
        ],
        "success": [
            "Producer emits required artifact deterministically.",
            "Produced artifact conforms to contract shape.",
        ],
    },
    "consumer_wiring_gap": {
        "intent": "Restore consumer-side ingestion/use of required artifact inputs.",
        "description": "Repair consumer wiring so required artifacts are read and mapped correctly.",
        "actions": [
            "Locate consumer boundary and failing ingestion path from diagnosis evidence.",
            "Add or restore minimal read/map logic for required input artifacts.",
            "Ensure downstream mapping uses governed keys and contract-defined fields only.",
            "Run targeted tests validating consumer mapping correctness.",
        ],
        "success": [
            "Consumer reads required artifact input(s) correctly.",
            "Consumer mapping/output no longer fails for diagnosed gap.",
        ],
    },
    "invariant_violation": {
        "intent": "Restore upstream invariant enforcement rather than suppressing the violation.",
        "description": "Fix the root-cause path so the violated invariant holds under normal execution.",
        "actions": [
            "Trace the violated invariant to upstream producer/validator logic.",
            "Implement minimal root-cause correction that restores invariant compliance.",
            "Do not add suppression, allow-list bypass, or post-hoc masking logic.",
            "Run invariant-focused tests and relevant preflight checks.",
        ],
        "success": [
            "Diagnosed invariant no longer violates under the same input.",
            "No suppression/bypass logic was introduced.",
        ],
    },
    "test_expectation_drift": {
        "intent": "Align tests with correct governed behavior, or restore behavior if tests are authoritative per diagnosis.",
        "description": "Apply minimal correction based on diagnosis evidence indicating expectation drift origin.",
        "actions": [
            "Inspect diagnosed failing assertions and corresponding governed behavior.",
            "If diagnosis indicates behavior is correct, update only mismatched test expectations.",
            "If diagnosis indicates behavior regression, fix implementation and keep tests authoritative.",
            "Run targeted pytest cases proving expectation/behavior alignment.",
        ],
        "success": [
            "Targeted test expectations match authoritative behavior.",
            "Diagnosed drift condition is eliminated.",
        ],
    },
    "manifest_or_registry_mismatch": {
        "intent": "Restore manifest/registry alignment for artifact class and intended consumers.",
        "description": "Correct taxonomy or consumer-pin mismatches in standards/registry surfaces only.",
        "actions": [
            "Locate mismatched manifest or registry entries identified in diagnosis evidence.",
            "Update artifact_class/intended_consumers (or equivalent registry fields) to authoritative values.",
            "Keep unrelated contract entries unchanged.",
            "Run contract enforcement checks to verify registry alignment.",
        ],
        "success": [
            "Manifest/registry mismatch findings are resolved.",
            "Contract enforcement passes for the corrected registry surface.",
        ],
    },
    "control_surface_input_missing": {
        "intent": "Restore required control-surface input artifact generation/availability.",
        "description": "Repair minimal path that ensures required control input artifact exists before preflight.",
        "actions": [
            "Identify missing control input artifact(s) listed in diagnosis evidence.",
            "Restore generation or handoff path that produces required input artifact(s).",
            "Ensure input artifact path and shape match governed expectations.",
            "Run preflight checks verifying input presence before execution.",
        ],
        "success": [
            "Required control-surface inputs are present for preflight.",
            "Preflight no longer blocks for missing control input on same scenario.",
        ],
    },
    "fixture_gap": {
        "intent": "Restore deterministic fixture coverage for the diagnosed governed behavior.",
        "description": "Apply a fixture-first correction that closes missing or stale fixture surface without fabricating implementation behavior.",
        "actions": [
            "Identify missing or stale fixture surfaces from diagnosis evidence and governed source refs.",
            "Add or update only the minimum fixture(s) needed to represent the diagnosed happy/failure path.",
            "Keep fixture data deterministic and contract-valid; do not use generated randomness.",
            "Run targeted tests that consume the repaired fixture surface.",
        ],
        "success": [
            "Fixture surface required by diagnosis exists and is deterministic.",
            "Targeted tests no longer fail due to missing/stale fixture input.",
        ],
    },
    "certification_surface_gap": {
        "intent": "Restore missing certification evidence surface required for governed progression.",
        "description": "Repair certification artifact production or linkage so governance can verify required certification signals.",
        "actions": [
            "Locate the certification surface or link identified as missing in diagnosis evidence.",
            "Restore minimal producer/linkage path emitting required certification evidence references.",
            "Keep certification semantics strict; do not bypass certification gates.",
            "Run certification-related validation checks proving evidence is present and consumable.",
        ],
        "success": [
            "Required certification evidence surface is emitted and discoverable.",
            "Governance checks can consume certification evidence for the diagnosed scenario.",
        ],
    },
    "source_authority_anchor_gap": {
        "intent": "Restore source-authority anchor references so downstream decisions remain governed by authoritative inputs.",
        "description": "Repair missing/invalid authority anchor linkage without introducing alternate authority paths.",
        "actions": [
            "Identify missing or broken source-authority anchors named in diagnosis evidence.",
            "Restore canonical anchor references to authoritative roadmap/contract sources only.",
            "Keep non-authoritative and deprecated sources excluded from anchor resolution.",
            "Run targeted governance checks confirming source-authority anchor consumption succeeds.",
        ],
        "success": [
            "Authority anchor references resolve to authoritative governed sources.",
            "Diagnosed source-authority gap is eliminated without adding alternate authority paths.",
        ],
    },
    "policy_composition_gap": {
        "intent": "Restore deterministic policy composition so required rules are evaluated in governed order.",
        "description": "Repair missing/incorrect policy composition wiring while preserving policy precedence and fail-closed behavior.",
        "actions": [
            "Locate policy composition seam identified in diagnosis evidence.",
            "Restore required policy inputs and precedence ordering for the diagnosed path.",
            "Ensure unresolved policy inputs fail closed rather than defaulting to allow.",
            "Run policy composition validation checks for the diagnosed path.",
        ],
        "success": [
            "Policy composition includes all required governed inputs in deterministic order.",
            "Diagnosed policy composition failure no longer reproduces.",
        ],
    },
    "unknown_failure_class": {
        "intent": "Produce a governed manual-triage artifact path when no safe deterministic auto-repair template is available.",
        "description": "Generate bounded triage instructions that preserve loop continuity without fabricating a direct fix.",
        "actions": [
            "Treat the diagnosis as non-auto-repairable until explicit governed classification is established.",
            "Capture minimal reproducer evidence and classify candidate root causes using existing governed taxonomy only.",
            "Prepare a follow-up diagnosis update proposal with authoritative evidence refs; do not implement speculative code changes.",
            "Run baseline validation commands to confirm current failure state and preserve replay continuity.",
        ],
        "success": [
            "Manual triage packet is prepared with authoritative evidence references.",
            "No speculative implementation changes were introduced for unknown failure class.",
        ],
    },
    "override_temporal_validation_gap": {
        "intent": "Enforce temporal validation for override issuance and effective timestamps.",
        "description": "Add/repair strict temporal check ensuring override issuance is not in the future and validity windows are enforced.",
        "actions": [
            "Locate override validation logic handling issued_at/effective timestamps.",
            "Implement explicit temporal enforcement (e.g., issued_at <= now and valid time-window checks).",
            "Ensure invalid temporal inputs fail closed rather than defaulting to allow.",
            "Run targeted override enforcement tests.",
        ],
        "success": [
            "Temporal override validation rejects invalid/future-dated overrides.",
            "Override enforcement tests pass for temporal edge cases.",
        ],
    },
    "corroboration_validation_gap": {
        "intent": "Restore resolver-backed corroboration validation instead of string-only checks.",
        "description": "Replace superficial corroboration checks with deterministic resolver-backed validation.",
        "actions": [
            "Locate corroboration validation path identified in diagnosis evidence.",
            "Replace string/substring-only checks with resolver-backed corroboration validation logic.",
            "Ensure missing or unresolved corroboration fails closed.",
            "Run targeted corroboration validation tests.",
        ],
        "success": [
            "Corroboration validation uses resolver-backed evidence lookup.",
            "Invalid corroboration claims are blocked by validation.",
        ],
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
        "schema_example_drift",
        "manifest_or_registry_mismatch",
        "missing_required_surface",
        "control_surface_input_missing",
        "source_authority_anchor_gap",
        "certification_surface_gap",
        "policy_composition_gap",
        "corroboration_validation_gap",
        "override_temporal_validation_gap",
    } and "python scripts/run_contract_enforcement.py" not in commands:
        commands.append("python scripts/run_contract_enforcement.py")

    if root_cause in {"control_surface_input_missing", "invariant_violation"} and (
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
