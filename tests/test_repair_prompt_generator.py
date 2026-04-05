from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema
from spectrum_systems.modules.runtime.repair_prompt_generator import (
    RepairPromptGenerationError,
    generate_repair_prompt,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _diagnosis_fixture() -> dict:
    return json.loads((_REPO_ROOT / "contracts" / "examples" / "failure_diagnosis_artifact.json").read_text(encoding="utf-8"))


def _diagnosis_for(root_cause: str, *, fix_class: str, repair_area: str) -> dict:
    diagnosis = _diagnosis_fixture()
    diagnosis["primary_root_cause"] = root_cause
    diagnosis["secondary_contributors"] = []
    diagnosis["smallest_safe_fix_class"] = fix_class
    diagnosis["recommended_repair_area"] = repair_area
    diagnosis["evidence"] = [
        {
            "evidence_id": "E-aaaaaaaaaaaaaaaa",
            "source_surface": "contract_enforcement",
            "evidence_type": root_cause,
            "message": f"diagnosed {root_cause}",
            "artifact_ref": "contracts/standards-manifest.json",
            "details": {"field": "diagnosis", "value": root_cause},
        }
    ]
    return diagnosis


def test_missing_required_surface_generates_required_template() -> None:
    diagnosis = _diagnosis_for(
        "missing_required_surface",
        fix_class="restore_required_surface_artifact",
        repair_area="contracts/examples and producer generation boundary",
    )

    artifact = generate_repair_prompt(diagnosis, emitted_at="2026-04-05T00:00:00Z")

    assert artifact["trace"]["template_id"] == "missing_required_surface"
    assert "Create or restore the required artifact surface" in artifact["smallest_safe_fix_description"]
    assert any("Locate diagnosed repair surfaces" in step for step in artifact["step_by_step_actions"])


def test_schema_example_drift_generates_contract_alignment_prompt() -> None:
    diagnosis = _diagnosis_for(
        "schema_example_drift",
        fix_class="align_schema_example_pair",
        repair_area="contracts/schemas and contracts/examples",
    )

    artifact = generate_repair_prompt(diagnosis, emitted_at="2026-04-05T00:00:00Z")

    assert artifact["trace"]["template_id"] == "schema_example_drift"
    assert any("Update only the incorrect side" in step for step in artifact["step_by_step_actions"])
    assert "python scripts/run_contract_enforcement.py" in artifact["validation_commands"]


def test_manifest_mismatch_generates_registry_alignment_prompt() -> None:
    diagnosis = _diagnosis_for(
        "manifest_or_registry_mismatch",
        fix_class="align_manifest_registry_taxonomy",
        repair_area="contracts/standards-manifest.json and consuming manifests",
    )

    artifact = generate_repair_prompt(diagnosis, emitted_at="2026-04-05T00:00:00Z")

    assert artifact["trace"]["template_id"] == "manifest_or_registry_mismatch"
    assert any("artifact_class/intended_consumers" in step for step in artifact["step_by_step_actions"])
    assert any("Do NOT weaken schema" in c for c in artifact["constraints"])


def test_override_temporal_gap_generates_temporal_enforcement_prompt() -> None:
    diagnosis = _diagnosis_for(
        "override_temporal_validation_gap",
        fix_class="repair_override_temporal_validation",
        repair_area="override temporal validation surface",
    )

    artifact = generate_repair_prompt(diagnosis, emitted_at="2026-04-05T00:00:00Z")

    assert artifact["trace"]["template_id"] == "override_temporal_validation_gap"
    assert any("issued_at <= now" in step for step in artifact["step_by_step_actions"])


def test_corroboration_gap_generates_resolver_backed_prompt() -> None:
    diagnosis = _diagnosis_for(
        "corroboration_validation_gap",
        fix_class="restore_corroboration_validation",
        repair_area="corroboration and validation boundary",
    )

    artifact = generate_repair_prompt(diagnosis, emitted_at="2026-04-05T00:00:00Z")

    assert artifact["trace"]["template_id"] == "corroboration_validation_gap"
    assert any("resolver-backed" in step for step in artifact["step_by_step_actions"])


def test_deterministic_for_same_input() -> None:
    diagnosis = _diagnosis_for(
        "manifest_or_registry_mismatch",
        fix_class="align_manifest_registry_taxonomy",
        repair_area="contracts/standards-manifest.json and consuming manifests",
    )

    first = generate_repair_prompt(copy.deepcopy(diagnosis), emitted_at="2026-04-05T00:00:00Z")
    second = generate_repair_prompt(copy.deepcopy(diagnosis), emitted_at="2026-04-05T00:00:00Z")

    assert first == second


def test_fail_closed_on_incomplete_diagnosis() -> None:
    diagnosis = _diagnosis_fixture()
    diagnosis.pop("smallest_safe_fix_class")

    with pytest.raises(RepairPromptGenerationError, match="diagnosis_artifact failed schema validation"):
        generate_repair_prompt(diagnosis)


def test_contract_example_and_generated_artifact_validate() -> None:
    schema = load_schema("repair_prompt_artifact")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())

    example = json.loads((_REPO_ROOT / "contracts" / "examples" / "repair_prompt_artifact.json").read_text(encoding="utf-8"))
    validator.validate(example)

    diagnosis = _diagnosis_for(
        "schema_example_drift",
        fix_class="align_schema_example_pair",
        repair_area="contracts/schemas and contracts/examples",
    )
    generated = generate_repair_prompt(diagnosis, emitted_at="2026-04-05T00:00:00Z")
    validator.validate(generated)


def test_standards_manifest_registers_repair_prompt_artifact() -> None:
    manifest = json.loads((_REPO_ROOT / "contracts" / "standards-manifest.json").read_text(encoding="utf-8"))
    entries = [entry for entry in manifest.get("contracts", []) if entry.get("artifact_type") == "repair_prompt_artifact"]
    assert len(entries) == 1
    entry = entries[0]
    assert entry["artifact_class"] == "coordination"
    assert entry["example_path"] == "contracts/examples/repair_prompt_artifact.json"
