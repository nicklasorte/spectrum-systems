from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.github_closure_continuation import GithubClosureContinuationError, run_github_closure_continuation
from spectrum_systems.modules.runtime.github_review_ingestion import ingest_github_review_event


_FIXTURES = Path("tests/fixtures/github_events")


def _load_fixture(name: str) -> dict:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


def test_handoff_artifact_is_emitted_and_schema_valid(tmp_path: Path) -> None:
    result = ingest_github_review_event(
        event_name="issue_comment",
        payload=_load_fixture("issue_comment_pr_command.json"),
        output_root=tmp_path / "artifacts" / "github_review_ingestion",
        review_source="ril",
        run_mode="strict",
        emitted_at="2026-04-06T13:00:00Z",
        repo="example/repo",
        sha="abcdef",
        run_id="111",
    )

    handoff_path = Path(result["artifact_paths"]["github_review_handoff_artifact"])
    handoff_payload = json.loads(handoff_path.read_text(encoding="utf-8"))
    validate_artifact(handoff_payload, "github_review_handoff_artifact")

    refs = handoff_payload["artifact_refs"]
    assert refs["review_projection_bundle_artifact"] == "review_projection_bundle_artifact.json"
    assert refs["review_consumer_output_bundle_artifact"] == "review_consumer_output_bundle_artifact.json"


def test_continuation_consumes_handoff_refs_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    result = ingest_github_review_event(
        event_name="pull_request_review",
        payload=_load_fixture("pull_request_review_submitted.json"),
        output_root=tmp_path / "artifacts" / "github_review_ingestion",
        review_source="ril",
        run_mode="strict",
        emitted_at="2026-04-06T13:10:00Z",
        repo="example/repo",
        sha="abcdef",
        run_id="222",
    )
    handoff_path = Path(result["artifact_paths"]["github_review_handoff_artifact"])

    import spectrum_systems.modules.runtime.github_closure_continuation as module_under_test

    original_loader = module_under_test._load_json

    def _spy(path: Path, *, field: str) -> dict:
        if field == "ingestion_summary":
            expected = handoff_path.parent / json.loads(handoff_path.read_text(encoding="utf-8"))["artifact_refs"]["ingestion_summary_artifact"]
            assert path == expected
        return original_loader(path, field=field)

    monkeypatch.setattr(module_under_test, "_load_json", _spy)

    out = run_github_closure_continuation(
        github_review_handoff_path=handoff_path,
        output_root=tmp_path / "artifacts" / "github_closure_continuation",
        emitted_at="2026-04-06T13:20:00Z",
        closure_complete=False,
        final_verification_passed=False,
        hardening_completed=False,
        escalation_required=False,
        bounded_next_step_available=False,
        retry_budget=0,
    )

    assert out["status"] == "success"


def test_missing_handoff_ref_fails_closed(tmp_path: Path) -> None:
    result = ingest_github_review_event(
        event_name="workflow_dispatch",
        payload=_load_fixture("workflow_dispatch_manual.json"),
        output_root=tmp_path / "artifacts" / "github_review_ingestion",
        review_source="ril",
        run_mode="strict",
        pr_number=44,
        emitted_at="2026-04-06T13:30:00Z",
        repo="example/repo",
        sha="abcdef",
        run_id="333",
    )

    handoff_path = Path(result["artifact_paths"]["github_review_handoff_artifact"])
    payload = json.loads(handoff_path.read_text(encoding="utf-8"))
    payload["artifact_refs"]["ingestion_summary_artifact"] = ""
    handoff_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(Exception, match="required property|missing required handoff artifact ref|non-empty"):
        run_github_closure_continuation(
            github_review_handoff_path=handoff_path,
            output_root=tmp_path / "artifacts" / "github_closure_continuation",
            emitted_at="2026-04-06T13:40:00Z",
            closure_complete=False,
            final_verification_passed=False,
            hardening_completed=False,
            escalation_required=False,
            bounded_next_step_available=True,
            retry_budget=0,
        )
