from __future__ import annotations

import pytest

from spectrum_systems.modules.evaluation.eval_dataset_registry import (
    EvalDatasetRegistryError,
    build_eval_dataset,
    evaluate_dataset_membership,
)


def _policy() -> dict:
    return {
        "artifact_type": "eval_admission_policy",
        "schema_version": "1.0.0",
        "policy_id": "policy-bbc-core",
        "policy_version": "1.0.0",
        "policy_name": "BBC Core",
        "status": "active",
        "applies_to_artifact_types": ["eval_case", "failure_eval_case"],
        "require_provenance": True,
        "allow_failure_generated_cases": True,
        "allow_manual_cases": True,
        "duplicate_handling": "reject",
        "created_at": "2026-03-22T00:00:00Z",
        "created_by": "test-suite",
        "thresholds": {
            "minimum_admitted_members": 1,
            "maximum_rejected_ratio": 0.5,
        },
    }


def _dataset() -> dict:
    return {
        "dataset_id": "dataset-1",
        "dataset_version": "1.0.0",
        "dataset_name": "Dataset One",
        "status": "candidate",
        "intended_use": "development",
        "created_at": "2026-03-22T00:00:00Z",
        "created_by": "test-suite",
        "provenance": {
            "trace_id": "trace-1",
            "run_id": "run-1",
            "source_artifact_ids": ["eval-1", "fail-1"],
        },
        "members": [
            {
                "artifact_type": "eval_case",
                "artifact_id": "eval-1",
                "artifact_version": "1.0.0",
                "source": "manual",
                "provenance_ref": "trace://eval-1",
            },
            {
                "artifact_type": "failure_eval_case",
                "artifact_id": "fail-1",
                "artifact_version": "1.0.0",
                "source": "generated_failure",
                "provenance_ref": "trace://fail-1",
            },
        ],
    }


def test_valid_dataset_creation() -> None:
    dataset = build_eval_dataset(_dataset(), _policy())
    assert dataset["artifact_type"] == "eval_dataset"
    assert dataset["summary"]["admitted_members"] == 2
    assert dataset["summary"]["rejected_members"] == 0


def test_member_rejection_for_missing_provenance() -> None:
    policy = _policy()
    member = {
        "artifact_type": "eval_case",
        "artifact_id": "eval-1",
        "artifact_version": "1.0.0",
        "source": "manual",
        "provenance_ref": "",
    }
    result = evaluate_dataset_membership(member, policy, seen_keys=set())
    assert result["admission_status"] == "rejected"
    assert result["admission_reason_code"] == "missing_provenance"


def test_duplicate_rejection() -> None:
    policy = _policy()
    seen: set[str] = set()
    member = {
        "artifact_type": "eval_case",
        "artifact_id": "eval-dup",
        "artifact_version": "1.0.0",
        "source": "manual",
        "provenance_ref": "trace://eval-dup",
    }
    first = evaluate_dataset_membership(member, policy, seen_keys=seen)
    second = evaluate_dataset_membership(member, policy, seen_keys=seen)
    assert first["admission_status"] == "admitted"
    assert second["admission_status"] == "rejected"
    assert second["admission_reason_code"] == "duplicate"


def test_artifact_type_rejection() -> None:
    member = {
        "artifact_type": "unknown_case",
        "artifact_id": "eval-unknown",
        "artifact_version": "1.0.0",
        "source": "imported",
        "provenance_ref": "trace://unknown",
    }
    result = evaluate_dataset_membership(member, _policy(), seen_keys=set())
    assert result["admission_status"] == "rejected"
    assert result["admission_reason_code"] == "invalid_contract"


def test_policy_rejection_of_failure_generated_cases() -> None:
    policy = _policy()
    policy["allow_failure_generated_cases"] = False
    member = {
        "artifact_type": "failure_eval_case",
        "artifact_id": "fail-disallowed",
        "artifact_version": "1.0.0",
        "source": "generated_failure",
        "provenance_ref": "trace://fail-disallowed",
    }
    result = evaluate_dataset_membership(member, policy, seen_keys=set())
    assert result["admission_status"] == "rejected"
    assert result["admission_reason_code"] == "retired_source"


def test_policy_rejection_of_manual_cases() -> None:
    policy = _policy()
    policy["allow_manual_cases"] = False
    member = {
        "artifact_type": "eval_case",
        "artifact_id": "eval-manual",
        "artifact_version": "1.0.0",
        "source": "manual",
        "provenance_ref": "trace://eval-manual",
    }
    result = evaluate_dataset_membership(member, policy, seen_keys=set())
    assert result["admission_status"] == "rejected"
    assert result["admission_reason_code"] == "retired_source"


def test_deterministic_summary_counts() -> None:
    dataset = build_eval_dataset(_dataset(), _policy())
    assert dataset["summary"] == {
        "total_members": 2,
        "admitted_members": 2,
        "rejected_members": 0,
        "contains_failure_generated_cases": True,
    }


def test_fail_closed_on_malformed_input() -> None:
    malformed = _dataset()
    malformed["members"] = []
    with pytest.raises(EvalDatasetRegistryError):
        build_eval_dataset(malformed, _policy())
