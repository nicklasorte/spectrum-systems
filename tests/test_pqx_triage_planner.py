from __future__ import annotations

from copy import deepcopy

import pytest

from spectrum_systems.modules.runtime.pqx_triage_planner import (
    PQXTriagePlannerError,
    build_triage_plan_record,
)


def _review() -> dict:
    return {
        "schema_version": "1.0.0",
        "review_id": "REV-T-001",
        "checkpoint_id": "BUNDLE-T1:checkpoint:AI-01",
        "review_type": "checkpoint_review",
        "bundle_id": "BUNDLE-T1",
        "bundle_run_id": "queue-run-t-001",
        "roadmap_authority_ref": "docs/roadmaps/system_roadmap.md",
        "execution_plan_ref": "docs/roadmaps/execution_bundles.md",
        "scope": {"scope_type": "step", "step_id": "AI-01"},
        "findings": [
            {
                "finding_id": "F-002",
                "severity": "medium",
                "category": "docs",
                "title": "missing docs",
                "description": "docs gap",
                "affected_step_ids": ["AI-01"],
                "recommended_action": "document",
                "blocking": False,
                "source_refs": ["docs/review-actions/REV-T-001.md#F-002"],
            },
            {
                "finding_id": "F-001",
                "severity": "critical",
                "category": "runtime",
                "title": "critical issue",
                "description": "runtime break",
                "affected_step_ids": ["AI-02"],
                "recommended_action": "fix now",
                "blocking": True,
                "source_refs": ["docs/review-actions/REV-T-001.md#F-001"],
            },
        ],
        "overall_disposition": "approved_with_findings",
        "created_at": "2026-03-29T12:00:00Z",
        "provenance_refs": ["trace:test:1"],
    }


def _fix_gate_blocked() -> dict:
    return {
        "schema_version": "1.1.0",
        "fix_gate_id": "fix-gate:run-t-001:fix:REV-T-001:F-009",
        "created_at": "2026-03-29T12:02:00Z",
        "run_id": "run-t-001",
        "trace_id": "trace-t-001",
        "bundle_id": "BUNDLE-T1",
        "fix_id": "fix:REV-T-001:F-009",
        "originating_pending_fix_id": "fix:REV-T-001:F-009",
        "originating_review_artifact_id": "REV-T-001",
        "originating_finding_id": "F-009",
        "fix_execution_record_ref": "out/fix-step:fix:REV-T-001:F-009.fix_execution_record.json",
        "adjudication_inputs": {
            "execution_status": "failed",
            "validation_result": "failed",
            "accepted_target_step_ids": ["AI-01"],
            "insertion_point": {
                "mode": "patch_after_source",
                "anchor_step_id": "AI-01",
                "insert_before_step_id": "AI-02",
                "ordered_index": 1,
            },
            "artifact_refs": ["out/fix-step:fix:REV-T-001:F-009.json"],
        },
        "gate_status": "blocked",
        "allows_resume": False,
        "blocking_reason": "fix execution did not complete",
        "comparison_summary": {
            "mapping_status": "matched",
            "resolution_status": "unresolved",
            "reason_codes": ["EXECUTION_NOT_COMPLETE"],
            "replay_safe": True,
        },
        "producer": {
            "module": "spectrum_systems.modules.runtime.pqx_fix_gate",
            "function": "evaluate_fix_completion",
        },
    }


def test_build_triage_plan_is_deterministic_and_ordered() -> None:
    record = build_triage_plan_record(
        run_id="run-t-001",
        trace_id="trace-t-001",
        bundle_run_id="queue-run-t-001",
        bundle_id="BUNDLE-T1",
        roadmap_authority_ref="docs/roadmaps/system_roadmap.md",
        review_artifacts=[_review()],
        review_artifact_refs=["artifacts/reviews/rev-t-001.json"],
        fix_gate_records=[_fix_gate_blocked()],
        fix_gate_record_refs=["artifacts/fix-gates/fix-gate-t-001.json"],
        step_ids=["AI-01", "AI-02"],
        created_at="2026-03-29T12:03:00Z",
    )
    assert record["summary_counts"]["findings_total"] == 3
    assert record["findings_analyzed"] == ["F-001", "F-009", "F-002"]
    assert record["blocked_items"] == ["F-001", "F-009"]


def test_fail_closed_on_ambiguous_finding_mapping() -> None:
    review = _review()
    review["findings"][0]["affected_step_ids"] = ["AI-01", "AI-02"]
    with pytest.raises(PQXTriagePlannerError, match="ambiguous finding-to-step mapping"):
        build_triage_plan_record(
            run_id="run-t-001",
            trace_id="trace-t-001",
            bundle_run_id="queue-run-t-001",
            bundle_id="BUNDLE-T1",
            roadmap_authority_ref="docs/roadmaps/system_roadmap.md",
            review_artifacts=[review],
            review_artifact_refs=["artifacts/reviews/rev-t-001.json"],
            fix_gate_records=[],
            fix_gate_record_refs=[],
            step_ids=["AI-01", "AI-02"],
            created_at="2026-03-29T12:03:00Z",
        )


def test_fail_closed_on_invalid_insertion_target() -> None:
    review = _review()
    review["findings"][0]["affected_step_ids"] = ["AI-99"]
    with pytest.raises(PQXTriagePlannerError, match="outside active bundle scope"):
        build_triage_plan_record(
            run_id="run-t-001",
            trace_id="trace-t-001",
            bundle_run_id="queue-run-t-001",
            bundle_id="BUNDLE-T1",
            roadmap_authority_ref="docs/roadmaps/system_roadmap.md",
            review_artifacts=[review],
            review_artifact_refs=["artifacts/reviews/rev-t-001.json"],
            fix_gate_records=[],
            fix_gate_record_refs=[],
            step_ids=["AI-01", "AI-02"],
            created_at="2026-03-29T12:03:00Z",
        )


def test_no_mutation_of_inputs() -> None:
    review = _review()
    fix = _fix_gate_blocked()
    review_before = deepcopy(review)
    fix_before = deepcopy(fix)
    build_triage_plan_record(
        run_id="run-t-001",
        trace_id="trace-t-001",
        bundle_run_id="queue-run-t-001",
        bundle_id="BUNDLE-T1",
        roadmap_authority_ref="docs/roadmaps/system_roadmap.md",
        review_artifacts=[review],
        review_artifact_refs=["artifacts/reviews/rev-t-001.json"],
        fix_gate_records=[fix],
        fix_gate_record_refs=["artifacts/fix-gates/fix-gate-t-001.json"],
        step_ids=["AI-01", "AI-02"],
        created_at="2026-03-29T12:03:00Z",
    )
    assert review == review_before
    assert fix == fix_before


def test_replay_parity_same_inputs_same_output() -> None:
    kwargs = {
        "run_id": "run-t-001",
        "trace_id": "trace-t-001",
        "bundle_run_id": "queue-run-t-001",
        "bundle_id": "BUNDLE-T1",
        "roadmap_authority_ref": "docs/roadmaps/system_roadmap.md",
        "review_artifacts": [_review()],
        "review_artifact_refs": ["artifacts/reviews/rev-t-001.json"],
        "fix_gate_records": [_fix_gate_blocked()],
        "fix_gate_record_refs": ["artifacts/fix-gates/fix-gate-t-001.json"],
        "step_ids": ["AI-01", "AI-02"],
        "created_at": "2026-03-29T12:03:00Z",
    }
    assert build_triage_plan_record(**kwargs) == build_triage_plan_record(**kwargs)
