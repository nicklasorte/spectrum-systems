"""Tests for queue-step report parsing and deterministic decision gate."""

from __future__ import annotations

import copy
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.contracts import load_example  # noqa: E402
from spectrum_systems.modules.prompt_queue import (  # noqa: E402
    build_step_decision,
    parse_queue_step_report,
    validate_step_decision_artifact,
)
from spectrum_systems.modules.prompt_queue.review_parser import ReviewParseError  # noqa: E402
from spectrum_systems.modules.prompt_queue.step_decision import StepDecisionError  # noqa: E402


class FixedClock:
    def __init__(self, value: str):
        self._value = datetime.fromisoformat(value.replace("Z", "+00:00"))

    def __call__(self):
        return self._value.astimezone(timezone.utc)


def _base_execution_result() -> dict:
    return load_example("prompt_queue_execution_result")


def test_valid_report_produces_allow_decision():
    findings = parse_queue_step_report(_base_execution_result())
    decision = build_step_decision(findings, clock=FixedClock("2026-03-22T02:10:01Z"))
    validate_step_decision_artifact(decision)
    assert decision["decision"] == "allow"


def test_warning_findings_produce_warn_decision():
    artifact = _base_execution_result()
    artifact["produced_artifact_refs"] = ["artifacts/prompt_queue/simulated_outputs/other.output.json"]
    findings = parse_queue_step_report(artifact)
    decision = build_step_decision(findings, clock=FixedClock("2026-03-22T02:10:01Z"))
    assert decision["decision"] == "warn"


def test_malformed_report_fails_closed():
    malformed = _base_execution_result()
    malformed["unknown"] = "x"
    with pytest.raises(ReviewParseError):
        parse_queue_step_report(malformed)


def test_ambiguous_findings_produce_block():
    artifact = _base_execution_result()
    artifact["output_reference"] = None
    artifact["produced_artifact_refs"] = []
    findings = parse_queue_step_report(artifact)
    decision = build_step_decision(findings, clock=FixedClock("2026-03-22T02:10:01Z"))
    assert decision["decision"] == "block"
    assert "output_reference" in decision["blocking_reasons"]


def test_missing_required_fields_fail_closed():
    artifact = _base_execution_result()
    artifact.pop("execution_status")
    with pytest.raises(ReviewParseError):
        parse_queue_step_report(artifact)


def test_deterministic_output_is_stable():
    findings = parse_queue_step_report(_base_execution_result())
    left = build_step_decision(copy.deepcopy(findings), clock=FixedClock("2026-03-22T02:10:01Z"))
    right = build_step_decision(copy.deepcopy(findings), clock=FixedClock("2026-03-22T02:10:01Z"))
    assert left == right


def test_no_decision_produced_fails_closed():
    with pytest.raises(StepDecisionError):
        build_step_decision({"step_id": "step-001"})
