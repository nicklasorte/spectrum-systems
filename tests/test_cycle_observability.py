from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.orchestration.cycle_observability import (
    CycleObservabilityError,
    build_cycle_backlog_snapshot,
    build_cycle_status,
)


_REPO_ROOT = Path(__file__).resolve().parents[1]
_FIXTURES = _REPO_ROOT / "tests" / "fixtures" / "autonomous_cycle"


def _write(path: Path, payload: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return str(path)


def _load_fixture(name: str) -> dict:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


def _base_manifest(*, cycle_id: str, state: str, updated_at: str) -> dict:
    return {
        "cycle_id": cycle_id,
        "current_state": state,
        "roadmap_artifact_path": str(_REPO_ROOT / "docs" / "roadmap" / "system_roadmap.md"),
        "roadmap_review_artifact_paths": [],
        "execution_report_paths": [],
        "implementation_review_paths": [],
        "fix_roadmap_path": None,
        "fix_roadmap_markdown_path": None,
        "fix_group_refs": [],
        "fix_execution_report_paths": [],
        "certification_record_path": None,
        "blocking_issues": [],
        "next_action": "await_input",
        "roadmap_approval_state": "pending",
        "hard_gates": {
            "roadmap_approved": False,
            "execution_contracts_pinned": True,
            "review_templates_present": True,
        },
        "pqx_execution_request_path": None,
        "done_certification_input_refs": {
            "replay_result_ref": "a",
            "regression_result_ref": "b",
            "certification_pack_ref": "c",
            "error_budget_ref": "d",
            "policy_ref": "e",
        },
        "updated_at": updated_at,
        "pqx_request_ref": None,
        "execution_started_at": None,
        "execution_completed_at": None,
        "certification_status": "pending",
        "certification_summary": None,
        "required_judgments": [],
        "judgment_scope": None,
        "judgment_environment": None,
        "judgment_policy_paths": [],
        "judgment_input_context": {},
        "judgment_evidence_refs": [],
        "judgment_precedent_record_paths": [],
        "judgment_record_path": None,
        "judgment_application_record_path": None,
        "judgment_eval_result_path": None,
    }


def test_cycle_status_artifact_generation_deterministic_for_healthy_cycle(tmp_path: Path) -> None:
    manifest = _base_manifest(cycle_id="cycle-healthy", state="execution_complete_unreviewed", updated_at="2026-03-30T02:00:00Z")
    manifest["next_action"] = "request_implementation_reviews"
    manifest["execution_started_at"] = "2026-03-30T01:00:00Z"
    manifest["execution_completed_at"] = "2026-03-30T01:05:00Z"

    report = tmp_path / "execution_report.json"
    report.write_text((Path("contracts/examples/execution_report_artifact.json")).read_text(encoding="utf-8"), encoding="utf-8")
    manifest["execution_report_paths"] = [str(report)]

    path = tmp_path / "cycle_manifest.json"
    _write(path, manifest)

    first = build_cycle_status(path)
    second = build_cycle_status(path)

    assert first == second
    assert first["current_state"] == "execution_complete_unreviewed"
    assert first["phase_metrics"]["execution_seconds"] == 300.0


def test_blocked_cycle_status_normalizes_blocked_reason(tmp_path: Path) -> None:
    manifest = _load_fixture("cycle_status_blocked_manifest.json")
    path = tmp_path / "blocked_manifest.json"
    _write(path, manifest)

    status = build_cycle_status(path)

    assert status["current_state"] == "blocked"
    assert status["blocked_reason_summary"]["counts_by_category"]["missing_required_artifact"] == 1


def test_backlog_aggregation_across_multiple_cycles_and_metrics(tmp_path: Path) -> None:
    review = _load_fixture("implementation_review_claude.json")
    review["reviewed_at"] = "2026-03-30T03:00:00Z"
    review["cycle_id"] = "cycle-await-review"
    review["findings"] = [
        {
            "finding_id": "finding-crit-1",
            "title": "Critical contract issue",
            "severity": "critical",
            "category": "contract",
            "affected_paths": ["contracts/schemas/cycle_manifest.schema.json"],
        }
    ]
    review_path = tmp_path / "review.json"
    _write(review_path, review)

    cycle_a = _base_manifest(cycle_id="cycle-await-review", state="execution_complete_unreviewed", updated_at="2026-03-30T03:00:00Z")
    cycle_a["next_action"] = "request_implementation_reviews"
    cycle_a["execution_started_at"] = "2026-03-30T02:00:00Z"
    cycle_a["execution_completed_at"] = "2026-03-30T02:02:00Z"
    cycle_a["implementation_review_paths"] = [str(review_path)]

    cycle_b = _load_fixture("cycle_status_blocked_manifest.json")

    cycle_c = _base_manifest(cycle_id="cycle-certified", state="certified_done", updated_at="2026-03-30T03:10:00Z")
    cycle_c["next_action"] = "archive_cycle"
    cycle_c["certification_status"] = "passed"
    cycle_c["execution_started_at"] = "2026-03-30T01:00:00Z"
    cycle_c["execution_completed_at"] = "2026-03-30T01:03:00Z"

    p_a = tmp_path / "a.json"
    p_b = tmp_path / "b.json"
    p_c = tmp_path / "c.json"
    _write(p_a, cycle_a)
    _write(p_b, cycle_b)
    _write(p_c, cycle_c)

    snapshot = build_cycle_backlog_snapshot([p_a, p_b, p_c], generated_at="2026-03-30T04:00:00Z")

    assert snapshot["cycle_count"] == 3
    assert snapshot["queues"]["active_cycles"] == ["cycle-await-review", "cycle-blocked"]
    assert snapshot["queues"]["blocked_cycles"] == ["cycle-blocked"]
    assert snapshot["queues"]["awaiting_review_cycles"] == ["cycle-await-review"]
    assert snapshot["metrics"]["count_by_state"]["blocked"] == 1
    assert snapshot["metrics"]["blocked_by_reason"]["missing_required_artifact"] == 1
    assert snapshot["metrics"]["average_execution_seconds"] == 150.0
    assert snapshot["metrics"]["open_critical_findings"] == 1
    assert snapshot["metrics"]["certification_pass_count"] == 1
    assert snapshot["metrics"]["certification_fail_count"] == 1


def test_metrics_generation_is_deterministic_for_same_inputs(tmp_path: Path) -> None:
    manifest = _base_manifest(cycle_id="cycle-ready", state="execution_ready", updated_at="2026-03-30T05:00:00Z")
    manifest["next_action"] = "prepare_execution_request"
    path = tmp_path / "manifest.json"
    _write(path, manifest)

    first = build_cycle_backlog_snapshot([path], generated_at="2026-03-30T05:10:00Z")
    second = build_cycle_backlog_snapshot([path], generated_at="2026-03-30T05:10:00Z")

    assert first == second


def test_fail_closed_when_blocked_manifest_missing_required_details(tmp_path: Path) -> None:
    manifest = _base_manifest(cycle_id="cycle-bad", state="blocked", updated_at="2026-03-30T06:00:00Z")
    manifest["blocking_issues"] = []
    path = tmp_path / "bad_manifest.json"
    _write(path, manifest)

    with pytest.raises(CycleObservabilityError, match="blocked state requires blocking_issues details"):
        build_cycle_status(path)


def test_fail_closed_on_incomplete_timing_data(tmp_path: Path) -> None:
    manifest = _base_manifest(cycle_id="cycle-time-bad", state="execution_complete_unreviewed", updated_at="2026-03-30T07:00:00Z")
    manifest["next_action"] = "request_implementation_reviews"
    manifest["execution_started_at"] = "2026-03-30T06:00:00Z"
    path = tmp_path / "timing_bad.json"
    _write(path, manifest)

    with pytest.raises(CycleObservabilityError, match="incomplete timing data"):
        build_cycle_status(path)
