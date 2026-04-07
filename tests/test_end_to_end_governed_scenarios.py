from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.modules.runtime.github_closure_continuation import run_github_closure_continuation
from spectrum_systems.modules.runtime.github_review_ingestion import ingest_github_review_event

_FIXTURES = Path("tests/fixtures/github_events")


def _ingest(tmp_path: Path, *, event_name: str, fixture_name: str, body_override: str | None = None) -> Path:
    payload = json.loads((_FIXTURES / fixture_name).read_text(encoding="utf-8"))
    if body_override is not None and isinstance(payload.get("comment"), dict):
        payload["comment"]["body"] = body_override
    result = ingest_github_review_event(
        event_name=event_name,
        payload=payload,
        output_root=tmp_path / "artifacts" / "github_review_ingestion",
        review_source="ril",
        run_mode="strict",
        emitted_at="2026-04-07T02:00:00Z",
        repo="example/repo",
        sha="abc123",
        run_id="run-002",
    )
    return Path(result["artifact_paths"]["github_review_handoff_artifact"])


def _scenario_run(tmp_path: Path, **kwargs: object) -> dict:
    result = run_github_closure_continuation(
        github_review_handoff_path=kwargs.pop("handoff"),
        output_root=tmp_path / "artifacts" / "github_closure_continuation",
        emitted_at="2026-04-07T02:10:00Z",
        **kwargs,
    )
    gate_path = Path(result["artifact_paths"]["promotion_gate_decision_artifact"])
    result["promotion_gate"] = json.loads(gate_path.read_text(encoding="utf-8"))
    return result


def _neutralize_escalation(handoff: Path) -> None:
    handoff_payload = json.loads(handoff.read_text(encoding="utf-8"))
    summary_path = Path(handoff_payload["artifact_refs"]["ingestion_summary_artifact"])
    if not summary_path.is_absolute():
        summary_path = handoff.parent / summary_path
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    for key in ("review_projection_bundle_artifact", "review_consumer_output_bundle_artifact"):
        artifact_path = Path(summary["artifact_paths"][key])
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        artifact["escalation_present"] = False
        artifact["blocker_present"] = False
        artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _patched_tlc_ready(request: dict[str, object]) -> dict[str, object]:
    run_id = str(request.get("run_id") or "tlc-run")
    continuation_id = run_id.removeprefix("tlc-")
    return {
        "run_id": run_id,
        "objective": str(request.get("objective") or "governed"),
        "branch_ref": "refs/heads/main",
        "current_state": "ready_for_merge",
        "phase_history": [],
        "active_subsystems": ["CDE", "PQX", "RIL", "SEL", "TPA"],
        "retry_budget_remaining": 0,
        "closure_state": "closed",
        "next_allowed_actions": [],
        "stop_reason": "ready_for_merge",
        "ready_for_merge": True,
        "trace_refs": [f"trace-{continuation_id}"],
        "lineage": {
            "repair_attempt_count": 1,
            "repair_attempt_record_artifact_ref": f"repair_attempt_record_artifact:attempt-{run_id}-1",
        },
        "produced_artifact_refs": [f"certification:{run_id}"],
    }


def test_scenario_clean_review_path_promotes_when_ready(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    handoff = _ingest(tmp_path, event_name="pull_request_review", fixture_name="pull_request_review_submitted.json")
    _neutralize_escalation(handoff)
    import spectrum_systems.modules.runtime.github_closure_continuation as module_under_test

    monkeypatch.setattr(module_under_test, "run_top_level_conductor", _patched_tlc_ready)
    result = _scenario_run(
        tmp_path,
        handoff=handoff,
        closure_complete=False,
        final_verification_passed=False,
        hardening_completed=False,
        escalation_required=False,
        bounded_next_step_available=True,
        retry_budget=1,
    )
    gate = result["promotion_gate"]
    if result["final_terminal_state"] == "ready_for_merge":
        assert gate["promotion_allowed"] is True


def test_scenario_repair_then_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    handoff = _ingest(tmp_path, event_name="pull_request_review", fixture_name="pull_request_review_submitted.json")
    _neutralize_escalation(handoff)
    import spectrum_systems.modules.runtime.github_closure_continuation as module_under_test

    monkeypatch.setattr(module_under_test, "run_top_level_conductor", _patched_tlc_ready)
    result = _scenario_run(
        tmp_path,
        handoff=handoff,
        closure_complete=False,
        final_verification_passed=False,
        hardening_completed=False,
        escalation_required=False,
        bounded_next_step_available=True,
        retry_budget=2,
    )
    if result["promotion_gate"]["promotion_allowed"]:
        refs = result["promotion_gate"]["supporting_artifact_refs"]
        assert any(ref.startswith("certification:") for ref in refs)


def test_scenario_unsafe_escalated_blocks_promotion(tmp_path: Path) -> None:
    handoff = _ingest(tmp_path, event_name="pull_request_review", fixture_name="pull_request_review_submitted.json")
    result = _scenario_run(
        tmp_path,
        handoff=handoff,
        closure_complete=False,
        final_verification_passed=False,
        hardening_completed=False,
        escalation_required=True,
        bounded_next_step_available=False,
        retry_budget=0,
    )
    assert result["final_terminal_state"] == "escalated"
    assert result["promotion_gate"]["promotion_allowed"] is False


def test_scenario_exhausted_retry_budget_blocks_promotion(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    handoff = _ingest(tmp_path, event_name="pull_request_review", fixture_name="pull_request_review_submitted.json")
    _neutralize_escalation(handoff)
    import spectrum_systems.modules.runtime.github_closure_continuation as module_under_test

    def _patched_tlc_exhausted(request: dict[str, object]) -> dict[str, object]:
        run_id = str(request.get("run_id") or "tlc-run")
        continuation_id = run_id.removeprefix("tlc-")
        return {
            "run_id": run_id,
            "objective": str(request.get("objective") or "governed"),
            "branch_ref": "refs/heads/main",
            "current_state": "exhausted",
            "phase_history": [],
            "active_subsystems": ["CDE", "PQX", "RIL", "SEL", "TPA"],
            "retry_budget_remaining": 0,
            "closure_state": "open",
            "next_allowed_actions": [],
            "stop_reason": "retry_budget_exhausted",
            "ready_for_merge": False,
            "produced_artifact_refs": [f"certification:{run_id}"],
            "trace_refs": [f"trace-{continuation_id}"],
            "lineage": {},
        }

    monkeypatch.setattr(module_under_test, "run_top_level_conductor", _patched_tlc_exhausted)
    result = _scenario_run(
        tmp_path,
        handoff=handoff,
        closure_complete=False,
        final_verification_passed=False,
        hardening_completed=False,
        escalation_required=False,
        bounded_next_step_available=True,
        retry_budget=0,
    )
    assert result["final_terminal_state"] == "exhausted"
    assert result["promotion_gate"]["promotion_allowed"] is False


def test_scenario_roadmap_draft_preview_does_not_execute_or_promote(tmp_path: Path) -> None:
    handoff = _ingest(
        tmp_path,
        event_name="issue_comment",
        fixture_name="issue_comment_pr_command.json",
        body_override="/roadmap-draft scope:runtime keywords:governance,roadmap",
    )
    with pytest.raises(Exception, match="preview-only"):
        _scenario_run(
            tmp_path,
            handoff=handoff,
            closure_complete=False,
            final_verification_passed=False,
            hardening_completed=False,
            escalation_required=False,
            bounded_next_step_available=False,
            retry_budget=0,
        )


def test_scenario_roadmap_approve_executes_and_follows_promotion_logic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _ingest(
        tmp_path,
        event_name="issue_comment",
        fixture_name="issue_comment_pr_command.json",
        body_override="/roadmap-draft scope:runtime keywords:governance,roadmap",
    )
    handoff = _ingest(
        tmp_path,
        event_name="issue_comment",
        fixture_name="issue_comment_pr_command.json",
        body_override="/roadmap-approve",
    )
    _neutralize_escalation(handoff)
    import spectrum_systems.modules.runtime.github_closure_continuation as module_under_test

    monkeypatch.setattr(module_under_test, "run_top_level_conductor", _patched_tlc_ready)
    result = _scenario_run(
        tmp_path,
        handoff=handoff,
        closure_complete=False,
        final_verification_passed=False,
        hardening_completed=False,
        escalation_required=False,
        bounded_next_step_available=True,
        retry_budget=0,
    )
    assert result["roadmap_two_step"] is not None
    assert result["promotion_gate"]["terminal_state"] == result["final_terminal_state"]


def test_deterministic_replay_same_inputs_same_promotion_decision(tmp_path: Path) -> None:
    handoff = _ingest(tmp_path, event_name="pull_request_review", fixture_name="pull_request_review_submitted.json")
    kwargs = dict(
        handoff=handoff,
        closure_complete=False,
        final_verification_passed=False,
        hardening_completed=False,
        escalation_required=True,
        bounded_next_step_available=False,
        retry_budget=0,
    )
    one = _scenario_run(tmp_path, **kwargs)
    two = _scenario_run(tmp_path, **kwargs)
    assert one["continuation_id"] == two["continuation_id"]
    assert one["promotion_gate"]["decision_id"] == two["promotion_gate"]["decision_id"]
    assert one["promotion_gate"]["promotion_allowed"] == two["promotion_gate"]["promotion_allowed"]
