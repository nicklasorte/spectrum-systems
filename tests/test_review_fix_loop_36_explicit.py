"""Tests for scripts/run_review_fix_loop_36_explicit.py."""

from __future__ import annotations

import json
import subprocess
import sys
from importlib import util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_review_fix_loop_36_explicit.py"
ARTIFACT_ROOT = REPO_ROOT / "artifacts" / "review_fix_loop_36_explicit"
TRACE_PATH = REPO_ROOT / "artifacts" / "rdx_runs" / "REVIEW-FIX-LOOP-36-EXPLICIT-artifact-trace.json"


def _run_script() -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT_PATH)], cwd=str(REPO_ROOT), capture_output=True, text=True, check=True)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_generates_36_step_artifacts_and_12_checkpoints() -> None:
    _run_script()

    step_files = [p for p in ARTIFACT_ROOT.glob("*.json") if p.name.startswith(("review_", "fix_", "cross_", "replay_", "promotion_", "loop_", "merge_", "required_", "pre_", "pr_", "branch_", "consistency_", "post_", "weak_"))]
    assert len(step_files) >= 36

    for idx in range(1, 13):
        assert (ARTIFACT_ROOT / f"checkpoint-{idx}.json").is_file()

    trace = _load_json(TRACE_PATH)
    assert trace["batch_id"] == "REVIEW-FIX-LOOP-36-EXPLICIT"
    assert trace["checkpoint_count"] == 12


def test_required_outputs_exist() -> None:
    _run_script()

    required = [
        "review_cycle_record.json",
        "review_completeness_record.json",
        "fix_execution_record.json",
        "fix_replay_review_result.json",
        "cross_run_consistency_record.json",
        "replay_confidence_record.json",
        "promotion_readiness_decision.json",
        "review_fix_projection_bundle.json",
        "loop_termination_decision.json",
        "merge_readiness_validation_record.json",
        "required_artifact_presence_enforcement_result.json",
        "pre_merge_contract_enforcement_result.json",
        "pr_replay_checkpoint_validation_record.json",
        "pr_authenticity_ci_validation_record.json",
        "branch_merge_block_result.json",
        "delivery_report.json",
        "review_report.json",
        "checkpoint_summary.json",
        "registry_alignment_result.json",
        "loop_integrity_closeout.json",
    ]

    for name in required:
        path = ARTIFACT_ROOT / name
        assert path.is_file()
        assert path.stat().st_size > 2


def test_ownership_boundaries_and_fail_closed_controls() -> None:
    _run_script()

    assert _load_json(ARTIFACT_ROOT / "fix_execution_record.json")["owner"] == "PQX"
    assert _load_json(ARTIFACT_ROOT / "promotion_readiness_decision.json")["owner"] == "CDE"
    assert _load_json(ARTIFACT_ROOT / "loop_state_packet.json")["owner"] == "RIL"
    assert _load_json(ARTIFACT_ROOT / "review_fix_projection_bundle.json")["owner"] == "MAP"

    enforcement = _load_json(ARTIFACT_ROOT / "branch_merge_block_result.json")
    assert enforcement["owner"] == "SEL"
    assert enforcement["fail_closed"] is True
    assert "authenticity_invalid" in enforcement["blocked_when"]

    fix_gate = _load_json(ARTIFACT_ROOT / "fix_loop_admissibility_record.json")
    assert fix_gate["owner"] == "TPA"
    assert fix_gate["policy_scope_only"] is True


def test_registry_alignment_cross_checks_all_pass() -> None:
    _run_script()

    alignment = _load_json(ARTIFACT_ROOT / "registry_alignment_result.json")
    assert len(alignment["cross_checks"]) == 13
    assert all(status == "pass" for status in alignment["cross_checks"].values())

    summary = _load_json(ARTIFACT_ROOT / "checkpoint_summary.json")
    assert len(summary["checkpoints"]) == 12
    assert all(status == "pass" for status in summary["checkpoints"].values())


def test_step_1_uses_runtime_review_cycle_creation(monkeypatch) -> None:
    spec = util.spec_from_file_location("rf36_runner", SCRIPT_PATH)
    assert spec and spec.loader
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)

    called = {"value": False}

    def _fake_create_review_cycle(**kwargs):
        called["value"] = True
        return {
            "artifact_type": "review_cycle_record",
            "artifact_version": "1.0.0",
            "schema_version": "1.0.0",
            "standards_version": "1.0.0",
            "cycle_id": "rcy-aaaaaaaaaaaaaaaa",
            "parent_batch_id": kwargs["parent_batch_id"],
            "parent_umbrella_id": kwargs["parent_umbrella_id"],
            "iteration_number": 1,
            "max_iterations": kwargs["max_iterations"],
            "termination_state": "open",
            "status": "active",
            "review_request_ref": kwargs["review_request_ref"],
            "review_result_refs": [],
            "fix_slice_refs": [],
            "replay_result_refs": [],
            "lineage": list(kwargs["lineage"]),
            "created_at": kwargs["created_at"],
            "updated_at": kwargs["created_at"],
        }

    monkeypatch.setattr(module, "create_review_cycle", _fake_create_review_cycle)
    module.main()
    assert called["value"] is True
