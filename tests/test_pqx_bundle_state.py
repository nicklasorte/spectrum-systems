from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.modules.runtime.pqx_bundle_state import (
    PQXBundleStateError,
    add_pending_fix,
    assert_valid_advancement,
    attach_review_artifact,
    block_step,
    derive_resume_position,
    initialize_bundle_state,
    load_bundle_state,
    mark_bundle_complete,
    mark_step_complete,
    save_bundle_state,
    validate_bundle_state,
)


BUNDLE_PLAN = [
    {"bundle_id": "BUNDLE-01", "step_ids": ["B3-01", "B3-02"], "depends_on": []},
    {"bundle_id": "BUNDLE-02", "step_ids": ["B3-03"], "depends_on": ["BUNDLE-01"]},
]


def _init() -> dict:
    return initialize_bundle_state(
        bundle_plan=BUNDLE_PLAN,
        run_id="run-001",
        sequence_run_id="queue-run-001",
        roadmap_authority_ref="docs/roadmaps/system_roadmap.md",
        execution_plan_ref="docs/roadmaps/execution_bundles.md",
        now="2026-03-29T12:00:00Z",
    )


def test_initialize_and_persist_reload_parity(tmp_path: Path) -> None:
    state = _init()
    validate_bundle_state(state)

    persisted = save_bundle_state(state, tmp_path / "bundle_state.json", bundle_plan=BUNDLE_PLAN)
    reloaded = load_bundle_state(tmp_path / "bundle_state.json", bundle_plan=BUNDLE_PLAN)
    assert persisted == reloaded


def test_step_advancement_updates_deterministically() -> None:
    state = _init()
    assert_valid_advancement(state, BUNDLE_PLAN, step_id="B3-01")
    next_state = mark_step_complete(
        state,
        BUNDLE_PLAN,
        step_id="B3-01",
        artifact_refs=["data/pqx_runs/B3-01/run-1.result.json"],
        now="2026-03-29T12:00:01Z",
    )
    assert next_state["completed_step_ids"] == ["B3-01"]
    assert next_state["resume_position"]["next_step_id"] == "B3-02"


def test_dependency_block_for_out_of_order_step() -> None:
    state = _init()
    with pytest.raises(PQXBundleStateError, match="prior step 'B3-01'"):
        mark_step_complete(state, BUNDLE_PLAN, step_id="B3-02", artifact_refs=[], now="2026-03-29T12:00:01Z")


def test_bundle_order_block() -> None:
    state = _init()
    with pytest.raises(PQXBundleStateError, match="out-of-order"):
        mark_step_complete(state, BUNDLE_PLAN, step_id="B3-03", artifact_refs=[], now="2026-03-29T12:00:01Z")


def test_duplicate_completion_blocked() -> None:
    state = mark_step_complete(_init(), BUNDLE_PLAN, step_id="B3-01", artifact_refs=[], now="2026-03-29T12:00:01Z")
    with pytest.raises(PQXBundleStateError, match="already completed"):
        mark_step_complete(state, BUNDLE_PLAN, step_id="B3-01", artifact_refs=[], now="2026-03-29T12:00:02Z")


def test_review_and_fix_attachment_and_malformed_rejection() -> None:
    state = _init()
    state = attach_review_artifact(
        state,
        BUNDLE_PLAN,
        review_id="REV-001",
        bundle_id="BUNDLE-01",
        step_id="B3-01",
        artifact_ref="docs/reviews/REV-001.md",
        now="2026-03-29T12:00:01Z",
    )
    assert state["review_artifact_refs"][0]["review_id"] == "REV-001"

    state = add_pending_fix(
        state,
        BUNDLE_PLAN,
        fix_id="B3-FIX-01",
        finding_id="F-001",
        target_bundle_id="BUNDLE-01",
        target_step_id="B3-02",
        status="planned",
        now="2026-03-29T12:00:02Z",
    )
    assert state["pending_fix_ids"][0]["fix_id"] == "B3-FIX-01"

    with pytest.raises(PQXBundleStateError, match="target mismatch"):
        add_pending_fix(
            state,
            BUNDLE_PLAN,
            fix_id="B3-FIX-02",
            finding_id="F-002",
            target_bundle_id="BUNDLE-02",
            target_step_id="B3-02",
            status="planned",
            now="2026-03-29T12:00:03Z",
        )


def test_resume_position_and_bundle_completion() -> None:
    state = _init()
    state = mark_step_complete(state, BUNDLE_PLAN, step_id="B3-01", artifact_refs=[], now="2026-03-29T12:00:01Z")
    state = mark_step_complete(state, BUNDLE_PLAN, step_id="B3-02", artifact_refs=[], now="2026-03-29T12:00:02Z")
    state = mark_bundle_complete(state, BUNDLE_PLAN, bundle_id="BUNDLE-01", now="2026-03-29T12:00:03Z")

    resume = derive_resume_position(state, BUNDLE_PLAN)
    assert resume["bundle_id"] == "BUNDLE-02"
    assert resume["next_step_id"] == "B3-03"


def test_block_step_and_load_fail_closed_for_malformed_state(tmp_path: Path) -> None:
    state = block_step(_init(), BUNDLE_PLAN, step_id="B3-01", now="2026-03-29T12:00:01Z")
    assert state["blocked_step_ids"] == ["B3-01"]

    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"schema_version": "1.0.0"}), encoding="utf-8")
    with pytest.raises(PQXBundleStateError, match="invalid pqx_bundle_state artifact"):
        load_bundle_state(path, bundle_plan=BUNDLE_PLAN)
