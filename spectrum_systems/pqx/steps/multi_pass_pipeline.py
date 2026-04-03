from __future__ import annotations

from typing import Any, Callable, Dict, List

PASS_TYPES = ["extract", "critique", "contradiction", "gap", "synthesis"]


def run_multi_pass_pipeline(source: Dict[str, Any], runner: Callable[[str, Dict[str, Any]], Dict[str, Any]]) -> List[Dict[str, Any]]:
    outputs: List[Dict[str, Any]] = []
    prior = source
    for idx, pass_type in enumerate(PASS_TYPES, start=1):
        out = runner(pass_type, prior)
        if not isinstance(out, dict) or "artifact_ref" not in out:
            raise RuntimeError(f"{pass_type} pass did not produce governed artifact output")
        outputs.append(
            {
                "pass_id": f"pass_{idx}",
                "pass_type": pass_type,
                "trace_id": str(out.get("trace_id", "trace")),
                "input_ref": str(out.get("input_ref", "input")),
                "artifact_ref": str(out["artifact_ref"]),
                "output": out,
            }
        )
        prior = out
    return outputs
