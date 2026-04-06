from __future__ import annotations

from spectrum_systems.modules.runtime.top_level_conductor import run_top_level_conductor


def _base_request() -> dict:
    return {
        "objective": "orchestrate bounded run",
        "branch_ref": "refs/heads/main",
        "run_id": "tlc-test-run",
        "retry_budget": 1,
        "require_review": True,
        "require_recovery": True,
    }


def _allow_sel(_: dict) -> dict:
    return {"allowed": True, "trace_refs": ["trace-sel"]}


def test_basic_run_ready_for_merge() -> None:
    request = _base_request()
    request["subsystems"] = {
        "sel": _allow_sel,
        "pqx": lambda _: {"entry_valid": True, "validation_passed": True, "artifact_refs": ["pqx:ok"]},
        "tpa": lambda _: {"discipline_status": "accepted"},
        "ril": lambda _: {"outputs_exist": True, "artifact_refs": ["ril:ok"]},
        "cde": lambda _: {"decision_type": "lock", "closure_state": "closed", "artifact_refs": ["cde:lock"]},
    }

    result = run_top_level_conductor(request)

    assert result["current_state"] == "ready_for_merge"
    assert result["ready_for_merge"] is True
    assert result["stop_reason"] == "ready_for_merge"


def test_failure_recovery_continue_ready_for_merge() -> None:
    request = _base_request()
    pqx_results = iter(
        [
            {"entry_valid": True, "validation_passed": False, "artifact_refs": ["pqx:fail"]},
            {"entry_valid": True, "validation_passed": True, "artifact_refs": ["pqx:pass"]},
        ]
    )
    cde_results = iter(
        [
            {"decision_type": "continue_bounded", "closure_state": "open", "artifact_refs": ["cde:continue"]},
            {"decision_type": "lock", "closure_state": "closed", "artifact_refs": ["cde:lock"]},
        ]
    )
    request["subsystems"] = {
        "sel": _allow_sel,
        "pqx": lambda _: next(pqx_results),
        "tpa": lambda _: {"discipline_status": "accepted"},
        "fre": lambda _: {"recovery_completed": True, "artifact_refs": ["fre:ok"]},
        "ril": lambda _: {"outputs_exist": True, "artifact_refs": ["ril:ok"]},
        "cde": lambda _: next(cde_results),
        "prg": lambda _: {"proposed": True, "artifact_refs": ["prg:next"]},
    }

    result = run_top_level_conductor(request)

    assert result["current_state"] == "ready_for_merge"
    assert "PRG" in result["active_subsystems"]
    assert result["retry_budget_remaining"] == 0


def test_failure_with_no_recovery_blocks() -> None:
    request = _base_request()
    request["require_recovery"] = False
    request["subsystems"] = {
        "sel": _allow_sel,
        "pqx": lambda _: {"entry_valid": True, "validation_passed": False},
        "tpa": lambda _: {"discipline_status": "accepted"},
    }

    result = run_top_level_conductor(request)

    assert result["current_state"] == "blocked"
    assert result["stop_reason"] == "recovery_not_permitted"


def test_retry_budget_exhausted() -> None:
    request = _base_request()
    request["retry_budget"] = 0
    request["subsystems"] = {
        "sel": _allow_sel,
        "pqx": lambda _: {"entry_valid": True, "validation_passed": False},
        "tpa": lambda _: {"discipline_status": "accepted"},
    }

    result = run_top_level_conductor(request)

    assert result["current_state"] == "exhausted"
    assert result["stop_reason"] == "retry_budget_exhausted"


def test_sel_block_immediate() -> None:
    request = _base_request()
    request["subsystems"] = {
        "sel": lambda _: {"allowed": False, "reason": "policy_block"},
    }

    result = run_top_level_conductor(request)

    assert result["current_state"] == "blocked"
    assert result["stop_reason"].startswith("sel_block")
    assert result["phase_history"] == [{"from": "requested", "to": "blocked", "reason": "sel_block:state_transition"}]


def test_determinism_same_input_same_output() -> None:
    request = _base_request()
    request["run_id"] = "tlc-determinism"
    request["subsystems"] = {
        "sel": _allow_sel,
        "pqx": lambda _: {"entry_valid": True, "validation_passed": True},
        "tpa": lambda _: {"discipline_status": "accepted"},
        "ril": lambda _: {"outputs_exist": True},
        "cde": lambda _: {"decision_type": "lock", "closure_state": "closed"},
    }

    one = run_top_level_conductor(request)
    two = run_top_level_conductor(request)

    assert one == two


def test_no_direct_execution_outside_pqx() -> None:
    request = _base_request()
    calls = {"pqx": 0, "tpa": 0}

    def _pqx(_: dict) -> dict:
        calls["pqx"] += 1
        return {"entry_valid": True, "validation_passed": True}

    def _tpa(_: dict) -> dict:
        calls["tpa"] += 1
        return {"discipline_status": "accepted"}

    request["subsystems"] = {
        "sel": _allow_sel,
        "pqx": _pqx,
        "tpa": _tpa,
        "ril": lambda _: {"outputs_exist": True},
        "cde": lambda _: {"decision_type": "lock", "closure_state": "closed"},
    }

    result = run_top_level_conductor(request)

    assert result["current_state"] == "ready_for_merge"
    assert calls["pqx"] == 1
    assert calls["tpa"] == 1


def test_consumes_cde_output_without_reinterpretation() -> None:
    request = _base_request()
    request["subsystems"] = {
        "sel": _allow_sel,
        "pqx": lambda _: {"entry_valid": True, "validation_passed": True},
        "tpa": lambda _: {"discipline_status": "accepted"},
        "ril": lambda _: {"outputs_exist": True},
        "cde": lambda _: {"decision_type": "blocked", "closure_state": "pending_review"},
    }

    result = run_top_level_conductor(request)

    assert result["current_state"] == "blocked"
    assert result["stop_reason"] == "cde_blocked"
    assert result["closure_state"] == "pending_review"
