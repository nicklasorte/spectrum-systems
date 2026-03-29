from __future__ import annotations

from copy import deepcopy

import pytest

from spectrum_systems.modules.runtime.pqx_fix_gate import (
    PQXFixGateError,
    assert_fix_gate_allows_resume,
    evaluate_fix_completion,
)


def _bundle_state() -> dict:
    return {
        "schema_version": "1.3.0",
        "roadmap_authority_ref": "docs/roadmaps/system_roadmap.md",
        "execution_plan_ref": "docs/roadmaps/execution_bundles.md",
        "run_id": "run-gate-001",
        "sequence_run_id": "queue-run-gate-001",
        "active_bundle_id": "BUNDLE-T1",
        "completed_bundle_ids": [],
        "completed_step_ids": ["AI-01"],
        "blocked_step_ids": [],
        "pending_fix_ids": [
            {
                "fix_id": "fix:REV-1:F-1",
                "source_review_id": "REV-1",
                "source_finding_id": "F-1",
                "severity": "high",
                "priority": "P1",
                "affected_step_ids": ["AI-02"],
                "status": "complete",
                "blocking": True,
                "created_from_bundle_id": "BUNDLE-T1",
                "created_from_run_id": "run-gate-001",
                "notes": "patch runtime",
                "artifact_refs": ["docs/reviews/REV-1.md#f1"],
            }
        ],
        "executed_fixes": ["fix:REV-1:F-1"],
        "failed_fixes": [],
        "fix_artifacts": {"fix:REV-1:F-1": ["out/fix-1.json"]},
        "reinsertion_points": {
            "fix:REV-1:F-1": {
                "mode": "patch_after_source",
                "anchor_step_id": "AI-02",
                "insert_before_step_id": None,
                "ordered_index": 2,
            }
        },
        "fix_gate_results": {},
        "resolved_fixes": [],
        "unresolved_fixes": ["fix:REV-1:F-1"],
        "last_fix_gate_status": None,
        "review_artifact_refs": [],
        "review_requirements": [],
        "satisfied_review_checkpoint_ids": [],
        "artifact_index": {},
        "resume_position": {
            "bundle_id": "BUNDLE-T1",
            "next_step_id": "AI-02",
            "resume_token": "resume:queue-run-gate-001:BUNDLE-T1:1",
        },
        "created_at": "2026-03-29T12:00:00Z",
        "updated_at": "2026-03-29T12:01:00Z",
    }


def _fix_record() -> dict:
    return {
        "schema_version": "1.0.0",
        "fix_id": "fix:REV-1:F-1",
        "source_step_id": "AI-02",
        "execution_status": "complete",
        "artifacts": ["out/fix-1.json"],
        "validation_result": "passed",
        "insertion_point": {
            "mode": "patch_after_source",
            "anchor_step_id": "AI-02",
            "insert_before_step_id": None,
            "ordered_index": 2,
        },
        "trace_id": "trace:fix:1",
        "run_id": "run-gate-001",
    }


def test_successful_fix_resolution() -> None:
    state, record = evaluate_fix_completion(
        bundle_state=_bundle_state(),
        fix_execution_record=_fix_record(),
        fix_gate_record_ref="out/fix-1.fix_gate.json",
        now="2026-03-29T12:02:00Z",
    )
    assert record["gate_status"] == "passed"
    assert state["resolved_fixes"] == ["fix:REV-1:F-1"]
    assert_fix_gate_allows_resume(state)


def test_unresolved_fix_remains_blocked() -> None:
    fix = _fix_record()
    fix["validation_result"] = "failed"
    state, record = evaluate_fix_completion(
        bundle_state=_bundle_state(),
        fix_execution_record=fix,
        fix_gate_record_ref="out/fix-1.fix_gate.json",
        now="2026-03-29T12:02:00Z",
    )
    assert record["gate_status"] == "blocked"
    with pytest.raises(PQXFixGateError, match="last fix gate status"):
        assert_fix_gate_allows_resume(state)


def test_mismatched_fix_to_finding_mapping() -> None:
    fix = _fix_record()
    fix["insertion_point"] = {**fix["insertion_point"], "anchor_step_id": "OTHER-STEP"}
    state, record = evaluate_fix_completion(
        bundle_state=_bundle_state(),
        fix_execution_record=fix,
        fix_gate_record_ref="out/fix-1.fix_gate.json",
        now="2026-03-29T12:02:00Z",
    )
    assert record["gate_status"] == "blocked"
    assert "does not map" in record["reasons"][0]
    assert "fix:REV-1:F-1" in state["unresolved_fixes"]


def test_duplicate_resolution_attempt_is_rejected() -> None:
    state = _bundle_state()
    state["resolved_fixes"] = ["fix:REV-1:F-1"]
    with pytest.raises(PQXFixGateError, match="duplicate resolution"):
        evaluate_fix_completion(
            bundle_state=state,
            fix_execution_record=_fix_record(),
            fix_gate_record_ref="out/fix-1.fix_gate.json",
            now="2026-03-29T12:02:00Z",
        )


def test_grouped_fix_target_can_pass_when_approved() -> None:
    fix = _fix_record()
    fix["insertion_point"] = {**fix["insertion_point"], "anchor_step_id": "AI-03"}
    state = _bundle_state()
    state["reinsertion_points"]["fix:REV-1:F-1"]["anchor_step_id"] = "AI-03"
    state, record = evaluate_fix_completion(
        bundle_state=state,
        fix_execution_record=fix,
        fix_gate_record_ref="out/fix-1.fix_gate.json",
        approved_grouped_fix_targets={"fix:REV-1:F-1": ["AI-03"]},
        now="2026-03-29T12:02:00Z",
    )
    assert record["gate_status"] == "passed"
    assert "AI-03" in record["accepted_target_step_ids"]
    assert_fix_gate_allows_resume(state)


def test_replay_parity_is_deterministic() -> None:
    state = _bundle_state()
    fix = _fix_record()
    one_state, one_record = evaluate_fix_completion(
        bundle_state=state,
        fix_execution_record=fix,
        fix_gate_record_ref="out/fix-1.fix_gate.json",
        now="2026-03-29T12:02:00Z",
    )
    two_state, two_record = evaluate_fix_completion(
        bundle_state=deepcopy(state),
        fix_execution_record=deepcopy(fix),
        fix_gate_record_ref="out/fix-1.fix_gate.json",
        now="2026-03-29T12:02:00Z",
    )
    assert one_record == two_record
    assert one_state == two_state


def test_resume_safe_behavior_after_gate_pass() -> None:
    state, _ = evaluate_fix_completion(
        bundle_state=_bundle_state(),
        fix_execution_record=_fix_record(),
        fix_gate_record_ref="out/fix-1.fix_gate.json",
        now="2026-03-29T12:02:00Z",
    )
    assert state["last_fix_gate_status"] == "passed"
    assert state["unresolved_fixes"] == []
    assert_fix_gate_allows_resume(state)
