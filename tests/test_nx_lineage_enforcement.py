"""NX-10..12: Lineage enforcement red-team and coverage fixtures."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.lineage.lineage_enforcement import (
    CANONICAL_LINEAGE_REASON_CODES,
    LineageEnforcementError,
    assert_lineage_promotion_prerequisites,
    build_lineage_coverage_summary,
)


def _store() -> dict:
    return {
        "input-1": {
            "artifact_id": "input-1",
            "artifact_type": "input_bundle",
            "upstream_artifacts": [],
            "trace_id": "t1",
            "run_id": "r1",
        },
        "mid-1": {
            "artifact_id": "mid-1",
            "artifact_type": "eval_result",
            "upstream_artifacts": ["input-1"],
            "trace_id": "t1",
            "run_id": "r1",
        },
        "out-1": {
            "artifact_id": "out-1",
            "artifact_type": "closure_decision_artifact",
            "upstream_artifacts": ["mid-1"],
            "trace_id": "t1",
            "run_id": "r1",
        },
    }


def test_complete_lineage_allows() -> None:
    store = _store()
    res = assert_lineage_promotion_prerequisites(
        artifact=store["out-1"], artifact_store=store
    )
    assert res["decision"] == "allow"
    assert res["reason_code"] == "LINEAGE_OK"


# ---- NX-11 red team ----


def test_red_team_missing_parent_blocks() -> None:
    store = _store()
    artifact = dict(store["out-1"])
    artifact["upstream_artifacts"] = ["does-not-exist"]
    res = assert_lineage_promotion_prerequisites(artifact=artifact, artifact_store=store)
    assert res["decision"] == "block"
    assert res["reason_code"] == "LINEAGE_MISSING_PARENT_ARTIFACT"


def test_red_team_no_parents_non_root_blocks() -> None:
    store = _store()
    artifact = dict(store["out-1"])
    artifact["upstream_artifacts"] = []
    res = assert_lineage_promotion_prerequisites(artifact=artifact, artifact_store=store)
    assert res["decision"] == "block"
    assert res["reason_code"] == "LINEAGE_ORPHANED_NON_ROOT"


def test_red_team_missing_trace_id_blocks() -> None:
    store = _store()
    artifact = dict(store["out-1"])
    artifact["trace_id"] = ""
    res = assert_lineage_promotion_prerequisites(artifact=artifact, artifact_store=store)
    assert res["decision"] == "block"
    assert res["reason_code"] == "LINEAGE_MISSING_TRACE_ID"


def test_red_team_missing_run_id_blocks() -> None:
    store = _store()
    artifact = dict(store["out-1"])
    artifact["run_id"] = ""
    res = assert_lineage_promotion_prerequisites(artifact=artifact, artifact_store=store)
    assert res["decision"] == "block"
    assert res["reason_code"] == "LINEAGE_MISSING_RUN_ID"


def test_red_team_missing_produced_artifact_blocks() -> None:
    store = _store()
    artifact = dict(store["out-1"])
    artifact["artifact_id"] = "ghost-artifact"
    res = assert_lineage_promotion_prerequisites(artifact=artifact, artifact_store=store)
    assert res["decision"] == "block"
    assert res["reason_code"] == "LINEAGE_MISSING_PRODUCED_ARTIFACT"


def test_red_team_missing_input_chain_blocks() -> None:
    """Disconnect mid-1 from its input parent — chain to immutable input fails."""
    store = _store()
    # Remove the input-1 entry so traversal cannot reach an input type.
    store_broken = {k: v for k, v in store.items() if k != "input-1"}
    res = assert_lineage_promotion_prerequisites(
        artifact=store["out-1"], artifact_store=store_broken
    )
    assert res["decision"] == "block"
    # Either parent missing or input chain missing — both are valid fail-closed reasons
    assert res["reason_code"] in {
        "LINEAGE_MISSING_PARENT_ARTIFACT",
        "LINEAGE_MISSING_INPUT_CHAIN",
    }


def test_red_team_artifact_store_unavailable_blocks() -> None:
    res = assert_lineage_promotion_prerequisites(
        artifact={"artifact_id": "x", "artifact_type": "eval_result", "trace_id": "t", "run_id": "r"},
        artifact_store=None,
    )
    assert res["decision"] == "block"
    assert res["reason_code"] == "LINEAGE_STORE_UNAVAILABLE"


def test_red_team_input_artifact_no_parents_allowed() -> None:
    store = _store()
    res = assert_lineage_promotion_prerequisites(
        artifact=store["input-1"], artifact_store=store
    )
    assert res["decision"] == "allow"


def test_lineage_coverage_summary_blocks_on_any_failure() -> None:
    store = _store()
    bad = dict(store["out-1"])
    bad["artifact_id"] = "bad-out"
    bad["upstream_artifacts"] = ["does-not-exist"]
    summary = build_lineage_coverage_summary(
        artifacts=[store["input-1"], store["mid-1"], store["out-1"], bad],
        artifact_store={**store, "bad-out": bad},
    )
    assert summary["status"] == "blocked"
    assert summary["incomplete"] >= 1
    assert "LINEAGE_MISSING_PARENT_ARTIFACT" in summary["reason_codes"]


def test_lineage_coverage_summary_healthy() -> None:
    store = _store()
    summary = build_lineage_coverage_summary(
        artifacts=list(store.values()), artifact_store=store
    )
    assert summary["status"] == "healthy"
    assert summary["completeness_rate"] == pytest.approx(1.0)


def test_lineage_coverage_empty_blocks() -> None:
    summary = build_lineage_coverage_summary(artifacts=[], artifact_store={})
    assert summary["status"] == "blocked"


def test_canonical_reason_codes_are_finite() -> None:
    assert "LINEAGE_OK" in CANONICAL_LINEAGE_REASON_CODES
    assert "LINEAGE_MISSING_TRACE_ID" in CANONICAL_LINEAGE_REASON_CODES
