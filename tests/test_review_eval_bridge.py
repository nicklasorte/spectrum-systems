from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.contracts import load_example, load_schema  # noqa: E402
from spectrum_systems.modules.runtime.review_eval_bridge import (  # noqa: E402
    ReviewEvalBridgeError,
    build_eval_result_from_review_signal,
    canonicalize_review_signal,
)


def _review_signal() -> dict:
    return copy.deepcopy(load_example("review_control_signal"))


def test_review_signal_to_eval_result_is_schema_valid() -> None:
    eval_result = build_eval_result_from_review_signal(_review_signal())
    from jsonschema import Draft202012Validator, FormatChecker

    Draft202012Validator(load_schema("eval_result"), format_checker=FormatChecker()).validate(eval_result)
    assert eval_result["artifact_type"] == "eval_result"


def test_same_review_signal_produces_deterministic_eval_result() -> None:
    first = build_eval_result_from_review_signal(_review_signal())
    second = build_eval_result_from_review_signal(_review_signal())
    assert first == second


def test_malformed_review_signal_fails_closed() -> None:
    bad_signal = _review_signal()
    bad_signal.pop("gate_assessment")
    with pytest.raises(ReviewEvalBridgeError):
        canonicalize_review_signal(bad_signal)


def test_fail_review_maps_to_failed_eval_result() -> None:
    signal = _review_signal()
    signal["gate_assessment"] = "FAIL"
    signal["scale_recommendation"] = "NO"
    signal["critical_findings"] = ["critical issue [eval_family:review_gate_alignment]"]

    eval_result = build_eval_result_from_review_signal(signal)

    assert eval_result["result_status"] == "fail"
    assert "review_gate_failed" in eval_result["failure_modes"]
    assert "review_scale_not_recommended" in eval_result["failure_modes"]
    assert any(ref.startswith("review_control_signal:") for ref in eval_result["provenance_refs"])
