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


def _draft(tmp_path: Path) -> dict:
    payload = _load_fixture("issue_comment_pr_command.json")
    payload["comment"]["body"] = "/roadmap-draft scope:runtime keywords:governance,roadmap"
    return ingest_github_review_event(
        event_name="issue_comment",
        payload=payload,
        output_root=tmp_path / "artifacts" / "github_review_ingestion",
        review_source="ril",
        run_mode="strict",
        emitted_at="2026-04-06T11:00:00Z",
        repo="example/repo",
        sha="sha1",
        run_id="101",
    )


def _approve(tmp_path: Path, *, draft_id: str | None = None) -> dict:
    payload = _load_fixture("issue_comment_pr_command.json")
    suffix = f" draft_id:{draft_id}" if draft_id else ""
    payload["comment"]["body"] = f"/roadmap-approve{suffix}".strip()
    return ingest_github_review_event(
        event_name="issue_comment",
        payload=payload,
        output_root=tmp_path / "artifacts" / "github_review_ingestion",
        review_source="ril",
        run_mode="strict",
        emitted_at="2026-04-06T11:05:00Z",
        repo="example/repo",
        sha="sha2",
        run_id="102",
    )


def _neutralize_escalation(summary: dict) -> None:
    for key in ("review_projection_bundle_artifact", "review_consumer_output_bundle_artifact"):
        artifact_path = Path(summary["artifact_paths"][key])
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        artifact["escalation_present"] = False
        artifact["blocker_present"] = False
        artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_roadmap_draft_creates_artifact_and_metadata(tmp_path: Path) -> None:
    summary = _draft(tmp_path)
    roadmap = json.loads(Path(summary["artifact_paths"]["roadmap_two_step_artifact"]).read_text(encoding="utf-8"))
    validate_artifact(roadmap, "roadmap_two_step_artifact")
    assert roadmap["step_count"] == 2
    assert summary["roadmap_draft_id"]


def test_draft_command_does_not_trigger_continuation(tmp_path: Path) -> None:
    summary = _draft(tmp_path)
    handoff_path = Path(summary["artifact_paths"]["github_review_handoff_artifact"])
    with pytest.raises(GithubClosureContinuationError, match="preview-only"):
        run_github_closure_continuation(
            github_review_handoff_path=handoff_path,
            output_root=tmp_path / "artifacts" / "github_closure_continuation",
            emitted_at="2026-04-06T11:10:00Z",
            closure_complete=False,
            final_verification_passed=False,
            hardening_completed=False,
            escalation_required=False,
            bounded_next_step_available=True,
            retry_budget=0,
        )


def test_pr_feedback_draft_payload_fields_exist(tmp_path: Path) -> None:
    summary = _draft(tmp_path)
    assert summary["command_marker"] == "/roadmap-draft"
    assert "roadmap_draft_metadata" in summary["artifact_paths"]


def test_roadmap_approve_triggers_governed_continuation(tmp_path: Path) -> None:
    draft_summary = _draft(tmp_path)
    approve_summary = _approve(tmp_path, draft_id=draft_summary["roadmap_draft_id"])
    _neutralize_escalation(approve_summary)
    handoff = Path(approve_summary["artifact_paths"]["github_review_handoff_artifact"])

    result = run_github_closure_continuation(
        github_review_handoff_path=handoff,
        output_root=tmp_path / "artifacts" / "github_closure_continuation",
        emitted_at="2026-04-06T11:20:00Z",
        closure_complete=False,
        final_verification_passed=False,
        hardening_completed=False,
        escalation_required=False,
        bounded_next_step_available=True,
        retry_budget=0,
    )

    assert result["cde_decision"] in {"continue_bounded", "hardening_required", "final_verification_required", "blocked"}
    assert result["roadmap_two_step"]["draft_id"] == draft_summary["roadmap_draft_id"]


def test_invalid_approval_fails_closed(tmp_path: Path) -> None:
    _draft(tmp_path)
    with pytest.raises(Exception, match="missing draft artifact"):
        _approve(tmp_path, draft_id="NONEXISTENT")


def test_missing_or_stale_artifact_fails_closed(tmp_path: Path) -> None:
    draft_summary = _draft(tmp_path)
    draft_path = Path(draft_summary["artifact_paths"]["roadmap_two_step_artifact"])
    draft_path.unlink()
    with pytest.raises(Exception, match="missing draft artifact"):
        _approve(tmp_path, draft_id=draft_summary["roadmap_draft_id"])


def test_deterministic_draft_output(tmp_path: Path) -> None:
    first = _draft(tmp_path)
    second = _draft(tmp_path)
    one = json.loads(Path(first["artifact_paths"]["roadmap_two_step_artifact"]).read_text(encoding="utf-8"))
    two = json.loads(Path(second["artifact_paths"]["roadmap_two_step_artifact"]).read_text(encoding="utf-8"))
    assert one == two


def test_no_bypass_of_cde_tlc(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    draft_summary = _draft(tmp_path)
    approve_summary = _approve(tmp_path, draft_id=draft_summary["roadmap_draft_id"])
    _neutralize_escalation(approve_summary)
    handoff = Path(approve_summary["artifact_paths"]["github_review_handoff_artifact"])

    import spectrum_systems.modules.runtime.github_closure_continuation as module_under_test

    calls = {"cde": 0, "tlc": 0}
    original_cde = module_under_test.build_closure_decision_artifact
    original_tlc = module_under_test.run_top_level_conductor

    def _cde_spy(request: dict[str, object]) -> dict[str, object]:
        calls["cde"] += 1
        return original_cde(request)

    def _tlc_spy(request: dict[str, object]) -> dict[str, object]:
        calls["tlc"] += 1
        return original_tlc(request)

    monkeypatch.setattr(module_under_test, "build_closure_decision_artifact", _cde_spy)
    monkeypatch.setattr(module_under_test, "run_top_level_conductor", _tlc_spy)

    run_github_closure_continuation(
        github_review_handoff_path=handoff,
        output_root=tmp_path / "artifacts" / "github_closure_continuation",
        emitted_at="2026-04-06T11:25:00Z",
        closure_complete=False,
        final_verification_passed=False,
        hardening_completed=False,
        escalation_required=False,
        bounded_next_step_available=True,
        retry_budget=0,
    )

    assert calls["cde"] == 1
    assert calls["tlc"] == 1


def test_bounded_exactly_two_steps(tmp_path: Path) -> None:
    summary = _draft(tmp_path)
    roadmap = json.loads(Path(summary["artifact_paths"]["roadmap_two_step_artifact"]).read_text(encoding="utf-8"))
    assert roadmap["bounded"] is True
    assert len(roadmap["steps"]) == 2
