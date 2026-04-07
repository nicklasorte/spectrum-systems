from __future__ import annotations

import json
from pathlib import Path

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.github_closure_continuation import run_github_closure_continuation
from spectrum_systems.modules.runtime.github_review_ingestion import ingest_github_review_event

_FIXTURES = Path("tests/fixtures/github_events")


def _load_fixture(name: str) -> dict:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


def _build_handoff(tmp_path: Path) -> Path:
    payload = _load_fixture("pull_request_review_submitted.json")
    result = ingest_github_review_event(
        event_name="pull_request_review",
        payload=payload,
        output_root=tmp_path / "artifacts" / "github_review_ingestion",
        review_source="ril",
        run_mode="strict",
        emitted_at="2026-04-07T01:00:00Z",
        repo="example/repo",
        sha="abc123",
        run_id="run-001",
    )
    return Path(result["artifact_paths"]["github_review_handoff_artifact"])


def test_non_ready_state_cannot_promote(tmp_path: Path) -> None:
    handoff = _build_handoff(tmp_path)
    result = run_github_closure_continuation(
        github_review_handoff_path=handoff,
        output_root=tmp_path / "artifacts" / "github_closure_continuation",
        emitted_at="2026-04-07T01:10:00Z",
        closure_complete=False,
        final_verification_passed=False,
        hardening_completed=False,
        escalation_required=True,
        bounded_next_step_available=False,
        retry_budget=0,
    )
    gate = json.loads(Path(result["artifact_paths"]["promotion_gate_decision_artifact"]).read_text(encoding="utf-8"))
    validate_artifact(gate, "promotion_gate_decision_artifact")
    assert gate["promotion_allowed"] is False
    assert gate["terminal_state"] == "escalated"


def test_ready_for_merge_with_required_evidence_can_promote(tmp_path: Path) -> None:
    handoff = _build_handoff(tmp_path)
    result = run_github_closure_continuation(
        github_review_handoff_path=handoff,
        output_root=tmp_path / "artifacts" / "github_closure_continuation",
        emitted_at="2026-04-07T01:20:00Z",
        closure_complete=False,
        final_verification_passed=False,
        hardening_completed=False,
        escalation_required=False,
        bounded_next_step_available=True,
        retry_budget=1,
    )
    gate = json.loads(Path(result["artifact_paths"]["promotion_gate_decision_artifact"]).read_text(encoding="utf-8"))
    validate_artifact(gate, "promotion_gate_decision_artifact")
    if gate["terminal_state"] == "ready_for_merge":
        assert gate["promotion_allowed"] is True
        assert gate["missing_requirements"] == []
