from __future__ import annotations
from typing import Any, Dict
from spectrum_systems.modules.runtime.bne_utils import ensure_contract

def build_eval_slice_summary(*, trace_id: str, artifact_family: str, stage: str, required_eval_ids: list[str], observed_eval_ids: list[str]) -> Dict[str, Any]:
    missing = sorted(set(required_eval_ids) - set(observed_eval_ids))
    total = len(required_eval_ids)
    fail_count = len(missing)
    pass_count = max(total - fail_count, 0)
    return ensure_contract({
        "artifact_type": "eval_slice_summary",
        "schema_version": "1.0.0",
        "coverage_run_id": f"coverage:{trace_id}:{artifact_family}:{stage}",
        "slice_id": f"{artifact_family}:{stage}",
        "slice_name": f"{artifact_family}:{stage}",
        "total_cases": total,
        "pass_count": pass_count,
        "fail_count": fail_count,
        "indeterminate_count": 0,
        "pass_rate": pass_count / max(total, 1),
        "failure_rate": fail_count / max(total, 1),
        "latest_eval_run_refs": observed_eval_ids,
        "risk_class": "critical" if missing else "low",
        "priority": "p0" if missing else "p3",
        "status": "blocked" if missing else "healthy",
    }, "eval_slice_summary")
