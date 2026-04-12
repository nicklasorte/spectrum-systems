"""AEX boundary hardening and evaluation helpers.

This module keeps AEX bounded: it validates admission artifacts and emits admission
signals, but it does not execute work, orchestrate runtime flows, or make policy authority decisions.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.pqx_backbone import REPO_ROOT
from spectrum_systems.modules.runtime.lineage_authenticity import LineageAuthenticityError, verify_authenticity
from spectrum_systems.modules.runtime.repo_write_lineage_guard import RepoWriteLineageGuardError, validate_repo_write_lineage


class AEXHardeningError(ValueError):
    """Raised when a hardening invariant fails closed."""


def reset_duplicate_registry_state() -> None:
    if _DUPLICATE_REGISTRY.exists():
        _DUPLICATE_REGISTRY.unlink()

_DUPLICATE_REGISTRY = REPO_ROOT / "state" / "aex_admission_seen_requests.json"


def _utc_now() -> datetime:
    return datetime.now(tz=timezone.utc).replace(microsecond=0)


def _canonical_hash(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _artifact_ref(artifact_type: str, artifact_id: str) -> str:
    return f"{artifact_type}:{artifact_id}"


def build_admission_authenticity_record(
    *,
    build_admission_record: dict[str, Any],
    normalized_execution_request: dict[str, Any],
    created_at: str,
) -> dict[str, Any]:
    fail_reasons: list[str] = []
    auth_material: dict[str, dict[str, str]] = {}

    for artifact_name, artifact, issuer in (
        ("build_admission_record", build_admission_record, "AEX"),
        ("normalized_execution_request", normalized_execution_request, "AEX"),
    ):
        try:
            validate_artifact(artifact, artifact_name)
            auth_material[artifact_name] = verify_authenticity(artifact=artifact, expected_issuer=issuer)
        except Exception as exc:  # fail-closed and collect all failures
            fail_reasons.append(f"{artifact_name}_authenticity_invalid:{exc}")

    record = {
        "artifact_type": "admission_authenticity_record",
        "authenticity_record_id": f"aar-{_canonical_hash([build_admission_record.get('admission_id'), normalized_execution_request.get('request_id')])[:16]}",
        "request_id": str(normalized_execution_request.get("request_id") or "unknown"),
        "trace_id": str(normalized_execution_request.get("trace_id") or "unknown"),
        "created_at": created_at,
        "produced_by": "AEXHardening",
        "verification_status": "valid" if not fail_reasons else "invalid",
        "verification_fail_reasons": fail_reasons,
        "material": auth_material,
    }
    validate_artifact(record, "admission_authenticity_record")
    return record


def build_admission_bundle(
    *,
    build_admission_record: dict[str, Any],
    normalized_execution_request: dict[str, Any],
    admission_authenticity_record: dict[str, Any],
    admission_rejection_record: dict[str, Any] | None,
    created_at: str,
) -> dict[str, Any]:
    admission_id = str(build_admission_record.get("admission_id") or "unknown")
    bundle = {
        "artifact_type": "admission_bundle",
        "bundle_id": f"ab-{_canonical_hash([admission_id, normalized_execution_request.get('request_id')])[:16]}",
        "request_id": str(normalized_execution_request.get("request_id") or "unknown"),
        "trace_id": str(normalized_execution_request.get("trace_id") or "unknown"),
        "created_at": created_at,
        "produced_by": "AEXHardening",
        "admission_artifacts": {
            "build_admission_record_ref": _artifact_ref("build_admission_record", admission_id),
            "normalized_execution_request_ref": _artifact_ref(
                "normalized_execution_request", str(normalized_execution_request.get("request_id") or "unknown")
            ),
            "admission_authenticity_record_ref": _artifact_ref(
                "admission_authenticity_record", str(admission_authenticity_record.get("authenticity_record_id") or "unknown")
            ),
            "admission_rejection_record_ref": (
                _artifact_ref("admission_rejection_record", str(admission_rejection_record.get("rejection_id") or "unknown"))
                if isinstance(admission_rejection_record, dict)
                else None
            ),
        },
        "execution_type": str(normalized_execution_request.get("execution_type") or "unknown"),
        "repo_mutation_requested": bool(normalized_execution_request.get("repo_mutation_requested")),
        "bundle_hash": f"sha256:{_canonical_hash([build_admission_record, normalized_execution_request, admission_authenticity_record, admission_rejection_record])}",
    }
    validate_artifact(bundle, "admission_bundle")
    return bundle


def evaluate_admission_bundle(
    *,
    admission_bundle: dict[str, Any],
    build_admission_record: dict[str, Any],
    normalized_execution_request: dict[str, Any],
    admission_authenticity_record: dict[str, Any],
    tlc_handoff_record: dict[str, Any] | None,
    created_at: str,
) -> dict[str, Any]:
    fail_reasons: list[str] = []

    if admission_authenticity_record.get("verification_status") != "valid":
        fail_reasons.append("authenticity_invalid")

    execution_type = str(normalized_execution_request.get("execution_type") or "unknown")
    if execution_type != str(build_admission_record.get("execution_type") or ""):
        fail_reasons.append("classification_mismatch")

    if bool(normalized_execution_request.get("repo_mutation_requested")) and execution_type != "repo_write":
        fail_reasons.append("repo_write_classifier_integrity_failure")

    lineage_status = "not_required"
    if bool(normalized_execution_request.get("repo_mutation_requested")):
        lineage_status = "ready"
        if not isinstance(tlc_handoff_record, dict):
            fail_reasons.append("lineage_incomplete")
            lineage_status = "incomplete"
        else:
            try:
                validate_repo_write_lineage(
                    build_admission_record=build_admission_record,
                    normalized_execution_request=normalized_execution_request,
                    tlc_handoff_record=tlc_handoff_record,
                    expected_trace_id=str(normalized_execution_request.get("trace_id") or ""),
                    enforce_replay_protection=False,
                )
            except (RepoWriteLineageGuardError, LineageAuthenticityError) as exc:
                fail_reasons.append(f"lineage_invalid:{exc}")
                lineage_status = "invalid"

    record = {
        "artifact_type": "admission_eval_record",
        "admission_eval_id": f"aev-{_canonical_hash([admission_bundle.get('bundle_id'), fail_reasons])[:16]}",
        "request_id": str(admission_bundle.get("request_id") or "unknown"),
        "trace_id": str(admission_bundle.get("trace_id") or "unknown"),
        "created_at": created_at,
        "produced_by": "AEXHardening",
        "evaluation_status": "pass" if not fail_reasons else "fail",
        "lineage_readiness": lineage_status,
        "fail_reasons": fail_reasons,
    }
    validate_artifact(record, "admission_eval_record")
    return record


def validate_admission_replay(
    *,
    prior_bundle: dict[str, Any],
    replay_bundle: dict[str, Any],
    prior_eval: dict[str, Any],
    replay_eval: dict[str, Any],
    created_at: str,
) -> dict[str, Any]:
    input_fp = _canonical_hash(
        {
            "request_id": prior_bundle.get("request_id"),
            "trace_id": prior_bundle.get("trace_id"),
            "execution_type": prior_bundle.get("execution_type"),
            "repo_mutation_requested": prior_bundle.get("repo_mutation_requested"),
        }
    )
    replay_fp = _canonical_hash(
        {
            "request_id": replay_bundle.get("request_id"),
            "trace_id": replay_bundle.get("trace_id"),
            "execution_type": replay_bundle.get("execution_type"),
            "repo_mutation_requested": replay_bundle.get("repo_mutation_requested"),
        }
    )

    same_output = _canonical_hash(prior_eval.get("fail_reasons", [])) == _canonical_hash(replay_eval.get("fail_reasons", []))
    replay_match = input_fp == replay_fp and same_output
    fail_reasons: list[str] = [] if replay_match else ["replay_mismatch_detected"]

    record = {
        "artifact_type": "admission_replay_validation_record",
        "replay_validation_id": f"arv-{_canonical_hash([input_fp, replay_fp, same_output])[:16]}",
        "request_id": str(prior_bundle.get("request_id") or "unknown"),
        "trace_id": str(prior_bundle.get("trace_id") or "unknown"),
        "created_at": created_at,
        "produced_by": "AEXHardening",
        "replay_match": replay_match,
        "fail_reasons": fail_reasons,
        "input_fingerprint": f"sha256:{input_fp}",
        "output_fingerprint": f"sha256:{_canonical_hash(prior_eval.get('fail_reasons', []))}",
    }
    validate_artifact(record, "admission_replay_validation_record")
    return record


def build_candidate_admission_readiness(
    *,
    admission_eval_record: dict[str, Any],
    admission_authenticity_record: dict[str, Any],
    created_at: str,
) -> dict[str, Any]:
    non_authority_assertions = [
        "does_not_replace_tlc_orchestration",
        "does_not_replace_tpa_policy_authority",
        "does_not_replace_pqx_execution",
        "does_not_replace_sel_enforcement",
        "does_not_replace_cde_closure_authority",
    ]
    fail_reasons: list[str] = []
    if admission_eval_record.get("evaluation_status") != "pass":
        fail_reasons.append("admission_eval_incomplete_or_failed")
    if admission_authenticity_record.get("verification_status") != "valid":
        fail_reasons.append("authenticity_evidence_incomplete")

    record = {
        "artifact_type": "admission_readiness_record",
        "readiness_id": f"ard-{_canonical_hash([admission_eval_record.get('admission_eval_id'), admission_authenticity_record.get('authenticity_record_id')])[:16]}",
        "request_id": str(admission_eval_record.get("request_id") or "unknown"),
        "trace_id": str(admission_eval_record.get("trace_id") or "unknown"),
        "created_at": created_at,
        "produced_by": "AEXHardening",
        "readiness_status": "candidate_only" if not fail_reasons else "blocked",
        "fail_reasons": fail_reasons,
        "non_authority_assertions": non_authority_assertions,
    }
    validate_artifact(record, "admission_readiness_record")
    return record


def detect_duplicate_or_replay_attack(
    *,
    request_id: str,
    context_digest: str,
    payload_digest: str,
) -> dict[str, Any]:
    registry: dict[str, Any] = {"seen": {}}
    if _DUPLICATE_REGISTRY.exists():
        registry = json.loads(_DUPLICATE_REGISTRY.read_text(encoding="utf-8"))
    seen = registry.setdefault("seen", {})

    key = f"{request_id}:{payload_digest}"
    prior = seen.get(key)
    signals: list[str] = []
    blocked = False
    if isinstance(prior, dict):
        if prior.get("context_digest") != context_digest:
            signals.append("duplicate_request_context_mismatch")
            blocked = True
        else:
            signals.append("duplicate_request_replay_detected")
            blocked = True

    seen[key] = {"context_digest": context_digest, "payload_digest": payload_digest}
    _DUPLICATE_REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    _DUPLICATE_REGISTRY.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")

    return {
        "blocked": blocked,
        "signals": signals,
    }


def enforce_aex_tlc_handoff_integrity(
    *,
    build_admission_record: dict[str, Any],
    normalized_execution_request: dict[str, Any],
    tlc_handoff_record: dict[str, Any],
    created_at: str,
) -> dict[str, Any]:
    fail_reasons: list[str] = []
    expected_normalized_ref = f"normalized_execution_request:{normalized_execution_request.get('request_id')}"
    if build_admission_record.get("normalized_execution_request_ref") != expected_normalized_ref:
        fail_reasons.append("normalized_ref_drift")
    if tlc_handoff_record.get("normalized_execution_request_ref") != expected_normalized_ref:
        fail_reasons.append("handoff_normalized_ref_drift")
    if tlc_handoff_record.get("request_id") != normalized_execution_request.get("request_id"):
        fail_reasons.append("handoff_request_id_drift")
    if tlc_handoff_record.get("trace_id") != normalized_execution_request.get("trace_id"):
        fail_reasons.append("handoff_trace_id_drift")

    record = {
        "artifact_type": "aex_tlc_handoff_integrity_record",
        "handoff_integrity_id": f"ath-{_canonical_hash([normalized_execution_request.get('request_id'), fail_reasons])[:16]}",
        "request_id": str(normalized_execution_request.get("request_id") or "unknown"),
        "trace_id": str(normalized_execution_request.get("trace_id") or "unknown"),
        "created_at": created_at,
        "produced_by": "AEXHardening",
        "integrity_status": "pass" if not fail_reasons else "fail",
        "fail_reasons": fail_reasons,
    }
    validate_artifact(record, "aex_tlc_handoff_integrity_record")
    return record


def track_admission_rejection_debt(*, rejection_records: list[dict[str, Any]], created_at: str) -> dict[str, Any]:
    counts = Counter()
    for row in rejection_records:
        for code in row.get("rejection_reason_codes", []):
            counts[str(code)] += 1

    repeated = sorted([code for code, count in counts.items() if count > 1])
    debt = {
        "artifact_type": "admission_rejection_debt_record",
        "debt_record_id": f"ardebt-{_canonical_hash(sorted(counts.items()))[:16]}",
        "created_at": created_at,
        "produced_by": "AEXHardening",
        "reason_code_counts": dict(sorted(counts.items())),
        "repeated_reason_codes": repeated,
        "debt_status": "elevated" if repeated else "normal",
    }
    validate_artifact(debt, "admission_rejection_debt_record")
    return debt


def verify_authenticity_rotation_and_expiry(*, authenticity: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    current = now or _utc_now()
    expires_at = datetime.fromisoformat(str(authenticity.get("expires_at", "")).replace("Z", "+00:00"))
    key_id = str(authenticity.get("key_id") or "")
    # explicit local allowlist to avoid hidden policy lookups
    allowed_key_ids = {"aex-hs256-v1", "aex-hs256-v2"}

    fail_reasons: list[str] = []
    if key_id not in allowed_key_ids:
        fail_reasons.append("authenticity_key_rotation_unknown")
    if expires_at <= current:
        fail_reasons.append("authenticity_expired")
    if expires_at - current < timedelta(seconds=60):
        fail_reasons.append("authenticity_expiry_imminent")
    return {
        "status": "valid" if not fail_reasons else "invalid",
        "fail_reasons": fail_reasons,
    }


def compute_admission_effectiveness(*, outcomes: list[dict[str, Any]], created_at: str) -> dict[str, Any]:
    total = len(outcomes)
    blocked_bad = sum(1 for row in outcomes if row.get("expected") == "reject" and row.get("actual") == "reject")
    accepted_good = sum(1 for row in outcomes if row.get("expected") == "accept" and row.get("actual") == "accept")
    false_reject = sum(1 for row in outcomes if row.get("expected") == "accept" and row.get("actual") == "reject")
    false_accept = sum(1 for row in outcomes if row.get("expected") == "reject" and row.get("actual") == "accept")

    record = {
        "artifact_type": "admission_effectiveness_record",
        "effectiveness_id": f"aef-{_canonical_hash(outcomes)[:16]}",
        "created_at": created_at,
        "produced_by": "AEXHardening",
        "total_cases": total,
        "blocked_bad_requests": blocked_bad,
        "accepted_valid_requests": accepted_good,
        "false_rejections": false_reject,
        "false_acceptances": false_accept,
        "strictness_proxy": 0.0 if total == 0 else round((blocked_bad + false_reject) / total, 4),
    }
    validate_artifact(record, "admission_effectiveness_record")
    return record


def run_boundary_redteam(*, fixtures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for fixture in fixtures:
        if fixture.get("should_fail_closed") and fixture.get("observed") != "blocked":
            findings.append({
                "fixture_id": fixture.get("fixture_id", "unknown"),
                "exploit": fixture.get("exploit", "boundary_bypass"),
                "observed": fixture.get("observed"),
                "expected": "blocked",
            })
    return findings


def run_semantic_redteam(*, fixtures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for fixture in fixtures:
        if fixture.get("semantic_drift") and fixture.get("observed") == "accepted":
            findings.append({
                "fixture_id": fixture.get("fixture_id", "unknown"),
                "exploit": "semantic_drift_acceptance",
            })
    return findings
