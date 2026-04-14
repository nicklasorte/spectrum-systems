from __future__ import annotations

import json
from pathlib import Path

from spectrum_systems.modules.runtime.pytest_selection_integrity import evaluate_pytest_selection_integrity


def _policy_path(tmp_path: Path, *, threshold: int = 1, allow_equivalence: bool = False) -> Path:
    policy = {
        "artifact_type": "pytest_pr_selection_integrity_policy",
        "schema_version": "1.0.0",
        "policy_version": "1.0.0",
        "minimum_selection_threshold": threshold,
        "allow_bounded_equivalence": allow_equivalence,
        "governed_surface_prefixes": ["scripts/", "spectrum_systems/", "contracts/", "tests/"],
        "surface_rules": [
            {
                "path_prefix": "scripts/run_contract_preflight.py",
                "required_test_targets": ["tests/test_contract_preflight.py"],
            }
        ],
        "bounded_equivalence": [
            {
                "required_target": "tests/test_contract_preflight.py",
                "equivalent_targets": ["tests/test_run_github_pr_autofix_contract_preflight.py"],
            }
        ],
        "allowed_exceptions": [],
    }
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(policy), encoding="utf-8")
    return path


def test_blocks_with_empty_selection(tmp_path: Path) -> None:
    result = evaluate_pytest_selection_integrity(
        changed_paths=["scripts/run_contract_preflight.py"],
        selected_test_targets=[],
        required_test_targets=["tests/test_contract_preflight.py"],
        pytest_execution_record={"executed": True, "selection_reason_codes": []},
        policy_path=_policy_path(tmp_path),
        generated_at="2026-04-14T00:00:00Z",
    )
    assert result.decision == "BLOCK"
    assert "PYTEST_SELECTION_EMPTY" in result.blocking_reasons


def test_blocks_when_required_targets_missing(tmp_path: Path) -> None:
    result = evaluate_pytest_selection_integrity(
        changed_paths=["scripts/run_contract_preflight.py"],
        selected_test_targets=["tests/test_other.py"],
        required_test_targets=["tests/test_contract_preflight.py"],
        pytest_execution_record={"executed": True, "selection_reason_codes": []},
        policy_path=_policy_path(tmp_path),
        generated_at="2026-04-14T00:00:00Z",
    )
    assert result.decision == "BLOCK"
    assert "PYTEST_SELECTION_MISMATCH" in result.blocking_reasons


def test_blocks_when_threshold_not_met(tmp_path: Path) -> None:
    result = evaluate_pytest_selection_integrity(
        changed_paths=["scripts/run_contract_preflight.py"],
        selected_test_targets=["tests/test_contract_preflight.py"],
        required_test_targets=["tests/test_contract_preflight.py"],
        pytest_execution_record={"executed": True, "selection_reason_codes": []},
        policy_path=_policy_path(tmp_path, threshold=2),
        generated_at="2026-04-14T00:00:00Z",
    )
    assert result.decision == "BLOCK"
    assert "PYTEST_SELECTION_THRESHOLD_NOT_MET" in result.blocking_reasons


def test_allows_bounded_equivalence_when_enabled(tmp_path: Path) -> None:
    result = evaluate_pytest_selection_integrity(
        changed_paths=["scripts/run_contract_preflight.py"],
        selected_test_targets=["tests/test_run_github_pr_autofix_contract_preflight.py"],
        required_test_targets=["tests/test_contract_preflight.py"],
        pytest_execution_record={"executed": True, "selection_reason_codes": []},
        policy_path=_policy_path(tmp_path, allow_equivalence=True),
        generated_at="2026-04-14T00:00:00Z",
    )
    assert result.decision == "ALLOW"
    assert result.blocking_reasons == []


def test_payload_includes_provenance_binding_fields(tmp_path: Path) -> None:
    result = evaluate_pytest_selection_integrity(
        changed_paths=["scripts/run_contract_preflight.py"],
        selected_test_targets=["tests/test_contract_preflight.py"],
        required_test_targets=["tests/test_contract_preflight.py"],
        pytest_execution_record={"executed": True, "selection_reason_codes": []},
        policy_path=_policy_path(tmp_path),
        generated_at="2026-04-14T00:00:00Z",
        provenance={
            "source_commit_sha": "abc123",
            "source_head_ref": "refs/pull/1/head",
            "workflow_run_id": "123",
            "producer_script": "scripts/run_contract_preflight.py",
            "produced_at": "2026-04-14T00:00:00Z",
            "source_pytest_execution_record_ref": "outputs/contract_preflight/pytest_execution_record.json",
            "source_pytest_execution_record_hash": "a" * 64,
            "artifact_hash": "b" * 64,
        },
    )
    assert result.payload["schema_version"] == "1.1.0"
    assert result.payload["source_pytest_execution_record_ref"] == "outputs/contract_preflight/pytest_execution_record.json"
    assert result.payload["artifact_hash"] == "b" * 64
