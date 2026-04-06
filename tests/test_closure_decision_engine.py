from __future__ import annotations

from copy import deepcopy

import pytest
from jsonschema import Draft202012Validator

from spectrum_systems.contracts import load_schema
from spectrum_systems.modules.runtime.closure_decision_engine import (
    ClosureDecisionEngineError,
    build_closure_decision_artifact,
    maybe_build_next_step_prompt_artifact,
)


EMITTED_AT = "2026-04-06T00:00:00Z"
TRACE_ID = "trace-cde-test-001"


def _base_request(**overrides):
    base = {
        "subject_scope": "runtime_control_loop",
        "trace_id": TRACE_ID,
        "emitted_at": EMITTED_AT,
        "source_artifacts": [
            {
                "artifact_type": "review_projection_bundle_artifact",
                "review_projection_bundle_id": "rpb-1111111111111111",
                "artifact_ref": "review_projection_bundle_artifact:rpb-1111111111111111",
                "critical_count": 0,
                "high_priority_count": 0,
                "medium_priority_count": 0,
                "unresolved_action_item_ids": [],
                "blocker_present": False,
                "escalation_present": False,
            }
        ],
        "closure_complete": False,
        "final_verification_passed": False,
        "hardening_completed": False,
        "bounded_next_step_available": False,
        "next_step_ref": None,
    }
    base.update(overrides)
    return base


def _validate(instance: dict, schema_name: str):
    validator = Draft202012Validator(load_schema(schema_name))
    errors = sorted(validator.iter_errors(instance), key=lambda err: str(list(err.absolute_path)))
    assert errors == []


def test_final_verification_pass_leads_to_lock():
    request = _base_request(
        closure_complete=True,
        final_verification_passed=True,
        source_artifacts=[
            {
                "artifact_type": "review_consumer_output_bundle_artifact",
                "review_consumer_output_bundle_id": "rco-aaaaaaaaaaaaaaaa",
                "artifact_ref": "review_consumer_output_bundle_artifact:rco-aaaaaaaaaaaaaaaa",
                "unresolved_action_item_ids": [],
                "blocker_present": False,
            }
        ],
    )
    artifact = build_closure_decision_artifact(request)
    assert artifact["decision_type"] == "lock"
    assert artifact["lock_status"] == "locked"
    assert artifact["next_step_class"] == "none"
    _validate(artifact, "closure_decision_artifact")


def test_open_critical_items_lead_to_hardening_required():
    request = _base_request(
        bounded_next_step_available=True,
        next_step_ref="hardening_batch:hb-001",
        source_artifacts=[
            {
                "artifact_type": "review_signal_artifact",
                "review_signal_artifact_id": "rsa-abcabcabcabcabca",
                "artifact_ref": "review_signal_artifact:rsa-abcabcabcabcabca",
                "critical_count": 1,
                "high_priority_count": 0,
                "unresolved_action_item_ids": ["AT-101"],
            }
        ],
    )
    artifact = build_closure_decision_artifact(request)
    assert artifact["decision_type"] == "hardening_required"
    assert artifact["next_step_class"] == "hardening_batch"
    assert artifact["next_step_ref"] == "hardening_batch:hb-001"


def test_post_hardening_requires_final_verification():
    request = _base_request(
        hardening_completed=True,
        bounded_next_step_available=True,
        next_step_ref="final_verification:fv-001",
    )
    artifact = build_closure_decision_artifact(request)
    assert artifact["decision_type"] == "final_verification_required"
    assert artifact["next_step_class"] == "final_verification"


def test_no_safe_next_step_or_malformed_evidence_becomes_blocked():
    no_step_artifact = build_closure_decision_artifact(_base_request())
    assert no_step_artifact["decision_type"] == "blocked"
    assert "no_safe_bounded_next_step" in no_step_artifact["decision_reason_codes"]

    malformed_request = _base_request(
        source_artifacts=[
            {
                "artifact_type": "review_projection_bundle_artifact",
                "review_projection_bundle_id": "rpb-bbbbbbbbbbbbbbbb",
                "artifact_ref": "review_projection_bundle_artifact:rpb-bbbbbbbbbbbbbbbb",
                "critical_count": -1,
            }
        ]
    )
    malformed_artifact = build_closure_decision_artifact(malformed_request)
    assert malformed_artifact["decision_type"] == "blocked"
    assert "malformed_evidence" in malformed_artifact["decision_reason_codes"]


def test_escalation_case():
    request = _base_request(escalation_required=True)
    artifact = build_closure_decision_artifact(request)
    assert artifact["decision_type"] == "escalate"
    assert artifact["next_step_class"] == "escalation"


def test_deterministic_replay_produces_same_artifact():
    request = _base_request(
        bounded_next_step_available=True,
        next_step_ref="bounded_continue:bc-001",
    )
    first = build_closure_decision_artifact(deepcopy(request))
    second = build_closure_decision_artifact(deepcopy(request))
    assert first == second


def test_traceability_refs_propagate_to_decision_artifact():
    request = _base_request(
        source_artifacts=[
            {
                "artifact_type": "review_projection_bundle_artifact",
                "review_projection_bundle_id": "rpb-feedfeedfeedfeed",
                "artifact_ref": "review_projection_bundle_artifact:rpb-feedfeedfeedfeed",
            },
            {
                "artifact_type": "review_signal_artifact",
                "review_signal_artifact_id": "rsa-0000000000000000",
                "artifact_ref": "review_signal_artifact:rsa-0000000000000000",
            },
        ]
    )
    artifact = build_closure_decision_artifact(request)
    assert artifact["evidence_refs"] == [
        "review_projection_bundle_artifact:rpb-feedfeedfeedfeed",
        "review_signal_artifact:rsa-0000000000000000",
    ]
    assert artifact["source_artifact_refs"] == artifact["evidence_refs"]


def test_optional_next_step_prompt_generation_correctness():
    decision = build_closure_decision_artifact(
        _base_request(
            bounded_next_step_available=True,
            next_step_ref="hardening_batch:hb-900",
            source_artifacts=[
                {
                    "artifact_type": "review_signal_artifact",
                    "review_signal_artifact_id": "rsa-9999999999999999",
                    "artifact_ref": "review_signal_artifact:rsa-9999999999999999",
                    "critical_count": 1,
                }
            ],
        )
    )
    prompt = maybe_build_next_step_prompt_artifact(
        closure_decision_artifact=decision,
        required_inputs=decision["source_artifact_refs"],
        stop_conditions=["all_critical_and_high_items_resolved"],
        boundedness_notes=["deterministic_next_step_only"],
        emitted_at=EMITTED_AT,
    )
    assert prompt is not None
    assert prompt["prompt_class"] == "hardening_batch"
    assert prompt["source_closure_decision_ref"] == decision["closure_decision_id"]
    _validate(prompt, "next_step_prompt_artifact")


def test_unsupported_source_artifact_fails_closed():
    with pytest.raises(ClosureDecisionEngineError):
        build_closure_decision_artifact(
            _base_request(
                source_artifacts=[
                    {
                        "artifact_type": "unknown_artifact",
                        "artifact_ref": "unknown_artifact:u-1",
                    }
                ]
            )
        )
