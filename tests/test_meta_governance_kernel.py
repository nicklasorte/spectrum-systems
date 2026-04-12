"""Deterministic tests for MG-KERNEL-24-01 meta-governance layer."""

from __future__ import annotations

import json
from pathlib import Path

from spectrum_systems.modules.runtime.meta_governance_kernel import run_meta_governance_kernel_24_01


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_emits_required_reports_and_checkpoint_artifacts(tmp_path: Path) -> None:
    outputs = run_meta_governance_kernel_24_01(tmp_path)

    for name in (
        "delivery_report.json",
        "review_report.json",
        "checkpoint_summary.json",
        "registry_cross_check.json",
    ):
        assert outputs[name]
        assert (tmp_path / name).is_file()


def test_registry_invariants_and_authority_boundaries_hold(tmp_path: Path) -> None:
    run_meta_governance_kernel_24_01(tmp_path)

    cross_check = _load(tmp_path / "registry_cross_check.json")
    assert cross_check["status"] == "PASS"
    assert all(cross_check["checks"].values())

    report_bundle = _load(tmp_path / "report_evidence_quality_bundle.json")
    assert report_bundle["false_readiness_detector"]["owner"] == "SEL"


def test_serial_hard_checkpoints_emit_for_each_umbrella(tmp_path: Path) -> None:
    run_meta_governance_kernel_24_01(tmp_path)

    checkpoint_summary = _load(tmp_path / "checkpoint_summary.json")
    assert checkpoint_summary["status"] == "PASS"
    umbrellas = [checkpoint["umbrella"] for checkpoint in checkpoint_summary["checkpoints"]]
    assert umbrellas == [
        "ROADMAP_AND_PROMPT_BURDEN",
        "REPORT_AND_EVIDENCE_QUALITY",
        "LIVE_TRUTH_AND_OPERATIONAL_RISK",
        "LEARNING_AND_GOVERNANCE_DEBT",
    ]
    assert all(checkpoint["status"] == "PASS" for checkpoint in checkpoint_summary["checkpoints"])
