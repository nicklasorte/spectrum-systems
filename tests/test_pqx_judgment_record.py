from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.modules.runtime.pqx_judgment import PQXJudgmentError, build_pqx_judgment_record


def test_blocked_admission_emits_judgment_record() -> None:
    record = build_pqx_judgment_record(
        record_id="judgment:1",
        decision_type="blocked_bundle_admission",
        outcome="blocked",
        reasons=["readiness gate failed"],
        artifact_refs=["out/record.json"],
        bundle_id="BUNDLE-PQX-CORE",
        slice_id=None,
        run_id="run-1",
        trace_id="trace-1",
        created_at="2026-03-29T00:00:00Z",
        policy_refs=["docs/roadmaps/system_roadmap.md"],
    )
    assert record["outcome"] == "blocked"


def test_blocked_review_emits_judgment_record() -> None:
    record = build_pqx_judgment_record(
        record_id="judgment:2",
        decision_type="blocked_review_checkpoint",
        outcome="blocked",
        reasons=["required review unresolved"],
        artifact_refs=["out/review.json"],
        bundle_id="BUNDLE-PQX-CORE",
        slice_id="AI-02",
        run_id="run-2",
        trace_id="trace-2",
        created_at="2026-03-29T00:00:00Z",
    )
    assert record["affected_slice_id"] == "AI-02"


def test_resolved_fix_emits_judgment_record() -> None:
    record = build_pqx_judgment_record(
        record_id="judgment:3",
        decision_type="resolved_fix",
        outcome="resolved",
        reasons=["fix gate passed"],
        artifact_refs=["out/fix_gate.json"],
        bundle_id="BUNDLE-PQX-CORE",
        slice_id="AI-03",
        run_id="run-3",
        trace_id="trace-3",
        created_at="2026-03-29T00:00:00Z",
    )
    assert record["outcome"] == "resolved"


def test_resumed_execution_emits_judgment_record() -> None:
    record = build_pqx_judgment_record(
        record_id="judgment:4",
        decision_type="resumed_bundle_after_pause",
        outcome="resumed",
        reasons=["resume token validated"],
        artifact_refs=["out/state.json"],
        bundle_id="BUNDLE-PQX-CORE",
        slice_id=None,
        run_id="run-4",
        trace_id="trace-4",
        created_at="2026-03-29T00:00:00Z",
    )
    assert record["outcome"] == "resumed"


def test_missing_reason_fails_closed() -> None:
    with pytest.raises(PQXJudgmentError, match="at least one decision reason"):
        build_pqx_judgment_record(
            record_id="judgment:5",
            decision_type="blocked_bundle_admission",
            outcome="blocked",
            reasons=[],
            artifact_refs=["out/state.json"],
            bundle_id="BUNDLE-PQX-CORE",
            slice_id=None,
            run_id="run-5",
            trace_id="trace-5",
            created_at="2026-03-29T00:00:00Z",
        )
