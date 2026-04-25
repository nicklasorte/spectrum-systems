"""HOP trend reporting (Phase 2).

Streams the experience store and emits a single
``hop_harness_trend_report`` artifact summarising:

- top failure modes (count by ``failure_class``);
- cost trend (min / max / mean across recorded scores);
- pattern effectiveness (mean score per candidate tag);
- frontier movement (count of frontier artifacts and best score seen).

The report is advisory-only. It never deletes or rewrites any artifact.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import fmean
from typing import Any, Mapping

from spectrum_systems.modules.hop.artifacts import finalize_artifact, make_trace
from spectrum_systems.modules.hop.experience_store import (
    ExperienceStore,
    HopStoreError,
)
from spectrum_systems.modules.hop.schemas import validate_hop_artifact


def _utcnow() -> str:
    return (
        datetime.now(tz=timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


@dataclass(frozen=True)
class TrendReportConfig:
    max_failure_modes: int = 10
    max_pattern_effectiveness_rows: int = 20


def build_trend_report(
    store: ExperienceStore,
    *,
    config: TrendReportConfig | None = None,
    trace_id: str = "hop_trend_reports",
) -> dict[str, Any]:
    cfg = config or TrendReportConfig()
    failure_counts: Counter[str] = Counter()
    score_records: list[Mapping[str, Any]] = []
    candidate_records: dict[str, Mapping[str, Any]] = {}

    for rec in store.iter_index(artifact_type="hop_harness_failure_hypothesis"):
        fields = rec.get("fields", {}) or {}
        cls = fields.get("failure_class")
        if isinstance(cls, str) and cls:
            failure_counts[cls] += 1

    score_count = 0
    cost_values: list[float] = []
    score_values_by_candidate: dict[str, list[float]] = defaultdict(list)
    for rec in store.iter_index(artifact_type="hop_harness_score"):
        score_count += 1
        try:
            payload = store.read_artifact("hop_harness_score", rec["artifact_id"])
        except HopStoreError:
            continue
        score_records.append(payload)
        cost = payload.get("cost")
        if isinstance(cost, (int, float)):
            cost_values.append(float(cost))
        cid = str(payload.get("candidate_id", ""))
        if cid:
            score_values_by_candidate[cid].append(float(payload.get("score", 0.0)))

    candidate_tags: dict[str, list[str]] = {}
    for rec in store.iter_index(artifact_type="hop_harness_candidate"):
        try:
            payload = store.read_artifact("hop_harness_candidate", rec["artifact_id"])
        except HopStoreError:
            continue
        cid = str(payload.get("candidate_id", ""))
        if not cid:
            continue
        candidate_records[cid] = payload
        tags = payload.get("tags") or []
        if isinstance(tags, list):
            candidate_tags[cid] = [str(t) for t in tags]

    pattern_buckets: dict[str, list[float]] = defaultdict(list)
    for cid, scores in score_values_by_candidate.items():
        for tag in candidate_tags.get(cid, []) or []:
            pattern_buckets[tag].extend(scores)

    pattern_rows = []
    for tag in sorted(pattern_buckets.keys()):
        scores = pattern_buckets[tag]
        if not scores:
            continue
        pattern_rows.append(
            {
                "pattern_tag": tag,
                "candidate_count": sum(
                    1 for cid in candidate_tags if tag in candidate_tags.get(cid, [])
                ),
                "mean_score": float(fmean(scores)),
            }
        )
    pattern_rows.sort(key=lambda r: (-r["mean_score"], r["pattern_tag"]))
    pattern_rows = pattern_rows[: cfg.max_pattern_effectiveness_rows]

    frontier_count = 0
    best_score_seen = 0.0
    for rec in store.iter_index(artifact_type="hop_harness_frontier"):
        frontier_count += 1
        try:
            payload = store.read_artifact("hop_harness_frontier", rec["artifact_id"])
        except HopStoreError:
            continue
        frontier_payload = payload.get("frontier") or payload.get("members") or []
        for member in frontier_payload if isinstance(frontier_payload, list) else []:
            if isinstance(member, Mapping):
                m_score = float(member.get("score", 0.0))
                if m_score > best_score_seen:
                    best_score_seen = m_score
        # also consider raw score artifacts for the best-score seen.
    for s in score_records:
        v = float(s.get("score", 0.0))
        if v > best_score_seen:
            best_score_seen = v

    cost_trend = {
        "sample_count": len(cost_values),
        "min_cost": float(min(cost_values)) if cost_values else 0.0,
        "max_cost": float(max(cost_values)) if cost_values else 0.0,
        "mean_cost": float(fmean(cost_values)) if cost_values else 0.0,
    }

    top_failure_modes = [
        {"failure_class": cls, "count": count}
        for cls, count in failure_counts.most_common(cfg.max_failure_modes)
    ]

    payload: dict[str, Any] = {
        "artifact_type": "hop_harness_trend_report",
        "schema_ref": "hop/harness_trend_report.schema.json",
        "schema_version": "1.0.0",
        "trace": make_trace(primary=trace_id),
        "report_id": f"trend_{score_count:08d}_{frontier_count:08d}_{sum(failure_counts.values()):08d}",
        "window_run_count": score_count,
        "top_failure_modes": top_failure_modes,
        "cost_trend": cost_trend,
        "pattern_effectiveness": pattern_rows,
        "frontier_movement": {
            "frontier_count": frontier_count,
            "best_score_seen": min(1.0, max(0.0, best_score_seen)),
        },
        "advisory_only": True,
        "generated_at": _utcnow(),
    }
    finalize_artifact(payload, id_prefix="hop_trend_")
    validate_hop_artifact(payload, "hop_harness_trend_report")
    return payload


def _find_existing_trend_report(
    store: ExperienceStore, report_id: str
) -> dict[str, Any] | None:
    for rec in store.iter_index(artifact_type="hop_harness_trend_report"):
        fields = rec.get("fields", {}) or {}
        if fields.get("report_id") == report_id:
            try:
                return store.read_artifact(
                    "hop_harness_trend_report", rec["artifact_id"]
                )
            except HopStoreError:
                continue
    return None


def emit_trend_report(
    store: ExperienceStore,
    *,
    config: TrendReportConfig | None = None,
    trace_id: str = "hop_trend_reports",
) -> dict[str, Any]:
    """Emit a trend report. Idempotent when the underlying store is unchanged.

    The ``report_id`` is derived from the deterministic counts of scores,
    frontiers, and failures in the store, so two emits over an unchanged
    store return the same record without re-creating the artifact.
    """
    report = build_trend_report(store, config=config, trace_id=trace_id)
    existing = _find_existing_trend_report(store, report["report_id"])
    if existing is not None:
        return existing
    try:
        store.write_artifact(report)
    except HopStoreError as exc:
        if "duplicate_artifact" in str(exc):
            return report
        raise
    return report
