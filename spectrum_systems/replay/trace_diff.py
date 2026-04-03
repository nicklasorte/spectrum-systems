from __future__ import annotations

from typing import Any, Dict


def diff_runs(left_run: Dict[str, Any], right_run: Dict[str, Any]) -> Dict[str, Any]:
    diffs = []
    all_keys = sorted(set(left_run) | set(right_run))
    for key in all_keys:
        if left_run.get(key) != right_run.get(key):
            diffs.append({"path": key, "left": left_run.get(key), "right": right_run.get(key)})
    return {
        "artifact_type": "trace_diff_report",
        "schema_version": "1.0.0",
        "diff_id": "tdr-" + f"{abs(hash((tuple(sorted(left_run.items())), tuple(sorted(right_run.items()))))) & ((1<<64)-1):016x}",
        "left_run_id": str(left_run.get("run_id", "left")),
        "right_run_id": str(right_run.get("run_id", "right")),
        "diffs": diffs,
    }
