from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.github_closure_continuation import (
    GithubClosureContinuationError,
    run_github_closure_continuation,
)
from spectrum_systems.modules.runtime.github_review_ingestion import ingest_github_review_event


_FIXTURES = Path("tests/fixtures/github_events")


def _load_fixture(name: str) -> dict:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


def _build_ingestion_summary(tmp_path: Path) -> tuple[Path, Path]:
    payload = _load_fixture("pull_request_review_submitted.json")
    result = ingest_github_review_event(
        event_name="pull_request_review",
        payload=payload,
        output_root=tmp_path / "artifacts" / "github_review_ingestion",
        review_source="ril",
        run_mode="strict",
        emitted_at="2026-04-06T12:00:00Z",
        repo="example/repo",
        sha="abc123",
        run_id="555",
    )
    summary_path = tmp_path / "ingestion_result.json"
    summary_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    handoff_path = Path(result["artifact_paths"]["github_review_handoff_artifact"])
    return summary_path, handoff_path


def _build_ingestion_summary_with_roadmap(tmp_path: Path) -> tuple[Path, Path]:
    payload = _load_fixture("issue_comment_pr_command.json")
    payload["comment"]["body"] = "/roadmap-2step scope:runtime keywords:governance,roadmap"
    result = ingest_github_review_event(
        event_name="issue_comment",
        payload=payload,
        output_root=tmp_path / "artifacts" / "github_review_ingestion",
        review_source="ril",
        run_mode="strict",
        emitted_at="2026-04-06T12:00:00Z",
        repo="example/repo",
        sha="abc123",
        run_id="555",
    )
    summary_path = tmp_path / "ingestion_result.json"
    summary_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    handoff_path = Path(result["artifact_paths"]["github_review_handoff_artifact"])
    return summary_path, handoff_path


def _neutralize_escalation(summary_path: Path) -> None:
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    for key in ("review_projection_bundle_artifact", "review_consumer_output_bundle_artifact"):
        artifact_path = Path(summary["artifact_paths"][key])
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        artifact["escalation_present"] = False
        artifact["blocker_present"] = False
        artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_valid_outputs_cde_lock_no_tlc(tmp_path: Path) -> None:
    summary_path, handoff_path = _build_ingestion_summary(tmp_path)
    _neutralize_escalation(summary_path)

    result = run_github_closure_continuation(
        github_review_handoff_path=handoff_path,
        output_root=tmp_path / "artifacts" / "github_closure_continuation",
        emitted_at="2026-04-06T12:10:00Z",
        closure_complete=True,
        final_verification_passed=True,
        hardening_completed=True,
        escalation_required=False,
        bounded_next_step_available=False,
        retry_budget=1,
    )

    assert result["cde_decision"] == "lock"
    assert result["tlc_ran"] is False
    assert result["final_terminal_state"] == "blocked"
    assert result["branch_update_policy"]["branch_update_allowed"] is False
    assert result["artifact_paths"]["top_level_conductor_run_artifact"] is None
    assert result["artifact_paths"]["promotion_gate_decision_artifact"] is not None

    closure = json.loads(Path(result["artifact_paths"]["closure_decision_artifact"]).read_text(encoding="utf-8"))
    validate_artifact(closure, "closure_decision_artifact")
    promotion_gate = json.loads(Path(result["artifact_paths"]["promotion_gate_decision_artifact"]).read_text(encoding="utf-8"))
    validate_artifact(promotion_gate, "promotion_gate_decision_artifact")
    assert promotion_gate["promotion_allowed"] is False
    assert "top_level_conductor_run_artifact" in promotion_gate["missing_requirements"]


def test_valid_outputs_continue_bounded_runs_tlc(tmp_path: Path) -> None:
    summary_path, handoff_path = _build_ingestion_summary(tmp_path)
    _neutralize_escalation(summary_path)

    result = run_github_closure_continuation(
        github_review_handoff_path=handoff_path,
        output_root=tmp_path / "artifacts" / "github_closure_continuation",
        emitted_at="2026-04-06T12:20:00Z",
        closure_complete=False,
        final_verification_passed=False,
        hardening_completed=False,
        escalation_required=False,
        bounded_next_step_available=True,
        retry_budget=0,
    )

    assert result["cde_decision"] == "continue_bounded"
    assert result["tlc_ran"] is True
    assert result["final_terminal_state"] in {"ready_for_merge", "blocked", "exhausted", "escalated"}
    assert result["artifact_paths"]["promotion_gate_decision_artifact"] is not None

    tlc_path = result["artifact_paths"]["top_level_conductor_run_artifact"]
    assert tlc_path is not None
    tlc_artifact = json.loads(Path(tlc_path).read_text(encoding="utf-8"))
    validate_artifact(tlc_artifact, "top_level_conductor_run_artifact")

    prompt_path = result["artifact_paths"]["next_step_prompt_artifact"]
    assert prompt_path is not None
    prompt = json.loads(Path(prompt_path).read_text(encoding="utf-8"))
    validate_artifact(prompt, "next_step_prompt_artifact")
    promotion_gate = json.loads(Path(result["artifact_paths"]["promotion_gate_decision_artifact"]).read_text(encoding="utf-8"))
    validate_artifact(promotion_gate, "promotion_gate_decision_artifact")
    assert promotion_gate["terminal_state"] == result["final_terminal_state"]
    assert result["branch_update_policy"]["branch_update_allowed"] == promotion_gate["promotion_allowed"]


def test_blocked_decision_does_not_invoke_tlc(tmp_path: Path) -> None:
    summary_path, handoff_path = _build_ingestion_summary(tmp_path)
    _neutralize_escalation(summary_path)

    result = run_github_closure_continuation(
        github_review_handoff_path=handoff_path,
        output_root=tmp_path / "artifacts" / "github_closure_continuation",
        emitted_at="2026-04-06T12:25:00Z",
        closure_complete=False,
        final_verification_passed=False,
        hardening_completed=False,
        escalation_required=False,
        bounded_next_step_available=False,
        retry_budget=1,
    )

    assert result["cde_decision"] == "blocked"
    assert result["tlc_ran"] is False
    assert result["final_terminal_state"] == "blocked"


def test_escalate_decision_does_not_invoke_tlc(tmp_path: Path) -> None:
    summary_path, handoff_path = _build_ingestion_summary(tmp_path)

    result = run_github_closure_continuation(
        github_review_handoff_path=handoff_path,
        output_root=tmp_path / "artifacts" / "github_closure_continuation",
        emitted_at="2026-04-06T12:30:00Z",
        closure_complete=False,
        final_verification_passed=False,
        hardening_completed=False,
        escalation_required=True,
        bounded_next_step_available=False,
        retry_budget=1,
    )

    assert result["cde_decision"] == "escalate"
    assert result["tlc_ran"] is False
    assert result["final_terminal_state"] == "escalated"


def test_missing_required_ril_artifact_fails_closed(tmp_path: Path) -> None:
    _, handoff_path = _build_ingestion_summary(tmp_path)
    handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
    handoff["artifact_refs"].pop("review_projection_bundle_artifact")
    handoff_path.write_text(json.dumps(handoff, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(Exception, match="required property|missing required handoff artifact ref"):
        run_github_closure_continuation(
            github_review_handoff_path=handoff_path,
            output_root=tmp_path / "artifacts" / "github_closure_continuation",
            emitted_at="2026-04-06T12:30:00Z",
            closure_complete=False,
            final_verification_passed=False,
            hardening_completed=False,
            escalation_required=False,
            bounded_next_step_available=True,
            retry_budget=1,
        )


def test_deterministic_path_generation(tmp_path: Path) -> None:
    summary_path, handoff_path = _build_ingestion_summary(tmp_path)

    kwargs = {
        "github_review_handoff_path": handoff_path,
        "output_root": tmp_path / "artifacts" / "github_closure_continuation",
        "emitted_at": "2026-04-06T12:35:00Z",
        "closure_complete": False,
        "final_verification_passed": False,
        "hardening_completed": False,
        "escalation_required": False,
        "bounded_next_step_available": True,
        "retry_budget": 1,
    }
    one = run_github_closure_continuation(**kwargs)
    two = run_github_closure_continuation(**kwargs)

    assert one["continuation_id"] == two["continuation_id"]
    assert one["continuation_dir"] == two["continuation_dir"]
    assert one["branch_update_policy"] == two["branch_update_policy"]


def test_schema_validation_of_produced_artifacts(tmp_path: Path) -> None:
    summary_path, handoff_path = _build_ingestion_summary(tmp_path)

    result = run_github_closure_continuation(
        github_review_handoff_path=handoff_path,
        output_root=tmp_path / "artifacts" / "github_closure_continuation",
        emitted_at="2026-04-06T12:40:00Z",
        closure_complete=False,
        final_verification_passed=False,
        hardening_completed=False,
        escalation_required=False,
        bounded_next_step_available=True,
        retry_budget=1,
    )

    closure = json.loads(Path(result["artifact_paths"]["closure_decision_artifact"]).read_text(encoding="utf-8"))
    validate_artifact(closure, "closure_decision_artifact")

    if result["artifact_paths"]["next_step_prompt_artifact"]:
        prompt = json.loads(Path(result["artifact_paths"]["next_step_prompt_artifact"]).read_text(encoding="utf-8"))
        validate_artifact(prompt, "next_step_prompt_artifact")

    if result["artifact_paths"]["top_level_conductor_run_artifact"]:
        tlc = json.loads(Path(result["artifact_paths"]["top_level_conductor_run_artifact"]).read_text(encoding="utf-8"))
        validate_artifact(tlc, "top_level_conductor_run_artifact")


def test_no_raw_review_consumption_downstream_of_ril(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    summary_path, handoff_path = _build_ingestion_summary(tmp_path)
    captured_request: dict[str, object] = {}

    import spectrum_systems.modules.runtime.github_closure_continuation as module_under_test

    original_builder = module_under_test.build_closure_decision_artifact

    def _spy(request: dict[str, object]) -> dict[str, object]:
        captured_request.update(request)
        return original_builder(request)

    monkeypatch.setattr(module_under_test, "build_closure_decision_artifact", _spy)

    run_github_closure_continuation(
        github_review_handoff_path=handoff_path,
        output_root=tmp_path / "artifacts" / "github_closure_continuation",
        emitted_at="2026-04-06T12:45:00Z",
        closure_complete=False,
        final_verification_passed=False,
        hardening_completed=False,
        escalation_required=False,
        bounded_next_step_available=False,
        retry_budget=1,
    )

    source_artifacts = captured_request["source_artifacts"]
    assert isinstance(source_artifacts, list)
    artifact_types = {row["artifact_type"] for row in source_artifacts if isinstance(row, dict)}
    assert artifact_types == {"review_projection_bundle_artifact", "review_consumer_output_bundle_artifact"}


def test_no_closure_decisioning_outside_cde(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    summary_path, handoff_path = _build_ingestion_summary(tmp_path)
    _neutralize_escalation(summary_path)

    import spectrum_systems.modules.runtime.github_closure_continuation as module_under_test

    calls = {"count": 0}
    original_builder = module_under_test.build_closure_decision_artifact

    def _spy(request: dict[str, object]) -> dict[str, object]:
        calls["count"] += 1
        return original_builder(request)

    monkeypatch.setattr(module_under_test, "build_closure_decision_artifact", _spy)

    result = run_github_closure_continuation(
        github_review_handoff_path=handoff_path,
        output_root=tmp_path / "artifacts" / "github_closure_continuation",
        emitted_at="2026-04-06T12:50:00Z",
        closure_complete=True,
        final_verification_passed=True,
        hardening_completed=True,
        escalation_required=False,
        bounded_next_step_available=False,
        retry_budget=1,
    )

    assert calls["count"] == 1
    assert result["cde_decision"] == "lock"


def test_missing_handoff_artifact_fails_closed(tmp_path: Path) -> None:
    _, handoff_path = _build_ingestion_summary(tmp_path)
    handoff_payload = json.loads(handoff_path.read_text(encoding="utf-8"))
    handoff_payload["artifact_refs"].pop("review_consumer_output_bundle_artifact")
    handoff_path.write_text(json.dumps(handoff_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(Exception, match="required property|missing required handoff artifact ref"):
        run_github_closure_continuation(
            github_review_handoff_path=handoff_path,
            output_root=tmp_path / "artifacts" / "github_closure_continuation",
            emitted_at="2026-04-06T12:52:00Z",
            closure_complete=False,
            final_verification_passed=False,
            hardening_completed=False,
            escalation_required=False,
            bounded_next_step_available=True,
            retry_budget=0,
        )


def test_roadmap_artifact_is_fed_into_continuation_pipeline(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    summary_path, handoff_path = _build_ingestion_summary_with_roadmap(tmp_path)
    _neutralize_escalation(summary_path)
    captured_request: dict[str, object] = {}

    import spectrum_systems.modules.runtime.github_closure_continuation as module_under_test

    original_builder = module_under_test.build_closure_decision_artifact

    def _spy(request: dict[str, object]) -> dict[str, object]:
        captured_request.update(request)
        return original_builder(request)

    monkeypatch.setattr(module_under_test, "build_closure_decision_artifact", _spy)

    result = run_github_closure_continuation(
        github_review_handoff_path=handoff_path,
        output_root=tmp_path / "artifacts" / "github_closure_continuation",
        emitted_at="2026-04-06T12:53:00Z",
        closure_complete=False,
        final_verification_passed=False,
        hardening_completed=False,
        escalation_required=False,
        bounded_next_step_available=True,
        retry_budget=0,
    )

    assert result["cde_decision"] == "continue_bounded"
    assert isinstance(captured_request.get("next_step_ref"), str)
    assert str(captured_request["next_step_ref"]).startswith("roadmap_two_step_artifact:R2S-")
    assert result["roadmap_two_step"] is not None


def test_branch_update_policy_only_allows_ready_for_merge_terminal_state(tmp_path: Path) -> None:
    summary_path, handoff_path = _build_ingestion_summary(tmp_path)
    _neutralize_escalation(summary_path)

    lock_result = run_github_closure_continuation(
        github_review_handoff_path=handoff_path,
        output_root=tmp_path / "artifacts" / "github_closure_continuation",
        emitted_at="2026-04-06T12:53:00Z",
        closure_complete=True,
        final_verification_passed=True,
        hardening_completed=True,
        escalation_required=False,
        bounded_next_step_available=False,
        retry_budget=0,
    )
    assert lock_result["branch_update_policy"]["branch_update_allowed"] is False

    continue_result = run_github_closure_continuation(
        github_review_handoff_path=handoff_path,
        output_root=tmp_path / "artifacts" / "github_closure_continuation",
        emitted_at="2026-04-06T12:54:00Z",
        closure_complete=False,
        final_verification_passed=False,
        hardening_completed=False,
        escalation_required=False,
        bounded_next_step_available=True,
        retry_budget=0,
    )
    assert continue_result["cde_decision"] == "continue_bounded"
    assert continue_result["final_terminal_state"] == "exhausted"
    assert continue_result["branch_update_policy"]["branch_update_allowed"] is False


def test_ready_for_merge_without_trace_continuity_cannot_promote(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    summary_path, handoff_path = _build_ingestion_summary(tmp_path)
    _neutralize_escalation(summary_path)

    import spectrum_systems.modules.runtime.github_closure_continuation as module_under_test

    def _patched(_: dict[str, object]) -> dict[str, object]:
        result = json.loads(Path("contracts/examples/top_level_conductor_run_artifact.json").read_text(encoding="utf-8"))
        result["current_state"] = "ready_for_merge"
        result["ready_for_merge"] = True
        result["trace_refs"] = ["trace-mismatch"]
        return result

    monkeypatch.setattr(module_under_test, "run_top_level_conductor", _patched)
    result = run_github_closure_continuation(
        github_review_handoff_path=handoff_path,
        output_root=tmp_path / "artifacts" / "github_closure_continuation",
        emitted_at="2026-04-06T12:59:00Z",
        closure_complete=False,
        final_verification_passed=False,
        hardening_completed=False,
        escalation_required=False,
        bounded_next_step_available=True,
        retry_budget=1,
    )
    promotion_gate = json.loads(Path(result["artifact_paths"]["promotion_gate_decision_artifact"]).read_text(encoding="utf-8"))
    assert promotion_gate["terminal_state"] == "ready_for_merge"
    assert promotion_gate["promotion_allowed"] is False
    assert "trace_lineage_continuity" in promotion_gate["missing_requirements"]
    assert result["branch_update_policy"]["branch_update_allowed"] is False
