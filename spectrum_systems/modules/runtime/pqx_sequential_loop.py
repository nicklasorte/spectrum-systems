"""Deterministic sequential PQX loop orchestration (CON-046)."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from spectrum_systems.modules.pqx_backbone import REPO_ROOT
from spectrum_systems.modules.runtime.codex_to_pqx_task_wrapper import run_wrapped_pqx_task
from spectrum_systems.modules.runtime.control_loop import (
    ControlLoopError,
    build_trace_context_from_replay_artifact,
    run_control_loop,
)
from spectrum_systems.modules.runtime.control_integration import enforce_control_before_execution
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

    execution_trace: dict[str, Any] = {
        "artifact_type": "pqx_sequential_execution_trace",
        "schema_version": "1.0.0",
        "trace_id": _deterministic_trace_id([dict(item) for item in slices], context),
        "slices": [],
        "final_status": "ALLOW",
        "blocking_reason": None,
    }

    carry_context = {
        "artifact_refs": list(context.get("artifact_refs", [])) if isinstance(context.get("artifact_refs"), list) else [],
        "context_bundle": deepcopy(context.get("context_bundle", {})) if isinstance(context.get("context_bundle"), dict) else {},
    }

    for raw_slice in slices:
        slice_request = _require_mapping(raw_slice, label="slice")
        slice_id = _require_non_empty_string(slice_request.get("slice_id"), label="slice.slice_id")
        raw_wrapper = slice_request.get("wrapper")
        if not isinstance(raw_wrapper, Mapping):
            raise PQXSequentialLoopError(f"slice[{slice_id}].wrapper must be an object")
        wrapper = raw_wrapper

        required_context = _require_mapping(
            slice_request.get("required_context") if isinstance(slice_request.get("required_context"), dict) else context,
            label=f"slice[{slice_id}].required_context",
        )
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
            execution_trace["slices"].append(
                {
                    "slice_id": slice_id,
                    "input_ref": slice_request.get("input_ref"),
                    "output_ref": None,
                    "eval_result_ref": None,
                    "control_decision": None,
                    "enforcement_result": "BLOCK",
                    "status": "blocked",
                }
            )
            execution_trace["final_status"] = "BLOCK"
            execution_trace["blocking_reason"] = ",".join(context_enforcement.blocking_reasons)
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
            execution_trace["slices"].append(
                {
                    "slice_id": slice_id,
                    "input_ref": slice_request.get("input_ref"),
                    "output_ref": runner_result.get("result"),
                    "eval_result_ref": None,
                    "control_decision": None,
                    "enforcement_result": "BLOCK",
                    "status": "blocked",
                }
            )
            execution_trace["final_status"] = "BLOCK"
            execution_trace["blocking_reason"] = str(runner_result.get("reason") or "pqx slice execution failed")
            break

        record_ref = _require_non_empty_string(
            runner_result.get("slice_execution_record"), label=f"slice[{slice_id}].slice_execution_record"
        )
        execution_record = _load_json_ref(record_ref)
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

        integration_result = enforce_control_before_execution(
            {
                "artifact": replay_artifact,
                "stage": stage,
                "runtime_environment": runtime_environment,
            }
        )
        enforcement_label = _map_enforcement_label(integration_result)

        eval_ref = f"evaluation_control_decision:{decision_artifact.get('decision_id', '')}"
        output_ref = _repo_ref(_require_non_empty_string(runner_result.get("result"), label="runner result"))
        input_ref = slice_request.get("input_ref") or f"codex_pqx_task_wrapper:{wrapper.get('wrapper_id', '')}"

        execution_trace["slices"].append(
            {
                "slice_id": slice_id,
                "input_ref": input_ref,
                "output_ref": output_ref,
                "eval_result_ref": eval_ref,
                "control_decision": decision_artifact.get("decision"),
                "enforcement_result": enforcement_label,
                "status": "completed" if enforcement_label == "ALLOW" else "stopped",
            }
        )

        carry_context["artifact_refs"].append(output_ref)
        carry_context["artifact_refs"].append(eval_ref)
        slice_request["artifact_refs"] = list(carry_context["artifact_refs"])
        slice_request["context_bundle"] = deepcopy(carry_context["context_bundle"])

        if enforcement_label in {"BLOCK", "REQUIRE_REVIEW"}:
            execution_trace["final_status"] = enforcement_label
            execution_trace["blocking_reason"] = str(
                (integration_result.get("enforcement_result") or {}).get("rationale")
                or (integration_result.get("enforcement_result") or {}).get("final_status")
                or enforcement_label
            )
            break

    return execution_trace


__all__ = ["PQXSequentialLoopError", "run_pqx_sequential"]
