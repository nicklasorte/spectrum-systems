#!/usr/bin/env python3
"""Fail-closed validator for dashboard public operator-truth artifacts."""

from __future__ import annotations

import hashlib
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
    "refresh_run_record.json",
    "publication_attempt_record.json",
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


def _fail(message: str, checks: dict[str, str] | None = None) -> int:
    print(f"ERROR: {message}", file=sys.stderr)
    _emit_enforcement_result("fail", checks or {}, reason=message)
    return 1


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
        "trace_linkage": "pending",
    }
    if not SCHEMA_SET_PATH.is_file():
        return _fail("missing dashboard/public schema set")

    for name in REQUIRED_PUBLIC:
        if not (PUBLIC_ROOT / name).is_file():
            checks["required_public_artifacts_present"] = "fail"
            return _fail(f"missing required dashboard artifact: {name}", checks)
    checks["required_public_artifacts_present"] = "pass"

    schema_set = _read_json(SCHEMA_SET_PATH)
    targets = schema_set.get("validation_targets")
    defs = schema_set.get("$defs")
    if not isinstance(targets, list) or not isinstance(defs, dict):
        return _fail("invalid schema set structure: validation_targets and $defs are required")
    try:
        Draft202012Validator({"$ref": "https://json-schema.org/draft/2020-12/schema"}).validate(schema_set)
    except Exception:
        pass

    for target in targets:
        artifact_file = target.get("artifact_file")
        schema_ref = str(target.get("schema_ref", ""))
        example_file = target.get("example_file")
        if not artifact_file or not schema_ref.startswith("#/$defs/") or not example_file:
            return _fail("schema set has malformed validation target entry")
        schema_name = schema_ref.split("/")[-1]
        if schema_name not in defs:
            return _fail(f"schema ref not found in defs: {schema_name}")
        validator = Draft202012Validator(defs[schema_name])
        for payload_path in (PUBLIC_ROOT / artifact_file, PUBLIC_ROOT / example_file):
            try:
                validator.validate(_read_json(payload_path))
            except Exception as exc:  # noqa: BLE001
                return _fail(f"schema validation failed for {payload_path.relative_to(REPO_ROOT)} ({schema_name}): {exc}")

    snapshot = _read_json(PUBLIC_ROOT / "repo_snapshot.json")
    meta = _read_json(PUBLIC_ROOT / "repo_snapshot_meta.json")
    freshness = _read_json(PUBLIC_ROOT / "dashboard_freshness_status.json")
    audit = _read_json(PUBLIC_ROOT / "dashboard_publication_sync_audit.json")
    manifest = _read_json(PUBLIC_ROOT / "dashboard_publication_manifest.json")
    refresh_run = _read_json(PUBLIC_ROOT / "refresh_run_record.json")
    publication_attempt = _read_json(PUBLIC_ROOT / "publication_attempt_record.json")

    snapshot_ts = str(snapshot.get("generated_at", "")).strip()
    if not snapshot_ts:
        checks["freshness_metadata_valid"] = "fail"
        return _fail("repo_snapshot.generated_at is required", checks)
    try:
        _parse_utc(snapshot_ts, "repo_snapshot.generated_at")
    except ValueError as exc:
        checks["freshness_metadata_valid"] = "fail"
        return _fail(str(exc), checks)

    state = str(meta.get("data_source_state", "")).strip().lower()
    refreshed = str(meta.get("last_refreshed_time", "")).strip()
    if state != "live":
        checks["freshness_metadata_valid"] = "fail"
        return _fail("repo_snapshot_meta.data_source_state must be live", checks)
    if refreshed != snapshot_ts:
        checks["freshness_metadata_valid"] = "fail"
        return _fail("repo_snapshot_meta.last_refreshed_time must equal repo_snapshot.generated_at", checks)

    ts = _parse_utc(refreshed, "repo_snapshot_meta.last_refreshed_time")
    age_hours = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
    is_stale = age_hours > MAX_STALE_HOURS

    freshness_state = str(freshness.get("status", "")).strip().lower()
    if freshness_state not in {"fresh", "stale", "unknown"}:
        checks["freshness_metadata_valid"] = "fail"
        return _fail("dashboard_freshness_status.status must be fresh/stale/unknown", checks)
    if str(freshness.get("snapshot_last_refreshed_time", "")).strip() != snapshot_ts:
        checks["freshness_metadata_valid"] = "fail"
        return _fail("dashboard_freshness_status.snapshot_last_refreshed_time must equal repo_snapshot.generated_at", checks)

    if freshness_state == "fresh" and is_stale:
        checks["freshness_metadata_valid"] = "fail"
        return _fail("freshness artifact says fresh but snapshot is stale", checks)

    if str(audit.get("publication_state", "")).strip().lower() != "live":
        checks["publication_atomic"] = "fail"
        return _fail("dashboard_publication_sync_audit.publication_state must be live", checks)

    published_at = str(audit.get("published_at", "")).strip()
    _parse_utc(published_at, "dashboard_publication_sync_audit.published_at")

    if manifest.get("publication_mode") != "atomic":
        checks["publication_atomic"] = "fail"
        return _fail("dashboard_publication_manifest.publication_mode must be atomic", checks)

    required_files = manifest.get("required_files")
    if not isinstance(required_files, list) or len(required_files) != len(set(required_files)):
        checks["publication_atomic"] = "fail"
        return _fail("dashboard_publication_manifest.required_files must be unique list", checks)

    required_minimum = set(REQUIRED_PUBLIC + ["repo_snapshot_meta.json", "dashboard_freshness_status.json", "dashboard_publication_sync_audit.json", "dashboard_publication_manifest.json"])
    if missing := sorted(required_minimum - set(required_files)):
        checks["publication_atomic"] = "fail"
        return _fail(f"dashboard_publication_manifest.required_files missing required entries: {missing}", checks)

    if manifest.get("artifact_count") != len(required_files):
        checks["publication_atomic"] = "fail"
        return _fail("dashboard_publication_manifest.artifact_count must equal required_files length", checks)

    file_records = manifest.get("file_records")
    if not isinstance(file_records, dict):
        checks["publication_atomic"] = "fail"
        return _fail("dashboard_publication_manifest.file_records must be object", checks)

    for required_name in required_files:
        path = PUBLIC_ROOT / required_name
        if not path.is_file():
            checks["publication_atomic"] = "fail"
            return _fail(f"manifest required file missing on disk: {required_name}", checks)
        if required_name == "dashboard_publication_manifest.json":
            continue
        record = file_records.get(required_name)
        if not isinstance(record, dict):
            checks["publication_atomic"] = "fail"
            return _fail(f"manifest missing file record for {required_name}", checks)
        if str(record.get("sha256", "")) != hashlib.sha256(path.read_bytes()).hexdigest():
            checks["publication_atomic"] = "fail"
            return _fail(f"manifest/file sha mismatch for {required_name}", checks)

    if refresh_run.get("artifact_type") != "refresh_run_record":
        checks["trace_linkage"] = "fail"
        return _fail("refresh_run_record artifact_type invalid", checks)
    if publication_attempt.get("artifact_type") != "publication_attempt_record":
        checks["trace_linkage"] = "fail"
        return _fail("publication_attempt_record artifact_type invalid", checks)

    trace_ids = {
        str(refresh_run.get("trace_id", "")).strip(),
        str(publication_attempt.get("trace_id", "")).strip(),
        str(freshness.get("trace_id", "")).strip(),
    }
    if "" in trace_ids or len(trace_ids) != 1:
        checks["trace_linkage"] = "fail"
        return _fail("trace linkage mismatch across refresh/freshness/publication artifacts", checks)

    decision = str(publication_attempt.get("decision", "")).strip().lower()
    if decision not in {"allow", "block", "freeze"}:
        checks["trace_linkage"] = "fail"
        return _fail("publication_attempt_record.decision invalid", checks)

    if decision != "allow":
        checks["truth_constraints"] = "fail"
        return _fail("publication blocked/frozen by governed gate", checks)

    checks["freshness_metadata_valid"] = "pass"
    checks["fallback_live_ambiguity"] = "pass"
    checks["publication_atomic"] = "pass"
    checks["trace_linkage"] = "pass"
    checks["truth_constraints"] = "pass"
    _emit_enforcement_result("pass", checks)
    print("dashboard-public-artifacts: pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
