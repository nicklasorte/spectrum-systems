from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

import pytest

from spectrum_systems.modules.prompt_queue.execution_queue_integration import ExecutionQueueIntegrationError
from spectrum_systems.modules.prompt_queue.queue_state_machine import (
    QueueLoopError,
    apply_transition_to_queue_state,
    run_queue_once,
)
from spectrum_systems.modules.prompt_queue.review_parser import ReviewParseError
from spectrum_systems.modules.runtime.roadmap_slice_registry import load_slice_registry


def _base_manifest(*, total_steps: int = 1, allow_warn: bool = False) -> dict:
    return {
        "queue_id": "queue-001",
        "created_at": "2026-03-28T00:00:00Z",
        "version": "1.0.0",
        "steps": [
            {
                "step_id": f"step-{index:03d}",
                "step_type": "execution",
                "input_refs": ["prompt_queue_work_item:wi-001"],
                "expected_outputs": ["prompt_queue_execution_result"],
                "metadata": {
                    "execution_mode": "simulated",
                },
            }
            for index in range(1, total_steps + 1)
        ],
        "execution_policy": {
            "stop_on_block": True,
            "allow_warn": allow_warn,
            "trace_id": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        },
    }


def _base_queue_state(*, total_steps: int = 1) -> dict:
    return {
        "queue_id": "queue-001",
        "queue_status": "running",
        "work_items": [
            {
                "work_item_id": "wi-001",
                "parent_work_item_id": None,
                "prompt_id": "prompt-gpq-001",
                "title": "Governed queue MVP execution loop",
                "status": "runnable",
                "priority": "high",
                "risk_level": "medium",
                "repo": "spectrum-systems",
                "branch": "feature/pqx-queue-05",
                "scope_paths": ["spectrum_systems/modules/prompt_queue"],
                "review_provider_primary": "codex",
                "review_provider_actual": None,
                "review_attempt_count": 0,
                "review_fallback_used": False,
                "review_fallback_reason": None,
                "created_at": "2026-03-28T00:00:00Z",
                "updated_at": "2026-03-28T00:00:00Z",
                "findings_artifact_path": None,
                "repair_prompt_artifact_path": "artifacts/prompt_queue/repair_prompts/wi-001.repair_prompt.json",
                "spawned_from_repair_prompt_artifact_path": None,
                "spawned_from_findings_artifact_path": "artifacts/prompt_queue/findings/wi-001.findings.json",
                "spawned_from_review_artifact_path": "docs/reviews/wi-001.md",
                "repair_loop_generation": 0,
                "child_work_item_ids": [],
                "gating_decision_artifact_path": "artifacts/prompt_queue/gating/wi-001.execution_gating_decision.json",
                "execution_result_artifact_path": None,
                "post_execution_decision_artifact_path": None,
                "next_step_action_artifact_path": None,
                "generation_count": 0,
                "loop_control_decision_artifact_path": None,
                "review_trigger_artifact_path": None,
                "spawned_from_execution_result_artifact_path": None,
                "spawned_from_post_execution_decision_artifact_path": None,
                "spawned_from_loop_control_decision_artifact_path": None,
                "review_invocation_result_artifact_path": None,
                "review_parsing_handoff_artifact_path": None,
                "findings_reentry_artifact_path": None,
                "loop_continuation_artifact_path": None,
                "blocked_recovery_decision_artifact_path": None,
                "retry_count": 0,
                "retry_budget": 2,
                "retry_decision_artifact_path": None,
            }
        ],
        "active_work_item_id": "wi-001",
        "created_at": "2026-03-28T00:00:00Z",
        "updated_at": "2026-03-28T00:00:00Z",
        "current_step_index": 0,
        "total_steps": total_steps,
        "step_results": [],
        "last_updated": "2026-03-28T00:00:00Z",
    }


def test_single_step_success_advances_and_completes(monkeypatch: pytest.MonkeyPatch) -> None:
    queue_state = _base_queue_state(total_steps=1)
    manifest = _base_manifest(total_steps=1)
    calls = {"count": 0}

    captured: dict = {}

    def _execute(**kwargs):
        calls["count"] += 1
        captured.update(kwargs)
        return {"execution_status": "success", "output_reference": "artifacts/output.json"}

    monkeypatch.setattr(
        "spectrum_systems.modules.prompt_queue.execution_queue_integration.run_queue_step_execution_adapter",
        _execute,
    )
    monkeypatch.setattr(
        "spectrum_systems.modules.prompt_queue.review_parser.parse_queue_step_report",
        lambda _result: {
            "step_id": "step-001",
            "queue_id": "queue-001",
            "trace_linkage": "queue-001",
            "source_execution_result_artifact_id": "execres-001",
            "validation_status": "valid",
            "findings": [],
            "severity_summary": {"error": 0, "ambiguous": 0, "warning": 0, "info": 0},
        },
    )
    monkeypatch.setattr(
        "spectrum_systems.modules.prompt_queue.step_decision.build_step_decision",
        lambda _findings: {
            "decision_id": "step-decision-001",
            "step_id": "step-001",
            "queue_id": "queue-001",
            "trace_linkage": "queue-001",
            "decision": "allow",
            "reason_codes": ["clean_findings"],
            "blocking_reasons": [],
            "derived_from_artifacts": ["execres-001"],
            "validation_result_refs": ["validation_result_record:vr-001"],
            "review_evidence_ref": "review_result_artifact:rqx-step-001",
            "preflight_decision": "ALLOW",
        },
    )
    monkeypatch.setattr(
        "spectrum_systems.modules.prompt_queue.post_execution_policy.build_queue_transition_decision",
        lambda _step_decision, _batch_decision: {
            "step_id": "step-001",
            "source_decision_ref": "step-decision-001",
            "batch_decision_artifact_ref": "queue-001:step-001",
            "transition_action": "continue",
            "transition_status": "allowed",
            "reason_codes": ["allow_clean_findings_continue"],
            "blocking_reasons": [],
        },
    )

    updated = run_queue_once(queue_state=queue_state, manifest=manifest)

    assert calls["count"] == 1
    assert updated["current_step_index"] == 1
    assert updated["queue_status"] == "completed"
    assert updated["active_work_item_id"] is None
    assert updated["step_results"][0]["step_id"] == "step-001"
    assert updated["step_results"][0]["status"] == "completed"
    input_refs = captured["input_refs"]
    assert "gating_decision_artifact" not in input_refs
    assert input_refs["permission_decision_record"]["artifact_type"] == "permission_decision_record"
    assert input_refs["permission_decision_record"]["provenance"]["producer"] == "permission_governance"
    assert input_refs["pqx_execution_authority_record"]["artifact_type"] == "pqx_execution_authority_record"


def test_step_failure_halts_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    queue_state = _base_queue_state(total_steps=1)
    manifest = _base_manifest(total_steps=1)

    def _execute(**kwargs):
        raise ExecutionQueueIntegrationError("execution adapter failed")

    monkeypatch.setattr(
        "spectrum_systems.modules.prompt_queue.execution_queue_integration.run_queue_step_execution_adapter",
        _execute,
    )

    with pytest.raises(QueueLoopError, match="execution failed without valid artifact"):
        run_queue_once(queue_state=queue_state, manifest=manifest)


def test_ambiguous_findings_halt(monkeypatch: pytest.MonkeyPatch) -> None:
    queue_state = _base_queue_state(total_steps=1)
    manifest = _base_manifest(total_steps=1)

    monkeypatch.setattr(
        "spectrum_systems.modules.prompt_queue.execution_queue_integration.run_queue_step_execution_adapter",
        lambda **kwargs: {"execution_status": "success", "output_reference": "artifacts/output.json"},
    )
    monkeypatch.setattr(
        "spectrum_systems.modules.prompt_queue.review_parser.parse_queue_step_report",
        lambda _result: (_ for _ in ()).throw(ReviewParseError("ambiguous findings")),
    )

    with pytest.raises(QueueLoopError, match="parsing fails"):
        run_queue_once(queue_state=queue_state, manifest=manifest)


def test_full_queue_completion_when_no_eligible_step() -> None:
    queue_state = _base_queue_state(total_steps=1)
    queue_state["queue_status"] = "running"
    queue_state["current_step_index"] = 1
    queue_state["step_results"] = [
        {
            "step_id": "step-001",
            "step_index": 0,
            "status": "completed",
            "result_ref": "step-decision-001",
            "updated_at": "2026-03-28T00:01:00Z",
        }
    ]
    manifest = _base_manifest(total_steps=1)

    updated = run_queue_once(queue_state=queue_state, manifest=manifest)

    assert updated["queue_status"] == "completed"
    assert updated["current_step_index"] == 1
    assert updated["active_work_item_id"] is None


def test_deterministic_state_transition_application() -> None:
    queue_state = _base_queue_state(total_steps=2)
    transition = {
        "step_id": "step-001",
        "source_decision_ref": "step-decision-001",
        "batch_decision_artifact_ref": "queue-001:step-001",
        "transition_action": "continue",
        "transition_status": "allowed",
    }

    fixed_clock = lambda: datetime(2026, 3, 28, 12, 0, 0, tzinfo=timezone.utc)
    updated_a = apply_transition_to_queue_state(deepcopy(queue_state), deepcopy(transition), clock=fixed_clock)
    updated_b = apply_transition_to_queue_state(deepcopy(queue_state), deepcopy(transition), clock=fixed_clock)

    assert updated_a == updated_b
    assert updated_a["queue_status"] == "running"
    assert updated_a["current_step_index"] == 1


def test_no_step_skipping_fail_closed() -> None:
    queue_state = _base_queue_state(total_steps=2)
    queue_state["current_step_index"] = 1
    queue_state["step_results"] = [
        {
            "step_id": "step-002",
            "step_index": 0,
            "status": "completed",
            "result_ref": "step-decision-002",
            "updated_at": "2026-03-28T00:01:00Z",
        }
    ]
    manifest = _base_manifest(total_steps=2)
    with pytest.raises(QueueLoopError, match="no step skipping permitted"):
        run_queue_once(queue_state=queue_state, manifest=manifest)


def test_slice_registry_contains_prompt_independent_execution_contract() -> None:
    slices = load_slice_registry("contracts/roadmap/slice_registry.json")
    assert slices
    for row in slices:
        assert row["execution_type"] in {"code", "validation", "repair", "governance"}
        assert row["commands"]
        assert row["success_criteria"]


def test_fail_fast_missing_manifest() -> None:
    queue_state = _base_queue_state(total_steps=1)
    with pytest.raises(QueueLoopError, match="missing manifest"):
        run_queue_once(queue_state=queue_state, manifest={})


def test_fail_fast_transition_decision_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    queue_state = _base_queue_state(total_steps=1)
    manifest = _base_manifest(total_steps=1)

    monkeypatch.setattr(
        "spectrum_systems.modules.prompt_queue.execution_queue_integration.run_queue_step_execution_adapter",
        lambda **kwargs: {"execution_status": "success", "output_reference": "artifacts/output.json"},
    )
    monkeypatch.setattr(
        "spectrum_systems.modules.prompt_queue.review_parser.parse_queue_step_report",
        lambda _result: {
            "step_id": "step-001",
            "queue_id": "queue-001",
            "trace_linkage": "queue-001",
            "source_execution_result_artifact_id": "execres-001",
            "validation_status": "valid",
            "findings": [],
            "severity_summary": {"error": 0, "ambiguous": 0, "warning": 0, "info": 0},
        },
    )
    monkeypatch.setattr(
        "spectrum_systems.modules.prompt_queue.step_decision.build_step_decision",
        lambda _findings: {
            "decision_id": "step-decision-001",
            "step_id": "step-001",
            "queue_id": "queue-001",
            "trace_linkage": "queue-001",
            "decision": "allow",
            "reason_codes": ["clean_findings"],
            "blocking_reasons": [],
            "derived_from_artifacts": ["execres-001"],
            "validation_result_refs": ["validation_result_record:vr-001"],
            "review_evidence_ref": "review_result_artifact:rqx-step-001",
            "preflight_decision": "ALLOW",
        },
    )
    monkeypatch.setattr(
        "spectrum_systems.modules.prompt_queue.post_execution_policy.build_queue_transition_decision",
        lambda _step_decision, _batch_decision: None,
    )

    with pytest.raises(QueueLoopError, match="transition decision missing"):
        run_queue_once(queue_state=queue_state, manifest=manifest)


def test_fail_fast_multiple_steps_executed_in_one_loop() -> None:
    queue_state = _base_queue_state(total_steps=2)
    queue_state["current_step_index"] = 2
    queue_state["step_results"] = [
        {
            "step_id": "step-001",
            "step_index": 0,
            "status": "completed",
            "result_ref": "step-decision-001",
            "updated_at": "2026-03-28T00:01:00Z",
        },
        {
            "step_id": "step-002",
            "step_index": 1,
            "status": "blocked",
            "result_ref": "step-decision-002",
            "updated_at": "2026-03-28T00:02:00Z",
        },
    ]
    manifest = _base_manifest(total_steps=2)

    with pytest.raises(QueueLoopError, match="no eligible next step"):
        run_queue_once(queue_state=queue_state, manifest=manifest)


def test_governed_build_requires_validation_before_decision(monkeypatch: pytest.MonkeyPatch) -> None:
    queue_state = _base_queue_state(total_steps=1)
    manifest = _base_manifest(total_steps=1)

    monkeypatch.setattr(
        "spectrum_systems.modules.prompt_queue.execution_queue_integration.run_queue_step_execution_adapter",
        lambda **kwargs: {"execution_status": "success", "output_reference": "artifacts/output.json"},
    )
    monkeypatch.setattr(
        "spectrum_systems.modules.prompt_queue.review_parser.parse_queue_step_report",
        lambda _result: {
            "step_id": "step-001",
            "queue_id": "queue-001",
            "trace_linkage": "queue-001",
            "source_execution_result_artifact_id": "execres-001",
            "validation_status": "valid",
            "review_evidence_ref": "review_result_artifact:rqx-step-001",
            "validation_result_refs": [],
            "preflight_decision": "ALLOW",
            "findings": [],
            "severity_summary": {"error": 0, "ambiguous": 0, "warning": 0, "info": 0},
        },
    )

    with pytest.raises(QueueLoopError, match="step decision failed closed"):
        run_queue_once(queue_state=queue_state, manifest=manifest)


def test_governed_build_requires_review_before_decision(monkeypatch: pytest.MonkeyPatch) -> None:
    queue_state = _base_queue_state(total_steps=1)
    manifest = _base_manifest(total_steps=1)

    monkeypatch.setattr(
        "spectrum_systems.modules.prompt_queue.execution_queue_integration.run_queue_step_execution_adapter",
        lambda **kwargs: {"execution_status": "success", "output_reference": "artifacts/output.json"},
    )
    monkeypatch.setattr(
        "spectrum_systems.modules.prompt_queue.review_parser.parse_queue_step_report",
        lambda _result: {
            "step_id": "step-001",
            "queue_id": "queue-001",
            "trace_linkage": "queue-001",
            "source_execution_result_artifact_id": "execres-001",
            "validation_status": "valid",
            "review_evidence_ref": "",
            "validation_result_refs": ["validation_result_record:vr-001"],
            "preflight_decision": "ALLOW",
            "findings": [],
            "severity_summary": {"error": 0, "ambiguous": 0, "warning": 0, "info": 0},
        },
    )

    with pytest.raises(QueueLoopError, match="step decision failed closed"):
        run_queue_once(queue_state=queue_state, manifest=manifest)


def test_governed_build_requires_review_result_artifact_ref(monkeypatch: pytest.MonkeyPatch) -> None:
    queue_state = _base_queue_state(total_steps=1)
    manifest = _base_manifest(total_steps=1)

    monkeypatch.setattr(
        "spectrum_systems.modules.prompt_queue.execution_queue_integration.run_queue_step_execution_adapter",
        lambda **kwargs: {"execution_status": "success", "output_reference": "artifacts/output.json"},
    )
    monkeypatch.setattr(
        "spectrum_systems.modules.prompt_queue.review_parser.parse_queue_step_report",
        lambda _result: {
            "step_id": "step-001",
            "queue_id": "queue-001",
            "trace_linkage": "queue-001",
            "source_execution_result_artifact_id": "execres-001",
            "validation_status": "valid",
            "review_evidence_ref": "review_note:rqx-step-001",
            "validation_result_refs": ["validation_result_record:vr-001"],
            "preflight_decision": "ALLOW",
            "findings": [],
            "severity_summary": {"error": 0, "ambiguous": 0, "warning": 0, "info": 0},
        },
    )

    with pytest.raises(QueueLoopError, match="batch decision missing or invalid"):
        run_queue_once(queue_state=queue_state, manifest=manifest)


def test_governed_build_requires_validation_result_record_refs(monkeypatch: pytest.MonkeyPatch) -> None:
    queue_state = _base_queue_state(total_steps=1)
    manifest = _base_manifest(total_steps=1)

    monkeypatch.setattr(
        "spectrum_systems.modules.prompt_queue.execution_queue_integration.run_queue_step_execution_adapter",
        lambda **kwargs: {"execution_status": "success", "output_reference": "artifacts/output.json"},
    )
    monkeypatch.setattr(
        "spectrum_systems.modules.prompt_queue.review_parser.parse_queue_step_report",
        lambda _result: {
            "step_id": "step-001",
            "queue_id": "queue-001",
            "trace_linkage": "queue-001",
            "source_execution_result_artifact_id": "execres-001",
            "validation_status": "valid",
            "review_evidence_ref": "review_result_artifact:rqx-step-001",
            "validation_result_refs": ["validation_report:vr-001"],
            "preflight_decision": "ALLOW",
            "findings": [],
            "severity_summary": {"error": 0, "ambiguous": 0, "warning": 0, "info": 0},
        },
    )

    with pytest.raises(QueueLoopError, match="batch decision missing or invalid"):
        run_queue_once(queue_state=queue_state, manifest=manifest)


def test_governed_progression_requires_batch_decision_artifact() -> None:
    queue_state = _base_queue_state(total_steps=1)
    with pytest.raises(QueueLoopError, match="batch_decision_artifact_ref"):
        apply_transition_to_queue_state(
            queue_state,
            {
                "step_id": "step-001",
                "source_decision_ref": "step-decision-001",
                "transition_action": "continue",
                "transition_status": "allowed",
            },
        )


def test_pqx_completion_does_not_imply_decision(monkeypatch: pytest.MonkeyPatch) -> None:
    queue_state = _base_queue_state(total_steps=1)
    manifest = _base_manifest(total_steps=1)

    monkeypatch.setattr(
        "spectrum_systems.modules.prompt_queue.execution_queue_integration.run_queue_step_execution_adapter",
        lambda **kwargs: {"execution_status": "success", "output_reference": "artifacts/output.json"},
    )
    monkeypatch.setattr(
        "spectrum_systems.modules.prompt_queue.review_parser.parse_queue_step_report",
        lambda _result: (_ for _ in ()).throw(ReviewParseError("missing governed review output")),
    )

    with pytest.raises(QueueLoopError, match="parsing fails"):
        run_queue_once(queue_state=queue_state, manifest=manifest)


def test_batch_decision_artifact_allows_progression_when_complete(monkeypatch: pytest.MonkeyPatch) -> None:
    queue_state = _base_queue_state(total_steps=1)
    manifest = _base_manifest(total_steps=1)

    monkeypatch.setattr(
        "spectrum_systems.modules.prompt_queue.execution_queue_integration.run_queue_step_execution_adapter",
        lambda **kwargs: {"execution_status": "success", "output_reference": "artifacts/output.json"},
    )
    monkeypatch.setattr(
        "spectrum_systems.modules.prompt_queue.review_parser.parse_queue_step_report",
        lambda _result: {
            "step_id": "step-001",
            "queue_id": "queue-001",
            "trace_linkage": "queue-001",
            "source_execution_result_artifact_id": "execres-001",
            "validation_status": "valid",
            "review_evidence_ref": "review_result_artifact:rqx-step-001",
            "validation_result_refs": ["validation_result_record:vr-001"],
            "preflight_decision": "ALLOW",
            "findings": [],
            "severity_summary": {"error": 0, "ambiguous": 0, "warning": 0, "info": 0},
        },
    )

    updated = run_queue_once(queue_state=queue_state, manifest=manifest)
    assert updated["queue_status"] == "completed"


def test_fix_path_reenters_brf(monkeypatch: pytest.MonkeyPatch) -> None:
    queue_state = _base_queue_state(total_steps=1)
    queue_state["work_items"][0]["repair_loop_generation"] = 1
    manifest = _base_manifest(total_steps=1)

    monkeypatch.setattr(
        "spectrum_systems.modules.prompt_queue.execution_queue_integration.run_queue_step_execution_adapter",
        lambda **kwargs: {"execution_status": "failure", "output_reference": "artifacts/output-failed.json"},
    )
    monkeypatch.setattr(
        "spectrum_systems.modules.prompt_queue.review_parser.parse_queue_step_report",
        lambda _result: {
            "step_id": "step-001",
            "queue_id": "queue-001",
            "trace_linkage": "queue-001",
            "source_execution_result_artifact_id": "execres-001",
            "validation_status": "valid",
            "review_evidence_ref": "review_result_artifact:rqx-step-001",
            "validation_result_refs": ["validation_result_record:vr-001"],
            "preflight_decision": "ALLOW",
            "findings": [{"finding_type": "execution_status", "severity": "error"}],
            "severity_summary": {"error": 1, "ambiguous": 0, "warning": 0, "info": 0},
        },
    )

    updated = run_queue_once(queue_state=queue_state, manifest=manifest)
    assert updated["queue_status"] == "blocked"
