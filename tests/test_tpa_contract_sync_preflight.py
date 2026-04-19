from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from scripts import run_contract_preflight as preflight


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _seed_repo(tmp_path: Path, *, missing_required_in_example: bool = False) -> Path:
    repo = tmp_path
    _write_json(
        repo / "contracts/schemas/generated_eval_registry_change_request_record.schema.json",
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "required": ["artifact_type", "artifact_id", "created_at"],
            "properties": {
                "artifact_type": {"type": "string", "const": "generated_eval_promotion_request_record"},
                "artifact_id": {"type": "string", "minLength": 1},
                "created_at": {"type": "string", "format": "date-time"},
            },
        },
    )
    example_payload = {
        "artifact_type": "generated_eval_promotion_request_record",
        "artifact_id": "EX-1",
        "created_at": "2026-04-19T00:00:00Z",
    }
    if missing_required_in_example:
        example_payload.pop("created_at")
    _write_json(
        repo / "contracts/examples/generated_eval_registry_change_request_record.json",
        example_payload,
    )
    _write_json(
        repo / "contracts/standards-manifest.json",
        {
            "artifact_type": "standards_manifest",
            "artifact_id": "STD-CONTRACTS",
            "artifact_version": "1.0.0",
            "schema_version": "1.0.0",
            "standards_version": "1.0.0",
            "record_id": "REC-1",
            "run_id": "run-1",
            "created_at": "2026-04-19T00:00:00Z",
            "source_repo": "nicklasorte/spectrum-systems",
            "source_repo_version": "1.0.0",
            "contracts": [
                {
                    "artifact_type": "generated_eval_registry_change_request_record",
                    "artifact_class": "coordination",
                    "schema_version": "1.0.0",
                    "status": "stable",
                    "intended_consumers": ["spectrum-systems"],
                    "introduced_in": "1.0.0",
                    "last_updated_in": "1.0.0",
                    "example_path": "contracts/examples/generated_eval_promotion_request_record.json",
                    "notes": "test",
                }
            ],
        },
    )
    return repo


def test_ag07_broken_shape_is_repaired_deterministically(tmp_path: Path) -> None:
    repo = _seed_repo(tmp_path)
    changed = [
        "contracts/schemas/generated_eval_registry_change_request_record.schema.json",
        "contracts/examples/generated_eval_registry_change_request_record.json",
        "contracts/standards-manifest.json",
    ]
    check = preflight.run_tpa_contract_sync_check(repo_root=repo, changed_paths=changed, created_at="2026-04-19T00:00:00Z")
    assert check["auto_repair_eligible"] is True
    repair = preflight.run_tpa_contract_sync_autorepair(repo_root=repo, check_record=check, created_at="2026-04-19T00:00:01Z")

    assert repair["repair_result_record"]["repaired"] is True
    second = preflight.run_tpa_contract_sync_check(repo_root=repo, changed_paths=changed, created_at="2026-04-19T00:00:02Z")
    assert second["mismatches"] == []


def test_mismatch_across_schema_example_manifest_is_caught_early(tmp_path: Path) -> None:
    repo = _seed_repo(tmp_path)
    changed = [
        "contracts/schemas/generated_eval_registry_change_request_record.schema.json",
        "contracts/examples/generated_eval_registry_change_request_record.json",
        "contracts/standards-manifest.json",
    ]
    check = preflight.run_tpa_contract_sync_check(repo_root=repo, changed_paths=changed, created_at="2026-04-19T00:00:00Z")
    kinds = {item["mismatch_type"] for item in check["mismatches"]}
    assert "schema_artifact_type_mismatch" in kinds
    assert "example_artifact_type_mismatch" in kinds
    assert "manifest_example_path_mismatch" in kinds


def test_eligible_mismatch_emits_repair_plan_and_result_records(tmp_path: Path) -> None:
    repo = _seed_repo(tmp_path)
    changed = [
        "contracts/schemas/generated_eval_registry_change_request_record.schema.json",
        "contracts/examples/generated_eval_registry_change_request_record.json",
    ]
    check = preflight.run_tpa_contract_sync_check(repo_root=repo, changed_paths=changed, created_at="2026-04-19T00:00:00Z")
    repair = preflight.run_tpa_contract_sync_autorepair(repo_root=repo, check_record=check, created_at="2026-04-19T00:00:01Z")
    assert repair["repair_plan_record"]["artifact_type"] == "tpa_contract_sync_repair_plan_record"
    assert repair["repair_result_record"]["artifact_type"] == "tpa_contract_sync_repair_result_record"


def test_repaired_shape_passes_validate_examples(tmp_path: Path) -> None:
    repo = _seed_repo(tmp_path)
    changed = [
        "contracts/schemas/generated_eval_registry_change_request_record.schema.json",
        "contracts/examples/generated_eval_registry_change_request_record.json",
        "contracts/standards-manifest.json",
    ]
    check = preflight.run_tpa_contract_sync_check(repo_root=repo, changed_paths=changed, created_at="2026-04-19T00:00:00Z")
    preflight.run_tpa_contract_sync_autorepair(repo_root=repo, check_record=check, created_at="2026-04-19T00:00:01Z")

    schema = json.loads((repo / "contracts/schemas/generated_eval_registry_change_request_record.schema.json").read_text(encoding="utf-8"))
    example = json.loads((repo / "contracts/examples/generated_eval_registry_change_request_record.json").read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(example)


def test_ineligible_mismatch_stays_fail_closed(tmp_path: Path) -> None:
    repo = _seed_repo(tmp_path, missing_required_in_example=True)
    changed = [
        "contracts/schemas/generated_eval_registry_change_request_record.schema.json",
        "contracts/examples/generated_eval_registry_change_request_record.json",
        "contracts/standards-manifest.json",
    ]
    check = preflight.run_tpa_contract_sync_check(repo_root=repo, changed_paths=changed, created_at="2026-04-19T00:00:00Z")
    kinds = {item["mismatch_type"] for item in check["mismatches"]}
    assert "example_missing_non_derivable_required_fields" in kinds
    assert check["auto_repair_eligible"] is False


def test_tpa_autorepair_does_not_mutate_unrelated_artifacts(tmp_path: Path) -> None:
    repo = _seed_repo(tmp_path)
    unrelated = repo / "contracts/examples/unrelated_artifact.json"
    _write_json(unrelated, {"artifact_type": "unrelated_artifact", "value": 1})
    before = unrelated.read_text(encoding="utf-8")

    changed = [
        "contracts/schemas/generated_eval_registry_change_request_record.schema.json",
        "contracts/examples/generated_eval_registry_change_request_record.json",
        "contracts/standards-manifest.json",
    ]
    check = preflight.run_tpa_contract_sync_check(repo_root=repo, changed_paths=changed, created_at="2026-04-19T00:00:00Z")
    preflight.run_tpa_contract_sync_autorepair(repo_root=repo, check_record=check, created_at="2026-04-19T00:00:01Z")

    assert unrelated.read_text(encoding="utf-8") == before


def test_tpa_repair_output_is_deterministic(tmp_path: Path) -> None:
    repo = _seed_repo(tmp_path)
    changed = [
        "contracts/schemas/generated_eval_registry_change_request_record.schema.json",
        "contracts/examples/generated_eval_registry_change_request_record.json",
        "contracts/standards-manifest.json",
    ]
    check = preflight.run_tpa_contract_sync_check(repo_root=repo, changed_paths=changed, created_at="2026-04-19T00:00:00Z")
    first = preflight.run_tpa_contract_sync_autorepair(repo_root=repo, check_record=check, created_at="2026-04-19T00:00:01Z")

    repo2 = _seed_repo(tmp_path / "second")
    check2 = preflight.run_tpa_contract_sync_check(repo_root=repo2, changed_paths=changed, created_at="2026-04-19T00:00:00Z")
    second = preflight.run_tpa_contract_sync_autorepair(repo_root=repo2, check_record=check2, created_at="2026-04-19T00:00:01Z")

    assert first["repair_result_record"]["artifact_id"] == second["repair_result_record"]["artifact_id"]


def test_integration_changed_ag07_contracts_through_tpa_and_preflight_validation(tmp_path: Path) -> None:
    repo = _seed_repo(tmp_path)
    changed = [
        "contracts/schemas/generated_eval_registry_change_request_record.schema.json",
        "contracts/examples/generated_eval_registry_change_request_record.json",
        "contracts/standards-manifest.json",
    ]
    check = preflight.run_tpa_contract_sync_check(repo_root=repo, changed_paths=changed, created_at="2026-04-19T00:00:00Z")
    repair = preflight.run_tpa_contract_sync_autorepair(repo_root=repo, check_record=check, created_at="2026-04-19T00:00:01Z")

    schema = json.loads((repo / "contracts/schemas/generated_eval_registry_change_request_record.schema.json").read_text(encoding="utf-8"))
    example = json.loads((repo / "contracts/examples/generated_eval_registry_change_request_record.json").read_text(encoding="utf-8"))
    assert repair["repair_result_record"]["repaired"] is True
    Draft202012Validator(schema).validate(example)
