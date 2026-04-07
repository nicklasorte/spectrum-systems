from __future__ import annotations

from pathlib import Path

from spectrum_systems.modules.runtime.top_level_conductor import run_top_level_conductor


VALID_REVIEW = """---
module: tpa
review_date: 2026-04-05
---
# Review
"""

VALID_ACTIONS = """# Action Tracker

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
"""


def _request(tmp_path: Path, *, retry_budget: int = 2, pass_after_attempt: bool = True, safe_scope: list[str] | None = None):
    review_path = tmp_path / "review.md"
    action_path = tmp_path / "actions.md"
    review_path.write_text(VALID_REVIEW, encoding="utf-8")
    action_path.write_text(VALID_ACTIONS, encoding="utf-8")
    return {
        "objective": "pre-pr bounded repair loop",
        "branch_ref": "refs/heads/main",
        "run_id": "tlc-pre-pr-loop",
        "retry_budget": retry_budget,
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
        "repair_default_scope": safe_scope or ["contracts/standards-manifest.json"],
        "simulated_repair_files_touched": safe_scope or ["contracts/standards-manifest.json"],
        "repair_commands_run": ["pytest tests/test_contracts.py"],
        "repair_validation_passed_after_attempt": pass_after_attempt,
    }


def test_success_after_one_repair_attempt_ready_for_merge(tmp_path: Path) -> None:
    result = run_top_level_conductor(_request(tmp_path, pass_after_attempt=True))
    assert result["current_state"] == "ready_for_merge"
    assert result["ready_for_merge"] is True
    assert any(ref.startswith("repair_attempt_record_artifact:") for ref in result["produced_artifact_refs"])


def test_repeated_failure_exhausts_retry_budget(tmp_path: Path) -> None:
    result = run_top_level_conductor(_request(tmp_path, retry_budget=1, pass_after_attempt=False))
    assert result["current_state"] == "exhausted"
    assert result["stop_reason"] == "repair_attempts_exhausted"


def test_repair_outside_scope_blocked_by_sel(tmp_path: Path) -> None:
    request = _request(
        tmp_path,
        safe_scope=["contracts/standards-manifest.json"],
    )
    request["simulated_repair_files_touched"] = ["docs/architecture/system_registry.md"]
    result = run_top_level_conductor(request)
    assert result["current_state"] == "blocked"
    assert result["stop_reason"].startswith("sel_block")
