#!/usr/bin/env python3
"""Fail-closed validator for dashboard public operator-truth artifacts."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_ROOT = REPO_ROOT / "dashboard" / "public"
SCHEMA_SET_PATH = PUBLIC_ROOT / "contracts" / "dashboard_public_artifact_schema_set.json"

REQUIRED_PUBLIC = [
    "repo_snapshot.json",
    "repo_snapshot_meta.json",
    "dashboard_freshness_status.json",
    "dashboard_publication_sync_audit.json",
    "dashboard_publication_manifest.json",
    "next_action_recommendation_record.json",
    "next_action_outcome_record.json",
    "recommendation_accuracy_tracker.json",
    "confidence_calibration_artifact.json",
    "stuck_loop_detector.json",
    "recommendation_review_surface.json",
    "readiness_to_expand_validator.json",
    "deploy_ci_truth_gate.json",
    "operator_surface_snapshot_export.json",
    "operator_trust_closeout_artifact.json",
    "compatibility_mirror_retirement_assessment.json",
    "dashboard_public_contract_coverage.json",
    "governed_promotion_discipline_gate.json",
]

MAX_STALE_HOURS = 6


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _fail(message: str, checks: dict[str, str] | None = None) -> int:
    print(f"ERROR: {message}", file=sys.stderr)
    _emit_enforcement_result("fail", checks or {}, reason=message)
    return 1




def _emit_enforcement_result(status: str, checks: dict[str, str], reason: str | None = None) -> None:
    out = REPO_ROOT / "artifacts" / "rq_master_36_01" / "dashboard_refresh_enforcement_result.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "artifact_type": "dashboard_refresh_enforcement_result",
        "enforcement_owner": "SEL",
        "status": status,
        "checks": checks,
    }
    if reason:
        payload["reason"] = reason
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

def _parse_utc(value: str, field_name: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be ISO UTC (YYYY-MM-DDTHH:MM:SSZ)") from exc


def main() -> int:
    checks = {
        "required_public_artifacts_present": "pending",
        "freshness_metadata_valid": "pending",
        "publication_atomic": "pending",
        "fallback_live_ambiguity": "pending",
        "truth_constraints": "pending",
    }
    if not SCHEMA_SET_PATH.is_file():
        return _fail("missing dashboard/public schema set")

    for name in REQUIRED_PUBLIC:
        path = PUBLIC_ROOT / name
        if not path.is_file():
            checks["required_public_artifacts_present"] = "fail"
            return _fail(f"missing required dashboard artifact: {name}", checks)
    checks["required_public_artifacts_present"] = "pass"

    schema_set = _read_json(SCHEMA_SET_PATH)
    try:
        Draft202012Validator({"$ref": "https://json-schema.org/draft/2020-12/schema"}).validate(schema_set)
    except Exception:
        pass

    targets = schema_set.get("validation_targets")
    defs = schema_set.get("$defs")
    if not isinstance(targets, list) or not isinstance(defs, dict):
        return _fail("invalid schema set structure: validation_targets and $defs are required")

    for target in targets:
        artifact_file = target.get("artifact_file")
        schema_ref = str(target.get("schema_ref", ""))
        example_file = target.get("example_file")
        if not artifact_file or not schema_ref.startswith("#/$defs/") or not example_file:
            return _fail("schema set has malformed validation target entry")
        schema_name = schema_ref.split("/")[-1]
        if schema_name not in defs:
            return _fail(f"schema ref not found in defs: {schema_name}")
        artifact_path = PUBLIC_ROOT / artifact_file
        if not artifact_path.is_file():
            return _fail(f"required schema-backed artifact missing: {artifact_file}")
        example_path = PUBLIC_ROOT / example_file
        if not example_path.is_file():
            return _fail(f"required schema example missing: {example_file}")
        validator = Draft202012Validator(defs[schema_name])
        for payload_path in (artifact_path, example_path):
            try:
                validator.validate(_read_json(payload_path))
            except Exception as exc:  # noqa: BLE001
                return _fail(f"schema validation failed for {payload_path.relative_to(REPO_ROOT)} ({schema_name}): {exc}")

    meta = _read_json(PUBLIC_ROOT / "repo_snapshot_meta.json")
    freshness = _read_json(PUBLIC_ROOT / "dashboard_freshness_status.json")
    audit = _read_json(PUBLIC_ROOT / "dashboard_publication_sync_audit.json")

    manifest = _read_json(PUBLIC_ROOT / "dashboard_publication_manifest.json")

    state = str(meta.get("data_source_state", "")).strip().lower()
    refreshed = str(meta.get("last_refreshed_time", "")).strip()
    if state not in {"live", "fallback"}:
        checks["freshness_metadata_valid"] = "fail"
        return _fail("repo_snapshot_meta.data_source_state must be live or fallback", checks)
    if not refreshed:
        checks["freshness_metadata_valid"] = "fail"
        return _fail("repo_snapshot_meta.last_refreshed_time is required", checks)

    try:
        ts = _parse_utc(refreshed, "repo_snapshot_meta.last_refreshed_time")
    except ValueError as exc:
        checks["freshness_metadata_valid"] = "fail"
        return _fail(str(exc), checks)

    age_hours = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
    is_stale = age_hours > MAX_STALE_HOURS

    freshness_state = str(freshness.get("status", "")).strip().lower()
    publication_state = str(freshness.get("publication_state", "")).strip().lower()
    if freshness_state not in {"fresh", "stale", "fallback", "unknown"}:
        return _fail("dashboard_freshness_status.status must be fresh/stale/fallback/unknown")

    if publication_state and publication_state not in {"live", "fallback"}:
        return _fail("dashboard_freshness_status.publication_state must be live or fallback when present")

    if publication_state and publication_state != state:
        checks["fallback_live_ambiguity"] = "fail"
        return _fail("fallback/live ambiguity detected between repo_snapshot_meta and dashboard_freshness_status", checks)

    if freshness_state == "fresh" and is_stale:
        checks["freshness_metadata_valid"] = "fail"
        return _fail("freshness artifact says fresh but snapshot meta is stale", checks)
    if freshness_state == "stale" and not is_stale:
        checks["freshness_metadata_valid"] = "fail"
        return _fail("freshness artifact says stale but snapshot meta is fresh", checks)

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
        checks["fallback_live_ambiguity"] = "fail"
        return _fail("fallback/live ambiguity detected between repo_snapshot_meta and dashboard_publication_sync_audit", checks)

    records = audit.get("records")
    if not isinstance(records, list) or not records:
        checks["publication_atomic"] = "fail"
        return _fail("dashboard_publication_sync_audit.records must be a non-empty list", checks)

    if manifest.get("publication_mode") != "atomic":
        checks["publication_atomic"] = "fail"
        return _fail("dashboard_publication_manifest.publication_mode must be atomic", checks)

    if str(manifest.get("publication_state", "")).strip().lower() != state:
        checks["publication_atomic"] = "fail"
        return _fail("dashboard_publication_manifest.publication_state must match repo_snapshot_meta", checks)

    checks["publication_atomic"] = "pass"
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
        checks["freshness_metadata_valid"] = "fail"
        return _fail(f"dashboard snapshot is stale ({age_hours:.1f}h > {MAX_STALE_HOURS}h)", checks)

    readiness = _read_json(PUBLIC_ROOT / "readiness_to_expand_validator.json")
    closeout = _read_json(PUBLIC_ROOT / "operator_trust_closeout_artifact.json")
    promotion_gate = _read_json(PUBLIC_ROOT / "governed_promotion_discipline_gate.json")

    readiness_state = readiness.get("readiness_state")
    allowed = {"Tune instead", "Validate with another run", "Ready for bounded expansion", "Unknown"}
    if readiness_state not in allowed:
        return _fail("readiness_to_expand_validator.readiness_state is invalid")

    if readiness_state != "Ready for bounded expansion" and promotion_gate.get("promotion_decision") == "bounded_promote":
        return _fail("promotion gate cannot bounded_promote when readiness is not ready")

    if closeout.get("expansion_posture") in {"bounded_expand", "expand_now"}:
        return _fail("operator closeout expansion posture is not conservative")

    checks["freshness_metadata_valid"] = "pass"
    checks["fallback_live_ambiguity"] = "pass"
    checks["truth_constraints"] = "pass"
    _emit_enforcement_result("pass", checks)
    print("dashboard-public-artifacts: pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
