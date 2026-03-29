from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.modules.runtime.pqx_bundle_state import (
    PQXBundleStateError,
    add_pending_fix,
    assert_valid_advancement,
    derive_resume_position,
    ingest_review_result,
    initialize_bundle_state,
    load_bundle_state,
    mark_bundle_complete,
    mark_step_complete,
    save_bundle_state,
)


BUNDLE_PLAN = [
    {"bundle_id": "BUNDLE-01", "step_ids": ["B3-01", "B3-02"], "depends_on": []},
]

REVIEW_REQ = [
    {
        "checkpoint_id": "BUNDLE-01:checkpoint:B3-01",
        "bundle_id": "BUNDLE-01",
        "review_type": "checkpoint_review",
        "scope": "step",
        "step_id": "B3-01",
        "required": True,
        "blocking_review_before_continue": True,
    }
]


def _init(requirements: list[dict] | None = None) -> dict:
    return initialize_bundle_state(
        bundle_plan=BUNDLE_PLAN,
        run_id="run-001",
        sequence_run_id="queue-run-001",
        roadmap_authority_ref="docs/roadmaps/system_roadmap.md",
        execution_plan_ref="docs/roadmaps/execution_bundles.md",
        now="2026-03-29T12:00:00Z",
        review_requirements=requirements or [],
    )


def _review_artifact(**overrides: object) -> dict:
    payload = {
        "schema_version": "1.0.0",
        "review_id": "REV-001",
        "checkpoint_id": "BUNDLE-01:checkpoint:B3-01",
        "review_type": "checkpoint_review",
        "bundle_id": "BUNDLE-01",
        "bundle_run_id": "queue-run-001",
        "roadmap_authority_ref": "docs/roadmaps/system_roadmap.md",
        "execution_plan_ref": "docs/roadmaps/execution_bundles.md",
        "scope": {"scope_type": "step", "step_id": "B3-01"},
        "findings": [
            {
                "finding_id": "F-001",
                "severity": "high",
                "category": "architecture",
                "title": "Need controlled remediation",
                "description": "A blocking issue was identified.",
                "affected_step_ids": ["B3-02"],
                "recommended_action": "Implement deterministic remediation.",
                "blocking": True,
                "source_refs": ["docs/reviews/REV-001.md#f1"],
            }
        ],
        "overall_disposition": "approved_with_findings",
        "created_at": "2026-03-29T12:01:00Z",
        "provenance_refs": ["trace:rev:001"],
    }
    payload.update(overrides)
    return payload


def test_blocks_when_required_checkpoint_review_missing() -> None:
    state = _init(REVIEW_REQ)
    state = mark_step_complete(state, BUNDLE_PLAN, step_id="B3-01", artifact_refs=[], now="2026-03-29T12:00:01Z")
    with pytest.raises(PQXBundleStateError, match="review checkpoint unresolved"):
        assert_valid_advancement(state, BUNDLE_PLAN, step_id="B3-02")


def test_valid_review_artifact_ingests_and_persists_pending_fixes(tmp_path: Path) -> None:
    state = mark_step_complete(_init(REVIEW_REQ), BUNDLE_PLAN, step_id="B3-01", artifact_refs=[], now="2026-03-29T12:00:01Z")
    updated = ingest_review_result(
        state,
        BUNDLE_PLAN,
        review_artifact=_review_artifact(),
        artifact_ref="docs/reviews/REV-001.json",
        now="2026-03-29T12:00:02Z",
    )
    assert updated["review_artifact_refs"][0]["review_id"] == "REV-001"
    assert updated["pending_fix_ids"][0]["source_finding_id"] == "F-001"

    persisted = save_bundle_state(updated, tmp_path / "bundle_state.json", bundle_plan=BUNDLE_PLAN)
    reloaded = load_bundle_state(tmp_path / "bundle_state.json", bundle_plan=BUNDLE_PLAN)
    assert persisted == reloaded


def test_malformed_review_fails_closed() -> None:
    state = _init(REVIEW_REQ)
    with pytest.raises(PQXBundleStateError, match="invalid pqx_review_result artifact"):
        ingest_review_result(
            state,
            BUNDLE_PLAN,
            review_artifact={"schema_version": "1.0.0"},
            artifact_ref="docs/reviews/bad.json",
            now="2026-03-29T12:00:02Z",
        )


def test_wrong_reference_fails_closed() -> None:
    state = _init(REVIEW_REQ)
    with pytest.raises(PQXBundleStateError, match="bundle_run_id mismatch"):
        ingest_review_result(
            state,
            BUNDLE_PLAN,
            review_artifact=_review_artifact(bundle_run_id="other-run"),
            artifact_ref="docs/reviews/REV-001.json",
            now="2026-03-29T12:00:02Z",
        )


def test_blocking_findings_prevent_continuation_and_completion() -> None:
    state = mark_step_complete(_init(REVIEW_REQ), BUNDLE_PLAN, step_id="B3-01", artifact_refs=[], now="2026-03-29T12:00:01Z")
    state = ingest_review_result(
        state,
        BUNDLE_PLAN,
        review_artifact=_review_artifact(),
        artifact_ref="docs/reviews/REV-001.json",
        now="2026-03-29T12:00:02Z",
    )
    with pytest.raises(PQXBundleStateError, match="blocking findings unresolved"):
        assert_valid_advancement(state, BUNDLE_PLAN, step_id="B3-02")

    state["pending_fix_ids"][0]["status"] = "resolved"
    resumed = mark_step_complete(state, BUNDLE_PLAN, step_id="B3-02", artifact_refs=[], now="2026-03-29T12:00:03Z")
    completed = mark_bundle_complete(resumed, BUNDLE_PLAN, bundle_id="BUNDLE-01", now="2026-03-29T12:00:04Z")
    assert completed["completed_bundle_ids"] == ["BUNDLE-01"]


def test_duplicate_conflicting_review_attachments_fail_closed() -> None:
    state = mark_step_complete(_init(REVIEW_REQ), BUNDLE_PLAN, step_id="B3-01", artifact_refs=[], now="2026-03-29T12:00:01Z")
    state = ingest_review_result(
        state,
        BUNDLE_PLAN,
        review_artifact=_review_artifact(),
        artifact_ref="docs/reviews/REV-001.json",
        now="2026-03-29T12:00:02Z",
    )
    with pytest.raises(PQXBundleStateError, match="conflicting review artifact"):
        ingest_review_result(
            state,
            BUNDLE_PLAN,
            review_artifact=_review_artifact(review_id="REV-002"),
            artifact_ref="docs/reviews/REV-002.json",
            now="2026-03-29T12:00:03Z",
        )


def test_legacy_add_pending_fix_still_works() -> None:
    state = _init()
    state = add_pending_fix(
        state,
        BUNDLE_PLAN,
        fix_id="B3-FIX-01",
        finding_id="F-legacy",
        target_bundle_id="BUNDLE-01",
        target_step_id="B3-02",
        status="planned",
        now="2026-03-29T12:00:02Z",
    )
    assert state["pending_fix_ids"][0]["status"] == "planned"
    assert state["unresolved_fixes"] == ["B3-FIX-01"]


def test_initialize_sets_fix_gate_defaults() -> None:
    state = _init()
    assert state["fix_gate_results"] == {}
    assert state["resolved_fixes"] == []
    assert state["unresolved_fixes"] == []
    assert state["last_fix_gate_status"] is None


def test_resume_position_still_deterministic() -> None:
    state = _init()
    state = mark_step_complete(state, BUNDLE_PLAN, step_id="B3-01", artifact_refs=[], now="2026-03-29T12:00:01Z")
    resume = derive_resume_position(state, BUNDLE_PLAN)
    assert resume["next_step_id"] == "B3-02"


def test_load_fail_closed_for_malformed_state(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"schema_version": "1.1.0"}), encoding="utf-8")
    with pytest.raises(PQXBundleStateError, match="invalid pqx_bundle_state artifact"):
        load_bundle_state(path, bundle_plan=BUNDLE_PLAN)
