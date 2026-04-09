"""Deterministic authenticity helpers for repo-write lineage artifacts."""

from __future__ import annotations

import hashlib
import hmac
import inspect
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from spectrum_systems.utils.deterministic_id import canonical_json
from spectrum_systems.modules.runtime.lineage_issuance_registry import record_authoritative_lineage_issuance

AUDIENCE_REPO_WRITE_BOUNDARY = "pqx_repo_write_boundary"
ISSUER_DEFAULT_KEY_IDS = {
    "AEX": "aex-hs256-v1",
    "TLC": "tlc-hs256-v1",
    "TPA": "tpa-hs256-v1",
}
_ISSUER_SECRET_ENV = {
    "AEX": "SPECTRUM_LINEAGE_AUTH_SECRET_AEX",
    "TLC": "SPECTRUM_LINEAGE_AUTH_SECRET_TLC",
    "TPA": "SPECTRUM_LINEAGE_AUTH_SECRET_TPA",
}
_ISSUER_KEY_ENV = {
    "AEX": "SPECTRUM_LINEAGE_AUTH_KEY_ID_AEX",
    "TLC": "SPECTRUM_LINEAGE_AUTH_KEY_ID_TLC",
    "TPA": "SPECTRUM_LINEAGE_AUTH_KEY_ID_TPA",
}


class LineageAuthenticityError(ValueError):
    """Raised when lineage authenticity material is missing or invalid."""


def _utc_now() -> datetime:
    return datetime.now(tz=timezone.utc).replace(microsecond=0)


def _format_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text).astimezone(timezone.utc)


def _require_issuer(issuer: str) -> str:
    normalized = str(issuer or "").strip()
    if normalized not in ISSUER_DEFAULT_KEY_IDS:
        raise LineageAuthenticityError(f"authenticity_unknown_issuer:{normalized or 'missing'}")
    return normalized


def _issuer_secret(issuer: str) -> str:
    required_issuer = _require_issuer(issuer)
    env_name = _ISSUER_SECRET_ENV[required_issuer]
    secret = os.environ.get(env_name)
    if not isinstance(secret, str) or not secret.strip():
        raise LineageAuthenticityError(f"authenticity_secret_missing_for_issuer:{required_issuer}")
    return secret.strip()


def _issuer_key_id(issuer: str) -> str:
    required_issuer = _require_issuer(issuer)
    configured = os.environ.get(_ISSUER_KEY_ENV[required_issuer])
    if isinstance(configured, str) and configured.strip():
        return configured.strip()
    return ISSUER_DEFAULT_KEY_IDS[required_issuer]


def _canonical_payload(artifact: dict[str, Any]) -> dict[str, Any]:
    payload = dict(artifact)
    payload.pop("authenticity", None)
    return payload


_AUTHORIZED_ISSUANCE_CALLERS: dict[tuple[str, str], set[str]] = {
    ("AEX", "normalized_execution_request"): {
        "spectrum_systems.aex.engine:AEXEngine.admit_codex_request",
    },
    ("AEX", "build_admission_record"): {
        "spectrum_systems.aex.engine:AEXEngine.admit_codex_request",
    },
    ("TLC", "tlc_handoff_record"): {
        "spectrum_systems.modules.runtime.top_level_conductor:_build_tlc_handoff_record",
        "spectrum_systems.modules.runtime.github_pr_autofix_review_artifact_validation:_build_tlc_handoff",
    },
    ("TPA", "tpa_slice_artifact"): {
        "spectrum_systems.modules.runtime.pqx_sequence_runner:_build_tpa_slice_artifact",
        "spectrum_systems.modules.runtime.github_pr_autofix_review_artifact_validation:_build_tpa_gate_artifact",
    },
}


def _auth_scope(artifact: dict[str, Any]) -> str:
    artifact_type = str(artifact.get("artifact_type") or "unknown")
    request_id = str(artifact.get("request_id") or "missing")
    trace_id = str(artifact.get("trace_id") or "missing")
    return f"repo_write_lineage:{artifact_type}:{request_id}:{trace_id}"


def compute_payload_digest(artifact: dict[str, Any]) -> str:
    digest = hashlib.sha256(canonical_json(_canonical_payload(artifact)).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _lineage_token_id() -> str:
    return f"lin-{uuid.uuid4().hex[:24]}"


def _compute_attestation(
    *,
    issuer: str,
    key_id: str,
    payload_digest: str,
    audience: str,
    scope: str,
    issued_at: str,
    expires_at: str,
    lineage_token_id: str,
    secret: str,
) -> str:
    message = f"{issuer}|{key_id}|{payload_digest}|{audience}|{scope}|{issued_at}|{expires_at}|{lineage_token_id}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def _caller_identity(frame_info: inspect.FrameInfo) -> str:
    module_name = frame_info.frame.f_globals.get("__name__", "<unknown>")
    function_name = frame_info.function
    if "self" in frame_info.frame.f_locals:
        owner = frame_info.frame.f_locals["self"].__class__.__name__
        function_name = f"{owner}.{function_name}"
    return f"{module_name}:{function_name}"


def _enforce_boundary_issuance_authority(*, artifact: dict[str, Any], issuer: str) -> None:
    artifact_type = str(artifact.get("artifact_type") or "").strip()
    if not artifact_type:
        raise LineageAuthenticityError("authenticity_artifact_type_required")
    allowed_callers = _AUTHORIZED_ISSUANCE_CALLERS.get((issuer, artifact_type))
    if not allowed_callers:
        raise LineageAuthenticityError(f"authenticity_issuer_artifact_type_unissuable:{issuer}:{artifact_type}")

    call_stack = inspect.stack(context=0)
    try:
        observed_callers = {_caller_identity(frame_info) for frame_info in call_stack[2:10]}
    finally:
        del call_stack
    if observed_callers.isdisjoint(allowed_callers):
        raise LineageAuthenticityError(
            f"authenticity_boundary_issuer_forbidden:{issuer}:{artifact_type}"
        )


def issue_authenticity(*, artifact: dict[str, Any], issuer: str) -> dict[str, str]:
    required_issuer = _require_issuer(issuer)
    _enforce_boundary_issuance_authority(artifact=artifact, issuer=required_issuer)
    key_id = _issuer_key_id(required_issuer)
    payload_digest = compute_payload_digest(artifact)
    audience = AUDIENCE_REPO_WRITE_BOUNDARY
    scope = _auth_scope(artifact)
    issued_at_dt = _utc_now()
    ttl_seconds = int(os.environ.get("SPECTRUM_LINEAGE_AUTH_TTL_SECONDS") or "900")
    if ttl_seconds <= 0:
        raise LineageAuthenticityError("authenticity_ttl_invalid")
    issued_at = _format_timestamp(issued_at_dt)
    expires_at = _format_timestamp(issued_at_dt + timedelta(seconds=ttl_seconds))
    lineage_token_id = _lineage_token_id()
    authenticity = {
        "issuer": required_issuer,
        "key_id": key_id,
        "payload_digest": payload_digest,
        "audience": audience,
        "scope": scope,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "lineage_token_id": lineage_token_id,
        "attestation": _compute_attestation(
            issuer=required_issuer,
            key_id=key_id,
            payload_digest=payload_digest,
            audience=audience,
            scope=scope,
            issued_at=issued_at,
            expires_at=expires_at,
            lineage_token_id=lineage_token_id,
            secret=_issuer_secret(required_issuer),
        ),
    }
    record_authoritative_lineage_issuance(
        artifact=artifact,
        issuer=required_issuer,
        key_id=authenticity["key_id"],
        payload_digest=authenticity["payload_digest"],
        issued_at=authenticity["issued_at"],
    )
    return authenticity


def verify_authenticity(*, artifact: dict[str, Any], expected_issuer: str) -> dict[str, str]:
    authenticity = artifact.get("authenticity")
    if not isinstance(authenticity, dict):
        raise LineageAuthenticityError("authenticity_required")

    issuer = _require_issuer(str(authenticity.get("issuer") or ""))
    if issuer != expected_issuer:
        raise LineageAuthenticityError("authenticity_issuer_mismatch")

    key_id = authenticity.get("key_id")
    if not isinstance(key_id, str) or not key_id.strip():
        raise LineageAuthenticityError("authenticity_key_id_required")
    expected_key_id = _issuer_key_id(issuer)
    if key_id.strip() != expected_key_id:
        raise LineageAuthenticityError("authenticity_issuer_key_binding_mismatch")

    payload_digest = authenticity.get("payload_digest")
    if not isinstance(payload_digest, str) or not payload_digest.strip():
        raise LineageAuthenticityError("authenticity_payload_digest_required")

    expected_payload_digest = compute_payload_digest(artifact)
    if payload_digest != expected_payload_digest:
        raise LineageAuthenticityError("authenticity_payload_digest_mismatch")

    audience = authenticity.get("audience")
    if audience != AUDIENCE_REPO_WRITE_BOUNDARY:
        raise LineageAuthenticityError("authenticity_audience_invalid")

    scope = authenticity.get("scope")
    if not isinstance(scope, str) or not scope.strip():
        raise LineageAuthenticityError("authenticity_scope_required")
    expected_scope = _auth_scope(artifact)
    if scope != expected_scope:
        raise LineageAuthenticityError("authenticity_scope_mismatch")

    issued_at = authenticity.get("issued_at")
    expires_at = authenticity.get("expires_at")
    if not isinstance(issued_at, str) or not issued_at.strip():
        raise LineageAuthenticityError("authenticity_issued_at_required")
    if not isinstance(expires_at, str) or not expires_at.strip():
        raise LineageAuthenticityError("authenticity_expires_at_required")

    try:
        issued_at_dt = _parse_timestamp(issued_at)
        expires_at_dt = _parse_timestamp(expires_at)
    except ValueError as exc:
        raise LineageAuthenticityError("authenticity_timestamp_invalid") from exc

    if issued_at_dt >= expires_at_dt:
        raise LineageAuthenticityError("authenticity_expiry_order_invalid")

    now = _utc_now()
    if now > expires_at_dt:
        raise LineageAuthenticityError("authenticity_expired")
    if issued_at_dt > now + timedelta(seconds=5):
        raise LineageAuthenticityError("authenticity_issued_in_future")

    max_age_seconds = int(os.environ.get("SPECTRUM_LINEAGE_AUTH_MAX_AGE_SECONDS") or "3600")
    if max_age_seconds <= 0:
        raise LineageAuthenticityError("authenticity_max_age_invalid")
    if now - issued_at_dt > timedelta(seconds=max_age_seconds):
        raise LineageAuthenticityError("authenticity_stale")

    lineage_token_id = authenticity.get("lineage_token_id")
    if not isinstance(lineage_token_id, str) or not lineage_token_id.strip():
        raise LineageAuthenticityError("authenticity_lineage_token_id_required")
    attestation = authenticity.get("attestation")
    if not isinstance(attestation, str) or not attestation.strip():
        raise LineageAuthenticityError("authenticity_attestation_required")

    expected_attestation = _compute_attestation(
        issuer=issuer,
        key_id=expected_key_id,
        payload_digest=payload_digest,
        audience=audience,
        scope=expected_scope,
        issued_at=issued_at,
        expires_at=expires_at,
        lineage_token_id=lineage_token_id,
        secret=_issuer_secret(issuer),
    )
    if not hmac.compare_digest(attestation, expected_attestation):
        raise LineageAuthenticityError("authenticity_attestation_mismatch")

    return {
        "issuer": issuer,
        "key_id": expected_key_id,
        "payload_digest": payload_digest,
        "lineage_token_id": lineage_token_id,
        "scope": expected_scope,
        "audience": audience,
        "issued_at": issued_at,
    }
