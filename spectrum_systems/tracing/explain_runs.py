from __future__ import annotations

from typing import Any, Dict, Iterable


def explain_run_failure(run_id: str, trace_events: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    failed = [e for e in trace_events if e.get("status") == "failed"]
    summary = failed[0].get("message", "no failure message") if failed else "no failure detected"
    hotspots = sorted({str(e.get("step", "unknown")) for e in failed})
    return {
        "artifact_type": "explain_run_report",
        "schema_version": "1.0.0",
        "report_id": "exr-" + f"{abs(hash((run_id, tuple(hotspots), summary))) & ((1<<64)-1):016x}",
        "run_id": run_id,
        "failure_summary": summary,
        "hotspots": hotspots,
    }
