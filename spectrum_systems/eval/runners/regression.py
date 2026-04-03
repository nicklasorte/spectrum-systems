from __future__ import annotations

from typing import Dict, Iterable, Any


def build_regression_report(baseline: Iterable[Dict[str, Any]], candidate: Iterable[Dict[str, Any]], baseline_run_id: str, candidate_run_id: str) -> Dict[str, Any]:
    baseline_map = {str(r["case_id"]): r.get("status") for r in baseline}
    candidate_map = {str(r["case_id"]): r.get("status") for r in candidate}
    regressed = sorted(
        case_id
        for case_id, status in candidate_map.items()
        if baseline_map.get(case_id) == "pass" and status == "fail"
    )
    return {
        "artifact_type": "eval_regression_report",
        "schema_version": "1.0.0",
        "report_id": "err-" + f"{abs(hash((baseline_run_id, candidate_run_id, tuple(regressed)))) & ((1<<64)-1):016x}",
        "baseline_run_id": baseline_run_id,
        "candidate_run_id": candidate_run_id,
        "regressed_case_ids": regressed,
        "status": "regression_detected" if regressed else "pass",
    }
