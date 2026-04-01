import json
import subprocess
import sys
from pathlib import Path

import pytest

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.orchestration.roadmap_eligibility import (
    RoadmapEligibilityError,
    build_roadmap_eligibility,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def _base_roadmap() -> dict:
    return {
        "artifact_id": "roadmap-test-001",
        "artifact_type": "governed_roadmap_artifact",
        "schema_version": "1.0.0",
        "roadmap_ref": "docs/roadmaps/system_roadmap.md",
        "generated_at": "2026-03-30T00:00:00Z",
        "available_artifact_refs": ["artifact://review-approved"],
        "satisfied_trust_requirements": ["trust:strategy"],
        "satisfied_review_requirements": ["review:approved"],
        "satisfied_eval_requirements": ["eval:passed"],
        "steps": [
            {
                "step_id": "STEP-001",
                "order_index": 1,
                "title": "Completed",
                "status": "completed",
                "strategy_alignment": "baseline hardening complete",
                "primary_trust_gain": "policy confidence",
                "hardening_vs_expansion": "hardening",
                "behavior_affecting": False,
                "dependency_step_ids": [],
                "dependency_artifact_refs": [],
                "trust_requirements": [],
                "review_requirements": [],
                "eval_requirements": [],
            },
            {
                "step_id": "STEP-002",
                "order_index": 2,
                "title": "Eligible",
                "status": "planned",
                "strategy_alignment": "aligned with roadmap authority",
                "primary_trust_gain": "determinism",
                "hardening_vs_expansion": "hardening",
                "behavior_affecting": True,
                "replay_trace_implications": "replay lineage required",
                "dependency_step_ids": ["STEP-001"],
                "dependency_artifact_refs": ["artifact://review-approved"],
                "trust_requirements": ["trust:strategy"],
                "review_requirements": ["review:approved"],
                "eval_requirements": ["eval:passed"],
            },
            {
                "step_id": "STEP-003",
                "order_index": 3,
                "title": "Blocked",
                "status": "planned",
                "strategy_alignment": "expansion after controls",
                "primary_trust_gain": "coverage",
                "hardening_vs_expansion": "expansion",
                "behavior_affecting": True,
                "replay_trace_implications": "expansion impacts replay",
                "eval_control_path": "eval/control/path",
                "dependency_step_ids": ["STEP-404"],
                "dependency_artifact_refs": ["artifact://missing"],
                "trust_requirements": ["trust:control"],
                "review_requirements": ["review:implementation"],
                "eval_requirements": ["eval:execution"],
            },
        ],
    }


def _write_roadmap(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "governed-roadmap.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def test_eligibility_artifact_schema_validates(tmp_path: Path) -> None:
    path = _write_roadmap(tmp_path, _base_roadmap())
    artifact = build_roadmap_eligibility(path)
    validate_artifact(artifact, "roadmap_eligibility_artifact")


def test_incomplete_dependency_step_ids_are_blocked(tmp_path: Path) -> None:
    path = _write_roadmap(tmp_path, _base_roadmap())
    artifact = build_roadmap_eligibility(path)
    blocked = {item["step_id"]: item for item in artifact["blocked_steps"]}
    assert "STEP-003" in blocked
    assert "STEP-404" in blocked["STEP-003"]["missing_dependency_step_ids"]


def test_unmet_trust_requirements_are_blocked(tmp_path: Path) -> None:
    roadmap = _base_roadmap()
    roadmap["steps"][1]["trust_requirements"] = ["trust:missing"]
    path = _write_roadmap(tmp_path, roadmap)
    artifact = build_roadmap_eligibility(path)
    blocked = {item["step_id"]: item for item in artifact["blocked_steps"]}
    assert "STEP-002" in blocked
    assert blocked["STEP-002"]["missing_trust_requirements"] == ["trust:missing"]


def test_ready_step_marked_eligible(tmp_path: Path) -> None:
    path = _write_roadmap(tmp_path, _base_roadmap())
    artifact = build_roadmap_eligibility(path)
    assert artifact["eligible_step_ids"] == ["STEP-002"]
    statuses = {item["roadmap_row_id"]: item for item in artifact["strategy_status_artifacts"]}
    assert statuses["STEP-002"]["strategy_gate_decision"] == "allow"


def test_completed_steps_not_recommended(tmp_path: Path) -> None:
    path = _write_roadmap(tmp_path, _base_roadmap())
    artifact = build_roadmap_eligibility(path)
    assert "STEP-001" not in artifact["recommended_next_step_ids"]


def test_repeat_runs_are_deterministic(tmp_path: Path) -> None:
    path = _write_roadmap(tmp_path, _base_roadmap())
    first = build_roadmap_eligibility(path)
    second = build_roadmap_eligibility(path)
    assert first == second


def test_malformed_roadmap_fails_closed(tmp_path: Path) -> None:
    roadmap = _base_roadmap()
    roadmap["steps"][1].pop("dependency_step_ids")
    path = _write_roadmap(tmp_path, roadmap)
    with pytest.raises(RoadmapEligibilityError):
        build_roadmap_eligibility(path)


def test_cli_writes_valid_artifact(tmp_path: Path) -> None:
    path = _write_roadmap(tmp_path, _base_roadmap())
    out_path = tmp_path / "eligibility.json"
    cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "run_roadmap_eligibility.py"),
        "--roadmap",
        str(path),
        "--output",
        str(out_path),
    ]
    completed = subprocess.run(cmd, check=False, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    validate_artifact(payload, "roadmap_eligibility_artifact")


def test_missing_strategy_alignment_blocks(tmp_path: Path) -> None:
    roadmap = _base_roadmap()
    roadmap["steps"][1]["strategy_alignment"] = ""
    path = _write_roadmap(tmp_path, roadmap)
    artifact = build_roadmap_eligibility(path)
    statuses = {item["roadmap_row_id"]: item for item in artifact["strategy_status_artifacts"]}
    assert statuses["STEP-002"]["strategy_gate_decision"] == "block"


def test_missing_primary_trust_gain_blocks(tmp_path: Path) -> None:
    roadmap = _base_roadmap()
    roadmap["steps"][1]["primary_trust_gain"] = ""
    path = _write_roadmap(tmp_path, roadmap)
    artifact = build_roadmap_eligibility(path)
    statuses = {item["roadmap_row_id"]: item for item in artifact["strategy_status_artifacts"]}
    assert statuses["STEP-002"]["strategy_gate_decision"] == "block"


def test_expansion_without_eval_control_path_blocks(tmp_path: Path) -> None:
    roadmap = _base_roadmap()
    roadmap["steps"][2]["eval_control_path"] = ""
    path = _write_roadmap(tmp_path, roadmap)
    artifact = build_roadmap_eligibility(path)
    statuses = {item["roadmap_row_id"]: item for item in artifact["strategy_status_artifacts"]}
    assert statuses["STEP-003"]["strategy_gate_decision"] == "block"


def test_expansion_while_prior_hardening_partial_freezes(tmp_path: Path) -> None:
    roadmap = _base_roadmap()
    roadmap["steps"][1]["status"] = "in_progress"
    roadmap["steps"][2]["dependency_step_ids"] = []
    roadmap["steps"][2]["dependency_artifact_refs"] = []
    roadmap["steps"][2]["trust_requirements"] = []
    roadmap["steps"][2]["review_requirements"] = []
    roadmap["steps"][2]["eval_requirements"] = []
    path = _write_roadmap(tmp_path, roadmap)
    artifact = build_roadmap_eligibility(path)
    statuses = {item["roadmap_row_id"]: item for item in artifact["strategy_status_artifacts"]}
    assert statuses["STEP-003"]["strategy_gate_decision"] == "freeze"


def test_review_signal_fail_blocks_steps_via_review_requirements(tmp_path: Path) -> None:
    review_path = tmp_path / "review_control_signal.json"
    review_path.write_text(json.dumps({"gate_assessment": "FAIL", "scale_recommendation": "NO", "critical_findings": ["Critical control gap"]}), encoding="utf-8")

    roadmap = _base_roadmap()
    roadmap["review_control_signal_refs"] = [str(review_path)]
    path = _write_roadmap(tmp_path, roadmap)

    artifact = build_roadmap_eligibility(path)
    blocked = {item["step_id"]: item for item in artifact["blocked_steps"]}
    assert "STEP-002" in blocked
    assert "review:gate_fail" in blocked["STEP-002"]["unmet_review_requirements"]


def test_required_review_signal_missing_blocks_all_planned_steps(tmp_path: Path) -> None:
    roadmap = _base_roadmap()
    roadmap["review_signal_required"] = True
    path = _write_roadmap(tmp_path, roadmap)

    artifact = build_roadmap_eligibility(path)
    blocked = {item["step_id"]: item for item in artifact["blocked_steps"]}
    assert "STEP-002" in blocked
    assert "review:required_signal_missing" in blocked["STEP-002"]["unmet_review_requirements"]
