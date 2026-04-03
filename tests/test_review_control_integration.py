from __future__ import annotations

import json
from pathlib import Path

from spectrum_systems.modules.runtime.evaluation_control import build_evaluation_control_decision
from spectrum_systems.modules.runtime.review_signal_extractor import extract_review_signal

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _replay_result() -> dict:
    return json.loads((_REPO_ROOT / "contracts" / "examples" / "replay_result.json").read_text(encoding="utf-8"))


def test_fail_review_blocks_control_decision(tmp_path: Path) -> None:
    replay = _replay_result()
    review_path = tmp_path / "review_signal_fail.md"
    review_path.write_text(
        "---\n"
        "module: runtime\n"
        "review_type: failure\n"
        "review_date: 2026-04-01\n"
        "reviewer: test\n"
        "decision: FAIL\n"
        "status: final\n"
        "---\n"
        "## Critical Findings\n"
        "- review-driven block\n",
        encoding="utf-8",
    )
    review_signal = extract_review_signal(review_path)
    decision = build_evaluation_control_decision(replay, review_control_signal=review_signal)
    assert decision["decision"] == "deny"
    assert decision["system_response"] in {"freeze", "block"}


def test_required_missing_review_signal_fails_closed() -> None:
    replay = _replay_result()
    decision = build_evaluation_control_decision(replay, review_signal_required=True)
    assert decision["decision"] == "deny"
    assert "missing_required_signal" in decision["triggered_signals"]
