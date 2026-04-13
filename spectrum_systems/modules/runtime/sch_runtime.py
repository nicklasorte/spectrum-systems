"""SCH deterministic runtime for MASTER-ROADMAP-001."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Mapping

from spectrum_systems.contracts import validate_artifact


class SCHRuntimeError(ValueError):
    """Raised when SCH runtime checks fail closed."""


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stable_id(prefix: str, payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"{prefix}-{hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:12]}"


def _require_mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SCHRuntimeError(f"{field} must be an object")
    return value


def build_eval_artifact(*, payload: Mapping[str, Any]) -> dict[str, Any]:
    body = _require_mapping(payload, "payload")
    fail_reasons = sorted(str(v) for v in body.get("fail_reasons", []) if str(v).strip())
    status = "pass" if not fail_reasons else "fail"
    artifact = {
        "artifact_type": "sch_compatibility_result",
        "schema_version": "1.0.0",
        "artifact_id": _stable_id("sch-eval", body),
        "status": status,
        "generated_at": _now(),
        "details": {"checks": sorted(body.keys()), "fail_reasons": fail_reasons},
        "references": [str(body.get("trace_id") or "trace-missing")],
    }
    validate_artifact(artifact, "sch_compatibility_result")
    return artifact


def build_readiness_artifact(*, eval_artifact: Mapping[str, Any]) -> dict[str, Any]:
    rec = {
        "artifact_type": "sch_migration_record",
        "schema_version": "1.0.0",
        "artifact_id": _stable_id("sch-ready", eval_artifact),
        "status": "candidate_ready" if eval_artifact.get("status") == "pass" else "not_ready",
        "generated_at": _now(),
        "details": {
            "eval_ref": "sch_compatibility_result:" + str(eval_artifact.get("artifact_id") or "missing"),
            "non_authority_assertions": ["candidate_only", "no_closure_authority", "no_policy_authority"],
        },
        "references": ["CDE", "TPA", "SEL"],
    }
    validate_artifact(rec, "sch_migration_record")
    return rec


def validate_replay(*, baseline: Mapping[str, Any], replay: Mapping[str, Any]) -> dict[str, Any]:
    for field, value in (("baseline", baseline), ("replay", replay)):
        _require_mapping(value, field)
    keys = ["artifact_type", "schema_version", "status", "details"]
    left = {k: baseline.get(k) for k in keys}
    right = {k: replay.get(k) for k in keys}
    return {
        "is_match": left == right,
        "baseline_fingerprint": _stable_id("base", left),
        "replay_fingerprint": _stable_id("replay", right),
        "reason_codes": [] if left == right else ["replay_mismatch_detected"],
    }


def build_effectiveness_artifact(*, eval_artifact: Mapping[str, Any], replay_result: Mapping[str, Any]) -> dict[str, Any]:
    artifact = {
        "artifact_type": "sch_stale_schema_report",
        "schema_version": "1.0.0",
        "artifact_id": _stable_id("sch-effect", [eval_artifact, replay_result]),
        "status": "stable" if replay_result.get("is_match") and eval_artifact.get("status") == "pass" else "mildly_divergent",
        "generated_at": _now(),
        "details": {"eval_status": eval_artifact.get("status"), "replay_match": bool(replay_result.get("is_match"))},
        "references": [str(eval_artifact.get("artifact_id") or "missing")],
    }
    validate_artifact(artifact, "sch_stale_schema_report")
    return artifact


def run_red_team_round(*, fixture: Mapping[str, Any]) -> dict[str, Any]:
    base = dict(_require_mapping(fixture, "fixture"))
    exploit = bool(base.get("authority_creep_attempt")) or bool(base.get("unbounded_input"))
    artifact = {
        "artifact_type": "sch_schema_evolution_bundle",
        "schema_version": "1.0.0",
        "artifact_id": _stable_id("sch-bundle", base),
        "status": "materially_inconsistent" if exploit else "pass",
        "generated_at": _now(),
        "details": {
            "exploit_detected": exploit,
            "fix_pack": ["reject_authority_creep", "enforce_candidate_only", "bound_input_surface"],
        },
        "references": ["AEX", "PQX", "TLC"],
    }
    validate_artifact(artifact, "sch_schema_evolution_bundle")
    return artifact
