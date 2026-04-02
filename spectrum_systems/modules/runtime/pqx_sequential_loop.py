"""Deterministic sequential PQX loop orchestration (CON-046/CON-047)."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.pqx_backbone import REPO_ROOT
from spectrum_systems.modules.runtime.codex_to_pqx_task_wrapper import run_wrapped_pqx_task
from spectrum_systems.modules.runtime.control_loop import (
    ControlLoopError,
    build_trace_context_from_replay_artifact,
    run_control_loop,
)
from spectrum_systems.modules.runtime.enforcement_engine import (
    EnforcementError,
    enforce_control_decision,
)
from spectrum_systems.modules.runtime.pqx_required_context_enforcement import (
    enforce_pqx_required_context,
)


class PQXSequentialLoopError(ValueError):
    """Raised when sequential loop inputs or control outputs are invalid."""


def _require_mapping(value: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PQXSequentialLoopError(f"{label} must be an object")
    return dict(value)


def _require_non_empty_string(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PQXSequentialLoopError(f"{label} must be a non-empty string")
    return value.strip()


def _repo_ref(path: str) -> str:
    try:
        return str(Path(path).resolve().relative_to(REPO_ROOT))
    except Exception:
        return path


def _load_json_ref(path_ref: str) -> dict[str, Any]:
    path = Path(path_ref)
    resolved = path if path.is_absolute() else (REPO_ROOT / path)
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    return _require_mapping(payload, label=f"artifact at {path_ref}")


def _deterministic_trace_id(slices: list[dict[str, Any]], initial_context: dict[str, Any]) -> str:
    try:
        encoded = json.dumps({"slices": slices, "initial_context": initial_context}, sort_keys=True, separators=(",", ":"))
    except TypeError as exc:
        raise PQXSequentialLoopError(f"inputs must be JSON-serializable for deterministic trace id: {exc}") from exc
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]
    return f"pqx-seq-{digest}"


def _map_enforcement_label(integration_result: dict[str, Any]) -> str:
    enforcement = integration_result.get("enforcement_result")
    if not isinstance(enforcement, dict):
        raise PQXSequentialLoopError("enforcement output invalid: enforcement_result missing")
    final_status = enforcement.get("final_status")
    mapping = {"allow": "ALLOW", "deny": "BLOCK", "require_review": "REQUIRE_REVIEW"}
    normalized = mapping.get(final_status)
    if normalized is None:
        raise PQXSequentialLoopError("enforcement output invalid: unsupported final_status")
    return normalized


def _derive_run_id(*, context: dict[str, Any], slices: list[dict[str, Any]], trace_id: str) -> str:
    raw = context.get("run_id")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    for slice_payload in slices:
        wrapper = slice_payload.get("wrapper")
        if isinstance(wrapper, Mapping):
            identity = wrapper.get("task_identity")
            if isinstance(identity, Mapping):
                run_id = identity.get("run_id")
                if isinstance(run_id, str) and run_id.strip():
                    return run_id.strip()
    return trace_id


def _validate_trace_invariants(trace: dict[str, Any]) -> None:
    slices = trace.get("slices")
    if not isinstance(slices, list) or not slices:
        raise PQXSequentialLoopError("trace invariant failed: slices must be non-empty")

    for row in slices:
        if not isinstance(row, dict):
            raise PQXSequentialLoopError("trace invariant failed: slice row must be object")
        status = row.get("status")
        slice_id = row.get("slice_id")
        if status in {"completed", "stopped"}:
            required_refs = (
                "wrapper_ref",
                "pqx_execution_artifact_ref",
                "slice_execution_record_ref",
                "eval_result_ref",
                "control_decision_ref",
            )
            for key in required_refs:
                value = row.get(key)
                if not isinstance(value, str) or not value.strip():
                    raise PQXSequentialLoopError(
                        f"trace invariant failed: required ref '{key}' missing for slice {slice_id}"
                    )
        if status == "completed":
            if row.get("final_slice_status") != "ALLOW":
                raise PQXSequentialLoopError(
                    f"trace invariant failed: completed slice {slice_id} must have final_slice_status ALLOW"
                )

    final_status = trace.get("final_status")
    terminal_slice = slices[-1]
    terminal_status = terminal_slice.get("final_slice_status")
    if final_status == "ALLOW":
        if any(row.get("final_slice_status") != "ALLOW" for row in slices):
            raise PQXSequentialLoopError("trace invariant failed: final_status ALLOW contradicts per-slice outcomes")
        if trace.get("blocking_reason") is not None or trace.get("stopping_slice_id") is not None:
            raise PQXSequentialLoopError(
                "trace invariant failed: ALLOW final_status must not include blocking_reason or stopping_slice_id"
            )
    elif final_status in {"BLOCK", "REQUIRE_REVIEW"}:
        if terminal_status != final_status:
            raise PQXSequentialLoopError("trace invariant failed: final_status contradicts terminal per-slice outcome")
        if not isinstance(trace.get("blocking_reason"), str) or not str(trace.get("blocking_reason")).strip():
            raise PQXSequentialLoopError("trace invariant failed: blocking_reason required for blocked/review-stopped run")
        if trace.get("stopping_slice_id") != terminal_slice.get("slice_id"):
            raise PQXSequentialLoopError("trace invariant failed: stopping_slice_id must identify terminal slice")
    else:
        raise PQXSequentialLoopError("trace invariant failed: unsupported final_status")


def run_pqx_sequential(
    slices: list,
    initial_context: dict,
) -> dict[str, Any]:
    """Execute ordered PQX slices through existing eval, decision, and enforcement seams."""

    if not isinstance(slices, list) or not slices:
        raise PQXSequentialLoopError("slices must be a non-empty ordered list")

    context = _require_mapping(initial_context, label="initial_context")
    stage = _require_non_empty_string(context.get("stage"), label="initial_context.stage")
    runtime_environment = _require_non_empty_string(
        context.get("runtime_environment"), label="initial_context.runtime_environment"
    )

    normalized_slices = [dict(item) for item in slices]
    trace_id = _deterministic_trace_id(normalized_slices, context)
    execution_trace: dict[str, Any] = {
        "artifact_type": "pqx_sequential_execution_trace",
        "schema_version": "1.0.0",
        "trace_id": trace_id,
        "run_id": _derive_run_id(context=context, slices=normalized_slices, trace_id=trace_id),
        "ordered_slice_ids": [],
        "slices": [],
        "authority_evidence_refs": [],
        "final_status": "ALLOW",
        "blocking_reason": None,
        "stopping_slice_id": None,
    }

    carry_context = {
        "artifact_refs": list(context.get("artifact_refs", [])) if isinstance(context.get("artifact_refs"), list) else [],
        "context_bundle": deepcopy(context.get("context_bundle", {})) if isinstance(context.get("context_bundle"), dict) else {},
    }

    for raw_slice in slices:
        slice_request = _require_mapping(raw_slice, label="slice")
        slice_id = _require_non_empty_string(slice_request.get("slice_id"), label="slice.slice_id")
        execution_trace["ordered_slice_ids"].append(slice_id)

        raw_wrapper = slice_request.get("wrapper")
        if not isinstance(raw_wrapper, Mapping):
            raise PQXSequentialLoopError(f"slice[{slice_id}].wrapper must be an object")
        wrapper = raw_wrapper
        wrapper_id = _require_non_empty_string(wrapper.get("wrapper_id"), label=f"slice[{slice_id}].wrapper.wrapper_id")
        wrapper_ref = f"codex_pqx_task_wrapper:{wrapper_id}"

        required_context = _require_mapping(
            slice_request.get("required_context") if isinstance(slice_request.get("required_context"), dict) else context,
            label=f"slice[{slice_id}].required_context",
        )
        if not required_context.get("authority_evidence_ref") and execution_trace["authority_evidence_refs"]:
            required_context["authority_evidence_ref"] = execution_trace["authority_evidence_refs"][-1]
        classification = _require_non_empty_string(
            required_context.get("classification"), label=f"slice[{slice_id}].required_context.classification"
        )
        execution_context = _require_non_empty_string(
            required_context.get("execution_context"), label=f"slice[{slice_id}].required_context.execution_context"
        )

        context_enforcement = enforce_pqx_required_context(
            classification=classification,
            execution_context=execution_context,
            changed_paths=slice_request.get("changed_paths"),
            pqx_task_wrapper=wrapper,
            authority_evidence_ref=required_context.get("authority_evidence_ref"),
        )
        if context_enforcement.status != "allow":
            reason = ",".join(context_enforcement.blocking_reasons)
            execution_trace["slices"].append(
                {
                    "slice_id": slice_id,
                    "input_ref": slice_request.get("input_ref"),
                    "wrapper_ref": wrapper_ref,
                    "pqx_execution_artifact_ref": None,
                    "slice_execution_record_ref": None,
                    "eval_result_ref": None,
                    "control_decision_ref": None,
                    "control_decision_summary": None,
                    "enforcement_result": {
                        "final_status": "block",
                        "rationale": reason,
                    },
                    "final_slice_status": "BLOCK",
                    "status": "blocked",
                }
            )
            execution_trace["final_status"] = "BLOCK"
            execution_trace["blocking_reason"] = reason
            execution_trace["stopping_slice_id"] = slice_id
            break

        runner_result = run_wrapped_pqx_task(
            wrapper=wrapper,
            roadmap_path=Path(_require_non_empty_string(slice_request.get("roadmap_path"), label=f"slice[{slice_id}].roadmap_path")),
            state_path=Path(_require_non_empty_string(slice_request.get("state_path"), label=f"slice[{slice_id}].state_path")),
            runs_root=Path(_require_non_empty_string(slice_request.get("runs_root"), label=f"slice[{slice_id}].runs_root")),
            pqx_output_text=_require_non_empty_string(
                slice_request.get("pqx_output_text"), label=f"slice[{slice_id}].pqx_output_text"
            ),
        )
        if runner_result.get("status") != "complete":
            reason = str(runner_result.get("reason") or "pqx slice execution failed")
            execution_trace["slices"].append(
                {
                    "slice_id": slice_id,
                    "input_ref": slice_request.get("input_ref"),
                    "wrapper_ref": wrapper_ref,
                    "pqx_execution_artifact_ref": None,
                    "slice_execution_record_ref": None,
                    "eval_result_ref": None,
                    "control_decision_ref": None,
                    "control_decision_summary": None,
                    "enforcement_result": {
                        "final_status": "block",
                        "rationale": reason,
                    },
                    "final_slice_status": "BLOCK",
                    "status": "blocked",
                }
            )
            execution_trace["final_status"] = "BLOCK"
            execution_trace["blocking_reason"] = reason
            execution_trace["stopping_slice_id"] = slice_id
            break

        record_ref = _require_non_empty_string(
            runner_result.get("slice_execution_record"), label=f"slice[{slice_id}].slice_execution_record"
        )
        execution_record = _load_json_ref(record_ref)
        try:
            validate_artifact(execution_record, "pqx_slice_execution_record")
        except Exception as exc:
            raise PQXSequentialLoopError(f"invalid pqx_slice_execution_record for slice {slice_id}: {exc}") from exc
        execution_record_ref = _repo_ref(record_ref)
        replay_ref = _require_non_empty_string(
            execution_record.get("replay_result_ref"), label=f"slice[{slice_id}] replay_result_ref"
        )
        replay_artifact = _load_json_ref(replay_ref)

        try:
            trace_context = build_trace_context_from_replay_artifact(replay_artifact)
            eval_result = run_control_loop(replay_artifact, trace_context)
        except ControlLoopError as exc:
            raise PQXSequentialLoopError(f"eval result missing for slice {slice_id}: {exc}") from exc

        decision_artifact = eval_result.get("evaluation_control_decision")
        if not isinstance(decision_artifact, dict):
            raise PQXSequentialLoopError(f"control decision missing for slice {slice_id}")

        try:
            enforcement_result = enforce_control_decision(decision_artifact)
        except EnforcementError as exc:
            raise PQXSequentialLoopError(f"enforcement mapping failed for slice {slice_id}: {exc}") from exc
        integration_result = {"enforcement_result": enforcement_result}
        enforcement_label = _map_enforcement_label(integration_result)

        control_decision_ref = _require_non_empty_string(
            execution_record.get("control_decision_ref") or f"evaluation_control_decision:{decision_artifact.get('decision_id', '')}",
            label=f"slice[{slice_id}].control_decision_ref",
        )
        eval_ref = _require_non_empty_string(
            f"evaluation_control_decision:{decision_artifact.get('decision_id', '')}",
            label=f"slice[{slice_id}].eval_result_ref",
        )
        output_ref = _repo_ref(_require_non_empty_string(runner_result.get("result"), label="runner result"))
        input_ref = slice_request.get("input_ref") or wrapper_ref

        enforcement_summary = {
            "final_status": _require_non_empty_string(
                enforcement_result.get("final_status"), label=f"slice[{slice_id}].enforcement_result.final_status"
            ),
            "rationale": _require_non_empty_string(
                enforcement_result.get("rationale_code") or enforcement_label,
                label=f"slice[{slice_id}].enforcement_result.rationale",
            ),
        }

        execution_trace["slices"].append(
            {
                "slice_id": slice_id,
                "input_ref": input_ref,
                "wrapper_ref": wrapper_ref,
                "pqx_execution_artifact_ref": output_ref,
                "slice_execution_record_ref": execution_record_ref,
                "eval_result_ref": eval_ref,
                "control_decision_ref": control_decision_ref,
                "control_decision_summary": {
                    "decision": _require_non_empty_string(decision_artifact.get("decision"), label=f"slice[{slice_id}].decision"),
                    "decision_id": _require_non_empty_string(
                        decision_artifact.get("decision_id"), label=f"slice[{slice_id}].decision_id"
                    ),
                },
                "enforcement_result": enforcement_summary,
                "final_slice_status": enforcement_label,
                "status": "completed" if enforcement_label == "ALLOW" else "stopped",
            }
        )

        carry_context["artifact_refs"].append(output_ref)
        carry_context["artifact_refs"].append(execution_record_ref)
        carry_context["artifact_refs"].append(eval_ref)
        execution_trace["authority_evidence_refs"].append(execution_record_ref)
        slice_request["artifact_refs"] = list(carry_context["artifact_refs"])
        slice_request["context_bundle"] = deepcopy(carry_context["context_bundle"])
        slice_request["authority_evidence_ref"] = execution_record_ref
        if isinstance(slice_request.get("required_context"), dict):
            slice_request["required_context"]["authority_evidence_ref"] = execution_record_ref

        if enforcement_label in {"BLOCK", "REQUIRE_REVIEW"}:
            execution_trace["final_status"] = enforcement_label
            execution_trace["blocking_reason"] = enforcement_summary["rationale"]
            execution_trace["stopping_slice_id"] = slice_id
            break

    _validate_trace_invariants(execution_trace)
    try:
        validate_artifact(execution_trace, "pqx_sequential_execution_trace")
    except Exception as exc:
        raise PQXSequentialLoopError(f"pqx_sequential_execution_trace validation failed: {exc}") from exc

    return execution_trace


__all__ = ["PQXSequentialLoopError", "run_pqx_sequential"]
