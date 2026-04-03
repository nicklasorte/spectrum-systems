from __future__ import annotations

from datetime import datetime, timezone

import pytest

from spectrum_systems.modules.runtime.context_selector import (
    ContextSelectorError,
    build_context_bundle,
)


_NOW = datetime(2026, 4, 3, tzinfo=timezone.utc)


def _artifact(
    artifact_type: str,
    artifact_id: str,
    *,
    created_at: str,
    batch_id: str = "BATCH-O",
    module_refs: list[str] | None = None,
    status: str | None = None,
) -> dict:
    payload = {
        "artifact_type": artifact_type,
        "artifact_id": artifact_id,
        "created_at": created_at,
        "batch_id": batch_id,
        "module_refs": module_refs or [],
    }
    if status is not None:
        payload["status"] = status
    return payload


def _bundle() -> dict:
    return build_context_bundle(
        roadmap_state={"source_refs": ["roadmap:rm-1"]},
        target_scope={"scope_type": "batch_id", "scope_id": "BATCH-O"},
        review_artifacts=[
            _artifact("review_artifact", "rvw-1", created_at="2026-04-03T00:00:00Z", module_refs=["m/a.py"]),
        ],
        eval_artifacts=[
            _artifact("eval_result", "eval-1", created_at="2026-04-03T01:00:00Z", module_refs=["m/a.py"]),
        ],
        failure_artifacts=[
            _artifact("failure_eval_case", "fail-open", created_at="2026-04-03T00:30:00Z", module_refs=["m/a.py"], status="open"),
            _artifact("failure_eval_case", "fail-closed", created_at="2026-04-03T00:20:00Z", module_refs=["m/a.py"], status="closed"),
        ],
        build_report_artifacts=[
            _artifact("build_report", "br-1", created_at="2026-04-03T02:00:00Z", module_refs=["m/a.py"]),
        ],
        handoff_artifacts=[
            _artifact("next_slice_handoff", "handoff-1", created_at="2026-04-03T02:30:00Z", module_refs=["m/a.py"]),
        ],
        pqx_execution_artifacts=[
            _artifact("pqx_review_result", "pqx-1", created_at="2026-04-03T03:00:00Z", module_refs=["m/b.py"]),
        ],
        touched_module_refs=["m/a.py"],
        active_risks=[
            {
                "risk_id": "r1",
                "risk_ref": "risk_register:r1",
                "status": "active",
                "severity": "high",
                "related_refs": ["failure_eval_case:fail-open"],
            }
        ],
        intent_refs=["intent:ctx-governed-pipeline"],
        trace_id="trace-1",
        now=_NOW,
    )


def test_selection_includes_relevant_and_excludes_irrelevant() -> None:
    bundle = _bundle()
    refs = bundle["selected_artifact_refs"]
    assert "build_report:br-1" in refs
    assert "next_slice_handoff:handoff-1" in refs
    assert all("unknown" not in ref for ref in refs)


def test_fail_closed_when_required_inputs_missing() -> None:
    with pytest.raises(ContextSelectorError, match="missing required inputs"):
        build_context_bundle(
            roadmap_state={},
            target_scope={"scope_type": "batch_id", "scope_id": "BATCH-O"},
            review_artifacts=[],
            eval_artifacts=[],
            failure_artifacts=[],
            build_report_artifacts=[],
            handoff_artifacts=[],
            pqx_execution_artifacts=[],
            touched_module_refs=[],
            active_risks=[],
            intent_refs=[],
            trace_id="",
        )


def test_ranking_is_deterministic() -> None:
    b1 = _bundle()
    b2 = _bundle()
    assert b1["selected_artifact_refs"] == b2["selected_artifact_refs"]


def test_lifecycle_drops_stale_but_keeps_active_risk_linked_artifacts() -> None:
    stale = _artifact("eval_result", "eval-stale", created_at="2026-02-01T00:00:00Z", module_refs=["m/a.py"])
    risk_linked_stale = _artifact("failure_eval_case", "fail-risk-old", created_at="2026-02-01T00:00:00Z", module_refs=["m/a.py"], status="open")

    bundle = build_context_bundle(
        roadmap_state={"source_refs": []},
        target_scope={"scope_type": "batch_id", "scope_id": "BATCH-O"},
        review_artifacts=[],
        eval_artifacts=[stale],
        failure_artifacts=[risk_linked_stale],
        build_report_artifacts=[_artifact("build_report", "br-1", created_at="2026-04-03T02:00:00Z")],
        handoff_artifacts=[_artifact("next_slice_handoff", "handoff-1", created_at="2026-04-03T02:30:00Z")],
        pqx_execution_artifacts=[],
        touched_module_refs=["m/a.py"],
        active_risks=[
            {
                "risk_id": "r1",
                "risk_ref": "risk_register:r1",
                "status": "active",
                "severity": "critical",
                "related_refs": ["failure_eval_case:fail-risk-old"],
            }
        ],
        intent_refs=[],
        trace_id="trace-2",
        now=_NOW,
        stale_after_days=14,
    )
    refs = bundle["selected_artifact_refs"]
    assert "eval_result:eval-stale" not in refs
    assert "failure_eval_case:fail-risk-old" in refs
