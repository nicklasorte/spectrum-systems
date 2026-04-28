"""OC-16..18: Fast trust gate manifest + coverage red-team tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.modules.governance.fast_trust_gate import (
    DEFAULT_MANIFEST_PATH,
    REQUIRED_SEAMS,
    audit_fast_trust_gate_coverage,
    build_fast_trust_gate_run_summary,
    load_fast_trust_gate_manifest,
)


def test_default_manifest_loads_and_is_well_formed():
    manifest = load_fast_trust_gate_manifest()
    assert manifest["artifact_type"] == "fast_trust_gate_manifest"
    seams = manifest["required_seams"]
    assert set(seams) == set(REQUIRED_SEAMS)


def test_default_manifest_covers_required_seams():
    manifest = load_fast_trust_gate_manifest()
    coverage = audit_fast_trust_gate_coverage(manifest)
    assert coverage["coverage_status"] == "sufficient"
    assert coverage["missing_seams"] == []
    assert coverage["missing_selectors"] == []


# ---- OC-17 red team: dropping a seam must fail ----


def test_dropping_a_seam_yields_insufficient(tmp_path: Path):
    manifest = load_fast_trust_gate_manifest()
    weakened = json.loads(json.dumps(manifest))
    # Drop trust_regression_pack from required seams
    weakened["required_seams"] = [
        s for s in weakened["required_seams"] if s != "trust_regression_pack"
    ]
    weakened["selectors"] = [
        s for s in weakened["selectors"] if s["seam"] != "trust_regression_pack"
    ]
    coverage = audit_fast_trust_gate_coverage(weakened)
    assert coverage["coverage_status"] == "insufficient"
    assert "trust_regression_pack" in coverage["missing_seams"]


def test_dropping_a_selector_only_yields_insufficient():
    manifest = load_fast_trust_gate_manifest()
    weakened = json.loads(json.dumps(manifest))
    weakened["selectors"] = [
        s for s in weakened["selectors"] if s["seam"] != "proof_intake"
    ]
    coverage = audit_fast_trust_gate_coverage(weakened)
    assert coverage["coverage_status"] == "insufficient"
    assert "proof_intake" in coverage["missing_selectors"]


def test_run_summary_marks_missing_seams_as_failed():
    manifest = load_fast_trust_gate_manifest()
    summary = build_fast_trust_gate_run_summary(
        run_id="ftg-1",
        audit_timestamp="2026-04-28T00:00:00Z",
        manifest=manifest,
        seam_results=[
            {"seam": "registry_validation", "status": "ok"},
            {"seam": "authority_shape_preflight", "status": "ok"},
            # other seams missing on purpose
        ],
    )
    assert summary["overall_status"] == "failed"
    assert "trust_regression_pack" in summary["missing_seams"]


def test_run_summary_ok_when_every_required_seam_ok():
    manifest = load_fast_trust_gate_manifest()
    seam_results = [{"seam": s, "status": "ok"} for s in REQUIRED_SEAMS]
    summary = build_fast_trust_gate_run_summary(
        run_id="ftg-1",
        audit_timestamp="2026-04-28T00:00:00Z",
        manifest=manifest,
        seam_results=seam_results,
    )
    assert summary["overall_status"] == "ok"
    assert summary["sufficiency"] == "sufficient"
    assert summary["reason_code"] == "FAST_TRUST_GATE_OK"


def test_one_failed_seam_propagates_to_overall():
    manifest = load_fast_trust_gate_manifest()
    seam_results = [{"seam": s, "status": "ok"} for s in REQUIRED_SEAMS]
    seam_results[0]["status"] = "failed"
    summary = build_fast_trust_gate_run_summary(
        run_id="ftg-1",
        audit_timestamp="2026-04-28T00:00:00Z",
        manifest=manifest,
        seam_results=seam_results,
    )
    assert summary["overall_status"] == "failed"


def test_default_manifest_path_exists():
    assert DEFAULT_MANIFEST_PATH.exists()
