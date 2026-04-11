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
    "next_action_recommendation_record.json",
    "next_action_outcome_record.json",
    "recommendation_accuracy_tracker.json",
    "confidence_calibration_artifact.json",
    "stuck_loop_detector.json",
    "readiness_to_expand_validator.json",
]

MAX_STALE_HOURS = 6


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _fail(message: str) -> int:
    print(f"ERROR: {message}", file=sys.stderr)
    return 1


def main() -> int:
    for name in REQUIRED_PUBLIC:
        path = PUBLIC_ROOT / name
        if not path.is_file():
            return _fail(f"missing required dashboard artifact: {name}")

    meta = _read_json(PUBLIC_ROOT / "repo_snapshot_meta.json")
    state = str(meta.get("data_source_state", "")).strip().lower()
    refreshed = str(meta.get("last_refreshed_time", "")).strip()

    if state not in {"live", "fallback"}:
        return _fail("repo_snapshot_meta.data_source_state must be live or fallback")

    if not refreshed:
        return _fail("repo_snapshot_meta.last_refreshed_time is required")

    try:
        ts = datetime.strptime(refreshed, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return _fail("repo_snapshot_meta.last_refreshed_time must be ISO UTC (YYYY-MM-DDTHH:MM:SSZ)")

    age_hours = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
    if age_hours > MAX_STALE_HOURS:
        return _fail(f"dashboard snapshot is stale ({age_hours:.1f}h > {MAX_STALE_HOURS}h)")

    recommendation = _read_json(PUBLIC_ROOT / "next_action_recommendation_record.json")
    accuracy = _read_json(PUBLIC_ROOT / "recommendation_accuracy_tracker.json")

    provenance = recommendation.get("provenance")
    if not isinstance(provenance, list) or not provenance:
        return _fail("next_action_recommendation_record requires non-empty provenance")

    confidence = float(accuracy.get("accuracy", 0.0))
    if confidence < 0.0 or confidence > 1.0:
        return _fail("recommendation_accuracy_tracker.accuracy must be between 0 and 1")

    if state == "fallback" and confidence > 0.6:
        return _fail("fallback mode must degrade recommendation confidence (accuracy <= 0.6)")

    print("dashboard-public-artifacts: pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
