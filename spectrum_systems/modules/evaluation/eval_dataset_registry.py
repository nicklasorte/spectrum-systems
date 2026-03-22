"""Deterministic eval dataset registry helpers for BBC governance."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema


class EvalDatasetRegistryError(Exception):
    """Raised when eval dataset membership or summary validation fails."""


class EvalAdmissionPolicyError(Exception):
    """Raised when eval admission policy artifacts are malformed."""


def _validate(instance: dict[str, Any], schema_name: str) -> None:
    schema = load_schema(schema_name)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(instance)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def evaluate_dataset_membership(
    member: dict[str, Any],
    policy: dict[str, Any],
    seen_keys: set[str] | None = None,
) -> dict[str, Any]:
    """Deterministically classify one member under the supplied policy."""
    try:
        _validate(policy, "eval_admission_policy")
    except Exception as exc:  # pragma: no cover - defensive fail-closed boundary
        raise EvalAdmissionPolicyError("Invalid eval admission policy") from exc

    required_member_fields = {
        "artifact_type",
        "artifact_id",
        "artifact_version",
        "source",
        "provenance_ref",
    }
    missing = sorted(field for field in required_member_fields if field not in member)
    if missing:
        raise EvalDatasetRegistryError(f"Member missing required fields: {missing}")

    artifact_type = str(member["artifact_type"])
    source = str(member["source"])
    provenance_ref = str(member["provenance_ref"])
    key = f"{artifact_type}:{member['artifact_id']}:{member['artifact_version']}"
    allowed_sources = {"manual", "generated_failure", "imported"}

    status = "admitted"
    reason = "meets_policy"

    if source not in allowed_sources:
        status = "rejected"
        reason = "invalid_contract"
    elif artifact_type not in set(policy["applies_to_artifact_types"]):
        status = "rejected"
        reason = "invalid_contract"
    elif policy["require_provenance"] and not provenance_ref.strip():
        status = "rejected"
        reason = "missing_provenance"
    elif source == "generated_failure" and not policy["allow_failure_generated_cases"]:
        status = "rejected"
        reason = "retired_source"
    elif source == "manual" and not policy["allow_manual_cases"]:
        status = "rejected"
        reason = "retired_source"
    elif seen_keys is not None and key in seen_keys and policy["duplicate_handling"] == "reject":
        status = "rejected"
        reason = "duplicate"

    result = {
        "artifact_type": artifact_type,
        "artifact_id": str(member["artifact_id"]),
        "artifact_version": str(member["artifact_version"]),
        "source": source,
        "admission_status": status,
        "admission_reason_code": reason,
        "provenance_ref": provenance_ref,
    }

    if seen_keys is not None:
        seen_keys.add(key)

    return result


def build_eval_dataset(dataset: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    """Build a fully evaluated eval_dataset artifact and validate fail-closed."""
    try:
        _validate(policy, "eval_admission_policy")
    except Exception as exc:
        raise EvalAdmissionPolicyError("Invalid eval admission policy") from exc

    if not isinstance(dataset, dict):
        raise EvalDatasetRegistryError("dataset must be a dict")

    for field in (
        "dataset_id",
        "dataset_version",
        "dataset_name",
        "status",
        "intended_use",
        "created_by",
        "provenance",
        "members",
    ):
        if field not in dataset:
            raise EvalDatasetRegistryError(f"dataset missing required field: {field}")

    members = dataset.get("members")
    if not isinstance(members, list) or not members:
        raise EvalDatasetRegistryError("dataset members must be a non-empty list")

    # Canonicalize members before duplicate evaluation so duplicate outcomes are
    # permutation-invariant for the same logical member set. Duplicate identity
    # fields are (artifact_type, artifact_id, artifact_version), and we use
    # source + provenance_ref as explicit deterministic tie-breakers for members
    # that share the duplicate key.
    canonical_members = sorted(
        members,
        key=lambda member: (
            str(member.get("artifact_type", "")),
            str(member.get("artifact_id", "")),
            str(member.get("artifact_version", "")),
            str(member.get("source", "")),
            str(member.get("provenance_ref", "")),
        ),
    )

    seen_keys: set[str] = set()
    evaluated_members = [
        evaluate_dataset_membership(member, policy, seen_keys=seen_keys)
        for member in canonical_members
    ]

    admitted = sum(1 for m in evaluated_members if m["admission_status"] == "admitted")
    rejected = len(evaluated_members) - admitted
    # This field tracks admitted generated-failure provenance, not artifact type.
    contains_failure = any(
        m["admission_status"] == "admitted" and m["source"] == "generated_failure"
        for m in evaluated_members
    )

    artifact = {
        "artifact_type": "eval_dataset",
        "schema_version": "1.0.0",
        "dataset_id": str(dataset["dataset_id"]),
        "dataset_version": str(dataset["dataset_version"]),
        "dataset_name": str(dataset["dataset_name"]),
        "status": str(dataset["status"]),
        "intended_use": str(dataset["intended_use"]),
        "admission_policy_id": str(policy["policy_id"]),
        "created_at": str(dataset.get("created_at") or _now_iso()),
        "created_by": str(dataset["created_by"]),
        "provenance": dict(dataset["provenance"]),
        "members": evaluated_members,
        "summary": {
            "total_members": len(evaluated_members),
            "admitted_members": admitted,
            "rejected_members": rejected,
            "contains_failure_generated_cases": contains_failure,
        },
    }

    summary = artifact["summary"]
    if summary["admitted_members"] + summary["rejected_members"] != summary["total_members"]:
        raise EvalDatasetRegistryError("dataset summary counts do not add up")

    minimum_required = int(policy["thresholds"]["minimum_admitted_members"])
    if artifact["status"] == "approved" and summary["admitted_members"] < 1:
        raise EvalDatasetRegistryError("approved dataset must include at least one admitted member")
    if summary["admitted_members"] < minimum_required:
        raise EvalDatasetRegistryError(
            "dataset admitted members below policy threshold: "
            f"required>={minimum_required}, found={summary['admitted_members']}"
        )

    rejected_ratio = summary["rejected_members"] / summary["total_members"]
    if rejected_ratio > float(policy["thresholds"]["maximum_rejected_ratio"]):
        raise EvalDatasetRegistryError("dataset rejected ratio exceeds policy threshold")

    for member in artifact["members"]:
        if member["admission_status"] == "admitted" and member["admission_reason_code"] != "meets_policy":
            raise EvalDatasetRegistryError("admitted member has rejection reason code")

    try:
        _validate(artifact, "eval_dataset")
    except Exception as exc:
        raise EvalDatasetRegistryError("generated eval_dataset failed contract validation") from exc

    return artifact


def build_registry_snapshot(
    *,
    snapshot_id: str,
    trace_id: str,
    run_id: str,
    active_policy_id: str,
    datasets: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a deterministic registry snapshot over supplied dataset artifacts."""
    if not datasets:
        raise EvalDatasetRegistryError("datasets must be a non-empty list")

    dataset_entries = []
    for dataset in datasets:
        try:
            _validate(dataset, "eval_dataset")
        except Exception as exc:
            raise EvalDatasetRegistryError("registry snapshot received invalid dataset") from exc

        summary = dataset["summary"]
        dataset_policy_id = str(dataset["admission_policy_id"])
        if dataset_policy_id != active_policy_id:
            raise EvalDatasetRegistryError(
                "registry snapshot active_policy_id mismatch: "
                f"dataset {dataset['dataset_id']} uses {dataset_policy_id}, "
                f"snapshot requested {active_policy_id}"
            )
        approved_for_use = dataset["status"] == "approved" and summary["admitted_members"] >= 1
        dataset_entries.append(
            {
                "dataset_id": dataset["dataset_id"],
                "dataset_version": dataset["dataset_version"],
                "status": dataset["status"],
                "intended_use": dataset["intended_use"],
                "approved_for_use": approved_for_use,
            }
        )

    snapshot = {
        "artifact_type": "eval_registry_snapshot",
        "schema_version": "1.0.0",
        "snapshot_id": snapshot_id,
        "created_at": _now_iso(),
        "provenance": {
            "trace_id": trace_id,
            "run_id": run_id,
        },
        "active_policy_id": active_policy_id,
        "datasets": dataset_entries,
    }

    try:
        _validate(snapshot, "eval_registry_snapshot")
    except Exception as exc:
        raise EvalDatasetRegistryError("generated eval_registry_snapshot failed contract validation") from exc

    return snapshot
