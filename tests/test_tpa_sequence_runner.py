from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from spectrum_systems.modules.runtime.pqx_sequence_runner import (
    PQXSequenceRunnerError,
    _deterministic_gate_selection,
    execute_sequence_run,
)


class FixedClock:
    def __init__(self, stamps: list[str]):
        self._values = [datetime.fromisoformat(v.replace("Z", "+00:00")) for v in stamps]

    def __call__(self):
        if self._values:
            return self._values.pop(0)
        return datetime(2026, 4, 3, 0, 0, 0, tzinfo=timezone.utc)


def _tpa_slice_requests() -> list[dict]:
    return [
        {
            "slice_id": "AI-01-P",
            "trace_id": "trace-tpa-plan",
            "tpa_plan": {
                "artifact_kind": "plan",
                "files_touched": ["spectrum_systems/modules/runtime/pqx_sequence_runner.py"],
                "seams_reused": ["pqx_sequence_runner.execute_sequence_run"],
                "abstraction_intent": "reuse_existing",
                "context_bundle_ref": "context_bundle_v2:ctx2-abc123abc123abcd",
                "known_risk_refs": ["risk_register:risk-high-1"],
                "prior_failure_pattern_refs": ["failure_pattern:unused-helper-regression"],
                "modules_affected": ["spectrum_systems/modules/runtime/pqx_sequence_runner.py"],
                "improvement_objective": "Prevent known context-linked failures while keeping TPA bounded.",
                "context_rationale": "Recent failures and review/eval signals show repeated helper/indirection regressions.",
                "constraints_acknowledged": {"build_small": True, "no_redesign": True},
            },
        },
        {"slice_id": "AI-01-B", "trace_id": "trace-tpa-build"},
        {"slice_id": "AI-01-S", "trace_id": "trace-tpa-simplify"},
        {"slice_id": "AI-01-G", "trace_id": "trace-tpa-gate"},
    ]


def _executor(payload: dict) -> dict:
    slice_id = payload["slice_id"]
    result = {
        "execution_status": "success",
        "slice_execution_record": f"records/{slice_id}.json",
        "done_certification_record": f"certs/{slice_id}.json",
        "pqx_slice_audit_bundle": f"audit/{slice_id}.json",
        "certification_complete": True,
        "audit_complete": True,
    }
    if slice_id.endswith("-B"):
        result["tpa_build"] = {
            "artifact_kind": "build",
            "files_touched": ["spectrum_systems/modules/runtime/pqx_sequence_runner.py"],
            "new_layers": 0,
            "unused_helpers": [],
            "unnecessary_indirection": [],
            "plan_scope_match": True,
            "abstraction_justifications": [],
            "context_bundle_ref": "context_bundle_v2:ctx2-abc123abc123abcd",
            "known_failure_patterns_avoided": ["failure_pattern:unused-helper-regression"],
            "existing_abstractions_satisfied": True,
            "speculative_expansion_detected": False,
            "reused_module_refs": ["spectrum_systems/modules/runtime/pqx_sequence_runner.py"],
        }
    elif slice_id.endswith("-S"):
        result["tpa_simplify"] = {
            "artifact_kind": "simplify",
            "source_build_artifact_id": f"tpa:{payload['run_id']}:AI-01-B",
            "actions": ["reduce_nesting", "rename_for_clarity"],
            "behavior_changed": False,
            "new_layers_introduced": 0,
            "context_bundle_ref": "context_bundle_v2:ctx2-abc123abc123abcd",
            "redundant_code_paths_removed": 1,
            "duplicate_logic_collapsed": [],
            "pattern_consistency_refs": ["pattern:pqx-tpa-runtime-style"],
        }
    elif slice_id.endswith("-G"):
        selected = _deterministic_gate_selection(
            run_id=payload["run_id"],
            step_id="AI-01",
            build_artifact_id=f"tpa:{payload['run_id']}:AI-01-B",
            simplify_artifact_id=f"tpa:{payload['run_id']}:AI-01-S",
        )
        result["tpa_gate"] = {
            "artifact_kind": "gate",
            "build_artifact_id": f"tpa:{payload['run_id']}:AI-01-B",
            "simplify_artifact_id": f"tpa:{payload['run_id']}:AI-01-S",
            "behavioral_equivalence": True,
            "contract_valid": True,
            "tests_valid": True,
            "selected_pass": selected,
            "selection_reason": "equivalence proven and deterministic control selected pass",
            "context_bundle_ref": "context_bundle_v2:ctx2-abc123abc123abcd",
            "review_signal_refs": ["review_artifact:rvw-001"],
            "eval_signal_refs": ["eval_result:ev-001"],
            "addressed_failure_pattern_refs": ["failure_pattern:unused-helper-regression"],
            "unaddressed_failure_pattern_refs": [],
            "high_risk_unmitigated": False,
            "risk_mitigation_refs": ["mitigation:risk-high-1-covered"],
        }
    return result


def test_tpa_happy_path_emits_artifacts_and_deterministic_selection(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    first = execute_sequence_run(
        slice_requests=_tpa_slice_requests(),
        state_path=state_path,
        queue_run_id="queue-tpa-001",
        run_id="run-tpa-001",
        trace_id="trace-tpa-batch-001",
        execute_slice=_executor,
        clock=FixedClock([f"2026-04-03T00:00:{i:02d}Z" for i in range(1, 45)]),
    )
    second = execute_sequence_run(
        slice_requests=_tpa_slice_requests(),
        state_path=tmp_path / "state-second.json",
        queue_run_id="queue-tpa-001",
        run_id="run-tpa-001",
        trace_id="trace-tpa-batch-001",
        execute_slice=_executor,
        clock=FixedClock([f"2026-04-03T00:01:{i:02d}Z" for i in range(1, 45)]),
    )

    assert first["completed_slice_ids"] == ["AI-01-P", "AI-01-B", "AI-01-S", "AI-01-G"]
    assert first["tpa_artifacts"]["AI-01"]["plan"]["phase"] == "plan"
    assert first["tpa_artifacts"]["AI-01"]["build"]["phase"] == "build"
    assert first["tpa_artifacts"]["AI-01"]["simplify"]["phase"] == "simplify"
    assert first["tpa_artifacts"]["AI-01"]["gate"]["phase"] == "gate"
    assert (
        first["tpa_artifacts"]["AI-01"]["gate"]["artifact"]["selected_pass"]
        == second["tpa_artifacts"]["AI-01"]["gate"]["artifact"]["selected_pass"]
    )


def test_tpa_build_small_fails_on_unused_helpers(tmp_path: Path) -> None:
    def _bad_executor(payload: dict) -> dict:
        response = _executor(payload)
        if payload["slice_id"].endswith("-B"):
            response["tpa_build"]["unused_helpers"] = ["helper_that_is_not_used"]
        return response

    with pytest.raises(PQXSequenceRunnerError, match="unused_helpers"):
        execute_sequence_run(
            slice_requests=_tpa_slice_requests(),
            state_path=tmp_path / "state.json",
            queue_run_id="queue-tpa-002",
            run_id="run-tpa-002",
            trace_id="trace-tpa-batch-002",
            execute_slice=_bad_executor,
            clock=FixedClock([f"2026-04-03T00:10:{i:02d}Z" for i in range(1, 40)]),
        )


def test_tpa_gate_fails_on_nondeterministic_selection(tmp_path: Path) -> None:
    def _bad_gate_executor(payload: dict) -> dict:
        response = _executor(payload)
        if payload["slice_id"].endswith("-G"):
            expected = response["tpa_gate"]["selected_pass"]
            response["tpa_gate"]["selected_pass"] = "pass_1_build" if expected == "pass_2_simplify" else "pass_2_simplify"
        return response

    with pytest.raises(PQXSequenceRunnerError, match="deterministic control decision"):
        execute_sequence_run(
            slice_requests=_tpa_slice_requests(),
            state_path=tmp_path / "state.json",
            queue_run_id="queue-tpa-003",
            run_id="run-tpa-003",
            trace_id="trace-tpa-batch-003",
            execute_slice=_bad_gate_executor,
            clock=FixedClock([f"2026-04-03T00:20:{i:02d}Z" for i in range(1, 40)]),
        )


def test_tpa_build_fails_when_prior_failure_patterns_not_avoided(tmp_path: Path) -> None:
    def _bad_build_executor(payload: dict) -> dict:
        response = _executor(payload)
        if payload["slice_id"].endswith("-B"):
            response["tpa_build"]["known_failure_patterns_avoided"] = []
        return response

    with pytest.raises(PQXSequenceRunnerError, match="prior failure patterns"):
        execute_sequence_run(
            slice_requests=_tpa_slice_requests(),
            state_path=tmp_path / "state.json",
            queue_run_id="queue-tpa-004",
            run_id="run-tpa-004",
            trace_id="trace-tpa-batch-004",
            execute_slice=_bad_build_executor,
            clock=FixedClock([f"2026-04-03T00:30:{i:02d}Z" for i in range(1, 40)]),
        )


def test_tpa_gate_blocks_unaddressed_failure_patterns(tmp_path: Path) -> None:
    def _bad_gate_executor(payload: dict) -> dict:
        response = _executor(payload)
        if payload["slice_id"].endswith("-G"):
            response["tpa_gate"]["unaddressed_failure_pattern_refs"] = ["failure_pattern:unused-helper-regression"]
        return response

    with pytest.raises(PQXSequenceRunnerError, match="unaddressed repeated failure patterns"):
        execute_sequence_run(
            slice_requests=_tpa_slice_requests(),
            state_path=tmp_path / "state.json",
            queue_run_id="queue-tpa-005",
            run_id="run-tpa-005",
            trace_id="trace-tpa-batch-005",
            execute_slice=_bad_gate_executor,
            clock=FixedClock([f"2026-04-03T00:40:{i:02d}Z" for i in range(1, 40)]),
        )


def test_tpa_gate_blocks_high_risk_without_mitigation(tmp_path: Path) -> None:
    def _bad_gate_executor(payload: dict) -> dict:
        response = _executor(payload)
        if payload["slice_id"].endswith("-G"):
            response["tpa_gate"]["high_risk_unmitigated"] = True
            response["tpa_gate"]["risk_mitigation_refs"] = []
        return response

    with pytest.raises(PQXSequenceRunnerError, match="high-risk context lacks mitigation"):
        execute_sequence_run(
            slice_requests=_tpa_slice_requests(),
            state_path=tmp_path / "state.json",
            queue_run_id="queue-tpa-006",
            run_id="run-tpa-006",
            trace_id="trace-tpa-batch-006",
            execute_slice=_bad_gate_executor,
            clock=FixedClock([f"2026-04-03T00:50:{i:02d}Z" for i in range(1, 40)]),
        )
