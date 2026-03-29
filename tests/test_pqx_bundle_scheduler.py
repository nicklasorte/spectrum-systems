from __future__ import annotations

from spectrum_systems.modules.runtime.pqx_bundle_orchestrator import BundleDefinition, select_next_runnable_bundle


def _plan() -> list[BundleDefinition]:
    return [
        BundleDefinition(bundle_id="BUNDLE-A", ordered_step_ids=("AI-01",), depends_on=()),
        BundleDefinition(bundle_id="BUNDLE-B", ordered_step_ids=("AI-02",), depends_on=("BUNDLE-A",)),
    ]


def test_scheduler_selects_dependency_valid_readiness_approved_bundle() -> None:
    decision = select_next_runnable_bundle(
        bundle_plan=_plan(),
        bundle_states={
            "BUNDLE-A": {"status": "pending", "readiness_approved": True, "unresolved_findings": [], "pending_fix_ids": []},
            "BUNDLE-B": {"status": "pending", "readiness_approved": True, "unresolved_findings": [], "pending_fix_ids": []},
        },
        run_id="run-1",
        trace_id="trace-1",
        now="2026-03-29T00:00:00Z",
    )
    assert decision["outcome"] == "selected"
    assert decision["selected_bundle_id"] == "BUNDLE-A"


def test_scheduler_blocks_on_ambiguous_runnable_bundle() -> None:
    plan = [BundleDefinition(bundle_id="BUNDLE-A", ordered_step_ids=("AI-01",), depends_on=()), BundleDefinition(bundle_id="BUNDLE-C", ordered_step_ids=("AI-03",), depends_on=())]
    decision = select_next_runnable_bundle(
        bundle_plan=plan,
        bundle_states={
            "BUNDLE-A": {"status": "pending", "readiness_approved": True, "unresolved_findings": [], "pending_fix_ids": []},
            "BUNDLE-C": {"status": "pending", "readiness_approved": True, "unresolved_findings": [], "pending_fix_ids": []},
        },
        run_id="run-2",
        trace_id="trace-2",
        now="2026-03-29T00:00:00Z",
    )
    assert decision["outcome"] == "blocked"
    assert decision["block_type"] == "AMBIGUOUS_RUNNABLE_BUNDLE"


def test_scheduler_blocks_when_no_runnable_bundle_exists() -> None:
    decision = select_next_runnable_bundle(
        bundle_plan=_plan(),
        bundle_states={
            "BUNDLE-A": {"status": "pending", "readiness_approved": False, "unresolved_findings": ["F-1"], "pending_fix_ids": ["fix-1"]},
            "BUNDLE-B": {"status": "pending", "readiness_approved": False, "unresolved_findings": [], "pending_fix_ids": []},
        },
        run_id="run-3",
        trace_id="trace-3",
        now="2026-03-29T00:00:00Z",
    )
    assert decision["outcome"] == "blocked"
    assert decision["block_type"] == "NO_RUNNABLE_BUNDLE"


def test_scheduler_respects_canary_freeze_state() -> None:
    decision = select_next_runnable_bundle(
        bundle_plan=[BundleDefinition(bundle_id="BUNDLE-A", ordered_step_ids=("AI-01",), depends_on=())],
        bundle_states={"BUNDLE-A": {"status": "pending", "readiness_approved": True, "unresolved_findings": [], "pending_fix_ids": [], "canary_status": "frozen"}},
        run_id="run-4",
        trace_id="trace-4",
        now="2026-03-29T00:00:00Z",
    )
    assert decision["outcome"] == "blocked"
    assert decision["block_type"] == "NO_RUNNABLE_BUNDLE"
    assert any(item["block_type"] == "CANARY_FROZEN" for item in decision["blocked_candidates"])
