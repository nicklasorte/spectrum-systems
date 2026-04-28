"""OC-07..09: Dashboard truth projection unit + red-team tests."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.observability.dashboard_truth_projection import (
    DashboardTruthProjectionError,
    build_dashboard_truth_projection,
)


def _aligned_inputs():
    repo_truth = {
        "current_status": "pass",
        "latest_proof_ref": "lpb-1",
        "owning_system": "GOV",
        "reason_code": "ALIGNED",
        "bottleneck_category": "none",
        "next_safe_action": "merge",
        "proof_digest": "deadbeef",
    }
    dashboard_view = dict(repo_truth)
    return repo_truth, dashboard_view


def test_projection_id_required():
    with pytest.raises(DashboardTruthProjectionError):
        build_dashboard_truth_projection(
            projection_id="",
            audit_timestamp="2026-04-28T00:00:00Z",
            repo_truth=None,
            dashboard_view=None,
        )


def test_aligned_inputs_yield_aligned():
    repo, dash = _aligned_inputs()
    out = build_dashboard_truth_projection(
        projection_id="dtp-1",
        audit_timestamp="2026-04-28T00:00:00Z",
        repo_truth=repo,
        dashboard_view=dash,
    )
    assert out["alignment_status"] == "aligned"
    assert out["current_status"] == "pass"
    assert out["alignment_findings"] == []


def test_no_inputs_yields_unknown():
    out = build_dashboard_truth_projection(
        projection_id="dtp-1",
        audit_timestamp="2026-04-28T00:00:00Z",
        repo_truth=None,
        dashboard_view=None,
    )
    assert out["alignment_status"] == "unknown"
    assert out["current_status"] == "unknown"


# ---- OC-08 red team: drift / corruption / missing owner / digest mismatch ----


def test_status_drift_blocks_with_block_severity():
    repo, dash = _aligned_inputs()
    dash["current_status"] = "block"
    out = build_dashboard_truth_projection(
        projection_id="dtp-1",
        audit_timestamp="2026-04-28T00:00:00Z",
        repo_truth=repo,
        dashboard_view=dash,
    )
    kinds = {f["finding_kind"] for f in out["alignment_findings"]}
    assert "stale_status" in kinds
    assert any(f["severity"] == "block" for f in out["alignment_findings"])
    assert out["alignment_status"] in ("drifted", "corrupt")
    assert out["current_status"] == "unknown"


def test_missing_owner_warns():
    repo, dash = _aligned_inputs()
    dash["owning_system"] = ""
    out = build_dashboard_truth_projection(
        projection_id="dtp-1",
        audit_timestamp="2026-04-28T00:00:00Z",
        repo_truth=repo,
        dashboard_view=dash,
    )
    kinds = {f["finding_kind"] for f in out["alignment_findings"]}
    assert "missing_owner" in kinds


def test_digest_mismatch_blocks():
    repo, dash = _aligned_inputs()
    dash["proof_digest"] = "cafebabe"
    out = build_dashboard_truth_projection(
        projection_id="dtp-1",
        audit_timestamp="2026-04-28T00:00:00Z",
        repo_truth=repo,
        dashboard_view=dash,
    )
    kinds = {f["finding_kind"] for f in out["alignment_findings"]}
    assert "digest_mismatch" in kinds


def test_corrupt_proof_ref_in_dashboard_blocks():
    repo, dash = _aligned_inputs()
    dash["latest_proof_ref"] = "lpb 1\n"  # contains whitespace
    out = build_dashboard_truth_projection(
        projection_id="dtp-1",
        audit_timestamp="2026-04-28T00:00:00Z",
        repo_truth=repo,
        dashboard_view=dash,
    )
    kinds = {f["finding_kind"] for f in out["alignment_findings"]}
    assert "ref_corrupt" in kinds
    assert out["alignment_status"] == "corrupt"


def test_missing_dashboard_view_marks_missing():
    repo, _ = _aligned_inputs()
    out = build_dashboard_truth_projection(
        projection_id="dtp-1",
        audit_timestamp="2026-04-28T00:00:00Z",
        repo_truth=repo,
        dashboard_view=None,
    )
    assert out["alignment_status"] == "missing"


def test_freshness_audit_propagates_stale_status():
    repo, dash = _aligned_inputs()
    out = build_dashboard_truth_projection(
        projection_id="dtp-1",
        audit_timestamp="2026-04-28T00:00:00Z",
        repo_truth=repo,
        dashboard_view=dash,
        freshness_audit={"overall_status": "stale"},
    )
    assert out["freshness_status"] == "stale"
    kinds = {f["finding_kind"] for f in out["alignment_findings"]}
    assert "stale_status" in kinds


def test_category_mismatch_blocks():
    repo, dash = _aligned_inputs()
    dash["bottleneck_category"] = "eval"
    out = build_dashboard_truth_projection(
        projection_id="dtp-1",
        audit_timestamp="2026-04-28T00:00:00Z",
        repo_truth=repo,
        dashboard_view=dash,
    )
    kinds = {f["finding_kind"] for f in out["alignment_findings"]}
    assert "category_mismatch" in kinds
