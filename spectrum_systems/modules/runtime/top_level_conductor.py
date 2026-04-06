"""Top-Level Conductor (TLC-001): thin deterministic orchestration shell.

TLC owns only bounded run-state progression and subsystem invocation order.
It does not duplicate logic owned by PQX/TPA/FRE/RIL/CDE/PRG/SEL.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Callable


TERMINAL_STATES = {"ready_for_merge", "blocked", "exhausted", "escalated"}


class TopLevelConductorError(ValueError):
    """Raised when TLC input or transition invariants are violated."""


def _canonical_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _require_non_empty_str(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TopLevelConductorError(f"{field} must be a non-empty string")
    return value.strip()


def _require_bool(value: Any, *, field: str) -> bool:
    if not isinstance(value, bool):
        raise TopLevelConductorError(f"{field} must be boolean")
    return value


def _require_non_negative_int(value: Any, *, field: str) -> int:
    if not isinstance(value, int) or value < 0:
        raise TopLevelConductorError(f"{field} must be a non-negative integer")
    return value


def _default_sel(_: dict[str, Any]) -> dict[str, Any]:
    return {"allowed": True, "reason": "allow"}


def _default_pqx(_: dict[str, Any]) -> dict[str, Any]:
    return {"entry_valid": True, "validation_passed": True, "artifact_refs": [], "trace_refs": []}


def _default_tpa(_: dict[str, Any]) -> dict[str, Any]:
    return {"discipline_status": "accepted"}


def _default_fre(_: dict[str, Any]) -> dict[str, Any]:
    return {"recovery_completed": True, "artifact_refs": [], "trace_refs": []}


def _default_ril(_: dict[str, Any]) -> dict[str, Any]:
    return {"outputs_exist": True, "artifact_refs": [], "trace_refs": []}


def _default_cde(_: dict[str, Any]) -> dict[str, Any]:
    return {"decision_type": "lock", "closure_state": "closed", "artifact_refs": [], "trace_refs": []}


def _default_prg(_: dict[str, Any]) -> dict[str, Any]:
    return {"proposed": True, "artifact_refs": [], "trace_refs": []}


def _extract_refs(result: dict[str, Any], *, produced_refs: list[str], trace_refs: list[str]) -> None:
    for key in ("artifact_ref", "artifacts_ref"):
        value = result.get(key)
        if isinstance(value, str) and value.strip():
            produced_refs.append(value.strip())
    for key in ("artifact_refs", "produced_artifact_refs"):
        value = result.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item.strip():
                    produced_refs.append(item.strip())

    for key in ("trace_ref", "trace_id"):
        value = result.get(key)
        if isinstance(value, str) and value.strip():
            trace_refs.append(value.strip())
    for key in ("trace_refs",):
        value = result.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item.strip():
                    trace_refs.append(item.strip())


def _next_actions_for_state(state: str) -> list[str]:
    if state in TERMINAL_STATES:
        return []
    action_map = {
        "requested": ["admit"],
        "admitted": ["execute"],
        "executing": ["evaluate"],
        "discipline_pending": ["enforce_discipline"],
        "validation_failed": ["recover", "block", "exhaust"],
        "recovering": ["review"],
        "reviewing": ["decide_closure"],
        "closure_decision_pending": ["lock", "continue_bounded", "block", "exhaust", "escalate"],
        "direction_pending": ["execute"],
    }
    return action_map.get(state, [])


def _transition(
    *,
    state: dict[str, Any],
    to_state: str,
    reason: str,
) -> None:
    from_state = state["current_state"]
    state["phase_history"].append({"from": from_state, "to": to_state, "reason": reason})
    state["current_state"] = to_state
    state["next_allowed_actions"] = _next_actions_for_state(to_state)


def _enforce_sel(
    *,
    state: dict[str, Any],
    sel_fn: Callable[[dict[str, Any]], dict[str, Any]],
    boundary: str,
) -> bool:
    payload = {
        "run_id": state["run_id"],
        "objective": state["objective"],
        "branch_ref": state["branch_ref"],
        "current_state": state["current_state"],
        "boundary": boundary,
    }
    result = sel_fn(payload)
    state["active_subsystems"].append("SEL")
    _extract_refs(result if isinstance(result, dict) else {}, produced_refs=state["produced_artifact_refs"], trace_refs=state["trace_refs"])
    if not isinstance(result, dict) or not bool(result.get("allowed", False)):
        _transition(state=state, to_state="blocked", reason=f"sel_block:{boundary}")
        state["stop_reason"] = f"sel_block:{boundary}"
        return False
    return True


def run_top_level_conductor(run_request: dict[str, Any]) -> dict[str, Any]:
    """Run one deterministic bounded TLC state machine invocation."""
    if not isinstance(run_request, dict):
        raise TopLevelConductorError("run_request must be an object")

    objective = _require_non_empty_str(run_request.get("objective"), field="objective")
    branch_ref = _require_non_empty_str(run_request.get("branch_ref"), field="branch_ref")
    retry_budget = _require_non_negative_int(run_request.get("retry_budget"), field="retry_budget")
    require_review = _require_bool(run_request.get("require_review"), field="require_review")
    require_recovery = _require_bool(run_request.get("require_recovery"), field="require_recovery")

    run_id = run_request.get("run_id")
    if not isinstance(run_id, str) or not run_id.strip():
        identity_seed = {
            "objective": objective,
            "branch_ref": branch_ref,
            "retry_budget": retry_budget,
            "require_review": require_review,
            "require_recovery": require_recovery,
        }
        run_id = f"tlc-{_canonical_hash(identity_seed)[:12]}"

    subsystems = run_request.get("subsystems") if isinstance(run_request.get("subsystems"), dict) else {}
    sel_fn = subsystems.get("sel", _default_sel)
    pqx_fn = subsystems.get("pqx", _default_pqx)
    tpa_fn = subsystems.get("tpa", _default_tpa)
    fre_fn = subsystems.get("fre", _default_fre)
    ril_fn = subsystems.get("ril", _default_ril)
    cde_fn = subsystems.get("cde", _default_cde)
    prg_fn = subsystems.get("prg", _default_prg)

    for name, fn in (("sel", sel_fn), ("pqx", pqx_fn), ("tpa", tpa_fn), ("fre", fre_fn), ("ril", ril_fn), ("cde", cde_fn), ("prg", prg_fn)):
        if not callable(fn):
            raise TopLevelConductorError(f"subsystems.{name} must be callable")

    lineage = deepcopy(run_request.get("lineage")) if isinstance(run_request.get("lineage"), dict) else {}
    lineage.setdefault("request_hash", _canonical_hash({
        "objective": objective,
        "branch_ref": branch_ref,
        "retry_budget": retry_budget,
        "require_review": require_review,
        "require_recovery": require_recovery,
        "run_id": run_id,
    }))

    state: dict[str, Any] = {
        "run_id": run_id,
        "objective": objective,
        "branch_ref": branch_ref,
        "current_state": "requested",
        "phase_history": [],
        "active_subsystems": [],
        "retry_budget_remaining": retry_budget,
        "closure_state": "pending",
        "next_allowed_actions": ["admit"],
        "stop_reason": None,
        "ready_for_merge": False,
        "produced_artifact_refs": [],
        "trace_refs": [],
        "lineage": lineage,
    }

    while state["current_state"] not in TERMINAL_STATES:
        if not _enforce_sel(state=state, sel_fn=sel_fn, boundary="state_transition"):
            break

        if state["current_state"] == "requested":
            _transition(state=state, to_state="admitted", reason="request_admitted")
            continue

        if state["current_state"] == "admitted":
            _transition(state=state, to_state="executing", reason="execution_admitted")
            continue

        if state["current_state"] == "executing":
            if not _enforce_sel(state=state, sel_fn=sel_fn, boundary="execution"):
                break
            pqx_result = pqx_fn({"run_id": state["run_id"], "objective": state["objective"], "branch_ref": state["branch_ref"]})
            state["active_subsystems"].append("PQX")
            _extract_refs(pqx_result if isinstance(pqx_result, dict) else {}, produced_refs=state["produced_artifact_refs"], trace_refs=state["trace_refs"])
            if not isinstance(pqx_result, dict) or not bool(pqx_result.get("entry_valid", False)):
                _transition(state=state, to_state="blocked", reason="pqx_entry_invalid")
                state["stop_reason"] = "pqx_entry_invalid"
                break

            tpa_result = tpa_fn({"run_id": state["run_id"], "pqx_result": pqx_result})
            state["active_subsystems"].append("TPA")
            _extract_refs(tpa_result if isinstance(tpa_result, dict) else {}, produced_refs=state["produced_artifact_refs"], trace_refs=state["trace_refs"])

            if bool(pqx_result.get("validation_passed", False)):
                if require_review:
                    _transition(state=state, to_state="reviewing", reason="execution_validated")
                else:
                    _transition(state=state, to_state="closure_decision_pending", reason="execution_validated_no_review")
            else:
                _transition(state=state, to_state="validation_failed", reason="validation_failed")
            continue

        if state["current_state"] == "validation_failed":
            if not require_recovery:
                _transition(state=state, to_state="blocked", reason="recovery_not_permitted")
                state["stop_reason"] = "recovery_not_permitted"
                break
            if state["retry_budget_remaining"] <= 0:
                _transition(state=state, to_state="exhausted", reason="retry_budget_exhausted")
                state["stop_reason"] = "retry_budget_exhausted"
                break
            _transition(state=state, to_state="recovering", reason="retry_available")
            continue

        if state["current_state"] == "recovering":
            if not _enforce_sel(state=state, sel_fn=sel_fn, boundary="recovery"):
                break
            fre_result = fre_fn({"run_id": state["run_id"], "remaining_budget": state["retry_budget_remaining"]})
            state["active_subsystems"].append("FRE")
            _extract_refs(fre_result if isinstance(fre_result, dict) else {}, produced_refs=state["produced_artifact_refs"], trace_refs=state["trace_refs"])
            if not isinstance(fre_result, dict) or not bool(fre_result.get("recovery_completed", False)):
                _transition(state=state, to_state="blocked", reason="recovery_incomplete")
                state["stop_reason"] = "recovery_incomplete"
                break
            _transition(state=state, to_state="reviewing", reason="recovery_completed")
            continue

        if state["current_state"] == "reviewing":
            if not _enforce_sel(state=state, sel_fn=sel_fn, boundary="review"):
                break
            ril_result = ril_fn({"run_id": state["run_id"], "require_review": require_review})
            state["active_subsystems"].append("RIL")
            _extract_refs(ril_result if isinstance(ril_result, dict) else {}, produced_refs=state["produced_artifact_refs"], trace_refs=state["trace_refs"])
            if not isinstance(ril_result, dict) or not bool(ril_result.get("outputs_exist", False)):
                _transition(state=state, to_state="blocked", reason="review_outputs_missing")
                state["stop_reason"] = "review_outputs_missing"
                break
            _transition(state=state, to_state="closure_decision_pending", reason="review_outputs_available")
            continue

        if state["current_state"] == "closure_decision_pending":
            cde_result = cde_fn({"run_id": state["run_id"], "retry_budget_remaining": state["retry_budget_remaining"]})
            state["active_subsystems"].append("CDE")
            _extract_refs(cde_result if isinstance(cde_result, dict) else {}, produced_refs=state["produced_artifact_refs"], trace_refs=state["trace_refs"])
            decision = cde_result.get("decision_type") if isinstance(cde_result, dict) else None
            state["closure_state"] = str(cde_result.get("closure_state", "pending")) if isinstance(cde_result, dict) else "pending"

            if decision == "lock":
                _transition(state=state, to_state="ready_for_merge", reason="cde_lock")
                state["ready_for_merge"] = True
                state["stop_reason"] = "ready_for_merge"
                break

            if decision == "continue_bounded":
                if state["retry_budget_remaining"] <= 0:
                    _transition(state=state, to_state="exhausted", reason="retry_budget_exhausted")
                    state["stop_reason"] = "retry_budget_exhausted"
                    break
                if not _enforce_sel(state=state, sel_fn=sel_fn, boundary="direction"):
                    break
                prg_result = prg_fn({"run_id": state["run_id"], "closure_decision": cde_result})
                state["active_subsystems"].append("PRG")
                _extract_refs(prg_result if isinstance(prg_result, dict) else {}, produced_refs=state["produced_artifact_refs"], trace_refs=state["trace_refs"])
                state["retry_budget_remaining"] -= 1
                _transition(state=state, to_state="executing", reason="continue_bounded")
                continue

            if decision == "blocked":
                _transition(state=state, to_state="blocked", reason="cde_blocked")
                state["stop_reason"] = "cde_blocked"
                break

            if decision == "escalate":
                _transition(state=state, to_state="escalated", reason="cde_escalate")
                state["stop_reason"] = "cde_escalate"
                break

            _transition(state=state, to_state="blocked", reason="unknown_cde_decision")
            state["stop_reason"] = "unknown_cde_decision"
            break

        raise TopLevelConductorError(f"unsupported state: {state['current_state']}")

    state["active_subsystems"] = sorted(set(state["active_subsystems"]))
    state["produced_artifact_refs"] = sorted(set(state["produced_artifact_refs"]))
    state["trace_refs"] = sorted(set(state["trace_refs"]))
    if state["stop_reason"] is None and state["current_state"] in TERMINAL_STATES:
        state["stop_reason"] = state["current_state"]
    return state
