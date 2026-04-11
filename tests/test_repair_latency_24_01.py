"""Tests for scripts/run_repair_latency_24_01.py."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_repair_latency_24_01.py"
ARTIFACT_ROOT = REPO_ROOT / "artifacts" / "repair_latency_24_01"
TRACE_PATH = REPO_ROOT / "artifacts" / "rdx_runs" / "REPAIR-LATENCY-24-01-artifact-trace.json"


def _run_script() -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT_PATH)], cwd=str(REPO_ROOT), capture_output=True, text=True, check=True)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_script_emits_all_umbrella_checkpoints_and_trace() -> None:
    _run_script()

    for index in range(1, 5):
        checkpoint = ARTIFACT_ROOT / f"umbrella-{index}_checkpoint.json"
        assert checkpoint.is_file()

    trace = _load_json(TRACE_PATH)
    assert trace["execution_mode"] == "SERIAL WITH HARD CHECKPOINTS"
    assert trace["umbrella_sequence"] == ["UMBRELLA-1", "UMBRELLA-2", "UMBRELLA-3", "UMBRELLA-4"]


def test_umbrella_1_shift_left_and_fast_path_outputs() -> None:
    _run_script()

    ril_packet = _load_json(ARTIFACT_ROOT / "umbrella_1" / "repairable_failure_interpretation_packet.json")
    assert ril_packet["owner"] == "RIL"
    assert ril_packet["interpretation_boundary"] == "interpretation_only_not_authority"

    tpa_gate = _load_json(ARTIFACT_ROOT / "umbrella_1" / "fast_path_tpa_slice_artifact.json")
    assert tpa_gate["owner"] == "TPA"

    pqx_exec = _load_json(ARTIFACT_ROOT / "umbrella_1" / "fast_path_repair_execution_record.json")
    assert pqx_exec["lineage"] == ["AEX", "TLC", "TPA", "PQX"]


def test_umbrella_2_orchestration_shortcuts_and_post_repair_replay() -> None:
    _run_script()

    shortcut = _load_json(ARTIFACT_ROOT / "umbrella_2" / "repair_shortcut_handoff_record.json")
    assert shortcut["owner"] == "TLC"
    assert shortcut["orchestration_only"] is True

    replay = _load_json(ARTIFACT_ROOT / "umbrella_2" / "post_repair_replay_execution_record.json")
    assert replay["owner"] == "PQX"
    assert replay["replay_executed"] is True

    review = _load_json(ARTIFACT_ROOT / "umbrella_2" / "repair_replay_review_result.json")
    assert review["owner"] == "RQX"


def test_umbrella_3_repair_memory_and_prioritization_outputs() -> None:
    _run_script()

    scoreboard = _load_json(ARTIFACT_ROOT / "umbrella_3" / "repair_latency_scoreboard.json")
    assert scoreboard["owner"] == "PRG"
    assert scoreboard["median_seconds"]["fast_path"] < scoreboard["median_seconds"]["standard_path"]

    recommendation = _load_json(ARTIFACT_ROOT / "umbrella_3" / "repair_priority_recommendation.json")
    assert recommendation["authoritative"] is False

    umbrella_plan = _load_json(ARTIFACT_ROOT / "umbrella_3" / "repair_latency_umbrella_plan.json")
    assert umbrella_plan["owner"] == "RDX"


def test_umbrella_4_auto_remediation_and_closure_outputs() -> None:
    _run_script()

    admissibility = _load_json(ARTIFACT_ROOT / "umbrella_4" / "auto_remediation_admissibility_record.json")
    assert admissibility["owner"] == "TPA"

    strictness = _load_json(ARTIFACT_ROOT / "umbrella_4" / "repair_closure_strictness_decision.json")
    assert strictness["owner"] == "CDE"

    projection = _load_json(ARTIFACT_ROOT / "umbrella_4" / "repair_loop_projection_bundle.json")
    assert projection["owner"] == "MAP"
    assert projection["semantics_invented"] is False


def test_required_reporting_cross_checks_and_closeout_are_non_empty() -> None:
    _run_script()

    required_paths = [
        ARTIFACT_ROOT / "umbrella_1" / "canonical_delivery_report_artifact.json",
        ARTIFACT_ROOT / "umbrella_1" / "canonical_review_report_artifact.json",
        ARTIFACT_ROOT / "checkpoint_summary.json",
        ARTIFACT_ROOT / "registry_alignment_result.json",
        ARTIFACT_ROOT / "closeout_artifact.json",
    ]

    for path in required_paths:
        assert path.is_file()
        assert path.stat().st_size > 2

    alignment = _load_json(ARTIFACT_ROOT / "registry_alignment_result.json")
    assert len(alignment["cross_checks"]) == 15
    assert all(status == "pass" for status in alignment["cross_checks"].values())

    closeout = _load_json(ARTIFACT_ROOT / "closeout_artifact.json")
    assert all(closeout["final_success_conditions"].values())
