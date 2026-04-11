#!/usr/bin/env python3
"""Fail-closed validator for dashboard public operator-truth artifacts."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_ROOT = REPO_ROOT / "dashboard" / "public"

REQUIRED_PUBLIC = [
    "repo_snapshot.json",
    "repo_snapshot_meta.json",
    "dashboard_freshness_status.json",
    "dashboard_publication_sync_audit.json",
    "next_action_recommendation_record.json",
    "next_action_outcome_record.json",
    "recommendation_accuracy_tracker.json",
    "confidence_calibration_artifact.json",
    "stuck_loop_detector.json",
    "recommendation_review_surface.json",
    "readiness_to_expand_validator.json",
    "deploy_ci_truth_gate.json",
    "operator_surface_snapshot_export.json",
]

MAX_STALE_HOURS = 6


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _fail(message: str) -> int:
    print(f"ERROR: {message}", file=sys.stderr)
    return 1


def _parse_utc(value: str, field_name: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be ISO UTC (YYYY-MM-DDTHH:MM:SSZ)") from exc


def main() -> int:
    for name in REQUIRED_PUBLIC:
        path = PUBLIC_ROOT / name
        if not path.is_file():
            return _fail(f"missing required dashboard artifact: {name}")

    meta = _read_json(PUBLIC_ROOT / "repo_snapshot_meta.json")
    freshness = _read_json(PUBLIC_ROOT / "dashboard_freshness_status.json")
    audit = _read_json(PUBLIC_ROOT / "dashboard_publication_sync_audit.json")

    state = str(meta.get("data_source_state", "")).strip().lower()
    refreshed = str(meta.get("last_refreshed_time", "")).strip()
    if state not in {"live", "fallback"}:
        return _fail("repo_snapshot_meta.data_source_state must be live or fallback")
    if not refreshed:
        return _fail("repo_snapshot_meta.last_refreshed_time is required")

    try:
        ts = _parse_utc(refreshed, "repo_snapshot_meta.last_refreshed_time")
    except ValueError as exc:
        return _fail(str(exc))

    age_hours = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
    is_stale = age_hours > MAX_STALE_HOURS

    freshness_state = str(freshness.get("status", "")).strip().lower()
    publication_state = str(freshness.get("publication_state", "")).strip().lower()
    if freshness_state not in {"fresh", "stale", "fallback", "unknown"}:
        return _fail("dashboard_freshness_status.status must be fresh/stale/fallback/unknown")

    if publication_state and publication_state not in {"live", "fallback"}:
        return _fail("dashboard_freshness_status.publication_state must be live or fallback when present")

    if publication_state and publication_state != state:
        return _fail("fallback/live ambiguity detected between repo_snapshot_meta and dashboard_freshness_status")

    if freshness_state == "fresh" and is_stale:
        return _fail("freshness artifact says fresh but snapshot meta is stale")
    if freshness_state == "stale" and not is_stale:
        return _fail("freshness artifact says stale but snapshot meta is fresh")

    published_at = str(audit.get("published_at", "")).strip()
    if not published_at:
        return _fail("dashboard_publication_sync_audit.published_at is required")
    try:
        _parse_utc(published_at, "dashboard_publication_sync_audit.published_at")
    except ValueError as exc:
        return _fail(str(exc))

    audit_state = str(audit.get("publication_state", "")).strip().lower()
    if audit_state not in {"live", "fallback"}:
        return _fail("dashboard_publication_sync_audit.publication_state must be live or fallback")
    if audit_state != state:
        return _fail("fallback/live ambiguity detected between repo_snapshot_meta and dashboard_publication_sync_audit")

    records = audit.get("records")
    if not isinstance(records, list) or not records:
        return _fail("dashboard_publication_sync_audit.records must be a non-empty list")

    recommendation = _read_json(PUBLIC_ROOT / "next_action_recommendation_record.json")
    accuracy = _read_json(PUBLIC_ROOT / "recommendation_accuracy_tracker.json")

    records = recommendation.get("records")
    if isinstance(records, list):
        if not records:
            return _fail("next_action_recommendation_record.records must be non-empty")
        for row in records:
            provenance = row.get("provenance_categories")
            if not isinstance(provenance, list) or not provenance:
                return _fail("each recommendation record requires non-empty provenance_categories")
    else:
        provenance = recommendation.get("provenance")
        if not isinstance(provenance, list) or not provenance:
            return _fail("next_action_recommendation_record requires non-empty provenance")

    confidence = float(accuracy.get("accuracy", 0.0))
    if confidence < 0.0 or confidence > 1.0:
        return _fail("recommendation_accuracy_tracker.accuracy must be between 0 and 1")

    if state == "fallback" and confidence > 0.6:
        return _fail("fallback mode must degrade recommendation confidence (accuracy <= 0.6)")

    if is_stale and state == "live":
        return _fail(f"dashboard snapshot is stale ({age_hours:.1f}h > {MAX_STALE_HOURS}h)")

    print("dashboard-public-artifacts: pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
