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
_ALL_ROOT_CAUSES = load_schema("failure_diagnosis_artifact")["properties"]["primary_root_cause"]["enum"]


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


def test_contract_registration_missing_generates_registry_alignment_template() -> None:
    diagnosis = _diagnosis_for(
        "contract_registration_missing",
        fix_class="align_contract_registration",
        repair_area="contracts/standards-manifest.json",
    )

    artifact = generate_repair_prompt(diagnosis, emitted_at="2026-04-05T00:00:00Z")

    assert artifact["trace"]["template_id"] == "contract_registration_missing"
    assert "registration taxonomy" in artifact["smallest_safe_fix_description"]
    assert any("Locate diagnosed repair surfaces" in step for step in artifact["step_by_step_actions"])


def test_schema_mismatch_generates_contract_alignment_prompt() -> None:
    diagnosis = _diagnosis_for(
        "schema_mismatch",
        fix_class="align_schema_example_pair",
        repair_area="contracts/schemas and contracts/examples",
    )

    artifact = generate_repair_prompt(diagnosis, emitted_at="2026-04-05T00:00:00Z")

    assert artifact["trace"]["template_id"] == "schema_mismatch"
    assert any("Update only the incorrect side" in step for step in artifact["step_by_step_actions"])
    assert "python scripts/run_contract_enforcement.py" in artifact["validation_commands"]


def test_branch_policy_violation_generates_policy_prompt() -> None:
    diagnosis = _diagnosis_for(
        "branch_policy_violation",
        fix_class="enforce_branch_policy",
        repair_area=".github/workflows and governance policy surfaces",
    )

    artifact = generate_repair_prompt(diagnosis, emitted_at="2026-04-05T00:00:00Z")

    assert artifact["trace"]["template_id"] == "branch_policy_violation"
    assert any("policy" in step.lower() for step in artifact["step_by_step_actions"])
    assert any("Do NOT weaken schema" in c for c in artifact["constraints"])


def test_dependency_graph_violation_generates_dependency_prompt() -> None:
    diagnosis = _diagnosis_for(
        "dependency_graph_violation",
        fix_class="repair_dependency_graph",
        repair_area="runtime module dependency boundaries",
    )

    artifact = generate_repair_prompt(diagnosis, emitted_at="2026-04-05T00:00:00Z")

    assert artifact["trace"]["template_id"] == "dependency_graph_violation"
    assert any("dependency" in step.lower() for step in artifact["step_by_step_actions"])


def test_unknown_failure_generates_triage_prompt() -> None:
    diagnosis = _diagnosis_for(
        "unknown_failure",
        fix_class="manual_triage_required",
        repair_area="manual diagnosis queue",
    )

    artifact = generate_repair_prompt(diagnosis, emitted_at="2026-04-05T00:00:00Z")

    assert artifact["trace"]["template_id"] == "unknown_failure"
    assert "triage" in artifact["repair_intent"].lower()


def test_deterministic_for_same_input() -> None:
    diagnosis = _diagnosis_for(
        "contract_registration_missing",
        fix_class="align_contract_registration",
        repair_area="contracts/standards-manifest.json",
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
        "schema_mismatch",
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
    assert entry["schema_version"] == "1.1.0"


@pytest.mark.parametrize("root_cause", _ALL_ROOT_CAUSES)
def test_all_legal_root_causes_have_deterministic_generation(root_cause: str) -> None:
    diagnosis = _diagnosis_for(
        root_cause,
        fix_class=f"deterministic_fix_for_{root_cause}",
        repair_area=f"governed repair area for {root_cause}",
    )

    first = generate_repair_prompt(copy.deepcopy(diagnosis), emitted_at="2026-04-05T00:00:00Z")
    second = generate_repair_prompt(copy.deepcopy(diagnosis), emitted_at="2026-04-05T00:00:00Z")

    assert first == second
    assert first["trace"]["template_id"] == root_cause
    assert first["repair_prompt_text"]
    assert first["validation_commands"]
