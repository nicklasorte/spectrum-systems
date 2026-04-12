#!/usr/bin/env python3
"""Governed dashboard refresh/publish loop with fail-closed gates."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

UTC_FMT = "%Y-%m-%dT%H:%M:%SZ"
FRESHNESS_CONTRACT_VERSION = "1.0.0"
FRESHNESS_THRESHOLD_SECONDS = 6 * 3600
FAILURE_CLASSES = {
    "refresh_failed",
    "refresh_skipped",
    "refresh_partial",
    "stale_inputs",
    "publication_blocked",
    "freshness_contract_violation",
    "manifest_coherence_failure",
}

REQUIRED_SOURCES = {
    "next_action_recommendation_record.json": "artifacts/rq_master_36_01/next_action_recommendation_record.json",
    "next_action_outcome_record.json": "artifacts/rq_master_36_01/next_action_outcome_record.json",
    "recommendation_accuracy_tracker.json": "artifacts/rq_master_36_01/recommendation_accuracy_tracker.json",
    "confidence_calibration_artifact.json": "artifacts/rq_master_36_01/confidence_calibration_artifact.json",
    "stuck_loop_detector.json": "artifacts/rq_master_36_01/stuck_loop_detector.json",
    "recommendation_review_surface.json": "artifacts/rq_master_36_01/recommendation_review_surface.json",
    "readiness_to_expand_validator.json": "artifacts/rq_master_36_01/readiness_to_expand_validator.json",
    "deploy_ci_truth_gate.json": "artifacts/rq_master_36_01/deploy_ci_truth_gate.json",
    "operator_surface_snapshot_export.json": "artifacts/rq_master_36_01/operator_surface_snapshot_export.json",
    "error_budget_enforcement_outcome.json": "artifacts/rq_master_36_01/error_budget_enforcement_outcome.json",
    "recurrence_prevention_status.json": "artifacts/rq_master_36_01/recurrence_prevention_status.json",
    "judgment_application_artifact.json": "artifacts/rq_master_36_01/judgment_application_artifact.json",
    "operator_trust_closeout_artifact.json": "artifacts/rq_master_36_01/operator_trust_closeout_artifact.json",
    "compatibility_mirror_retirement_assessment.json": "artifacts/rq_master_36_01/compatibility_mirror_retirement_assessment.json",
    "dashboard_public_contract_coverage.json": "artifacts/rq_master_36_01/dashboard_public_contract_coverage.json",
    "governed_promotion_discipline_gate.json": "artifacts/rq_master_36_01/governed_promotion_discipline_gate.json",
    "cycle_comparator_03_05.json": "artifacts/rq_master_36_01/cycle_comparator_03_05.json",
    "current_bottleneck_record.json": "artifacts/ops_master_01/current_bottleneck_record.json",
    "drift_trend_continuity_artifact.json": "artifacts/ops_master_01/drift_trend_continuity_artifact.json",
    "canonical_roadmap_state_artifact.json": "artifacts/ops_master_01/canonical_roadmap_state_artifact.json",
    "maturity_phase_tracker.json": "artifacts/ops_master_01/maturity_phase_tracker.json",
    "hard_gate_status_record.json": "artifacts/ops_master_01/hard_gate_status_record.json",
    "current_run_state_record.json": "artifacts/ops_master_01/current_run_state_record.json",
    "deferred_item_register.json": "artifacts/ops_master_01/deferred_item_register.json",
    "deferred_return_tracker.json": "artifacts/ops_master_01/deferred_return_tracker.json",
    "constitutional_drift_checker_result.json": "artifacts/ops_master_01/constitutional_drift_checker_result.json",
    "roadmap_alignment_validator_result.json": "artifacts/ops_master_01/roadmap_alignment_validator_result.json",
    "serial_bundle_validator_result.json": "artifacts/ops_master_01/serial_bundle_validator_result.json",
}


@dataclass
class LoopContext:
    repo_root: Path
    dashboard_public_dir: Path
    dashboard_artifacts_dir: Path
    run_root: Path
    mode: str
    now: datetime



def iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).strftime(UTC_FMT)


def parse_iso_utc(value: str) -> datetime:
    return datetime.strptime(value, UTC_FMT).replace(tzinfo=timezone.utc)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _snapshot_paths(ctx: LoopContext) -> tuple[Path, Path]:
    return ctx.dashboard_artifacts_dir / "repo_snapshot.json", ctx.dashboard_public_dir / "repo_snapshot.json"


def evaluate_freshness(contract: dict[str, Any], snapshot_ts: str, now: datetime) -> dict[str, Any]:
    threshold = int(contract["freshness_source_of_truth"]["stale_threshold_seconds"])
    snap_dt = parse_iso_utc(snapshot_ts)
    age_seconds = max(0.0, (now - snap_dt).total_seconds())
    stale = age_seconds > threshold
    reason_codes = ["stale_snapshot"] if stale else ["freshness_ok"]
    return {
        "artifact_type": "dashboard_freshness_status_record",
        "contract_version": contract["contract_version"],
        "timestamp": iso_utc(now),
        "overall_verdict": "block" if stale else "pass",
        "artifacts": [
            {
                "artifact": "repo_snapshot.json",
                "verdict": "stale" if stale else "fresh",
                "age_seconds": round(age_seconds, 3),
                "threshold_seconds": threshold,
                "reason_codes": reason_codes,
            }
        ],
    }


def run_loop(ctx: LoopContext, inject_failure: str | None = None) -> int:
    start = datetime.now(timezone.utc)
    trace_id = f"trace-{iso_utc(start).replace(':','').replace('-','')}"
    refresh_run_id = f"refresh-{iso_utc(start).replace(':','').replace('-','')}"
    publish_attempt_id = f"publish-{iso_utc(start).replace(':','').replace('-','')}"

    contract = _load_json(ctx.repo_root / "contracts" / "examples" / "dashboard_freshness_contract.json")
    if inject_failure == "missing_contract":
        contract = {}

    snapshot_artifact, _ = _snapshot_paths(ctx)
    if not snapshot_artifact.is_file():
        raise RuntimeError("repo_snapshot.json must exist before publication stage")
    snapshot = _load_json(snapshot_artifact)

    authoritative_field = contract.get("freshness_source_of_truth", {}).get("authoritative_timestamp_field", "generated_at")
    snapshot_ts = str(snapshot.get(authoritative_field, "")).strip()
    if inject_failure == "malformed_timestamp":
        snapshot_ts = "bad-time"
    if not snapshot_ts:
        raise RuntimeError(f"Missing authoritative timestamp field: {authoritative_field}")

    freshness_status = evaluate_freshness(contract, snapshot_ts, ctx.now)
    freshness_status.update({"trace_id": trace_id, "refresh_run_id": refresh_run_id})

    stage_dir = ctx.dashboard_public_dir / ".refresh_stage"
    if stage_dir.exists():
        shutil.rmtree(stage_dir)
    stage_dir.mkdir(parents=True)

    refreshed_artifacts = ["repo_snapshot.json"]
    stale_artifacts = [] if freshness_status["overall_verdict"] == "pass" else ["repo_snapshot.json"]

    required = dict(REQUIRED_SOURCES)
    required["repo_snapshot.json"] = "artifacts/dashboard/repo_snapshot.json"
    missing_required = []

    for name, rel in sorted(required.items()):
        src = ctx.repo_root / rel
        if not src.is_file():
            missing_required.append(name)
            continue
        shutil.copy2(src, stage_dir / name)
        refreshed_artifacts.append(name)

    if inject_failure == "missing_required_artifact":
        target = stage_dir / "hard_gate_status_record.json"
        if target.exists():
            target.unlink()
            missing_required.append("hard_gate_status_record.json")

    meta_payload = {
        "last_refreshed_time": snapshot_ts,
        "snapshot_size": f"{(stage_dir / 'repo_snapshot.json').stat().st_size} bytes",
        "data_source_state": "live",
        "snapshot_source_path": "artifacts/dashboard/repo_snapshot.json",
        "snapshot_size_bytes": (stage_dir / "repo_snapshot.json").stat().st_size,
        "refresh_run_id": refresh_run_id,
        "trace_id": trace_id,
        "run_id": refresh_run_id,
    }
    _write_json(stage_dir / "repo_snapshot_meta.json", meta_payload)

    legacy_freshness = {
        "artifact_type": "dashboard_freshness_status",
        "batch_id": "DASHBOARD-REFRESH-PUBLISH-LOOP-01",
        "generated_at": iso_utc(ctx.now),
        "freshness_window_hours": int(FRESHNESS_THRESHOLD_SECONDS / 3600),
        "status": "fresh" if freshness_status["overall_verdict"] == "pass" else "stale",
        "snapshot_last_refreshed_time": snapshot_ts,
        "snapshot_age_hours": round(freshness_status["artifacts"][0]["age_seconds"] / 3600, 3),
        "publication_state": "live" if freshness_status["overall_verdict"] == "pass" else "stale",
        "contract_version": contract.get("contract_version", FRESHNESS_CONTRACT_VERSION),
        "trace_id": trace_id,
        "refresh_run_id": refresh_run_id,
        "reason_codes": freshness_status["artifacts"][0]["reason_codes"],
        "per_artifact_verdicts": freshness_status["artifacts"],
    }
    _write_json(stage_dir / "dashboard_freshness_status.json", legacy_freshness)
    _write_json(ctx.run_root / "dashboard_freshness_status_record.json", freshness_status)

    required_files = sorted(set(list(required.keys()) + [
        "repo_snapshot_meta.json",
        "dashboard_freshness_status.json",
        "dashboard_publication_sync_audit.json",
        "dashboard_publication_manifest.json",
        "refresh_run_record.json",
        "publication_attempt_record.json",
    ]))

    records = []
    for name in sorted([p.name for p in stage_dir.glob("*.json")]):
        fp = stage_dir / name
        records.append({
            "artifact": name,
            "source": "generated" if name in {"repo_snapshot_meta.json", "dashboard_freshness_status.json"} else required.get(name, "generated"),
            "sha256": hashlib.sha256(fp.read_bytes()).hexdigest(),
            "size_bytes": fp.stat().st_size,
        })

    _write_json(stage_dir / "dashboard_publication_sync_audit.json", {
        "artifact_type": "dashboard_publication_sync_audit",
        "published_at": snapshot_ts,
        "publication_state": "live" if freshness_status["overall_verdict"] == "pass" else "stale",
        "required_artifact_count": len(required_files),
        "trace_id": trace_id,
        "refresh_run_id": refresh_run_id,
        "records": records,
    })

    manifest = {
        "artifact_type": "dashboard_publication_manifest",
        "manifest_version": "1.1.0",
        "published_at": snapshot_ts,
        "publication_mode": "atomic",
        "publication_state": "live" if freshness_status["overall_verdict"] == "pass" else "stale",
        "publication_contract": "canonical_live_artifact_projection",
        "artifact_count": len(required_files),
        "required_files": required_files,
        "trace_id": trace_id,
        "refresh_run_id": refresh_run_id,
    }

    file_records = {}
    for name in required_files:
        fp = stage_dir / name
        if not fp.exists():
            continue
        file_records[name] = {
            "sha256": hashlib.sha256(fp.read_bytes()).hexdigest(),
            "size_bytes": fp.stat().st_size,
            "source": required.get(name, f"generated:{name}"),
        }
    manifest["file_records"] = file_records
    manifest["completeness_sha256"] = hashlib.sha256(
        "|".join(f"{n}:{file_records[n]['sha256']}" for n in sorted(file_records)).encode("utf-8")
    ).hexdigest()

    manifest_missing: list[str] = []
    reason_codes = []
    validation_pass = True
    if freshness_status["overall_verdict"] != "pass":
        validation_pass = False
        reason_codes.append("stale_snapshot")
    if missing_required or manifest_missing:
        validation_pass = False
        reason_codes.append("missing_required_artifact")
        if missing_required:
            print(
                f"required governed publication sources missing: {sorted(set(missing_required))}",
                file=sys.stderr,
            )
    if inject_failure == "malformed_manifest":
        manifest["publication_state"] = "invalid-state"
        validation_pass = False
        reason_codes.append("manifest_coherence_failure")

    # error-budget freeze
    eb_path = ctx.repo_root / "artifacts" / "rq_master_36_01" / "error_budget_enforcement_outcome.json"
    freeze = False
    if eb_path.exists():
        eb = _load_json(eb_path)
        if str(eb.get("status", "")).lower() in {"blocked", "exhausted", "freeze"}:
            freeze = True
            validation_pass = False
            reason_codes.append("error_budget_exhausted")

    decision = "allow" if validation_pass else "freeze" if freeze else "block"
    if not reason_codes:
        reason_codes = ["freshness_ok"]

    publication_attempt = {
        "artifact_type": "publication_attempt_record",
        "publish_attempt_id": publish_attempt_id,
        "refresh_run_id": refresh_run_id,
        "trace_id": trace_id,
        "decision": decision,
        "reason_codes": sorted(set(reason_codes)),
        "artifact_counts": {
            "required": len(required_files),
            "loaded": len(file_records),
            "valid": len(file_records) if validation_pass else max(0, len(file_records) - 1),
        },
        "freshness_summary": {
            "overall_verdict": freshness_status["overall_verdict"],
            "stale_artifact_count": len(stale_artifacts),
            "age_seconds": freshness_status["artifacts"][0]["age_seconds"],
            "threshold_seconds": FRESHNESS_THRESHOLD_SECONDS,
        },
        "validation_summary": {
            "overall_verdict": "pass" if validation_pass else "block",
            "missing_required_artifacts": sorted(set(missing_required + manifest_missing)),
        },
        "trigger_mode": ctx.mode,
        "timestamp": iso_utc(ctx.now),
    }
    _write_json(stage_dir / "publication_attempt_record.json", publication_attempt)
    _write_json(ctx.run_root / "publication_attempt_record.json", publication_attempt)

    refresh_run_record = {
        "artifact_type": "refresh_run_record",
        "refresh_run_id": refresh_run_id,
        "trace_id": trace_id,
        "run_id": refresh_run_id,
        "target_artifact_family": "dashboard_publication",
        "start_time": iso_utc(start),
        "end_time": iso_utc(datetime.now(timezone.utc)),
        "outcome": "success" if decision == "allow" else "partial" if file_records else "failed",
        "refreshed_artifacts": sorted(set(refreshed_artifacts + ["repo_snapshot_meta.json", "dashboard_freshness_status.json"])),
        "stale_artifacts_found": stale_artifacts,
        "failure_class": "publication_blocked" if decision != "allow" else None,
        "trigger_mode": ctx.mode,
    }
    if refresh_run_record["failure_class"] is None:
        refresh_run_record.pop("failure_class")
    _write_json(stage_dir / "refresh_run_record.json", refresh_run_record)
    _write_json(ctx.run_root / "refresh_run_record.json", refresh_run_record)
    _write_json(stage_dir / "dashboard_publication_manifest.json", manifest)

    # Recompute manifest completeness after all generated artifacts exist.
    file_records = {}
    for name in required_files:
        fp = stage_dir / name
        if not fp.exists():
            continue
        file_records[name] = {
            "sha256": hashlib.sha256(fp.read_bytes()).hexdigest(),
            "size_bytes": fp.stat().st_size,
            "source": required.get(name, f"generated:{name}"),
        }
    manifest["file_records"] = file_records
    manifest["completeness_sha256"] = hashlib.sha256(
        "|".join(f"{n}:{file_records[n]['sha256']}" for n in sorted(file_records)).encode("utf-8")
    ).hexdigest()
    _write_json(stage_dir / "dashboard_publication_manifest.json", manifest)
    manifest_missing = sorted(set(required_files) - set(file_records))

    metrics = {
        "artifact_type": "dashboard_refresh_publish_metrics",
        "timestamp": iso_utc(ctx.now),
        "trace_id": trace_id,
        "refresh_success_rate": 1.0 if decision == "allow" else 0.0,
        "refresh_latency_seconds": max(0.0, (datetime.now(timezone.utc) - start).total_seconds()),
        "publish_success_rate": 1.0 if decision == "allow" else 0.0,
        "dashboard_freshness_age_seconds": freshness_status["artifacts"][0]["age_seconds"],
        "stale_artifact_count": len(stale_artifacts),
        "freshness_gate_block_count": 0 if decision == "allow" else 1,
    }
    _write_json(ctx.run_root / "dashboard_refresh_publish_metrics.json", metrics)

    alert = {
        "artifact_type": "dashboard_refresh_publish_alert",
        "timestamp": iso_utc(ctx.now),
        "trace_id": trace_id,
        "status": "freeze" if decision == "freeze" else "ok" if decision == "allow" else "block",
        "reason_codes": publication_attempt["reason_codes"],
    }
    _write_json(ctx.run_root / "dashboard_refresh_publish_alert.json", alert)

    if decision != "allow":
        return 2

    for entry in stage_dir.iterdir():
        shutil.move(str(entry), ctx.dashboard_public_dir / entry.name)
    shutil.rmtree(stage_dir)
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run governed dashboard refresh/publish loop.")
    parser.add_argument("--mode", choices=["scheduled", "manual", "repair", "test"], default="manual")
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--inject-failure", choices=["malformed_timestamp", "malformed_manifest", "missing_required_artifact", "missing_contract"], default=None)
    parser.add_argument("--now", default=None, help="Deterministic UTC timestamp in ISO format.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    now = parse_iso_utc(args.now) if args.now else datetime.now(timezone.utc).replace(microsecond=0)
    ctx = LoopContext(
        repo_root=repo_root,
        dashboard_public_dir=repo_root / "dashboard" / "public",
        dashboard_artifacts_dir=repo_root / "artifacts" / "dashboard",
        run_root=repo_root / "artifacts" / "rq_master_36_01",
        mode=args.mode,
        now=now,
    )
    return run_loop(ctx, inject_failure=args.inject_failure)


if __name__ == "__main__":
    raise SystemExit(main())
