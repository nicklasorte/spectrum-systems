from __future__ import annotations

import copy
from pathlib import Path

import pytest

from spectrum_systems.modules.runtime.system_enforcement_layer import enforce_system_boundaries
from spectrum_systems.modules.runtime.top_level_conductor import (
    TopLevelConductorError,
    run_from_roadmap,
    run_top_level_conductor,
)


VALID_REVIEW = """---
module: tpa
review_date: 2026-04-05
---
# Review

## Overall Assessment
**Overall Verdict: CONDITIONAL PASS**

## Critical Risks
1. Bypass drift risk remains open.
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
| MI-2 | recovery rehearsal follow-up | Medium | Add recovery drill (R4) | Closed | |

## Blocking Items
- CR-1 blocks promotion.
"""


def _write_inputs(tmp_path: Path) -> tuple[Path, Path]:
    review_path = tmp_path / "review.md"
    action_path = tmp_path / "actions.md"
    review_path.write_text(VALID_REVIEW, encoding="utf-8")
    action_path.write_text(VALID_ACTIONS, encoding="utf-8")
    return review_path, action_path


def _base_request(tmp_path: Path) -> dict:
    review_path, action_path = _write_inputs(tmp_path)
    return {
        "objective": "orchestrate bounded run",
        "branch_ref": "refs/heads/main",
        "run_id": "tlc-test-run",
        "retry_budget": 1,
        "require_review": True,
        "require_recovery": True,
        "review_path": str(review_path),
        "action_tracker_path": str(action_path),
        "runtime_dir": str(tmp_path / "runtime"),
        "emitted_at": "2026-04-06T00:00:00Z",
        "repo_mutation_requested": False,
        "eval_summary_ref": "eval_summary_artifact:tlc-test-run",
        "eval_coverage_summary_ref": "eval_coverage_summary:tlc-test-run",
        "required_eval_statuses": {"governed_required_eval_set": "passed"},
        "certification_status": "passed",
        "certification_ref": "done_certification_record:tlc-test-run",
        "traceability_refs": [
            "review_projection_bundle_artifact:tlc-test-run",
            str(action_path),
        ],
    }


def test_golden_integration_run_ready_for_merge(tmp_path: Path) -> None:
    request = _base_request(tmp_path)

    result = run_top_level_conductor(request)

    assert result["current_state"] == "ready_for_merge"
    assert result["ready_for_merge"] is True
    assert result["stop_reason"] == "ready_for_merge"
    assert {"PQX", "TPA", "RIL", "CDE", "SEL"}.issubset(set(result["active_subsystems"]))
    assert any(ref.startswith("review_projection_bundle_artifact:") for ref in result["produced_artifact_refs"])
    assert any(ref.startswith("run_summary_artifact:") for ref in result["produced_artifact_refs"])
    assert result["trace_refs"]
    assert result["lineage"]["lineage_id"].startswith("lineage-")
    run_summary = result["lineage"]["run_summary_artifact"]
    assert run_summary["run_id"] == result["run_id"]
    assert run_summary["final_terminal_state"] == "ready_for_merge"
    assert run_summary["promotion_allowed"] is True


def test_blocked_run_sel_violation_stops_side_effects(tmp_path: Path) -> None:
    request = _base_request(tmp_path)

    def _blocking_sel(payload: dict) -> dict:
        tampered = copy.deepcopy(payload)
        tampered["execution_request"]["direct_cli"] = True
        sel = enforce_system_boundaries(tampered)
        return {
            "allowed": False,
            "artifact_ref": f"system_enforcement_result_artifact:{sel['enforcement_result_id']}",
            "trace_refs": sel["trace_refs"],
            "violations": sel["violations"],
        }

    request["subsystems"] = {"sel": _blocking_sel}
    result = run_top_level_conductor(request)

    assert result["current_state"] == "blocked"
    assert result["stop_reason"].startswith("sel_block")
    assert result["active_subsystems"] == ["SEL"]
    assert not any(name in result["active_subsystems"] for name in ("PQX", "TPA", "FRE", "RIL", "CDE", "PRG"))


def test_contract_validation_fails_closed_on_invalid_pqx_output(tmp_path: Path) -> None:
    request = _base_request(tmp_path)
    request["subsystems"] = {
        "pqx": lambda _: {
            "entry_valid": True,
            "validation_passed": True,
                "request_artifact": {
                    "schema_version": "9.9.9",
                    "run_id": "x",
                    "step_id": "y",
                    "step_name": "z",
                    "dependencies": [],
                    "requested_at": "2026-04-06T00:00:00Z",
                    "prompt": "p",
                },
                "execution_artifact": {
                    "schema_version": "9.9.9",
                    "run_id": "x",
                    "step_id": "y",
                    "execution_status": "success",
                    "started_at": "2026-04-06T00:00:00Z",
                    "completed_at": "2026-04-06T00:00:00Z",
                "output_text": "",
                "error": None,
            },
        }
    }

    with pytest.raises(Exception):
        run_top_level_conductor(request)


def test_sel_enforced_at_required_boundaries(tmp_path: Path) -> None:
    request = _base_request(tmp_path)
    boundaries: list[str] = []

    def _tracking_sel(payload: dict) -> dict:
        boundaries.append(payload["source_module"] + ":" + payload["execution_request"].get("requested_at", ""))
        sel = enforce_system_boundaries(payload)
        return {
            "allowed": sel["enforcement_status"] == "allow",
            "artifact_ref": f"system_enforcement_result_artifact:{sel['enforcement_result_id']}",
            "trace_refs": sel["trace_refs"],
            "violations": sel["violations"],
        }

    request["subsystems"] = {"sel": _tracking_sel}
    result = run_top_level_conductor(request)

    assert result["current_state"] == "ready_for_merge"
    assert len(boundaries) >= 4


def test_determinism_same_input_same_output(tmp_path: Path) -> None:
    request = _base_request(tmp_path)
    request["run_id"] = "tlc-determinism"

    one = run_top_level_conductor(copy.deepcopy(request))
    two = run_top_level_conductor(copy.deepcopy(request))

    assert one == two


def test_no_execution_outside_pqx(tmp_path: Path) -> None:
    request = _base_request(tmp_path)
    result = run_top_level_conductor(request)
    invocations = result["lineage"].get("subsystem_invocations", [])

    pqx_calls = [row for row in invocations if row["subsystem"] == "PQX"]
    non_pqx_execution = [
        row
        for row in invocations
        if row["subsystem"] != "PQX" and any("slice_execution_record" in ref for ref in row.get("output_refs", []))
    ]

    assert len(pqx_calls) == 1
    assert non_pqx_execution == []



def test_missing_review_inputs_fail_closed(tmp_path: Path) -> None:
    request = _base_request(tmp_path)
    request.pop("review_path")

    with pytest.raises(TopLevelConductorError, match="review_path"):
        run_top_level_conductor(request)


def test_run_from_roadmap_executes_bounded_steps(tmp_path: Path) -> None:
    roadmap = {
        "roadmap_id": "R2S-2D11D09E9BA6FD4E",
        "schema_version": "1.0.0",
        "generated_at": "2026-04-06T00:00:00Z",
        "source_refs": ["docs/vision.md#sha256:1", "docs/roadmaps/system_roadmap.md#sha256:2"],
        "steps": [
            {
                "step_id": "step_1",
                "description": "Step one.",
                "required_inputs": ["docs/vision.md#sha256:1"],
                "expected_outputs": ["output:step_1"],
            },
            {
                "step_id": "step_2",
                "description": "Step two.",
                "required_inputs": ["output:step_1"],
                "expected_outputs": ["output:step_2"],
            },
        ],
        "bounded": True,
        "step_count": 2,
    }
    review_path, action_path = _write_inputs(tmp_path)

    result = run_from_roadmap(
        roadmap,
        run_request_overrides={
            "review_path": str(review_path),
            "action_tracker_path": str(action_path),
            "runtime_dir": str(tmp_path / "runtime"),
            "emitted_at": "2026-04-06T00:00:00Z",
            "repo_mutation_requested": False,
            "eval_summary_ref": "eval_summary_artifact:roadmap-run",
            "eval_coverage_summary_ref": "eval_coverage_summary:roadmap-run",
            "required_eval_statuses": {"governed_required_eval_set": "passed"},
            "certification_status": "passed",
            "certification_ref": "done_certification_record:roadmap-run",
            "traceability_refs": [
                "review_projection_bundle_artifact:roadmap-run",
                str(action_path),
            ],
        },
    )

    assert result["execution_status"] == "completed"
    assert len(result["step_execution_artifacts"]) == 2
