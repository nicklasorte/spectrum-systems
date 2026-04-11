"""Deterministic tests for GOVERNED-KERNEL-24-01 execution kernel."""

from __future__ import annotations

import json
from pathlib import Path

from spectrum_systems.modules.runtime.governed_execution_kernel import run_governed_kernel_24_01


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_emits_required_reports_and_closeout_artifacts(tmp_path: Path) -> None:
    outputs = run_governed_kernel_24_01(tmp_path)

    for name in (
        "delivery_report.json",
        "review_report.json",
        "checkpoint_summary.json",
        "publication_manifest.json",
        "closeout_artifact.json",
    ):
        payload = outputs[name]
        assert payload
        assert (tmp_path / name).is_file()


def test_enforces_canonical_owner_boundaries_and_lineage(tmp_path: Path) -> None:
    run_governed_kernel_24_01(tmp_path)

    cross_check = _load(tmp_path / "registry_cross_check.json")
    assert cross_check["status"] == "PASS"
    assert all(cross_check["checks"].values())

    lineage = _load(tmp_path / "lineage_verification.json")
    assert lineage["required_chain"] == ["AEX", "TLC", "TPA", "PQX"]
    assert lineage["status"] == "PASS"


def test_deploy_gate_fail_closed_when_readiness_not_authorized(tmp_path: Path) -> None:
    run_governed_kernel_24_01(tmp_path)

    gate = _load(tmp_path / "deploy_promotion_gate.json")
    assert gate["owner"] == "SEL"
    assert gate["status"] == "BLOCK"
    assert gate["checked_constraints"]["reports_present"] is True
    assert gate["checked_constraints"]["readiness_evidence_sufficient"] is False

    cde = _load(tmp_path / "cde_authority_output.json")
    assert cde["owner"] == "CDE"
    assert cde["promotion_readiness"] == "not_authorized"
