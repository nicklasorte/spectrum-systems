import pytest

from spectrum_systems.modules.runtime.bne_utils import BNEBlockError
from spectrum_systems.modules.wpg.eval_coverage import build_eval_coverage_requirement_profile, enforce_eval_coverage


def test_eval_coverage_requirement_profile_contract_shape() -> None:
    profile = build_eval_coverage_requirement_profile(trace_id="trace-cov")
    assert profile["artifact_type"] == "eval_coverage_requirement_profile"
    assert profile["outputs"]["stage_requirements"]


def test_missing_required_eval_blocks() -> None:
    coverage = enforce_eval_coverage(
        trace_id="trace-cov",
        stage="working_paper_assembly",
        available_eval_classes=["contradiction_detection", "grounding_check"],
    )
    assert coverage["outputs"]["decision"] == "BLOCK"
    assert "uncertainty_detection" in coverage["outputs"]["missing_eval_classes"]


def test_unknown_stage_freeze_via_block_error() -> None:
    with pytest.raises(BNEBlockError):
        enforce_eval_coverage(trace_id="trace-cov", stage="unknown_stage", available_eval_classes=[])
