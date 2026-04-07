from __future__ import annotations

from pathlib import Path

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.top_level_conductor import run_top_level_conductor


def _request(tmp_path: Path) -> dict:
    review_path = tmp_path / "review.md"
    action_path = tmp_path / "actions.md"
    review_path.write_text("---\nmodule: tpa\nreview_date: 2026-04-05\n---\n# Review\n", encoding="utf-8")
    action_path.write_text("# Action Tracker\n", encoding="utf-8")
    return {
        "objective": "learning",
        "branch_ref": "refs/heads/main",
        "run_id": "tlc-roadmap-signal",
        "retry_budget": 1,
        "require_review": False,
        "require_recovery": True,
        "review_path": str(review_path),
        "action_tracker_path": str(action_path),
        "runtime_dir": str(tmp_path / "runtime"),
        "emitted_at": "2026-04-07T00:00:00Z",
        "pre_pr_command_ref": "pytest tests/test_contracts.py",
        "pre_pr_failures": [
            {
                "test_name": "tests/test_contracts.py::test_manifest_registry_alignment",
                "failure_message": "manifest entry missing",
                "artifact_ref": "pytest_failure:tests/test_contracts.py::test_manifest_registry_alignment",
                "markers": ["contract_behavior_changed"],
            }
        ],
        "repair_default_scope": ["contracts/standards-manifest.json"],
        "simulated_repair_files_touched": ["contracts/standards-manifest.json"],
        "repair_commands_run": ["pytest tests/test_contracts.py"],
        "repair_validation_passed_after_attempt": False,
    }


def test_roadmap_signal_generated_from_failure_learning(tmp_path: Path) -> None:
    result = run_top_level_conductor(_request(tmp_path))
    signal = result["lineage"]["latest_roadmap_signal_artifact"]
    validate_artifact(signal, "roadmap_signal_artifact")
    assert signal["recurrence_count"] >= 1
    assert signal["source_refs"]
