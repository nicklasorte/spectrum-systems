"""Adapter for live PQX handoff and execution report write-back."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema, validate_artifact
from spectrum_systems.modules.runtime.repo_write_lineage_guard import (
    RepoWriteLineageGuardError,
    validate_repo_write_lineage,
)
from spectrum_systems.modules.runtime.pqx_slice_runner import run_pqx_slice


class PQXHandoffError(ValueError):
    """Raised when PQX handoff inputs/outputs are invalid."""


def _load_json(path: str | Path) -> Dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise PQXHandoffError(f"expected object artifact: {path}")
    return payload


def _validate_request(payload: Dict[str, Any]) -> None:
    required = ("step_id", "roadmap_path", "state_path", "runs_root", "pqx_output_text")
    missing = [key for key in required if not isinstance(payload.get(key), str) or not payload.get(key).strip()]
    if missing:
        raise PQXHandoffError(f"pqx handoff request missing fields: {', '.join(missing)}")


def _validate_pqx_result_payload(payload: Dict[str, Any]) -> None:
    schema = load_schema("pqx_execution_result")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(payload), key=lambda err: str(list(err.absolute_path)))
    if errors:
        detail = "; ".join(error.message for error in errors)
        raise PQXHandoffError(f"pqx execution result failed schema validation: {detail}")


def _is_repo_mutation_requested(request: Dict[str, Any]) -> bool:
    if isinstance(request.get("repo_mutation_requested"), bool):
        return bool(request["repo_mutation_requested"])
    admission = request.get("build_admission_record")
    if isinstance(admission, dict):
        return str(admission.get("execution_type") or "") == "repo_write"
    normalized = request.get("normalized_execution_request")
    if isinstance(normalized, dict):
        return bool(normalized.get("repo_mutation_requested"))
    raise PQXHandoffError("repo_mutation_intent_unknown: explicit declaration required")


def _require_repo_write_admission_lineage(*, cycle_id: str, request: Dict[str, Any]) -> None:
    if not _is_repo_mutation_requested(request):
        return

    admission = request.get("build_admission_record")
    normalized = request.get("normalized_execution_request")
    tlc_handoff_record = request.get("tlc_handoff_record")
    expected_trace_id = request.get("trace_id")
    expected_trace = expected_trace_id if isinstance(expected_trace_id, str) and expected_trace_id else None
    try:
        validate_repo_write_lineage(
            build_admission_record=admission,
            normalized_execution_request=normalized,
            tlc_handoff_record=tlc_handoff_record,
            expected_trace_id=expected_trace,
        )
    except (RepoWriteLineageGuardError, Exception) as exc:
        raise PQXHandoffError(
            f"repo-write handoff rejected for cycle_id={cycle_id}: missing or invalid AEX admission lineage ({exc})"
        ) from exc


def handoff_to_pqx(*, cycle_id: str, request_path: str | Path, reports_root: Path) -> Dict[str, Any]:
    """Execute canonical PQX seam and emit validated execution_report_artifact payload/path."""

    request = _load_json(request_path)
    _validate_request(request)
    _require_repo_write_admission_lineage(cycle_id=cycle_id, request=request)

    result = run_pqx_slice(
        step_id=request["step_id"],
        roadmap_path=Path(request["roadmap_path"]),
        state_path=Path(request["state_path"]),
        runs_root=Path(request["runs_root"]),
        pqx_output_text=request["pqx_output_text"],
        contract_preflight_result_artifact_path=(
            Path(request["contract_preflight_result_artifact_path"])
            if isinstance(request.get("contract_preflight_result_artifact_path"), str)
            and request.get("contract_preflight_result_artifact_path", "").strip()
            else None
        ),
    )

    if result.get("status") != "complete":
        reason = result.get("reason", "pqx execution returned non-complete status")
        raise PQXHandoffError(f"pqx execution failed closed: {reason}")

    result_path = result.get("result")
    if not isinstance(result_path, str) or not Path(result_path).is_file():
        raise PQXHandoffError("pqx execution missing required result artifact path")

    pqx_result_payload = _load_json(result_path)
    _validate_pqx_result_payload(pqx_result_payload)

    if pqx_result_payload.get("execution_status") != "success":
        raise PQXHandoffError("pqx execution result reported failure status")

    produced_artifacts = []
    for key in (
        "request",
        "result",
        "slice_execution_record",
        "done_certification_record",
        "pqx_slice_audit_bundle",
    ):
        path_value = result.get(key)
        if isinstance(path_value, str) and Path(path_value).is_file():
            produced_artifacts.append(path_value)

    report_payload = {
        "artifact_id": f"execution-report-{cycle_id}-{result.get('run_id', 'missing-run')}",
        "artifact_type": "execution_report_artifact",
        "schema_version": "1.0.0",
        "cycle_id": cycle_id,
        "execution_mode": "pqx_live",
        "execution_status": "succeeded",
        "produced_artifacts": produced_artifacts,
        "started_at": pqx_result_payload["started_at"],
        "completed_at": pqx_result_payload["completed_at"],
        "notes": f"PQX handoff step_id={request['step_id']} run_id={result.get('run_id', 'unknown')}",
    }
    validate_artifact(report_payload, "execution_report_artifact")

    run_id = result.get("run_id", "unknown")
    report_path = reports_root / f"execution_report_{run_id}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report_payload, indent=2) + "\n", encoding="utf-8")

    return {
        "report_path": str(report_path),
        "report_payload": report_payload,
        "pqx_result": result,
        "pqx_result_payload": pqx_result_payload,
    }
