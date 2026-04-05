"""Governed closed-loop recovery orchestration (BATCH-FRE-03)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Callable

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema
from spectrum_systems.modules.runtime.repair_prompt_generator import generate_repair_prompt


class RecoveryOrchestrationError(ValueError):
    """Raised when recovery orchestration cannot produce a justified result safely."""


RecoveryExecutionRunner = Callable[[dict[str, Any]], dict[str, Any]]
ValidationCommandRunner = Callable[[str], dict[str, Any]]

_ALLOWED_RECOVERY_STATUSES = {"recovered", "partially_recovered", "blocked", "failed"}
_ALLOWED_EXECUTION_STATUSES = {"completed", "failed", "blocked"}
_ALLOWED_VALIDATION_STATUSES = {"passed", "failed", "blocked", "not_run"}
_DEFAULT_BLOCKING_CODES = {
    "invalid_diagnosis_artifact",
    "invalid_repair_prompt_artifact",
    "missing_validation_commands",
    "missing_execution_evidence",
    "invalid_execution_status",
    "missing_validation_evidence",
    "status_not_justified",
    "retry_budget_exhausted",
    "governance_block",
    "execution_error",
    "validation_blocked",
    "missing_governance_gate_evidence",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _canonical_hash(payload: Any) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _validate(instance: dict[str, Any], schema_name: str, *, label: str) -> None:
    validator = Draft202012Validator(load_schema(schema_name), format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda err: list(err.absolute_path))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise RecoveryOrchestrationError(f"{label} failed schema validation ({schema_name}): {details}")


def _normalize_validation_commands(repair_prompt_artifact: dict[str, Any]) -> list[str]:
    commands = repair_prompt_artifact.get("validation_commands")
    if not isinstance(commands, list) or not commands:
        raise RecoveryOrchestrationError("repair prompt artifact must include non-empty validation_commands")

    normalized: list[str] = []
    for raw_command in commands:
        if not isinstance(raw_command, str) or not raw_command.strip():
            raise RecoveryOrchestrationError("validation_commands must only include non-empty strings")
        normalized.append(raw_command.strip())
    return sorted(dict.fromkeys(normalized))


def _run_validation_commands(commands: list[str], validation_runner: ValidationCommandRunner) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for command in commands:
        result = validation_runner(command)
        if not isinstance(result, dict):
            raise RecoveryOrchestrationError("validation runner must return an object result")
        status = result.get("status")
        if status not in _ALLOWED_VALIDATION_STATUSES:
            raise RecoveryOrchestrationError(
                f"validation runner returned unsupported status '{status}' for command '{command}'"
            )
        rows.append(
            {
                "command": command,
                "status": status,
                "artifact_ref": str(result.get("artifact_ref") or "").strip() or None,
                "details": result.get("details") if isinstance(result.get("details"), dict) else {},
            }
        )
    return rows


def _normalize_governance_gate_evidence_refs(execution_result: dict[str, Any]) -> dict[str, str]:
    raw = execution_result.get("governance_gate_evidence_refs")
    if not isinstance(raw, dict):
        raise RecoveryOrchestrationError(
            "execution_result.governance_gate_evidence_refs must be an object with preflight/control/certification evidence"
        )

    preflight = str(raw.get("preflight") or "").strip()
    control = str(raw.get("control") or "").strip()
    certification = str(raw.get("certification") or "").strip()
    certification_applicable = raw.get("certification_applicable")
    if not isinstance(certification_applicable, bool):
        raise RecoveryOrchestrationError(
            "execution_result.governance_gate_evidence_refs.certification_applicable must be a boolean"
        )

    if not preflight:
        raise RecoveryOrchestrationError(
            "execution_result.governance_gate_evidence_refs.preflight must be a non-empty evidence reference"
        )
    if not control:
        raise RecoveryOrchestrationError(
            "execution_result.governance_gate_evidence_refs.control must be a non-empty evidence reference"
        )
    if certification_applicable and not certification:
        raise RecoveryOrchestrationError(
            "execution_result.governance_gate_evidence_refs.certification must be non-empty when certification_applicable=true"
        )

    normalized = {"preflight": preflight, "control": control}
    if certification_applicable:
        normalized["certification"] = certification
    return normalized


def _summarize_validation(results: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {status: 0 for status in sorted(_ALLOWED_VALIDATION_STATUSES)}
    for row in results:
        counts[row["status"]] += 1
    return {
        "total": len(results),
        "passed": counts["passed"],
        "failed": counts["failed"],
        "blocked": counts["blocked"],
        "not_run": counts["not_run"],
    }


def _remaining_failure_classes(
    *,
    diagnosis_artifact: dict[str, Any],
    validation_results: list[dict[str, Any]],
    execution_status: str,
    execution_reason_code: str | None,
) -> list[str]:
    remaining: set[str] = set()
    if execution_status in {"blocked", "failed"}:
        remaining.add(diagnosis_artifact["primary_root_cause"])
    if any(row["status"] in {"failed", "blocked", "not_run"} for row in validation_results):
        remaining.add(diagnosis_artifact["primary_root_cause"])
    if execution_reason_code in {"governance_block", "execution_error"}:
        remaining.add(diagnosis_artifact["primary_root_cause"])
    return sorted(remaining)


def _classify_recovery_status(
    *,
    execution_status: str,
    execution_reason_code: str | None,
    validation_summary: dict[str, Any],
) -> tuple[str, str | None]:
    if execution_status == "blocked":
        reason = execution_reason_code or "governance_block"
        return "blocked", reason

    if execution_status == "failed":
        reason = execution_reason_code or "execution_error"
        return "failed", reason

    if validation_summary["total"] == 0:
        raise RecoveryOrchestrationError("recovery classification requires at least one validation command result")

    if validation_summary["blocked"] > 0:
        return "blocked", "validation_blocked"

    if validation_summary["passed"] == validation_summary["total"] and validation_summary["failed"] == 0:
        return "recovered", None

    if validation_summary["passed"] > 0 and (validation_summary["failed"] + validation_summary["not_run"] > 0):
        return "partially_recovered", None

    if validation_summary["failed"] > 0 or validation_summary["not_run"] > 0:
        return "failed", execution_reason_code or "status_not_justified"

    raise RecoveryOrchestrationError("unable to classify recovery status deterministically")


def _retry_recommended(*, recovery_status: str, attempt_number: int, max_attempts: int) -> bool:
    if recovery_status not in _ALLOWED_RECOVERY_STATUSES:
        raise RecoveryOrchestrationError(f"unsupported recovery status '{recovery_status}'")
    if attempt_number >= max_attempts:
        return False
    return recovery_status in {"failed", "partially_recovered"}


def orchestrate_recovery(
    *,
    diagnosis_artifact: dict[str, Any],
    recovery_attempt_number: int,
    max_attempts: int,
    execution_runner: RecoveryExecutionRunner,
    validation_runner: ValidationCommandRunner,
    repair_prompt_artifact: dict[str, Any] | None = None,
    emitted_at: str | None = None,
    run_id: str = "run-fre-03",
    trace_id: str = "trace-fre-03",
) -> dict[str, Any]:
    """Execute one bounded governed recovery attempt and emit recovery_result_artifact."""
    if recovery_attempt_number < 1:
        raise RecoveryOrchestrationError("recovery_attempt_number must be >= 1")
    if max_attempts < 1:
        raise RecoveryOrchestrationError("max_attempts must be >= 1")

    _validate(diagnosis_artifact, "failure_diagnosis_artifact", label="diagnosis_artifact")

    decision_trace: list[dict[str, Any]] = [
        {
            "step": "diagnosis_validation",
            "decision": "accepted",
            "reason": "diagnosis artifact passed schema validation",
        }
    ]

    if repair_prompt_artifact is None:
        repair_prompt_artifact = generate_repair_prompt(
            diagnosis_artifact,
            emitted_at=emitted_at or diagnosis_artifact.get("emitted_at"),
            run_id=run_id,
            trace_id=trace_id,
        )
        decision_trace.append(
            {
                "step": "repair_prompt_source",
                "decision": "generated",
                "reason": "no repair prompt supplied; generated using FRE-02 deterministic generator",
            }
        )
    else:
        decision_trace.append(
            {
                "step": "repair_prompt_source",
                "decision": "consumed",
                "reason": "caller supplied repair prompt artifact",
            }
        )

    _validate(repair_prompt_artifact, "repair_prompt_artifact", label="repair_prompt_artifact")
    if repair_prompt_artifact["diagnosis_ref"] != diagnosis_artifact["diagnosis_id"]:
        raise RecoveryOrchestrationError("repair_prompt_artifact diagnosis_ref must match diagnosis_artifact diagnosis_id")

    commands = _normalize_validation_commands(repair_prompt_artifact)
    decision_trace.append(
        {
            "step": "validation_command_surface",
            "decision": "accepted",
            "reason": f"{len(commands)} required validation command(s) declared",
        }
    )

    if recovery_attempt_number > max_attempts:
        recovery_status = "blocked"
        blocking_reason_code = "retry_budget_exhausted"
        skipped_ref = (
            f"outputs/recovery/retry-budget-exhausted-validation-skipped-attempt-{recovery_attempt_number:02d}.json"
        )
        validation_results = [
            {
                "command": command,
                "status": "not_run",
                "artifact_ref": skipped_ref,
                "details": {
                    "reason_code": "retry_budget_exhausted",
                    "attempt_number": recovery_attempt_number,
                    "max_attempts": max_attempts,
                },
            }
            for command in commands
        ]
        validation_summary = _summarize_validation(validation_results)
        execution_artifact_refs = [
            f"outputs/recovery/retry-budget-exhausted-attempt-{recovery_attempt_number:02d}-of-{max_attempts:02d}.json"
        ]
        execution_mode = "no_execution"
        execution_status = "blocked"
        execution_reason_code = "retry_budget_exhausted"
        remaining_failure_classes = [diagnosis_artifact["primary_root_cause"]]
        decision_trace.append(
            {
                "step": "retry_budget",
                "decision": "blocked",
                "reason": f"attempt {recovery_attempt_number} exceeds max_attempts {max_attempts}",
            }
        )
    else:
        execution_result = execution_runner(
            {
                "diagnosis_artifact": diagnosis_artifact,
                "repair_prompt_artifact": repair_prompt_artifact,
                "recovery_attempt_number": recovery_attempt_number,
                "max_attempts": max_attempts,
            }
        )
        if not isinstance(execution_result, dict):
            raise RecoveryOrchestrationError("execution runner must return an object result")

        execution_status = execution_result.get("execution_status")
        if execution_status not in _ALLOWED_EXECUTION_STATUSES:
            raise RecoveryOrchestrationError(
                f"execution runner returned unsupported execution_status '{execution_status}'"
            )

        execution_reason_code = str(execution_result.get("reason_code") or "").strip() or None
        execution_mode = str(execution_result.get("repair_execution_mode") or "bounded_governed_execution")
        gate_evidence_refs = _normalize_governance_gate_evidence_refs(execution_result)
        decision_trace.append(
            {
                "step": "governance_gate_evidence",
                "decision": "accepted",
                "reason": (
                    "execution attempt includes governance evidence refs "
                    f"(preflight={gate_evidence_refs['preflight']}, control={gate_evidence_refs['control']}, "
                    f"certification={gate_evidence_refs.get('certification', 'not_applicable')})"
                ),
            }
        )

        raw_refs = execution_result.get("execution_artifact_refs")
        if not isinstance(raw_refs, list) or any(not isinstance(ref, str) or not ref.strip() for ref in raw_refs):
            raise RecoveryOrchestrationError("execution_result.execution_artifact_refs must be a list of non-empty strings")
        execution_artifact_refs = sorted(
            dict.fromkeys([*(ref.strip() for ref in raw_refs), *gate_evidence_refs.values()])
        )
        if not execution_artifact_refs:
            raise RecoveryOrchestrationError("execution_result.execution_artifact_refs cannot be empty")

        validation_results = _run_validation_commands(commands, validation_runner)
        validation_summary = _summarize_validation(validation_results)
        recovery_status, blocking_reason_code = _classify_recovery_status(
            execution_status=execution_status,
            execution_reason_code=execution_reason_code,
            validation_summary=validation_summary,
        )
        remaining_failure_classes = _remaining_failure_classes(
            diagnosis_artifact=diagnosis_artifact,
            validation_results=validation_results,
            execution_status=execution_status,
            execution_reason_code=execution_reason_code,
        )

    retry_recommended = _retry_recommended(
        recovery_status=recovery_status,
        attempt_number=recovery_attempt_number,
        max_attempts=max_attempts,
    )

    recovery_result_seed = {
        "diagnosis_ref": diagnosis_artifact["diagnosis_id"],
        "repair_prompt_ref": repair_prompt_artifact["repair_prompt_id"],
        "recovery_attempt_number": recovery_attempt_number,
        "recovery_status": recovery_status,
        "blocking_reason_code": blocking_reason_code,
        "execution_artifact_refs": execution_artifact_refs,
        "validation_summary": validation_summary,
        "remaining_failure_classes": remaining_failure_classes,
        "retry_recommended": retry_recommended,
    }
    recovery_result_id = f"RREC-{_canonical_hash(recovery_result_seed)[:20]}"

    validation_artifact_refs = sorted(
        {
            row["artifact_ref"]
            for row in validation_results
            if isinstance(row.get("artifact_ref"), str) and row["artifact_ref"]
        }
    )

    artifact = {
        "artifact_type": "recovery_result_artifact",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": diagnosis_artifact["standards_version"],
        "recovery_result_id": recovery_result_id,
        "diagnosis_ref": diagnosis_artifact["diagnosis_id"],
        "repair_prompt_ref": repair_prompt_artifact["repair_prompt_id"],
        "recovery_attempt_number": recovery_attempt_number,
        "max_attempts": max_attempts,
        "recovery_status": recovery_status,
        "blocking_reason_code": blocking_reason_code,
        "repair_execution_mode": execution_mode,
        "execution_artifact_refs": execution_artifact_refs,
        "validation_artifact_refs": validation_artifact_refs,
        "attempted_validation_commands": commands,
        "validation_results": validation_results,
        "validation_summary": validation_summary,
        "remaining_failure_classes": remaining_failure_classes,
        "retry_recommended": retry_recommended,
        "stop_condition": "max_attempts_reached" if recovery_attempt_number >= max_attempts else "attempt_complete",
        "deterministic_decision_trace": decision_trace,
        "emitted_at": emitted_at or _utc_now(),
        "trace": {
            "run_id": run_id,
            "trace_id": trace_id,
            "policy_id": "FRE-006.recovery_orchestrator.v1",
            "governing_ref": "docs/roadmaps/system_roadmap.md#batch-fre-03",
            "diagnosis_hash": _canonical_hash(diagnosis_artifact),
            "repair_prompt_hash": _canonical_hash(repair_prompt_artifact),
            "reason_code_vocab": sorted(_DEFAULT_BLOCKING_CODES),
        },
    }

    _validate(artifact, "recovery_result_artifact", label="recovery_result_artifact")
    return artifact
