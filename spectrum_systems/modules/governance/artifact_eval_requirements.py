from __future__ import annotations
from typing import Any, Dict, List
from spectrum_systems.modules.runtime.bne_utils import BNEBlockError, ensure_contract


def evaluate_required_evals(profile: Dict[str, Any], eval_results: List[Dict[str, Any]], artifact_family: str, stage: str, trace_id: str) -> Dict[str, Any]:
    ensure_contract(profile, "artifact_eval_requirement_profile")
    required = [r for r in profile.get("outputs", {}).get("requirements", []) if artifact_family in r.get("artifact_families", []) and stage in r.get("stages", [])]
    if not required:
        raise BNEBlockError(f"missing required eval profile mapping for family={artifact_family} stage={stage}")
    by_id = {e.get("eval_id"): e for e in eval_results}
    missing = [r["eval_id"] for r in required if r.get("eval_id") not in by_id]
    blocked = bool(missing or any((by_id[r["eval_id"]].get("result") != "pass" and r.get("blocking", True)) for r in required if r.get("eval_id") in by_id))
    total = len(required)
    fail_count = len(missing)
    pass_count = max(total - fail_count, 0)
    return ensure_contract(
        {
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
            "latest_eval_run_refs": [r.get("eval_id", "") for r in eval_results if r.get("eval_id")],
            "risk_class": "critical" if blocked else "low",
            "priority": "p0" if blocked else "p3",
            "status": "blocked" if blocked else "healthy",
        },
        "eval_slice_summary",
    )
