"""Tests for unified prompt queue transition decision artifact and fail-closed semantics."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.contracts import load_example  # noqa: E402
from spectrum_systems.modules.prompt_queue import (  # noqa: E402
    TransitionDecisionBuildError,
    build_queue_transition_decision,
    validate_prompt_queue_transition_decision_artifact,
)


class FixedClock:
    def __init__(self, values: list[str]):
        self._values = [datetime.fromisoformat(v.replace("Z", "+00:00")) for v in values]

    def __call__(self):
        if not self._values:
            return datetime(2026, 3, 28, 12, 0, 0, tzinfo=timezone.utc)
        return self._values.pop(0)


def _step_decision(decision: str, reason_codes: list[str]) -> dict:
    return {
        "decision_id": "step-decision-step-001-20260328T115959Z",
        "step_id": "step-001",
        "queue_id": "queue-001",
        "trace_linkage": "trace-001",
        "decision": decision,
        "reason_codes": reason_codes,
        "blocking_reasons": ["validation"] if decision == "block" else [],
        "derived_from_artifacts": ["execres-wi-001-attempt-1"],
        "timestamp": "2026-03-28T11:59:59Z",
        "generator_version": "prompt_queue_step_decision.v1",
    }


def _handoff(status: str = "handoff_completed") -> dict:
    return {
        "review_parsing_handoff_artifact_id": "review-parsing-handoff-wi-001-20260328T120000Z",
        "findings_artifact_path": "artifacts/prompt_queue/findings/wi-001.findings.json",
        "review_invocation_result_artifact_path": "artifacts/prompt_queue/review_invocation_results/wi-001.json",
        "handoff_status": status,
        "handoff_reason_code": "handoff_completed_findings_emitted" if status == "handoff_completed" else "handoff_failed_review_parse_error",
    }


def test_transition_schema_example_validates():
    validate_prompt_queue_transition_decision_artifact(load_example("prompt_queue_transition_decision"))


def test_allow_step_decision_maps_to_continue():
    artifact = build_queue_transition_decision(
        _step_decision("allow", ["clean_findings"]),
        clock=FixedClock(["2026-03-28T12:00:01Z"]),
    )
    assert artifact["transition_action"] == "continue"
    assert artifact["transition_status"] == "allowed"
    assert artifact["reason_codes"] == ["allow_clean_findings_continue"]


def test_review_worthy_findings_map_to_request_review():
    artifact = build_queue_transition_decision(
        _step_decision("warn", ["warnings_detected"]),
        clock=FixedClock(["2026-03-28T12:00:01Z"]),
    )
    assert artifact["transition_action"] == "request_review"


def test_findings_handoff_enables_reentry_with_findings():
    artifact = build_queue_transition_decision(
        _step_decision("block", ["errors_detected"]),
        findings_handoff=_handoff("handoff_completed"),
        clock=FixedClock(["2026-03-28T12:00:01Z"]),
    )
    assert artifact["transition_action"] == "reenter_with_findings"


def test_retry_eligible_path_maps_to_retry_allowed():
    artifact = build_queue_transition_decision(
        _step_decision("block", ["errors_detected"]),
        clock=FixedClock(["2026-03-28T12:00:01Z"]),
    )
    assert artifact["transition_action"] == "retry_allowed"


def test_ambiguous_inputs_fail_closed():
    with pytest.raises(TransitionDecisionBuildError, match="more than one transition action inferred"):
        build_queue_transition_decision(
            _step_decision("block", ["errors_detected", "ambiguity_detected"]),
            clock=FixedClock(["2026-03-28T12:00:01Z"]),
        )


def test_missing_lineage_fails_fast():
    decision = _step_decision("allow", ["clean_findings"])
    decision.pop("decision_id")
    with pytest.raises(TransitionDecisionBuildError, match="source decision reference"):
        build_queue_transition_decision(decision, clock=FixedClock(["2026-03-28T12:00:01Z"]))


def test_conflicting_findings_and_decision_inputs_fail_fast():
    with pytest.raises(TransitionDecisionBuildError, match="more than one transition action inferred"):
        build_queue_transition_decision(
            _step_decision("block", ["errors_detected", "invalid_report"]),
            findings_handoff=_handoff("handoff_completed"),
            clock=FixedClock(["2026-03-28T12:00:01Z"]),
        )


def test_deterministic_output_is_stable_for_same_inputs():
    first = build_queue_transition_decision(
        _step_decision("warn", ["warnings_detected"]),
        clock=FixedClock(["2026-03-28T12:00:01Z"]),
    )
    second = build_queue_transition_decision(
        _step_decision("warn", ["warnings_detected"]),
        clock=FixedClock(["2026-03-28T12:00:01Z"]),
    )
    assert first == second
