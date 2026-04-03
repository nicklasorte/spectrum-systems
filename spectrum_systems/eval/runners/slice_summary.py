from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List


def summarize_slices(eval_rows: Iterable[Dict[str, Any]], coverage_run_id: str) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in eval_rows:
        grouped[str(row["slice_id"])].append(row)

    summaries: List[Dict[str, Any]] = []
    for slice_id, rows in sorted(grouped.items()):
        total = len(rows)
        pass_count = sum(1 for r in rows if r.get("status") == "pass")
        fail_count = sum(1 for r in rows if r.get("status") == "fail")
        indeterminate_count = total - pass_count - fail_count
        summaries.append(
            {
                "artifact_type": "eval_slice_summary",
                "schema_version": "1.0.0",
                "coverage_run_id": coverage_run_id,
                "slice_id": slice_id,
                "slice_name": slice_id,
                "total_cases": total,
                "pass_count": pass_count,
                "fail_count": fail_count,
                "indeterminate_count": indeterminate_count,
                "pass_rate": pass_count / total if total else 0,
                "failure_rate": fail_count / total if total else 0,
                "latest_eval_run_refs": sorted({str(r.get("run_id", "run")) for r in rows}),
                "risk_class": "medium",
                "priority": "p1",
                "status": "blocked" if fail_count else "healthy",
            }
        )
    return summaries
