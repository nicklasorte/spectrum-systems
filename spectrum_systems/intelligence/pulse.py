from __future__ import annotations

from typing import Any, Dict, Iterable, List


def build_trend_report(trend_id: str, points: Iterable[Dict[str, Any]], window: str) -> Dict[str, Any]:
    series = [{"bucket": str(p["bucket"]), "value": float(p["value"])} for p in points]
    return {
        "artifact_type": "trend_report_artifact",
        "schema_version": "1.0.0",
        "trend_id": trend_id,
        "window": window,
        "series": series,
    }


def build_improvement_recommendations(signals: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    recs: List[Dict[str, Any]] = []
    for idx, signal in enumerate(signals, start=1):
        recs.append(
            {
                "artifact_type": "improvement_recommendation_record",
                "schema_version": "1.0.0",
                "recommendation_id": f"irr-{idx:016x}",
                "source_signal_ids": [str(signal.get("signal_id", f"signal-{idx}"))],
                "recommendation": f"Investigate {signal.get('signal_type', 'signal')} for {signal.get('artifact_family', 'unknown')}",
                "target_area": str(signal.get("artifact_family", "unknown")),
            }
        )
    return recs
