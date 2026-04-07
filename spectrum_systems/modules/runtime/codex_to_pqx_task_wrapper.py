"""Deterministic Codex-to-PQX task wrapper builder (CON-038)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.permission_governance import (
    PermissionGovernanceError,
    evaluate_permission_decision,
    require_checkpoint_decision,
)
from spectrum_systems.modules.runtime.pqx_execution_policy import (
    PQXExecutionPolicyError,
    classify_changed_paths,
    evaluate_pqx_execution_policy,
)
from spectrum_systems.modules.runtime.pqx_slice_runner import run_pqx_slice


class CodexToPQXWrapperError(ValueError):
    """Raised when codex-to-pqx wrapper inputs are invalid and must fail closed."""


@dataclass(frozen=True)
class CodexTaskWrapperBuildResult:
    wrapper: dict[str, Any]
    runner_kwargs: dict[str, Any]


def _require_non_empty_string(payload: Mapping[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise CodexToPQXWrapperError(f"{field} must be a non-empty string")
    return value.strip()


def _optional_non_empty_string(payload: Mapping[str, Any], field: str) -> str | None:
    value = payload.get(field)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise CodexToPQXWrapperError(f"{field} must be a non-empty string when provided")
    return value.strip()


def _normalize_dependencies(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise CodexToPQXWrapperError("dependencies must be a list of non-empty strings")
    normalized: list[str] = []
    for index, dep in enumerate(value):
        if not isinstance(dep, str) or not dep.strip():
            raise CodexToPQXWrapperError(f"dependencies[{index}] must be a non-empty string")
        normalized.append(dep.strip())
    return sorted(set(normalized))


def _normalize_changed_paths(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise CodexToPQXWrapperError("changed_paths must be a list of repository-relative paths")
    try:
        classified = classify_changed_paths(value)
        return classified["governed_paths"] + classified["non_governed_paths"]
    except PQXExecutionPolicyError as exc:
        raise CodexToPQXWrapperError(str(exc)) from exc


def _normalize_authority_context(value: Any) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise CodexToPQXWrapperError("authority_context must be an object")
    allowed = {"authority_evidence_ref", "contract_preflight_result_artifact_path", "notes"}
    unknown = sorted(set(value.keys()) - allowed)
    if unknown:
        raise CodexToPQXWrapperError(f"authority_context includes unsupported fields: {', '.join(unknown)}")

    normalized: dict[str, str] = {}
    for field in sorted(allowed):
        raw = value.get(field)
        if raw is None:
            continue
        if not isinstance(raw, str) or not raw.strip():
            raise CodexToPQXWrapperError(f"authority_context.{field} must be a non-empty string when provided")
        normalized[field] = raw.strip()
    return normalized


def _build_wrapper_id(*, task_id: str, requested_at: str, step_id: str, prompt: str) -> str:
    digest = hashlib.sha256(f"{task_id}|{requested_at}|{step_id}|{prompt}".encode("utf-8")).hexdigest()
    return f"codex-pqx-{digest[:16]}"


def build_codex_pqx_task_wrapper(normalized_input: Mapping[str, Any]) -> CodexTaskWrapperBuildResult:
    """Validate normalized Codex task input and build deterministic PQX wrapper payload."""

    task_id = _require_non_empty_string(normalized_input, "task_id")
    step_id = _require_non_empty_string(normalized_input, "step_id")
    step_name = _require_non_empty_string(normalized_input, "step_name")
    prompt = _require_non_empty_string(normalized_input, "prompt")
    requested_at = _require_non_empty_string(normalized_input, "requested_at")
    execution_context = _require_non_empty_string(normalized_input, "execution_context")
    run_id = _optional_non_empty_string(normalized_input, "run_id") or task_id

    dependencies = _normalize_dependencies(normalized_input.get("dependencies"))
    changed_paths = _normalize_changed_paths(normalized_input.get("changed_paths"))
    authority_context = _normalize_authority_context(normalized_input.get("authority_context"))

    policy = evaluate_pqx_execution_policy(
        changed_paths=changed_paths,
        execution_context=execution_context,
    ).to_dict()

    if policy["status"] != "allow":
        reasons = ", ".join(policy.get("blocking_reasons", [])) or "policy rejected wrapper input"
        raise CodexToPQXWrapperError(f"governance posture blocked wrapper creation: {reasons}")

    if policy["pqx_required"] and not authority_context.get("authority_evidence_ref"):
        raise CodexToPQXWrapperError(
            "governed wrapper input requires authority_context.authority_evidence_ref"
        )

    stage_contract = normalized_input.get("stage_contract")
    if stage_contract is None:
        default_stage_contract_path = Path(__file__).resolve().parents[3] / "contracts" / "examples" / "stage_contracts" / "pqx_stage_contract.json"
        stage_contract = json.loads(default_stage_contract_path.read_text(encoding="utf-8"))
    if not isinstance(stage_contract, Mapping):
        raise CodexToPQXWrapperError("stage_contract must be an object when provided")
    try:
        permission = evaluate_permission_decision(
            workflow_id=task_id,
            stage_contract=stage_contract,
            action_name="execute_tool",
            tool_name="python",
            resource_scope="write:artifacts/pqx/",
            request_id=f"prr-{task_id}-{step_id}",
            trace_id=f"trace-{task_id}",
            trace_refs=[f"task:{task_id}", f"step:{step_id}"],
        )
        require_checkpoint_decision(
            permission_decision_record=permission.permission_decision_record,
            human_checkpoint_decision=normalized_input.get("human_checkpoint_decision"),
        )
    except PermissionGovernanceError as exc:
        raise CodexToPQXWrapperError(f"permission policy blocked wrapper creation: {exc}") from exc
    if permission.permission_decision_record["decision"] == "deny":
        raise CodexToPQXWrapperError("permission policy denied governed execution request")

    wrapper_id = _build_wrapper_id(task_id=task_id, requested_at=requested_at, step_id=step_id, prompt=prompt)
    row_snapshot = {
        "row_index": int(normalized_input.get("row_index", 0)),
        "step_id": step_id,
        "step_name": step_name,
        "dependencies": dependencies,
        "status": str(normalized_input.get("row_status", "ready")),
    }

    pqx_execution_request = {
        "schema_version": "1.1.0",
        "run_id": run_id,
        "step_id": step_id,
        "step_name": step_name,
        "dependencies": dependencies,
        "requested_at": requested_at,
        "prompt": prompt,
        "roadmap_version": _optional_non_empty_string(normalized_input, "roadmap_version"),
        "row_snapshot": row_snapshot,
    }
    validate_artifact(pqx_execution_request, "pqx_execution_request")

    wrapper = {
        "schema_version": "1.0.0",
        "artifact_type": "codex_pqx_task_wrapper",
        "wrapper_id": wrapper_id,
        "task_identity": {
            "task_id": task_id,
            "run_id": run_id,
            "step_id": step_id,
            "step_name": step_name,
        },
        "task_source": {
            "source_type": "codex_prompt",
            "prompt": prompt,
        },
        "execution_intent": {
            "execution_context": execution_context,
            "mode": "governed" if policy["pqx_required"] else "exploration_only",
        },
        "governance": {
            "classification": policy["classification"],
            "pqx_required": bool(policy["pqx_required"]),
            "authority_state": policy["authority_state"],
            "authority_resolution": policy["authority_resolution"],
            "authority_evidence_ref": authority_context.get("authority_evidence_ref"),
            "contract_preflight_result_artifact_path": authority_context.get("contract_preflight_result_artifact_path"),
        },
        "changed_paths": changed_paths,
        "metadata": {
            "requested_at": requested_at,
            "dependencies": dependencies,
            "policy_version": str(policy.get("policy_version", "1.0.0")),
            "authority_notes": authority_context.get("notes"),
        },
        "pqx_execution_request": pqx_execution_request,
    }
    validate_artifact(wrapper, "codex_pqx_task_wrapper")

    runner_kwargs = {
        "step_id": step_id,
        "contract_preflight_result_artifact_path": (
            Path(authority_context["contract_preflight_result_artifact_path"])
            if authority_context.get("contract_preflight_result_artifact_path")
            else None
        ),
        "changed_paths": changed_paths,
    }

    return CodexTaskWrapperBuildResult(wrapper=wrapper, runner_kwargs=runner_kwargs)


def run_wrapped_pqx_task(
    *,
    wrapper: Mapping[str, Any],
    roadmap_path: Path,
    state_path: Path,
    runs_root: Path,
    pqx_output_text: str,
) -> dict[str, Any]:
    """Run wrapped task through existing PQX seam using deterministic wrapper-derived kwargs."""

    validate_artifact(dict(wrapper), "codex_pqx_task_wrapper")
    request = wrapper["pqx_execution_request"]
    governance = wrapper["governance"]

    if governance.get("pqx_required") and governance.get("authority_evidence_ref") in (None, ""):
        raise CodexToPQXWrapperError("wrapped governed task missing authority_evidence_ref")

    return run_pqx_slice(
        step_id=str(request["step_id"]),
        roadmap_path=roadmap_path,
        state_path=state_path,
        runs_root=runs_root,
        pqx_output_text=pqx_output_text,
        contract_preflight_result_artifact_path=(
            Path(str(governance["contract_preflight_result_artifact_path"]))
            if isinstance(governance.get("contract_preflight_result_artifact_path"), str)
            and str(governance.get("contract_preflight_result_artifact_path", "")).strip()
            else None
        ),
        changed_paths=list(wrapper.get("changed_paths", [])),
    )


def dump_wrapper(path: Path, wrapper: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(wrapper, indent=2) + "\n", encoding="utf-8")
