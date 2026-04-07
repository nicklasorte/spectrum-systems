from __future__ import annotations

import copy
from pathlib import Path

import pytest

from spectrum_systems.contracts import load_example, validate_artifact
from spectrum_systems.modules.runtime.top_level_conductor import run_from_roadmap


VALID_REVIEW = """---
module: tpa
review_date: 2026-04-05
---
# Review

## Overall Assessment
**Overall Verdict: CONDITIONAL PASS**
"""

VALID_ACTIONS = """# Action Tracker

## Critical Items
| ID | Risk | Severity | Recommended Action | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| CR-1 | bounded risk | Critical | governed fix | Closed | ok |

## High-Priority Items
| ID | Risk | Severity | Recommended Action | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| HI-1 | pqx routing gap | High | Add route guard (R2) | Closed | |

## Medium-Priority Items
| ID | Risk | Severity | Recommended Action | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| MI-1 | docs traceability note | Medium | Add note update (R3) | Open | |
"""


def _roadmap() -> dict:
    return copy.deepcopy(load_example("roadmap_two_step_artifact"))


def _paths(tmp_path: Path) -> tuple[str, str]:
    review_path = tmp_path / "review.md"
    action_path = tmp_path / "actions.md"
    review_path.write_text(VALID_REVIEW, encoding="utf-8")
    action_path.write_text(VALID_ACTIONS, encoding="utf-8")
    return str(review_path), str(action_path)


def _ril_stub(payload: dict) -> dict:
    signal = copy.deepcopy(load_example("review_signal_artifact"))
    projection = copy.deepcopy(load_example("review_projection_bundle_artifact"))
    consumers = copy.deepcopy(load_example("review_consumer_output_bundle_artifact"))
    return {
        "outputs_exist": True,
        "artifact_refs": [
            f"review_signal_artifact:{signal['review_signal_id']}",
            f"review_projection_bundle_artifact:{projection['review_projection_bundle_id']}",
            f"review_consumer_output_bundle_artifact:{consumers['review_consumer_output_bundle_id']}",
        ],
        "trace_refs": [payload["trace_id"]],
        "review_signal_artifact": signal,
        "review_projection_bundle_artifact": projection,
        "review_consumer_output_bundle_artifact": consumers,
    }


def _cde_lock_stub(payload: dict) -> dict:
    artifact = copy.deepcopy(load_example("closure_decision_artifact"))
    artifact["decision_type"] = "lock"
    artifact["next_step_class"] = "none"
    artifact["next_step_ref"] = None
    artifact["bounded_next_step_available"] = False
    artifact["run_id"] = payload["run_id"]
    artifact["emitted_at"] = payload["emitted_at"]
    validate_artifact(artifact, "closure_decision_artifact")
    return {
        "decision_type": "lock",
        "next_step_class": "terminal",
        "closure_state": "closed",
        "artifact_refs": [f"closure_decision_artifact:{artifact['closure_decision_id']}"],
        "trace_refs": [payload["trace_id"]],
        "closure_decision_artifact": artifact,
    }


def test_valid_roadmap_executes_two_steps(tmp_path: Path) -> None:
    review_path, action_path = _paths(tmp_path)
    result = run_from_roadmap(
        _roadmap(),
        run_request_overrides={
            "review_path": review_path,
            "action_tracker_path": action_path,
            "runtime_dir": str(tmp_path / "runtime"),
            "emitted_at": "2026-04-06T00:00:00Z",
            "subsystems": {"ril": _ril_stub, "cde": _cde_lock_stub},
        },
    )

    assert result["execution_status"] == "completed"
    assert [s["step_id"] for s in result["step_execution_artifacts"]] == ["step_1", "step_2"]
    assert all(s["execution_status"] in {"succeeded", "fre_recovered"} for s in result["step_execution_artifacts"])


def test_step_failure_triggers_fre(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    review_path, action_path = _paths(tmp_path)

    def _failing_first_pqx(payload: dict) -> dict:
        if payload["run_id"].endswith("step_1"):
            from spectrum_systems.modules.runtime.top_level_conductor import _real_pqx

            base = _real_pqx(payload)
            base["validation_passed"] = False
            return base
        from spectrum_systems.modules.runtime.top_level_conductor import _real_pqx

        return _real_pqx(payload)

    def _fre_stub(payload: dict) -> dict:
        diagnosis = copy.deepcopy(load_example("failure_diagnosis_artifact"))
        diagnosis["emitted_at"] = payload["emitted_at"]
        recovery = copy.deepcopy(load_example("recovery_result_artifact"))
        recovery["recovery_status"] = "recovered"
        recovery["repair_prompt_ref"] = recovery.get("repair_prompt_ref") or "repair_prompt_artifact:rpa-1234567890abcdef"
        repair = copy.deepcopy(load_example("repair_prompt_artifact"))
        return {
            "recovery_completed": True,
            "artifact_refs": [
                f"failure_diagnosis_artifact:{diagnosis['diagnosis_id']}",
                f"repair_prompt_artifact:{repair['repair_prompt_id']}",
                f"recovery_result_artifact:{recovery['recovery_result_id']}",
            ],
            "trace_refs": [payload["trace_id"]],
            "failure_diagnosis_artifact": diagnosis,
            "repair_prompt_artifact": repair,
            "recovery_result_artifact": recovery,
        }

    monkeypatch.setattr(
        "spectrum_systems.modules.runtime.top_level_conductor.validate_system_handoff",
        lambda *_args, **_kwargs: {"allow": True, "violation_codes": []},
    )

    result = run_from_roadmap(
        _roadmap(),
        run_request_overrides={
            "review_path": review_path,
            "action_tracker_path": action_path,
            "runtime_dir": str(tmp_path / "runtime"),
            "emitted_at": "2026-04-06T00:00:00Z",
            "subsystems": {"pqx": _failing_first_pqx, "fre": _fre_stub, "ril": _ril_stub, "cde": _cde_lock_stub},
        },
    )

    first_run = result["tlc_runs"][0]
    assert "FRE" in first_run["active_subsystems"]


def test_missing_input_fails_closed() -> None:
    artifact = _roadmap()
    artifact["steps"][0]["required_inputs"] = []

    with pytest.raises(Exception):
        run_from_roadmap(artifact)


def test_deterministic_replay_identical_outputs(tmp_path: Path) -> None:
    review_path, action_path = _paths(tmp_path)
    overrides = {
        "review_path": review_path,
        "action_tracker_path": action_path,
        "runtime_dir": str(tmp_path / "runtime"),
        "emitted_at": "2026-04-06T00:00:00Z",
        "subsystems": {"ril": _ril_stub, "cde": _cde_lock_stub},
    }

    one = run_from_roadmap(_roadmap(), run_request_overrides=copy.deepcopy(overrides))
    two = run_from_roadmap(_roadmap(), run_request_overrides=copy.deepcopy(overrides))

    assert one == two


def test_invalid_roadmap_rejected() -> None:
    artifact = _roadmap()
    artifact["step_count"] = 3

    with pytest.raises(Exception):
        run_from_roadmap(artifact)


def test_eval_failure_cde_blocked(tmp_path: Path) -> None:
    review_path, action_path = _paths(tmp_path)

    def _blocking_cde(payload: dict) -> dict:
        artifact = copy.deepcopy(load_example("closure_decision_artifact"))
        artifact["closure_decision_id"] = "cda-1111111111111111"
        artifact["run_id"] = payload["run_id"]
        artifact["trace_id"] = payload["trace_id"]
        artifact["emitted_at"] = payload["emitted_at"]
        artifact["decision_type"] = "blocked"
        artifact["next_step_class"] = "none"
        artifact["next_step_ref"] = None
        artifact["bounded_next_step_available"] = False
        artifact["final_summary"] = "Eval failed; execution blocked by CDE."
        validate_artifact(artifact, "closure_decision_artifact")
        return {
            "decision_type": "blocked",
            "next_step_class": "terminal",
            "closure_state": "open",
            "artifact_refs": ["closure_decision_artifact:block"],
            "trace_refs": [payload["trace_id"]],
            "closure_decision_artifact": artifact,
        }

    result = run_from_roadmap(
        _roadmap(),
        run_request_overrides={
            "review_path": review_path,
            "action_tracker_path": action_path,
            "runtime_dir": str(tmp_path / "runtime"),
            "emitted_at": "2026-04-06T00:00:00Z",
            "subsystems": {"ril": _ril_stub, "cde": _blocking_cde},
        },
    )
    assert result["execution_status"] == "blocked"
    assert result["failure_mode"] == "cde_block"
