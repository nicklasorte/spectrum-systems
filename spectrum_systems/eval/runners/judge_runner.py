from __future__ import annotations

from typing import Any, Dict


class JudgeOutputError(RuntimeError):
    """Raised when structured judge output is malformed."""


def run_judge(judge_output: Dict[str, Any], judge_metadata: Dict[str, Any]) -> Dict[str, Any]:
    required = {"decision", "rationale", "confidence"}
    missing = sorted(required - set(judge_output.keys()))
    if missing:
        raise JudgeOutputError(f"judge output missing required keys: {missing}")
    return {
        "decision": judge_output["decision"],
        "rationale": judge_output["rationale"],
        "confidence": float(judge_output["confidence"]),
        "judge_metadata": dict(judge_metadata),
    }
