"""Fail-closed repo-write admission + lineage guard seam shared by TLC and PQX."""

from __future__ import annotations

from typing import Any

from spectrum_systems.contracts import validate_artifact


class RepoWriteLineageGuardError(ValueError):
    """Raised when repo-write lineage requirements are missing or invalid."""


def _require_non_empty_string(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RepoWriteLineageGuardError(f"repo_write_lineage_rejected:{field}_required")
    return value.strip()


def validate_repo_write_lineage(
    *,
    build_admission_record: Any,
    normalized_execution_request: Any,
    tlc_handoff_record: Any,
    expected_trace_id: str | None = None,
) -> dict[str, str]:
    """Validate strict AEX->TLC lineage requirements for repo-write execution."""

    if not isinstance(build_admission_record, dict):
        raise RepoWriteLineageGuardError("repo_write_lineage_rejected:build_admission_record_required")
    if not isinstance(normalized_execution_request, dict):
        raise RepoWriteLineageGuardError("repo_write_lineage_rejected:normalized_execution_request_required")
    if not isinstance(tlc_handoff_record, dict):
        raise RepoWriteLineageGuardError("repo_write_lineage_rejected:tlc_handoff_record_required")

    validate_artifact(build_admission_record, "build_admission_record")
    validate_artifact(normalized_execution_request, "normalized_execution_request")
    validate_artifact(tlc_handoff_record, "tlc_handoff_record")

    admission_status = _require_non_empty_string(build_admission_record.get("admission_status"), field="admission_status")
    if admission_status != "accepted":
        raise RepoWriteLineageGuardError("repo_write_lineage_rejected:admission_not_accepted")

    admission_execution_type = _require_non_empty_string(
        build_admission_record.get("execution_type"), field="build_admission_record.execution_type"
    )
    if admission_execution_type != "repo_write":
        raise RepoWriteLineageGuardError("repo_write_lineage_rejected:admission_execution_type_not_repo_write")

    normalized_execution_type = _require_non_empty_string(
        normalized_execution_request.get("execution_type"), field="normalized_execution_request.execution_type"
    )
    if normalized_execution_type != "repo_write":
        raise RepoWriteLineageGuardError("repo_write_lineage_rejected:normalized_execution_type_not_repo_write")

    if not bool(normalized_execution_request.get("repo_mutation_requested")):
        raise RepoWriteLineageGuardError("repo_write_lineage_rejected:repo_mutation_requested_false")

    admission_trace_id = _require_non_empty_string(build_admission_record.get("trace_id"), field="build_admission_record.trace_id")
    normalized_trace_id = _require_non_empty_string(
        normalized_execution_request.get("trace_id"), field="normalized_execution_request.trace_id"
    )
    if admission_trace_id != normalized_trace_id:
        raise RepoWriteLineageGuardError("repo_write_lineage_rejected:trace_id_mismatch")
    if expected_trace_id and expected_trace_id != admission_trace_id:
        raise RepoWriteLineageGuardError("repo_write_lineage_rejected:trace_id_not_continuous")

    request_id = _require_non_empty_string(normalized_execution_request.get("request_id"), field="request_id")
    if _require_non_empty_string(build_admission_record.get("request_id"), field="build_admission_record.request_id") != request_id:
        raise RepoWriteLineageGuardError("repo_write_lineage_rejected:request_id_mismatch")

    normalized_ref = _require_non_empty_string(
        build_admission_record.get("normalized_execution_request_ref"), field="normalized_execution_request_ref"
    )
    expected_normalized_ref = f"normalized_execution_request:{request_id}"
    if normalized_ref != expected_normalized_ref:
        raise RepoWriteLineageGuardError("repo_write_lineage_rejected:normalized_request_ref_unresolvable")

    handoff_status = _require_non_empty_string(tlc_handoff_record.get("handoff_status"), field="tlc_handoff_record.handoff_status")
    if handoff_status != "accepted":
        raise RepoWriteLineageGuardError("repo_write_lineage_rejected:handoff_not_accepted")
    handoff_trace_id = _require_non_empty_string(tlc_handoff_record.get("trace_id"), field="tlc_handoff_record.trace_id")
    handoff_request_id = _require_non_empty_string(tlc_handoff_record.get("request_id"), field="tlc_handoff_record.request_id")
    handoff_admission_id = _require_non_empty_string(
        tlc_handoff_record.get("build_admission_record_ref"), field="tlc_handoff_record.build_admission_record_ref"
    )
    handoff_normalized_ref = _require_non_empty_string(
        tlc_handoff_record.get("normalized_execution_request_ref"),
        field="tlc_handoff_record.normalized_execution_request_ref",
    )
    if handoff_trace_id != admission_trace_id:
        raise RepoWriteLineageGuardError("repo_write_lineage_rejected:handoff_trace_id_mismatch")
    if handoff_request_id != request_id:
        raise RepoWriteLineageGuardError("repo_write_lineage_rejected:handoff_request_id_mismatch")
    if handoff_admission_id != f"build_admission_record:{build_admission_record['admission_id']}":
        raise RepoWriteLineageGuardError("repo_write_lineage_rejected:handoff_admission_ref_mismatch")
    if handoff_normalized_ref != expected_normalized_ref:
        raise RepoWriteLineageGuardError("repo_write_lineage_rejected:handoff_normalized_ref_mismatch")

    _require_non_empty_string(build_admission_record.get("produced_by"), field="build_admission_record.produced_by")
    _require_non_empty_string(normalized_execution_request.get("produced_by"), field="normalized_execution_request.produced_by")

    return {
        "trace_id": admission_trace_id,
        "request_id": request_id,
        "admission_id": str(build_admission_record["admission_id"]),
        "normalized_execution_request_ref": expected_normalized_ref,
    }
