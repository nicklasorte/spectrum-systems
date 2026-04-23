"""Tests for FailureToEvalPipeline — RT-Loop-01 through RT-Loop-03."""

import pytest
from unittest.mock import Mock
from spectrum_systems.modules.feedback.failure_to_eval_pipeline import FailureToEvalPipeline
from spectrum_systems.modules.evaluation.error_taxonomy import ErrorType


@pytest.fixture
def pipeline():
    return FailureToEvalPipeline(
        artifact_store=Mock(),
        governance_system=Mock(),
        eval_registry=Mock(),
    )


def test_route_classified_error_creates_eval_candidate(pipeline):
    """RT-Loop-01: Classified error creates eval_candidate and governance approves it."""
    classified_error = {
        "artifact_type": "classified_error_artifact",
        "error_type": ErrorType.extraction_error,
        "source_artifact": {
            "artifact_type": "some_output",
            "artifact_id": "out-123",
        },
    }

    pipeline.governance_system.request_eval_adoption.return_value = {"approved": True}

    result = pipeline.route_classified_error(classified_error, "trace-001")

    assert result["artifact_type"] == "eval_adoption_decision"
    assert result["decision"] == "approved"
    assert result["trace_id"] == "trace-001"
    pipeline.eval_registry.add_candidate.assert_called_once()


def test_route_classified_error_requests_governance(pipeline):
    """RT-Loop-02: Governance denial prevents eval candidate from being added to suite."""
    classified_error = {
        "artifact_type": "classified_error_artifact",
        "error_type": ErrorType.reasoning_error,
        "source_artifact": {"artifact_type": "judgment", "artifact_id": "jdg-456"},
    }

    pipeline.governance_system.request_eval_adoption.return_value = {
        "approved": False,
        "reason": "eval_capacity_exhausted",
    }

    result = pipeline.route_classified_error(classified_error, "trace-002")

    assert result["approved"] is False
    pipeline.eval_registry.add_candidate.assert_not_called()


def test_eval_candidate_has_fixture_and_criteria(pipeline):
    """RT-Loop-03: Eval candidate includes a reproducible fixture and acceptance criteria."""
    classified_error = {
        "artifact_type": "classified_error_artifact",
        "error_type": ErrorType.schema_violation,
        "source_artifact": {"artifact_type": "output", "artifact_id": "out-789"},
    }

    pipeline.governance_system.request_eval_adoption.return_value = {"approved": True}

    pipeline.route_classified_error(classified_error, "trace-003")

    added_candidate = pipeline.eval_registry.add_candidate.call_args[0][0]
    assert "reproduction_fixture" in added_candidate
    assert added_candidate["reproduction_fixture"] != {}
    assert "acceptance_criteria" in added_candidate
    assert len(added_candidate["acceptance_criteria"]) > 0
