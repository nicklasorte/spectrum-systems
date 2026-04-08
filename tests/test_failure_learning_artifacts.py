from __future__ import annotations

from pathlib import Path

from spectrum_systems.modules.runtime.top_level_conductor import run_top_level_conductor


def _request(tmp_path: Path):
    review_path = tmp_path / "review.md"
    action_path = tmp_path / "actions.md"
    review_path.write_text("---\nmodule: tpa\nreview_date: 2026-04-05\n---\n# Review\n", encoding="utf-8")
    action_path.write_text(
        """# Action Tracker

## Critical Items
| ID | Risk | Severity | Recommended Action | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| CR-1 | Blocking risk in tpa control path | Critical | Add blocker-safe enforcement (R1) | Closed | fixed |

## High-Priority Items
| ID | Risk | Severity | Recommended Action | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| HI-1 | pqx routing gap | High | Add route guard (R2) | Closed | |

## Medium-Priority Items
| ID | Risk | Severity | Recommended Action | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| MI-1 | docs traceability note | Medium | Add note update (R3) | Open | |
""",
        encoding="utf-8",
    )
    return {
        "objective": "learning",
        "branch_ref": "refs/heads/main",
        "run_id": "tlc-learning",
        "retry_budget": 2,
        "require_review": False,
        "require_recovery": True,
        "review_path": str(review_path),
        "action_tracker_path": str(action_path),
        "runtime_dir": str(tmp_path / "runtime"),
        "emitted_at": "2026-04-07T00:00:00Z",
        "repo_mutation_requested": False,
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


def test_failure_learning_record_created_and_recurrence_increments(tmp_path: Path) -> None:
    result = run_top_level_conductor(_request(tmp_path))
    assert result["current_state"] == "exhausted"
    learning = result["lineage"]["latest_failure_learning_record_artifact"]
    assert learning["artifact_type"] == "failure_learning_record_artifact"
    assert learning["recurrence_count"] == 2
    assert learning["linked_eval_candidates"]
    assert learning["linked_eval_adoptions"]
    assert learning["last_seen_trace"] == "trace-tlc-learning"
