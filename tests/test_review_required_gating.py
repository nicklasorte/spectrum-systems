from __future__ import annotations

import copy
from pathlib import Path
import sys

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.contracts import load_example  # noqa: E402
from spectrum_systems.modules.runtime.evaluation_control import build_evaluation_control_decision  # noqa: E402
from spectrum_systems.modules.runtime.review_eval_bridge import build_eval_result_from_review_signal  # noqa: E402


def _replay() -> dict:
    return copy.deepcopy(load_example("replay_result"))


def _signal(review_type: str = "surgical", gate: str = "PASS") -> dict:
    signal = copy.deepcopy(load_example("review_control_signal"))
    signal["review_type"] = review_type
    signal["gate_assessment"] = gate
    signal["scale_recommendation"] = "YES" if gate == "PASS" else "NO"
    return signal


def test_missing_required_review_blocks() -> None:
    decision = build_evaluation_control_decision(_replay(), review_signal_required=True)
    assert decision["decision"] == "deny"
    assert decision["system_response"] == "block"


def test_missing_required_review_type_blocks() -> None:
    eval_result = build_eval_result_from_review_signal(_signal("failure", "PASS"))
    decision = build_evaluation_control_decision(
        _replay(),
        review_eval_results=[eval_result],
        required_review_types=["surgical"],
    )
    assert decision["decision"] == "deny"


def test_required_review_fail_blocks_even_if_replay_healthy() -> None:
    decision = build_evaluation_control_decision(
        _replay(),
        review_control_signal=_signal("surgical", "FAIL"),
        review_signal_required=True,
        required_review_types=["surgical"],
    )
    assert decision["decision"] == "deny"
    assert decision["system_response"] == "block"
