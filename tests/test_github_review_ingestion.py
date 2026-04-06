from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.github_review_ingestion import (
    GithubReviewIngestionError,
    build_governed_review_inputs,
    ingest_github_review_event,
)


_FIXTURES = Path("tests/fixtures/github_events")


def _load_fixture(name: str) -> dict:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


def test_pull_request_review_event_normalization() -> None:
    payload = _load_fixture("pull_request_review_submitted.json")

    normalized = build_governed_review_inputs(
        event_name="pull_request_review",
        payload=payload,
        review_source="ril",
        run_mode="strict",
        emitted_at="2026-04-06T10:00:00Z",
    )

    assert normalized.pr_number == 42
    assert normalized.event_name == "pull_request_review"
    assert normalized.source_event_ref == "pull_request_review:101"
    assert normalized.review_body.startswith("RIL trigger review")


def test_issue_comment_command_gating() -> None:
    payload = _load_fixture("issue_comment_pr_command.json")
    normalized = build_governed_review_inputs(
        event_name="issue_comment",
        payload=payload,
        review_source="ril",
        run_mode="strict",
        emitted_at="2026-04-06T11:00:00Z",
    )
    assert normalized.command_marker == "/run-ril"
    roadmap_payload = _load_fixture("issue_comment_pr_command.json")
    roadmap_payload["comment"]["body"] = "/roadmap-2step scope:runtime keywords:roadmap,governance"
    roadmap_normalized = build_governed_review_inputs(
        event_name="issue_comment",
        payload=roadmap_payload,
        review_source="ril",
        run_mode="strict",
        emitted_at="2026-04-06T11:00:00Z",
    )
    assert roadmap_normalized.command_marker == "/roadmap-2step"

    bad_payload = {
        "action": "created",
        "issue": {"number": 43, "pull_request": {"url": "https://example.test/pull/43"}},
        "comment": {"id": 303, "body": "no command marker"},
        "pull_request": {"number": 43},
    }
    with pytest.raises(GithubReviewIngestionError, match="command marker"):
        build_governed_review_inputs(
            event_name="issue_comment",
            payload=bad_payload,
            review_source="ril",
            run_mode="strict",
            emitted_at="2026-04-06T11:00:00Z",
        )


def test_workflow_dispatch_manual_input_path() -> None:
    payload = _load_fixture("workflow_dispatch_manual.json")

    normalized = build_governed_review_inputs(
        event_name="workflow_dispatch",
        payload=payload,
        review_source="ril",
        run_mode="strict",
        pr_number=44,
        emitted_at="2026-04-06T12:00:00Z",
    )

    assert normalized.pr_number == 44
    assert normalized.command_marker == "/run-ril"
    assert normalized.source_event_ref == "workflow_dispatch:ril:strict"


def test_malformed_event_fails_closed() -> None:
    malformed = {"action": "edited", "review": {"id": 1, "body": "x"}, "pull_request": {"number": 10}}

    with pytest.raises(GithubReviewIngestionError, match="action=submitted"):
        build_governed_review_inputs(
            event_name="pull_request_review",
            payload=malformed,
            review_source="ril",
            run_mode="strict",
            emitted_at="2026-04-06T09:00:00Z",
        )


def test_deterministic_artifact_path_generation(tmp_path: Path) -> None:
    payload = _load_fixture("pull_request_review_submitted.json")

    kwargs = {
        "event_name": "pull_request_review",
        "payload": payload,
        "output_root": tmp_path,
        "review_source": "ril",
        "run_mode": "strict",
        "emitted_at": "2026-04-06T10:00:00Z",
        "repo": "example/repo",
        "sha": "abc123",
        "run_id": "555",
    }

    first = ingest_github_review_event(**kwargs)
    second = ingest_github_review_event(**kwargs)

    assert first["artifact_dir"] == second["artifact_dir"]
    assert first["artifact_paths"] == second["artifact_paths"]


def test_end_to_end_ril_pipeline_invocation_and_schema_valid_outputs(tmp_path: Path) -> None:
    payload = _load_fixture("issue_comment_pr_command.json")

    summary = ingest_github_review_event(
        event_name="issue_comment",
        payload=payload,
        output_root=tmp_path,
        review_source="ril",
        run_mode="strict",
        emitted_at="2026-04-06T11:00:00Z",
        repo="example/repo",
        sha="def456",
        run_id="777",
    )

    produced = summary["artifact_paths"]
    required = {
        "normalized_review_source_artifact",
        "github_review_handoff_artifact",
        "review_signal_artifact",
        "review_control_signal_artifact",
        "review_integration_packet_artifact",
        "review_projection_bundle_artifact",
        "review_consumer_output_bundle_artifact",
    }
    assert required.issubset(set(produced.keys()))

    source_artifact = json.loads(Path(produced["normalized_review_source_artifact"]).read_text(encoding="utf-8"))
    validate_artifact(source_artifact, "reviewer_comment_set")

    validate_artifact(json.loads(Path(produced["review_signal_artifact"]).read_text(encoding="utf-8")), "review_signal_artifact")
    validate_artifact(
        json.loads(Path(produced["review_control_signal_artifact"]).read_text(encoding="utf-8")),
        "review_control_signal_artifact",
    )
    validate_artifact(
        json.loads(Path(produced["review_integration_packet_artifact"]).read_text(encoding="utf-8")),
        "review_integration_packet_artifact",
    )
    validate_artifact(
        json.loads(Path(produced["review_projection_bundle_artifact"]).read_text(encoding="utf-8")),
        "review_projection_bundle_artifact",
    )
    validate_artifact(
        json.loads(Path(produced["review_consumer_output_bundle_artifact"]).read_text(encoding="utf-8")),
        "review_consumer_output_bundle_artifact",
    )
    validate_artifact(
        json.loads(Path(produced["github_review_handoff_artifact"]).read_text(encoding="utf-8")),
        "github_review_handoff_artifact",
    )

    assert summary["guardrails"]["closure_or_repair_logic_invoked"] is False


def test_roadmap_command_emits_two_step_roadmap_artifact(tmp_path: Path) -> None:
    payload = _load_fixture("issue_comment_pr_command.json")
    payload["comment"]["body"] = "/roadmap-2step scope:runtime keywords:roadmap,governance"

    summary = ingest_github_review_event(
        event_name="issue_comment",
        payload=payload,
        output_root=tmp_path,
        review_source="ril",
        run_mode="strict",
        emitted_at="2026-04-06T11:00:00Z",
        repo="example/repo",
        sha="def456",
        run_id="777",
    )

    roadmap_path = Path(summary["artifact_paths"]["roadmap_two_step_artifact"])
    roadmap = json.loads(roadmap_path.read_text(encoding="utf-8"))
    validate_artifact(roadmap, "roadmap_two_step_artifact")
    assert roadmap["step_count"] == 2
