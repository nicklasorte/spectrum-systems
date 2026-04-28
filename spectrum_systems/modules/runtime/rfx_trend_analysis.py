"""RFX trend detection + hotspot mapping — RFX-07.

Detects systemic weak points across failures, repairs, replay drift, eval
gaps, telemetry / reliability freezes, and authority-shape findings. The
module is a non-owning phase-label support helper; canonical roles for
failure diagnosis (FRE), eval coverage (EVL), telemetry (OBS), reliability
posture (SLO), replay (REP), and registry boundaries remain with their
canonical owners recorded in ``docs/architecture/system_registry.md``.

Outputs:

  * ``rfx_trend_report``  — aggregated trend signals over the supplied corpus.
  * ``rfx_hotspot_record`` — focused record per hotspot with source refs.

Reason codes:

  * ``rfx_trend_input_missing``
  * ``rfx_hotspot_detected``
  * ``rfx_recurrence_threshold_exceeded``
  * ``rfx_eval_blind_spot_detected``
  * ``rfx_repair_loop_detected``
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from typing import Any


class RFXTrendAnalysisError(ValueError):
    """Raised when trend-analysis input is missing or malformed."""


_DEFAULT_RECURRENCE_THRESHOLD = 3
_DEFAULT_REPAIR_LOOP_THRESHOLD = 2
_DEFAULT_REPLAY_DRIFT_CLUSTER = 2


def _stable_id(payload: Any, *, prefix: str) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


_REASON_CODE_VARIANT_RE = re.compile(r"[_\W]+")


def _normalize_reason_code(code: Any) -> str | None:
    """Normalize a reason code to a stable cluster key.

    Strips trailing numeric variants and non-alphanumeric separators so a
    splitter that emits ``rfx_x_v1``, ``rfx_x_v2`` collapses to ``rfx_x_v``
    and is recognized as a single cluster. The transform is deterministic
    and intentionally conservative — tokens with explicit semantic meaning
    are preserved.
    """
    if not isinstance(code, str) or not code.strip():
        return None
    base = code.strip().lower()
    base = _REASON_CODE_VARIANT_RE.sub("_", base)
    # Strip a trailing numeric suffix from any token (e.g. v1, 2, attempt3).
    parts = base.split("_")
    parts = [re.sub(r"\d+$", "", p) for p in parts if p]
    return "_".join(p for p in parts if p) or None


def detect_recurring_reason_codes(
    failures: list[dict[str, Any]] | None,
    *,
    threshold: int = _DEFAULT_RECURRENCE_THRESHOLD,
) -> dict[str, int]:
    """Return mapping of normalized reason-code cluster → count where count ≥ threshold."""
    if not failures:
        return {}
    counts: Counter[str] = Counter()
    for f in failures:
        if not isinstance(f, dict):
            continue
        for key in ("reason_code", "code", "classification"):
            v = f.get(key)
            norm = _normalize_reason_code(v)
            if norm:
                counts[norm] += 1
                break
    return {k: v for k, v in counts.items() if v >= threshold}


def detect_repair_loops(
    repairs: list[dict[str, Any]] | None,
    *,
    threshold: int = _DEFAULT_REPAIR_LOOP_THRESHOLD,
) -> dict[str, int]:
    """Return mapping of repair_target → repeat-count where repeats ≥ threshold."""
    if not repairs:
        return {}
    counts: Counter[str] = Counter()
    for r in repairs:
        if not isinstance(r, dict):
            continue
        target = r.get("repair_target") or r.get("target") or r.get("subject")
        if isinstance(target, str) and target.strip():
            counts[target.strip()] += 1
    return {k: v for k, v in counts.items() if v >= threshold}


def detect_replay_drift_clusters(
    replay_results: list[dict[str, Any]] | None,
    *,
    cluster_size: int = _DEFAULT_REPLAY_DRIFT_CLUSTER,
) -> list[str]:
    """Return list of trace_ids whose replay records form a drift cluster.

    A drift cluster is declared when ``cluster_size`` or more replay records
    for the same trace_id show ``match=False``.
    """
    if not replay_results:
        return []
    by_trace: Counter[str] = Counter()
    for r in replay_results:
        if not isinstance(r, dict):
            continue
        match = r.get("match") if isinstance(r.get("match"), bool) else r.get("replay_match")
        if match is True:
            continue
        trace = r.get("trace_id")
        if isinstance(trace, str) and trace.strip():
            by_trace[trace.strip()] += 1
    return sorted(t for t, n in by_trace.items() if n >= cluster_size)


def detect_eval_blind_spots(
    failures: list[dict[str, Any]] | None,
    *,
    eval_coverage_refs: set[str] | None,
) -> list[str]:
    """Return reason codes that have failures but no covering eval ref.

    ``eval_coverage_refs`` is the set of reason codes already covered by
    EVL. Reason codes appearing in the failure corpus that are not in the
    coverage set are flagged as blind spots.
    """
    if not failures:
        return []
    covered = {str(c).strip().lower() for c in (eval_coverage_refs or set()) if isinstance(c, str)}
    seen: set[str] = set()
    for f in failures:
        if not isinstance(f, dict):
            continue
        for key in ("reason_code", "code", "classification"):
            v = f.get(key)
            if isinstance(v, str) and v.strip():
                seen.add(v.strip().lower())
                break
    return sorted(seen - covered)


def detect_authority_shape_failures(
    findings: list[dict[str, Any]] | None,
) -> list[str]:
    """Return list of authority-shape findings keyed by source path."""
    if not findings:
        return []
    out: list[str] = []
    for f in findings:
        if not isinstance(f, dict):
            continue
        path = f.get("path") or f.get("source_path") or f.get("file")
        code = f.get("reason_code") or f.get("code")
        if isinstance(path, str) and path.strip():
            tag = f"{path.strip()}::{code.strip()}" if isinstance(code, str) and code.strip() else path.strip()
            out.append(tag)
    return sorted(set(out))


def detect_telemetry_gaps(
    obs_records: list[dict[str, Any]] | None,
) -> list[str]:
    """Return list of trace_ids whose OBS record is incomplete."""
    if not obs_records:
        return []
    gaps: list[str] = []
    for r in obs_records:
        if not isinstance(r, dict):
            continue
        completeness = r.get("completeness") or r.get("telemetry_completeness") or r.get("status")
        if completeness in {"pass", "complete", True}:
            continue
        trace = r.get("trace_id")
        if isinstance(trace, str) and trace.strip():
            gaps.append(trace.strip())
    return sorted(set(gaps))


def detect_freeze_recurrence(
    freeze_records: list[dict[str, Any]] | None,
    *,
    threshold: int = _DEFAULT_REPAIR_LOOP_THRESHOLD,
) -> int:
    """Return total freeze-record count when count ≥ threshold, else 0."""
    if not freeze_records:
        return 0
    n = sum(1 for r in freeze_records if isinstance(r, dict))
    return n if n >= threshold else 0


def build_rfx_trend_report(
    *,
    failures: list[dict[str, Any]] | None,
    repairs: list[dict[str, Any]] | None,
    replay_results: list[dict[str, Any]] | None,
    obs_records: list[dict[str, Any]] | None,
    freeze_records: list[dict[str, Any]] | None,
    authority_findings: list[dict[str, Any]] | None,
    eval_coverage_refs: set[str] | None,
    recurrence_threshold: int = _DEFAULT_RECURRENCE_THRESHOLD,
) -> dict[str, Any]:
    """Build a deterministic ``rfx_trend_report`` artifact.

    Fails closed with ``rfx_trend_input_missing`` when every input source is
    absent (the report would have no observable surface to analyze).
    """
    inputs_present = any(
        x is not None and (not isinstance(x, list) or x)
        for x in [failures, repairs, replay_results, obs_records, freeze_records, authority_findings]
    )
    if not inputs_present:
        raise RFXTrendAnalysisError(
            "rfx_trend_input_missing: no failure/repair/replay/obs/freeze/authority input supplied"
        )

    recurring = detect_recurring_reason_codes(failures, threshold=recurrence_threshold)
    repair_loops = detect_repair_loops(repairs)
    drift_clusters = detect_replay_drift_clusters(replay_results)
    blind_spots = detect_eval_blind_spots(failures, eval_coverage_refs=eval_coverage_refs)
    authority_shape = detect_authority_shape_failures(authority_findings)
    telemetry_gaps = detect_telemetry_gaps(obs_records)
    freeze_recurrence = detect_freeze_recurrence(freeze_records)

    hotspots: list[dict[str, Any]] = []
    for code, count in sorted(recurring.items()):
        hotspots.append(
            {
                "artifact_type": "rfx_hotspot_record",
                "schema_version": "1.0.0",
                "hotspot_id": _stable_id({"reason_code": code, "count": count}, prefix="rfx-hotspot"),
                "kind": "recurring_reason_code",
                "reason_code": code,
                "occurrences": count,
                "reason_codes_emitted": ["rfx_recurrence_threshold_exceeded", "rfx_hotspot_detected"],
            }
        )
    for target, count in sorted(repair_loops.items()):
        hotspots.append(
            {
                "artifact_type": "rfx_hotspot_record",
                "schema_version": "1.0.0",
                "hotspot_id": _stable_id({"repair_target": target, "count": count}, prefix="rfx-hotspot"),
                "kind": "repair_loop",
                "repair_target": target,
                "occurrences": count,
                "reason_codes_emitted": ["rfx_repair_loop_detected", "rfx_hotspot_detected"],
            }
        )
    for code in blind_spots:
        hotspots.append(
            {
                "artifact_type": "rfx_hotspot_record",
                "schema_version": "1.0.0",
                "hotspot_id": _stable_id({"blind_spot": code}, prefix="rfx-hotspot"),
                "kind": "eval_blind_spot",
                "reason_code": code,
                "reason_codes_emitted": ["rfx_eval_blind_spot_detected", "rfx_hotspot_detected"],
            }
        )
    for trace in drift_clusters:
        hotspots.append(
            {
                "artifact_type": "rfx_hotspot_record",
                "schema_version": "1.0.0",
                "hotspot_id": _stable_id({"drift_trace": trace}, prefix="rfx-hotspot"),
                "kind": "replay_drift_cluster",
                "trace_id": trace,
                "reason_codes_emitted": ["rfx_hotspot_detected"],
            }
        )

    return {
        "artifact_type": "rfx_trend_report",
        "schema_version": "1.0.0",
        "report_id": _stable_id(
            {
                "recurring": recurring,
                "repair_loops": repair_loops,
                "drift_clusters": drift_clusters,
                "blind_spots": blind_spots,
                "authority_shape": authority_shape,
                "telemetry_gaps": telemetry_gaps,
                "freeze_recurrence": freeze_recurrence,
            },
            prefix="rfx-trend",
        ),
        "recurring_reason_codes": recurring,
        "repair_loops": repair_loops,
        "replay_drift_clusters": drift_clusters,
        "eval_blind_spots": blind_spots,
        "authority_shape_failures": authority_shape,
        "telemetry_gaps": telemetry_gaps,
        "freeze_recurrence_count": freeze_recurrence,
        "hotspots": hotspots,
    }


__all__ = [
    "RFXTrendAnalysisError",
    "build_rfx_trend_report",
    "detect_recurring_reason_codes",
    "detect_repair_loops",
    "detect_replay_drift_clusters",
    "detect_eval_blind_spots",
    "detect_authority_shape_failures",
    "detect_telemetry_gaps",
    "detect_freeze_recurrence",
]
