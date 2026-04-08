from __future__ import annotations

import copy
from pathlib import Path

import pytest

from spectrum_systems.contracts import load_example
from spectrum_systems.modules.runtime.system_registry_enforcer import validate_system_action, validate_system_handoff
from spectrum_systems.modules.runtime.top_level_conductor import TopLevelConductorError, run_top_level_conductor


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
        "objective": "harden handoff integrity",
        "branch_ref": "refs/heads/main",
        "run_id": "tlc-handoff-hardening",
        "retry_budget": 1,
        "require_review": True,
        "require_recovery": True,
        "review_path": str(review_path),
        "action_tracker_path": str(action_path),
        "runtime_dir": str(tmp_path / "runtime"),
        "emitted_at": "2026-04-06T00:00:00Z",
        "repo_mutation_requested": False,
    }


def test_valid_handoffs_across_expected_chain() -> None:
    trace_refs = ["trace-hnd-001"]
    pqx_payload = {
        "schema_version": "1.0.0",
        "run_id": "run-01",
        "step_id": "step-01",
        "execution_status": "success",
        "started_at": "2026-04-06T00:00:00Z",
        "completed_at": "2026-04-06T00:00:00Z",
        "output_text": "ok",
        "error": None,
    }
    assert validate_system_handoff(
        "PQX",
        "TPA",
        {
            "schema_name": "pqx_execution_result",
            "action_type": "execution",
            "payload": pqx_payload,
            "trace_refs": trace_refs,
            "required_fields": ["run_id", "execution_status"],
            "expected_trace_refs": trace_refs,
        },
    )["allow"]

    tpa_payload = copy.deepcopy(load_example("tpa_slice_artifact"))
    tpa_payload["trace_id"] = "trace-hnd-001"
    assert validate_system_handoff(
        "TPA",
        "FRE",
        {
            "schema_name": "tpa_slice_artifact",
            "action_type": "trust_policy_application",
            "payload": tpa_payload,
            "required_fields": ["slice_id", "artifact_id"],
            "expected_trace_refs": trace_refs,
        },
    )["allow"]

    fre_payload = copy.deepcopy(load_example("failure_diagnosis_artifact"))
    assert validate_system_handoff(
        "FRE",
        "RIL",
        {
            "schema_name": "failure_diagnosis_artifact",
            "action_type": "failure_diagnosis",
            "payload": fre_payload,
            "trace_refs": trace_refs,
            "required_fields": ["diagnosis_id", "primary_root_cause"],
            "expected_trace_refs": trace_refs,
        },
    )["allow"]

    projection = copy.deepcopy(load_example("review_projection_bundle_artifact"))
    assert validate_system_handoff(
        "RIL",
        "CDE",
        {
            "schema_name": "review_projection_bundle_artifact",
            "action_type": "review_projection",
            "payload": projection,
            "trace_refs": trace_refs,
            "required_fields": ["review_projection_bundle_id", "emitted_at"],
            "expected_trace_refs": trace_refs,
        },
    )["allow"]

    cde_payload = copy.deepcopy(load_example("closure_decision_artifact"))
    cde_payload["trace_id"] = "trace-hnd-001"
    cde_payload["decision_type"] = "continue_repair_bounded"
    cde_payload["next_step_class"] = "bounded_repair"
    cde_payload["next_step_ref"] = "repair_loop:run-01:1"
    cde_payload["bounded_next_step_available"] = True
    assert validate_system_handoff(
        "CDE",
        "TLC",
        {
            "schema_name": "closure_decision_artifact",
            "action_type": "closure_decisions",
            "payload": cde_payload,
            "required_fields": ["decision_type", "trace_id"],
            "expected_trace_refs": trace_refs,
        },
    )["allow"]


def test_invalid_handoffs_blocked_by_registry_rules() -> None:
    assert validate_system_action("PRG", "execution", "PQX")["block"]
    assert validate_system_action("RIL", "runtime_enforcement", "SEL")["block"]
    assert validate_system_action("TLC", "execution", "PQX")["block"]


def test_tlc_fails_closed_on_missing_or_malformed_outputs(tmp_path: Path) -> None:
    request = _base_request(tmp_path)

    request_missing = copy.deepcopy(request)
    request_missing["subsystems"] = {
        "pqx": lambda _: {
            "entry_valid": True,
            "validation_passed": True,
            "request_artifact": {
                "schema_version": "1.1.0",
                "run_id": "run-x",
                "step_id": "TLC-EXECUTE",
                "step_name": "exec",
                "dependencies": [],
                "requested_at": "2026-04-06T00:00:00Z",
                "prompt": "p",
            },
            "execution_artifact": {
                "schema_version": "1.0.0",
                "run_id": "run-x",
                "step_id": "TLC-EXECUTE",
                "execution_status": "success",
                "started_at": "2026-04-06T00:00:00Z",
                "completed_at": "2026-04-06T00:00:00Z",
                "output_text": "ok",
                "error": None,
            },
            # missing trace_refs + lineage
        }
    }

    with pytest.raises(TopLevelConductorError, match="trace refs|lineage"):
        run_top_level_conductor(request_missing)

    request_malformed = copy.deepcopy(request)
    request_malformed["require_review"] = False
    request_malformed["subsystems"] = {
        "cde": lambda _: {
            "decision_type": "lock",
            "closure_state": "closed",
            "artifact_refs": ["closure_decision_artifact:CDE-001"],
            "trace_refs": ["trace-x"],
            "closure_decision_artifact": {
                "artifact_type": "closure_decision_artifact",
                "artifact_class": "decision",
                "schema_version": "1.0.0",
                "closure_decision_id": "CDE-001",
                "subject_scope": "top_level_conductor",
                "subsystem_acronym": "TLC",
                "run_id": "run-01",
                "review_date": "2026-04-05",
                "action_tracker_ref": "x",
                "source_artifacts": [
                    {
                        "artifact_type": "review_projection_bundle_artifact",
                        "artifact_ref": "review_projection_bundle_artifact:RPB-001",
                        "blocker_count": 0,
                        "critical_count": 0,
                        "high_priority_count": 0,
                        "medium_priority_count": 0,
                        "unresolved_action_item_ids": [],
                    }
                ],
                "closure_complete": True,
                "final_verification_passed": True,
                "hardening_completed": True,
                "escalation_required": False,
                "bounded_next_step_available": False,
                "next_step_ref": None,
                "decision_type": "lock",
                "decision_rationale": "ok",
                "trace_id": "trace-x",
                "emitted_at": "2026-04-06T00:00:00Z",
        "repo_mutation_requested": False,
            },
            # missing next_step_class
        }
    }
    with pytest.raises(TopLevelConductorError, match="next_step_class"):
        run_top_level_conductor(request_malformed)


def test_handoff_validation_determinism() -> None:
    handoff = {
        "schema_name": "pqx_execution_result",
        "action_type": "execution",
        "payload": {
            "schema_version": "1.0.0",
            "run_id": "run-01",
            "step_id": "step-01",
            "execution_status": "success",
            "started_at": "2026-04-06T00:00:00Z",
            "completed_at": "2026-04-06T00:00:00Z",
            "output_text": "ok",
            "error": None,
            "trace_refs": ["trace-det-01"],
        },
        "required_fields": ["run_id", "execution_status"],
        "expected_trace_refs": ["trace-det-01"],
    }
    first = validate_system_handoff("PQX", "TPA", copy.deepcopy(handoff))
    second = validate_system_handoff("PQX", "TPA", copy.deepcopy(handoff))
    assert first == second


def test_registry_enforcement_duplicate_ownership_and_prohibited_behavior(monkeypatch: pytest.MonkeyPatch) -> None:
    result = validate_system_action("RIL", "runtime_enforcement", "SEL")
    assert result["block"]
    assert "prohibited_behavior" in result["violation_codes"]

    from spectrum_systems.modules.runtime import system_registry_enforcer as enforcer

    systems, owners_by_action, edges = enforcer._registry_indexes()
    forced_owners = dict(owners_by_action)
    forced_owners["execution"] = ["PQX", "TLC"]

    monkeypatch.setattr(enforcer, "_registry_indexes", lambda: (systems, forced_owners, edges))
    duplicate = validate_system_action("PQX", "execution", "TPA")
    assert duplicate["block"]
    assert "duplicate_action_ownership" in duplicate["violation_codes"]
