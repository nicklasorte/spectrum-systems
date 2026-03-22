from __future__ import annotations

import pytest

from spectrum_systems.modules.evaluation.eval_dataset_registry import (
    EvalDatasetRegistryError,
    build_eval_dataset,
    build_registry_snapshot,
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
        "admission_policy_id": "policy-bbc-core",
        "canonicalization_policy_id": "canon-bbc-v1",
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


def _canonicalization_policy() -> dict:
    return {
        "artifact_type": "eval_canonicalization_policy",
        "schema_version": "1.0.0",
        "policy_id": "canon-bbc-v1",
        "policy_version": "1.0.0",
        "policy_name": "BBC Canonicalization Policy v1",
        "status": "active",
        "applies_to_artifact_types": ["eval_case", "failure_eval_case"],
        "canonical_member_identity_fields": [
            "artifact_type",
            "artifact_id",
            "artifact_version",
        ],
        "canonical_ordering_fields": [
            "artifact_type",
            "artifact_id",
            "artifact_version",
            "source",
            "provenance_ref",
        ],
        "canonicalization_strategy": "sort_then_evaluate",
        "duplicate_selection_rule": "first_member_wins",
        "created_at": "2026-03-22T00:00:00Z",
        "created_by": "test-suite",
    }


def test_valid_dataset_creation() -> None:
    dataset = build_eval_dataset(_dataset(), _policy(), _canonicalization_policy())
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


def test_policy_rejection_of_manual_failure_cases() -> None:
    policy = _policy()
    policy["allow_manual_cases"] = False
    member = {
        "artifact_type": "failure_eval_case",
        "artifact_id": "fail-manual",
        "artifact_version": "1.0.0",
        "source": "manual",
        "provenance_ref": "trace://fail-manual",
    }
    result = evaluate_dataset_membership(member, policy, seen_keys=set())
    assert result["admission_status"] == "rejected"
    assert result["admission_reason_code"] == "retired_source"


def test_deterministic_summary_counts() -> None:
    dataset = build_eval_dataset(_dataset(), _policy(), _canonicalization_policy())
    assert dataset["summary"] == {
        "total_members": 2,
        "admitted_members": 2,
        "rejected_members": 0,
        "contains_failure_generated_cases": True,
    }


def test_duplicate_resolution_is_permutation_invariant() -> None:
    members = [
        {
            "artifact_type": "eval_case",
            "artifact_id": "dup-1",
            "artifact_version": "1.0.0",
            "source": "manual",
            "provenance_ref": "trace://z-manual",
        },
        {
            "artifact_type": "eval_case",
            "artifact_id": "dup-1",
            "artifact_version": "1.0.0",
            "source": "imported",
            "provenance_ref": "trace://a-imported",
        },
        {
            "artifact_type": "failure_eval_case",
            "artifact_id": "fail-1",
            "artifact_version": "1.0.0",
            "source": "generated_failure",
            "provenance_ref": "trace://fail-1",
        },
    ]
    dataset_a = _dataset()
    dataset_b = _dataset()
    dataset_a["members"] = members
    dataset_b["members"] = list(reversed(members))

    built_a = build_eval_dataset(dataset_a, _policy(), _canonicalization_policy())
    built_b = build_eval_dataset(dataset_b, _policy(), _canonicalization_policy())

    assert built_a["summary"] == built_b["summary"]
    assert built_a["members"] == built_b["members"]


def test_contains_failure_generated_cases_tracks_admitted_generated_source() -> None:
    dataset = _dataset()
    dataset["members"] = [
        {
            "artifact_type": "failure_eval_case",
            "artifact_id": "fail-imported",
            "artifact_version": "1.0.0",
            "source": "imported",
            "provenance_ref": "trace://fail-imported",
        }
    ]
    built = build_eval_dataset(dataset, _policy(), _canonicalization_policy())
    assert built["summary"]["contains_failure_generated_cases"] is False


def test_contains_failure_generated_cases_excludes_rejected_generated_source() -> None:
    dataset = _dataset()
    dataset["members"] = [
        {
            "artifact_type": "eval_case",
            "artifact_id": "eval-allowed",
            "artifact_version": "1.0.0",
            "source": "manual",
            "provenance_ref": "trace://eval-allowed",
        },
        {
            "artifact_type": "failure_eval_case",
            "artifact_id": "fail-generated",
            "artifact_version": "1.0.0",
            "source": "generated_failure",
            "provenance_ref": "trace://fail-generated",
        },
    ]
    policy = _policy()
    policy["allow_failure_generated_cases"] = False
    built = build_eval_dataset(dataset, policy, _canonicalization_policy())
    assert built["summary"]["contains_failure_generated_cases"] is False


def test_missing_canonicalization_policy_id_hard_fails() -> None:
    dataset = _dataset()
    dataset.pop("canonicalization_policy_id")
    with pytest.raises(EvalDatasetRegistryError, match="canonicalization_policy_id"):
        build_eval_dataset(dataset, _policy(), _canonicalization_policy())


def test_unknown_canonicalization_policy_id_hard_fails() -> None:
    dataset = _dataset()
    dataset["canonicalization_policy_id"] = "canon-unknown"
    with pytest.raises(EvalDatasetRegistryError, match="canonicalization_policy_id mismatch"):
        build_eval_dataset(dataset, _policy(), _canonicalization_policy())


def test_canonicalization_v1_locks_field_order_and_tie_break_behavior() -> None:
    dataset = _dataset()
    dataset["members"] = [
        {
            "artifact_type": "eval_case",
            "artifact_id": "dup-1",
            "artifact_version": "1.0.0",
            "source": "manual",
            "provenance_ref": "trace://z-manual",
        },
        {
            "artifact_type": "eval_case",
            "artifact_id": "dup-1",
            "artifact_version": "1.0.0",
            "source": "imported",
            "provenance_ref": "trace://a-imported",
        },
    ]
    built = build_eval_dataset(dataset, _policy(), _canonicalization_policy())
    assert built["members"][0]["source"] == "imported"
    assert built["members"][0]["admission_status"] == "admitted"
    assert built["members"][1]["source"] == "manual"
    assert built["members"][1]["admission_status"] == "rejected"
    assert built["canonicalization_policy_id"] == "canon-bbc-v1"


def test_membership_rejects_unsupported_source_at_admission_boundary() -> None:
    member = {
        "artifact_type": "eval_case",
        "artifact_id": "eval-malformed",
        "artifact_version": "1.0.0",
        "source": "unknown_source",
        "provenance_ref": "trace://eval-malformed",
    }
    result = evaluate_dataset_membership(member, _policy(), seen_keys=set())
    assert result["admission_status"] == "rejected"
    assert result["admission_reason_code"] == "invalid_contract"


def test_snapshot_rejects_active_policy_mismatch() -> None:
    dataset = build_eval_dataset(_dataset(), _policy(), _canonicalization_policy())
    with pytest.raises(EvalDatasetRegistryError, match="active_policy_id mismatch"):
        build_registry_snapshot(
            snapshot_id="snapshot-1",
            trace_id="trace-1",
            run_id="run-1",
            active_policy_id="policy-other",
            active_canonicalization_policy_id="canon-bbc-v1",
            datasets=[dataset],
        )


def test_snapshot_rejects_mixed_canonicalization_policy_ids() -> None:
    dataset_a = build_eval_dataset(_dataset(), _policy(), _canonicalization_policy())
    dataset_b = dict(dataset_a)
    dataset_b["dataset_id"] = "dataset-2"
    dataset_b["canonicalization_policy_id"] = "canon-bbc-v2"
    with pytest.raises(
        EvalDatasetRegistryError,
        match="active_canonicalization_policy_id mismatch",
    ):
        build_registry_snapshot(
            snapshot_id="snapshot-2",
            trace_id="trace-2",
            run_id="run-2",
            active_policy_id="policy-bbc-core",
            active_canonicalization_policy_id="canon-bbc-v1",
            datasets=[dataset_a, dataset_b],
        )


def test_snapshot_includes_canonicalization_policy_provenance() -> None:
    dataset = build_eval_dataset(_dataset(), _policy(), _canonicalization_policy())
    snapshot = build_registry_snapshot(
        snapshot_id="snapshot-3",
        trace_id="trace-3",
        run_id="run-3",
        active_policy_id="policy-bbc-core",
        active_canonicalization_policy_id="canon-bbc-v1",
        datasets=[dataset],
    )
    assert snapshot["active_canonicalization_policy_id"] == "canon-bbc-v1"
    assert snapshot["datasets"][0]["canonicalization_policy_id"] == "canon-bbc-v1"


def test_fail_closed_on_malformed_input() -> None:
    malformed = _dataset()
    malformed["members"] = []
    with pytest.raises(EvalDatasetRegistryError):
        build_eval_dataset(malformed, _policy(), _canonicalization_policy())
