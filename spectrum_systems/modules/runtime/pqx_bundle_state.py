"""Deterministic, schema-bound bundle-state helpers for governed PQX advancement."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from spectrum_systems.contracts import validate_artifact


class PQXBundleStateError(ValueError):
    """Raised when governed bundle-state operations violate fail-closed rules."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now(clock=utc_now) -> str:
    return clock().replace(microsecond=0).isoformat().replace("+00:00", "Z")


def validate_bundle_state(state: dict) -> None:
    try:
        validate_artifact(state, "pqx_bundle_state")
    except Exception as exc:  # pragma: no cover - bounded wrapper
        raise PQXBundleStateError(f"invalid pqx_bundle_state artifact: {exc}") from exc


def _validate_bundle_plan(bundle_plan: list[dict]) -> None:
    if not isinstance(bundle_plan, list) or not bundle_plan:
        raise PQXBundleStateError("bundle_plan must be a non-empty ordered list")

    bundle_ids: set[str] = set()
    step_ids: set[str] = set()
    for index, bundle in enumerate(bundle_plan):
        if not isinstance(bundle, dict):
            raise PQXBundleStateError(f"bundle plan entry at index {index} must be an object")
        bundle_id = bundle.get("bundle_id")
        if not isinstance(bundle_id, str) or not bundle_id:
            raise PQXBundleStateError(f"bundle plan entry at index {index} missing bundle_id")
        if bundle_id in bundle_ids:
            raise PQXBundleStateError(f"duplicate bundle_id in bundle_plan: {bundle_id}")
        bundle_ids.add(bundle_id)

        steps = bundle.get("step_ids")
        if not isinstance(steps, list) or not steps:
            raise PQXBundleStateError(f"bundle '{bundle_id}' must declare non-empty step_ids")
        for step in steps:
            if not isinstance(step, str) or not step:
                raise PQXBundleStateError(f"bundle '{bundle_id}' has invalid step id")
            if step in step_ids:
                raise PQXBundleStateError(f"duplicate step_id in bundle_plan: {step}")
            step_ids.add(step)

    for bundle in bundle_plan:
        dependencies = bundle.get("depends_on", [])
        if dependencies is None:
            dependencies = []
        if not isinstance(dependencies, list):
            raise PQXBundleStateError(f"bundle '{bundle['bundle_id']}' depends_on must be a list")
        unknown = [dep for dep in dependencies if dep not in bundle_ids]
        if unknown:
            raise PQXBundleStateError(
                f"bundle '{bundle['bundle_id']}' has unknown bundle dependencies: {unknown}"
            )


def _bundle_lookup(bundle_plan: list[dict]) -> dict[str, dict]:
    return {bundle["bundle_id"]: bundle for bundle in bundle_plan}


def _step_to_bundle(bundle_plan: list[dict]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for bundle in bundle_plan:
        for step_id in bundle["step_ids"]:
            mapping[step_id] = bundle["bundle_id"]
    return mapping


def _find_next_incomplete_bundle(bundle_plan: list[dict], completed_bundle_ids: list[str]) -> str | None:
    done = set(completed_bundle_ids)
    for bundle in bundle_plan:
        if bundle["bundle_id"] not in done:
            return bundle["bundle_id"]
    return None


def derive_resume_position(state: dict, bundle_plan: list[dict]) -> dict:
    _validate_bundle_plan(bundle_plan)
    validate_bundle_state(state)

    completed_steps = set(state["completed_step_ids"])
    completed_bundles = set(state["completed_bundle_ids"])
    current_bundle = state["active_bundle_id"]

    bundle_map = _bundle_lookup(bundle_plan)
    if current_bundle not in bundle_map:
        raise PQXBundleStateError(f"active_bundle_id not present in bundle plan: {current_bundle}")

    if current_bundle in completed_bundles:
        next_bundle = _find_next_incomplete_bundle(bundle_plan, state["completed_bundle_ids"])
        if next_bundle is None:
            return {
                "bundle_id": current_bundle,
                "next_step_id": None,
                "resume_token": f"resume:{state['sequence_run_id']}:{current_bundle}:{len(state['completed_step_ids'])}",
            }
        current_bundle = next_bundle

    steps = bundle_map[current_bundle]["step_ids"]
    next_step = next((step for step in steps if step not in completed_steps), None)

    return {
        "bundle_id": current_bundle,
        "next_step_id": next_step,
        "resume_token": f"resume:{state['sequence_run_id']}:{current_bundle}:{len(state['completed_step_ids'])}",
    }


def assert_valid_advancement(state: dict, bundle_plan: list[dict], *, step_id: str) -> None:
    _validate_bundle_plan(bundle_plan)
    validate_bundle_state(state)

    if step_id in state["completed_step_ids"]:
        raise PQXBundleStateError(f"step already completed: {step_id}")
    if step_id in state["blocked_step_ids"]:
        raise PQXBundleStateError(f"blocked step cannot advance without explicit remediation: {step_id}")

    step_map = _step_to_bundle(bundle_plan)
    if step_id not in step_map:
        raise PQXBundleStateError(f"step_id not declared in bundle plan: {step_id}")

    target_bundle_id = step_map[step_id]
    if target_bundle_id != state["active_bundle_id"]:
        raise PQXBundleStateError(
            f"out-of-order advancement blocked: step '{step_id}' belongs to '{target_bundle_id}' "
            f"but active bundle is '{state['active_bundle_id']}'"
        )

    bundle_map = _bundle_lookup(bundle_plan)
    for required_bundle in bundle_map[target_bundle_id].get("depends_on", []):
        if required_bundle not in state["completed_bundle_ids"]:
            raise PQXBundleStateError(
                f"bundle dependency unsatisfied for '{target_bundle_id}': '{required_bundle}' is incomplete"
            )

    for declared_step in bundle_map[target_bundle_id]["step_ids"]:
        if declared_step == step_id:
            break
        if declared_step not in state["completed_step_ids"]:
            raise PQXBundleStateError(
                f"step order violation: prior step '{declared_step}' must complete before '{step_id}'"
            )


def initialize_bundle_state(
    *,
    bundle_plan: list[dict],
    run_id: str,
    sequence_run_id: str,
    roadmap_authority_ref: str,
    execution_plan_ref: str,
    now: str,
) -> dict:
    _validate_bundle_plan(bundle_plan)

    if roadmap_authority_ref != "docs/roadmaps/system_roadmap.md":
        raise PQXBundleStateError(
            "malformed roadmap_authority_ref; expected docs/roadmaps/system_roadmap.md"
        )
    if not isinstance(execution_plan_ref, str) or not execution_plan_ref:
        raise PQXBundleStateError("execution_plan_ref is required")
    if not isinstance(run_id, str) or not run_id:
        raise PQXBundleStateError("run_id is required")
    if not isinstance(sequence_run_id, str) or not sequence_run_id:
        raise PQXBundleStateError("sequence_run_id is required")

    first_bundle = bundle_plan[0]["bundle_id"]
    initial = {
        "schema_version": "1.0.0",
        "roadmap_authority_ref": roadmap_authority_ref,
        "execution_plan_ref": execution_plan_ref,
        "run_id": run_id,
        "sequence_run_id": sequence_run_id,
        "active_bundle_id": first_bundle,
        "completed_bundle_ids": [],
        "completed_step_ids": [],
        "blocked_step_ids": [],
        "pending_fix_ids": [],
        "review_artifact_refs": [],
        "artifact_index": {},
        "resume_position": {
            "bundle_id": first_bundle,
            "next_step_id": bundle_plan[0]["step_ids"][0],
            "resume_token": f"resume:{sequence_run_id}:{first_bundle}:0",
        },
        "created_at": now,
        "updated_at": now,
    }
    validate_bundle_state(initial)
    return initial


def mark_step_complete(
    state: dict,
    bundle_plan: list[dict],
    *,
    step_id: str,
    artifact_refs: list[str] | None,
    now: str,
) -> dict:
    assert_valid_advancement(state, bundle_plan, step_id=step_id)
    updated = deepcopy(state)
    updated["completed_step_ids"].append(step_id)
    if artifact_refs:
        cleaned = [ref for ref in artifact_refs if isinstance(ref, str) and ref]
        if len(cleaned) != len(artifact_refs):
            raise PQXBundleStateError("artifact_refs must be non-empty strings")
        updated["artifact_index"][step_id] = list(dict.fromkeys(cleaned))
    updated["updated_at"] = now
    updated["resume_position"] = derive_resume_position(updated, bundle_plan)
    validate_bundle_state(updated)
    return updated


def mark_bundle_complete(state: dict, bundle_plan: list[dict], *, bundle_id: str, now: str) -> dict:
    _validate_bundle_plan(bundle_plan)
    validate_bundle_state(state)
    updated = deepcopy(state)

    if bundle_id in updated["completed_bundle_ids"]:
        raise PQXBundleStateError(f"bundle already completed: {bundle_id}")
    if bundle_id != updated["active_bundle_id"]:
        raise PQXBundleStateError(
            f"bundle completion out of order: active bundle is '{updated['active_bundle_id']}'"
        )

    bundle_map = _bundle_lookup(bundle_plan)
    if bundle_id not in bundle_map:
        raise PQXBundleStateError(f"bundle_id not declared in bundle plan: {bundle_id}")

    required_steps = bundle_map[bundle_id]["step_ids"]
    missing_steps = [step for step in required_steps if step not in updated["completed_step_ids"]]
    if missing_steps:
        raise PQXBundleStateError(
            f"bundle '{bundle_id}' cannot complete; required steps incomplete: {missing_steps}"
        )

    for dep in bundle_map[bundle_id].get("depends_on", []):
        if dep not in updated["completed_bundle_ids"]:
            raise PQXBundleStateError(
                f"bundle '{bundle_id}' cannot complete; dependent bundle '{dep}' incomplete"
            )

    updated["completed_bundle_ids"].append(bundle_id)
    next_bundle = _find_next_incomplete_bundle(bundle_plan, updated["completed_bundle_ids"])
    if next_bundle is not None:
        updated["active_bundle_id"] = next_bundle
    updated["updated_at"] = now
    updated["resume_position"] = derive_resume_position(updated, bundle_plan)
    validate_bundle_state(updated)
    return updated


def block_step(state: dict, bundle_plan: list[dict], *, step_id: str, now: str) -> dict:
    _validate_bundle_plan(bundle_plan)
    validate_bundle_state(state)
    step_map = _step_to_bundle(bundle_plan)
    if step_id not in step_map:
        raise PQXBundleStateError(f"step_id not declared in bundle plan: {step_id}")

    updated = deepcopy(state)
    if step_id in updated["completed_step_ids"]:
        raise PQXBundleStateError(f"cannot block already-completed step: {step_id}")
    if step_id not in updated["blocked_step_ids"]:
        updated["blocked_step_ids"].append(step_id)
    updated["updated_at"] = now
    updated["resume_position"] = derive_resume_position(updated, bundle_plan)
    validate_bundle_state(updated)
    return updated


def attach_review_artifact(
    state: dict,
    bundle_plan: list[dict],
    *,
    review_id: str,
    bundle_id: str,
    step_id: str,
    artifact_ref: str,
    now: str,
) -> dict:
    _validate_bundle_plan(bundle_plan)
    validate_bundle_state(state)

    if not all(isinstance(v, str) and v for v in (review_id, bundle_id, step_id, artifact_ref)):
        raise PQXBundleStateError("review artifact fields must be non-empty strings")

    step_map = _step_to_bundle(bundle_plan)
    if step_map.get(step_id) != bundle_id:
        raise PQXBundleStateError(f"review artifact linkage invalid: step '{step_id}' is not in bundle '{bundle_id}'")

    updated = deepcopy(state)
    review_entry = {
        "review_id": review_id,
        "bundle_id": bundle_id,
        "step_id": step_id,
        "artifact_ref": artifact_ref,
    }
    if review_entry in updated["review_artifact_refs"]:
        raise PQXBundleStateError(f"duplicate review artifact entry rejected: {review_id}")

    updated["review_artifact_refs"].append(review_entry)
    updated["updated_at"] = now
    validate_bundle_state(updated)
    return updated


def add_pending_fix(
    state: dict,
    bundle_plan: list[dict],
    *,
    fix_id: str,
    finding_id: str,
    target_bundle_id: str,
    target_step_id: str,
    status: str,
    now: str,
) -> dict:
    _validate_bundle_plan(bundle_plan)
    validate_bundle_state(state)

    step_map = _step_to_bundle(bundle_plan)
    if step_map.get(target_step_id) != target_bundle_id:
        raise PQXBundleStateError(
            f"pending fix target mismatch: step '{target_step_id}' is not in bundle '{target_bundle_id}'"
        )

    updated = deepcopy(state)
    candidate = {
        "fix_id": fix_id,
        "finding_id": finding_id,
        "target_bundle_id": target_bundle_id,
        "target_step_id": target_step_id,
        "status": status,
    }
    if candidate in updated["pending_fix_ids"]:
        raise PQXBundleStateError(f"duplicate pending fix entry rejected: {fix_id}")

    updated["pending_fix_ids"].append(candidate)
    updated["updated_at"] = now
    validate_bundle_state(updated)
    return updated


def load_bundle_state(state_path: str | Path, *, bundle_plan: list[dict]) -> dict:
    _validate_bundle_plan(bundle_plan)
    payload = json.loads(Path(state_path).read_text(encoding="utf-8"))
    validate_bundle_state(payload)
    payload["resume_position"] = derive_resume_position(payload, bundle_plan)
    validate_bundle_state(payload)
    return payload


def save_bundle_state(state: dict, state_path: str | Path, *, bundle_plan: list[dict]) -> dict:
    _validate_bundle_plan(bundle_plan)
    validate_bundle_state(state)
    state_path = Path(state_path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    ordered = deepcopy(state)
    ordered["resume_position"] = derive_resume_position(ordered, bundle_plan)
    validate_bundle_state(ordered)
    state_path.write_text(json.dumps(ordered, indent=2) + "\n", encoding="utf-8")
    reloaded = json.loads(state_path.read_text(encoding="utf-8"))
    validate_bundle_state(reloaded)
    if reloaded != ordered:
        raise PQXBundleStateError("persisted-reload mismatch detected for pqx_bundle_state")
    return reloaded
