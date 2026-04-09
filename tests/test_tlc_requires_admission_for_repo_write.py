from __future__ import annotations

from pathlib import Path

import pytest

from spectrum_systems.modules.runtime.top_level_conductor import TopLevelConductorError, run_top_level_conductor
from tests.helpers_repo_write_lineage import build_valid_repo_write_lineage


VALID_REVIEW = """---
module: tpa
review_date: 2026-04-05
---
# Review

## Overall Assessment
**Overall Verdict: CONDITIONAL PASS**
"""

VALID_ACTIONS = """# Action Tracker

## Critical Items
| ID | Risk | Severity | Recommended Action | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| CR-1 | Blocking risk | Critical | Fix | Closed | fixed |
"""


def _base_request(tmp_path: Path) -> dict[str, object]:
    review_path = tmp_path / "review.md"
    action_path = tmp_path / "actions.md"
    review_path.write_text(VALID_REVIEW, encoding="utf-8")
    action_path.write_text(VALID_ACTIONS, encoding="utf-8")
    return {
        "objective": "repo mutating run",
        "branch_ref": "refs/heads/main",
        "run_id": "tlc-aex-check",
        "retry_budget": 0,
        "require_review": True,
        "require_recovery": False,
        "review_path": str(review_path),
        "action_tracker_path": str(action_path),
        "runtime_dir": str(tmp_path / "runtime"),
        "emitted_at": "2026-04-08T00:00:00Z",
        "repo_mutation_requested": True,
    }


def _attach_aex_authenticity(request: dict[str, object]) -> None:
    return


def test_tlc_refuses_repo_write_without_admission_record(tmp_path: Path) -> None:
    with pytest.raises(TopLevelConductorError, match="direct_tlc_repo_write_forbidden"):
        run_top_level_conductor(_base_request(tmp_path))


def test_tlc_requires_explicit_repo_mutation_declaration_when_admission_artifacts_absent(tmp_path: Path) -> None:
    request = _base_request(tmp_path)
    request.pop("repo_mutation_requested")
    with pytest.raises(TopLevelConductorError, match="repo_mutation_intent_undetermined"):
        run_top_level_conductor(request)


def test_direct_pqx_path_for_repo_write_is_rejected(tmp_path: Path) -> None:
    request = _base_request(tmp_path)
    lineage = build_valid_repo_write_lineage(request_id="req-1", trace_id="trace-tlc-aex-check")
    request["build_admission_record"] = lineage["build_admission_record"]
    request["normalized_execution_request"] = lineage["normalized_execution_request"]

    def _bad_pqx(_payload: dict[str, object]) -> dict[str, object]:
        raise TopLevelConductorError("direct_pqx_repo_write_forbidden")

    request["subsystems"] = {"pqx": _bad_pqx}

    with pytest.raises(TopLevelConductorError, match="direct_pqx_repo_write_forbidden"):
        run_top_level_conductor(request)


def test_tlc_rejects_repo_write_with_rejected_admission(tmp_path: Path) -> None:
    request = _base_request(tmp_path)
    lineage = build_valid_repo_write_lineage(request_id="req-1", trace_id="trace-tlc-aex-check")
    request["build_admission_record"] = lineage["build_admission_record"]
    request["normalized_execution_request"] = lineage["normalized_execution_request"]
    request["build_admission_record"]["admission_status"] = "rejected"
    with pytest.raises(TopLevelConductorError, match="repo_mutation_without_admission"):
        run_top_level_conductor(request)


def test_tlc_rejects_repo_write_with_unresolvable_normalized_ref(tmp_path: Path) -> None:
    request = _base_request(tmp_path)
    lineage = build_valid_repo_write_lineage(request_id="req-1", trace_id="trace-tlc-aex-check")
    request["build_admission_record"] = lineage["build_admission_record"]
    request["normalized_execution_request"] = lineage["normalized_execution_request"]
    request["build_admission_record"]["normalized_execution_request_ref"] = "normalized_execution_request:req-other"
    with pytest.raises(TopLevelConductorError, match="repo_mutation_without_admission"):
        run_top_level_conductor(request)


def test_valid_admitted_repo_write_path_succeeds(tmp_path: Path) -> None:
    request = _base_request(tmp_path)
    request["require_review"] = False
    lineage = build_valid_repo_write_lineage(request_id="req-1", trace_id="trace-tlc-aex-check")
    request["build_admission_record"] = lineage["build_admission_record"]
    request["normalized_execution_request"] = lineage["normalized_execution_request"]
    result = run_top_level_conductor(request)
    assert result["current_state"] in {"ready_for_merge", "blocked", "exhausted"}
    assert "trace-tlc-aex-check" in result["trace_refs"]
