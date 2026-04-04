from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from spectrum_systems.modules.runtime.pqx_sequence_runner import (
    PQXSequenceRunnerError,
    _complexity_delta,
    _deterministic_selection_from_signals,
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
                "execution_mode": "feature_build",
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
            "complexity_signals": {
                "files_changed_count": 1,
                "lines_added": 22,
                "lines_removed": 8,
                "net_line_delta": 14,
                "functions_added_count": 2,
                "functions_removed_count": 0,
                "helpers_added_count": 1,
                "helpers_removed_count": 0,
                "wrappers_collapsed_count": 0,
                "deletions_count": 0,
                "public_surface_delta_count": 1,
                "approximate_max_nesting_delta": 1,
                "approximate_branching_delta": 1,
                "abstraction_added_count": 1,
                "abstraction_removed_count": 0,
            },
        }
    elif slice_id.endswith("-S"):
        simplify_signals = {
            "files_changed_count": 1,
            "lines_added": 10,
            "lines_removed": 18,
            "net_line_delta": -8,
            "functions_added_count": 1,
            "functions_removed_count": 1,
            "helpers_added_count": 0,
            "helpers_removed_count": 1,
            "wrappers_collapsed_count": 1,
            "deletions_count": 1,
            "public_surface_delta_count": 0,
            "approximate_max_nesting_delta": -1,
            "approximate_branching_delta": -1,
            "abstraction_added_count": 0,
            "abstraction_removed_count": 1,
        }
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
            "complexity_signals": simplify_signals,
            "delete_pass": {
                "deletion_considered": True,
                "deletion_performed": True,
                "deletion_rejected_reason": None,
                "deleted_items": ["obsolete_wrapper:legacy-branch"],
                "collapsed_abstractions": ["adapter-layer:thin-wrapper"],
                "removed_helpers": ["helper:unused_context_glue"],
                "removed_wrappers": ["wrapper:legacy_wrapper"],
                "indirection_avoided": ["direct_call:use_existing_runtime_seam"],
            },
        }
    elif slice_id.endswith("-G"):
        build_signals = {
            "files_changed_count": 1,
            "lines_added": 22,
            "lines_removed": 8,
            "net_line_delta": 14,
            "functions_added_count": 2,
            "functions_removed_count": 0,
            "helpers_added_count": 1,
            "helpers_removed_count": 0,
            "wrappers_collapsed_count": 0,
            "deletions_count": 0,
            "public_surface_delta_count": 1,
            "approximate_max_nesting_delta": 1,
            "approximate_branching_delta": 1,
            "abstraction_added_count": 1,
            "abstraction_removed_count": 0,
        }
        simplify_signals = {
            "files_changed_count": 1,
            "lines_added": 10,
            "lines_removed": 18,
            "net_line_delta": -8,
            "functions_added_count": 1,
            "functions_removed_count": 1,
            "helpers_added_count": 0,
            "helpers_removed_count": 1,
            "wrappers_collapsed_count": 1,
            "deletions_count": 1,
            "public_surface_delta_count": 0,
            "approximate_max_nesting_delta": -1,
            "approximate_branching_delta": -1,
            "abstraction_added_count": 0,
            "abstraction_removed_count": 1,
        }
        selected = _deterministic_selection_from_signals(
            build_signals=build_signals,
            simplify_signals=simplify_signals,
            simplicity_decision="allow",
        )
        result["tpa_gate"] = {
            "artifact_kind": "gate",
            "build_artifact_id": f"tpa:{payload['run_id']}:AI-01-B",
            "simplify_artifact_id": f"tpa:{payload['run_id']}:AI-01-S",
            "behavioral_equivalence": True,
            "contract_valid": True,
            "tests_valid": True,
            "selected_pass": selected,
            "rejected_pass": "pass_1_build" if selected == "pass_2_simplify" else "pass_2_simplify",
            "selection_inputs": {
                "build_artifact_id": f"tpa:{payload['run_id']}:AI-01-B",
                "simplify_artifact_id": f"tpa:{payload['run_id']}:AI-01-S",
                "comparison_inputs_present": True,
            },
            "selection_metrics": {
                "build": build_signals,
                "simplify": simplify_signals,
                "simplify_delta": _complexity_delta(build_signals, simplify_signals),
            },
            "selection_rationale": "equivalence proven and simplify has lower deterministic complexity score",
            "promotion_ready": True,
            "fail_closed_reason": None,
            "context_bundle_ref": "context_bundle_v2:ctx2-abc123abc123abcd",
            "review_signal_refs": ["review_artifact:rvw-001"],
            "eval_signal_refs": ["eval_result:ev-001"],
            "addressed_failure_pattern_refs": ["failure_pattern:unused-helper-regression"],
            "unaddressed_failure_pattern_refs": [],
            "high_risk_unmitigated": False,
            "risk_mitigation_refs": ["mitigation:risk-high-1-covered"],
            "simplicity_review": {
                "decision": "allow",
                "overall_severity": "low",
                "findings": [
                    {"category": "delete_instead_of_abstract", "severity": "low", "message": "Delete-pass completed."}
                ],
                "report_ref": "docs/reviews/2026-04-04-tpa-completion-hardening.md",
            },
            "complexity_regression_gate": {
                "decision": "allow",
                "policy_ref": "policy:tpa-complexity-regression:v1",
                "regression_detected": False,
                "historical_baseline_available": True,
                "historical_baseline_ref": "baseline:tpa:AI-01",
                "exception_justified": False,
            },
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
    assert first["tpa_artifacts"]["AI-01"]["observability_summary"]["artifact_type"] == "tpa_observability_summary"
    assert first["tpa_artifacts"]["AI-01"]["observability_summary"]["metrics"]["simplify_win_rate"] == 1.0
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


def test_tpa_gate_fails_closed_when_selection_inputs_missing(tmp_path: Path) -> None:
    def _bad_gate_executor(payload: dict) -> dict:
        response = _executor(payload)
        if payload["slice_id"].endswith("-G"):
            response["tpa_gate"]["selection_inputs"]["comparison_inputs_present"] = False
        return response

    with pytest.raises(PQXSequenceRunnerError, match="comparison inputs are missing"):
        execute_sequence_run(
            slice_requests=_tpa_slice_requests(),
            state_path=tmp_path / "state.json",
            queue_run_id="queue-tpa-003a",
            run_id="run-tpa-003a",
            trace_id="trace-tpa-batch-003a",
            execute_slice=_bad_gate_executor,
            clock=FixedClock([f"2026-04-03T00:25:{i:02d}Z" for i in range(1, 40)]),
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


def test_tpa_gate_blocks_on_high_severity_simplicity_review(tmp_path: Path) -> None:
    def _bad_review_executor(payload: dict) -> dict:
        response = _executor(payload)
        if payload["slice_id"].endswith("-G"):
            response["tpa_gate"]["simplicity_review"]["decision"] = "block"
            response["tpa_gate"]["simplicity_review"]["overall_severity"] = "critical"
            response["tpa_gate"]["selected_pass"] = "pass_1_build"
            response["tpa_gate"]["rejected_pass"] = "pass_2_simplify"
            response["tpa_gate"]["promotion_ready"] = True
        return response

    with pytest.raises(PQXSequenceRunnerError, match="cannot mark promotion_ready"):
        execute_sequence_run(
            slice_requests=_tpa_slice_requests(),
            state_path=tmp_path / "state-review-block.json",
            queue_run_id="queue-tpa-007",
            run_id="run-tpa-007",
            trace_id="trace-tpa-batch-007",
            execute_slice=_bad_review_executor,
            clock=FixedClock([f"2026-04-03T00:55:{i:02d}Z" for i in range(1, 40)]),
        )


def test_cleanup_only_mode_requires_strict_equivalence_and_replay_ref(tmp_path: Path) -> None:
    requests = _tpa_slice_requests()
    requests[0]["tpa_plan"]["execution_mode"] = "cleanup_only"
    requests[0]["tpa_plan"]["cleanup_scope"] = {
        "bounded_files": ["spectrum_systems/modules/runtime/pqx_sequence_runner.py"],
        "reason": "target complexity debt cleanup",
    }

    def _bad_cleanup_executor(payload: dict) -> dict:
        response = _executor(payload)
        if payload["slice_id"].endswith("-G"):
            response["tpa_gate"]["cleanup_only_validation"] = {
                "mode_enabled": True,
                "equivalence_proven": False,
                "replay_ref": None,
            }
        return response

    with pytest.raises(PQXSequenceRunnerError, match="strict equivalence proof"):
        execute_sequence_run(
            slice_requests=requests,
            state_path=tmp_path / "state-cleanup-only.json",
            queue_run_id="queue-tpa-008",
            run_id="run-tpa-008",
            trace_id="trace-tpa-batch-008",
            execute_slice=_bad_cleanup_executor,
            clock=FixedClock([f"2026-04-03T00:57:{i:02d}Z" for i in range(1, 40)]),
        )


def test_required_scope_non_tpa_slice_fails_closed_with_bypass_signal(tmp_path: Path) -> None:
    def _non_tpa_executor(_: dict) -> dict:
        return {
            "execution_status": "success",
            "slice_execution_record": "records/AI-01.json",
            "done_certification_record": "certs/AI-01.json",
            "pqx_slice_audit_bundle": "audit/AI-01.json",
            "certification_complete": True,
            "audit_complete": True,
        }

    with pytest.raises(PQXSequenceRunnerError, match="tpa_bypass_detected"):
        execute_sequence_run(
            slice_requests=[
                {
                    "slice_id": "AI-01",
                    "trace_id": "trace-direct-ai01",
                    "changed_paths": ["spectrum_systems/modules/runtime/pqx_sequence_runner.py"],
                }
            ],
            state_path=tmp_path / "state-bypass.json",
            queue_run_id="queue-tpa-009",
            run_id="run-tpa-009",
            trace_id="trace-tpa-batch-009",
            execute_slice=_non_tpa_executor,
            clock=FixedClock([f"2026-04-03T01:00:{i:02d}Z" for i in range(1, 30)]),
        )


def test_lightweight_mode_allows_minimal_simplify_artifact(tmp_path: Path) -> None:
    requests = _tpa_slice_requests()
    requests[0]["tpa_plan"]["tpa_mode"] = "lightweight"

    def _lightweight_executor(payload: dict) -> dict:
        response = _executor(payload)
        if payload["slice_id"].endswith("-S"):
            response.pop("tpa_simplify", None)
        return response

    state = execute_sequence_run(
        slice_requests=requests,
        state_path=tmp_path / "state-lightweight.json",
        queue_run_id="queue-tpa-010",
        run_id="run-tpa-010",
        trace_id="trace-tpa-batch-010",
        execute_slice=_lightweight_executor,
        clock=FixedClock([f"2026-04-03T01:10:{i:02d}Z" for i in range(1, 40)]),
    )
    assert state["tpa_artifacts"]["AI-01"]["plan"]["tpa_mode"] == "lightweight"
    assert state["tpa_artifacts"]["AI-01"]["simplify"]["phase"] == "simplify"


def test_lightweight_mode_blocks_when_not_eligible(tmp_path: Path) -> None:
    requests = _tpa_slice_requests()
    requests[0]["tpa_plan"]["tpa_mode"] = "lightweight"
    requests[0]["changed_paths"] = ["a.py", "b.py", "c.py"]
    requests[0]["estimated_loc_delta"] = 250

    with pytest.raises(PQXSequenceRunnerError, match="lightweight mode not eligible"):
        execute_sequence_run(
            slice_requests=requests,
            state_path=tmp_path / "state-lightweight-block.json",
            queue_run_id="queue-tpa-011",
            run_id="run-tpa-011",
            trace_id="trace-tpa-batch-011",
            execute_slice=_executor,
            clock=FixedClock([f"2026-04-03T01:20:{i:02d}Z" for i in range(1, 40)]),
        )


def test_non_tpa_slice_without_scope_evidence_does_not_force_tpa(tmp_path: Path) -> None:
    def _executor_without_tpa(_: dict) -> dict:
        return {
            "execution_status": "success",
            "slice_execution_record": "records/AI-01.json",
            "done_certification_record": "certs/AI-01.json",
            "pqx_slice_audit_bundle": "audit/AI-01.json",
            "certification_complete": True,
            "audit_complete": True,
        }

    state = execute_sequence_run(
        slice_requests=[{"slice_id": "AI-01", "trace_id": "trace-ai-01"}],
        state_path=tmp_path / "state-no-scope.json",
        queue_run_id="queue-tpa-012",
        run_id="run-tpa-012",
        trace_id="trace-tpa-batch-012",
        execute_slice=_executor_without_tpa,
        clock=FixedClock([f"2026-04-03T01:30:{i:02d}Z" for i in range(1, 20)]),
    )
    assert state["status"] == "completed"
