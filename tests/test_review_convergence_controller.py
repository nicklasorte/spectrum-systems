"""Tests for ReviewConvergenceController — RT-Loop-04 through RT-Loop-06."""

import pytest
from unittest.mock import patch
from spectrum_systems.modules.review_convergence_controller import ReviewConvergenceController

_MODULE = "spectrum_systems.modules.review_convergence_controller.run_review_fix_execution_cycle"


@pytest.fixture
def controller():
    return ReviewConvergenceController(max_iterations=3)


def test_converges_on_first_iteration(controller):
    """RT-Loop-04: Already-clean result returns immediately without further iterations."""
    with patch(_MODULE) as mock_run:
        mock_run.return_value = {
            "artifact_type": "review_fix_result",
            "review_status": "pass",
            "artifact_id": "res-1",
        }

        result = controller.run_until_clean({"artifact_type": "request"}, trace_id="trace-001")

        assert result["convergence_status"] == "CLEAN"
        assert result["convergence_iterations"] == 1
        assert mock_run.call_count == 1


def test_converges_after_fix(controller):
    """RT-Loop-05: Runs a second iteration after an incomplete fix, then stops when clean."""
    with patch(_MODULE) as mock_run:
        mock_run.side_effect = [
            {
                "artifact_type": "review_fix_result",
                "review_status": "fail",
                "remaining_issues": ["issue_1"],
                "fixed_artifact": {"data": "fixed"},
                "artifact_id": "res-1",
            },
            {
                "artifact_type": "review_fix_result",
                "review_status": "pass",
                "remaining_issues": [],
                "artifact_id": "res-2",
            },
        ]

        result = controller.run_until_clean({"artifact_type": "request"}, trace_id="trace-002")

        assert result["convergence_status"] == "CLEAN"
        assert result["convergence_iterations"] == 2
        assert mock_run.call_count == 2


def test_blocks_after_max_iterations(controller):
    """RT-Loop-06: Returns BLOCKED_MAX_ITERATIONS when no iteration produces a clean result."""
    with patch(_MODULE) as mock_run:
        mock_run.return_value = {
            "artifact_type": "review_fix_result",
            "review_status": "fail",
            "remaining_issues": ["persistent_issue"],
            "artifact_id": "res-x",
        }

        result = controller.run_until_clean({"artifact_type": "request"}, trace_id="trace-003")

        assert result["convergence_status"] == "BLOCKED_MAX_ITERATIONS"
        assert result["convergence_iterations"] == 3
        assert mock_run.call_count == 3
