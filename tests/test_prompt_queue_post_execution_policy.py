"""Tests for post-execution policy alignment with unified transition decision spine."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.prompt_queue import (  # noqa: E402
    TransitionDecisionBuildError,
    build_queue_transition_decision,
)


class FixedClock:
    def __init__(self, values: list[str]):
        self._values = [datetime.fromisoformat(v.replace("Z", "+00:00")) for v in values]

    def __call__(self):
        if not self._values:
            return datetime(2026, 3, 28, 12, 0, 0, tzinfo=timezone.utc)
        return self._values.pop(0)


def _step_decision() -> dict:
    return {
        "decision_id": "step-decision-step-001-20260328T115959Z",
        "step_id": "step-001",
        "queue_id": "queue-001",
        "trace_linkage": "trace-001",
        "decision": "allow",
        "reason_codes": ["clean_findings"],
        "blocking_reasons": [],
        "derived_from_artifacts": ["execres-wi-001-attempt-1"],
        "timestamp": "2026-03-28T11:59:59Z",
        "generator_version": "prompt_queue_step_decision.v1",
    }


def test_missing_prompt_queue_step_decision_fails_fast():
    with pytest.raises(TransitionDecisionBuildError, match="missing prompt_queue_step_decision"):
        build_queue_transition_decision(None, clock=FixedClock(["2026-03-28T12:00:01Z"]))


def test_missing_step_id_fails_fast():
    decision = _step_decision()
    decision.pop("step_id")
    with pytest.raises(TransitionDecisionBuildError, match="step_id"):
        build_queue_transition_decision(decision, clock=FixedClock(["2026-03-28T12:00:01Z"]))


def test_missing_queue_and_trace_lineage_fails_fast():
    decision = _step_decision()
    decision["queue_id"] = None
    decision["trace_linkage"] = None
    with pytest.raises(TransitionDecisionBuildError, match="queue_id or trace_linkage"):
        build_queue_transition_decision(decision, clock=FixedClock(["2026-03-28T12:00:01Z"]))
