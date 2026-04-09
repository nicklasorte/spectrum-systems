"""Deterministic authenticity helpers for repo-write lineage artifacts."""

from __future__ import annotations

import hashlib
import hmac
import os
from typing import Any

from spectrum_systems.utils.deterministic_id import canonical_json

DEFAULT_KEY_ID = "local-system-v1"
DEFAULT_SHARED_SECRET = "spectrum-lineage-auth-secret-v1"


def _lineage_secret() -> str:
    return str(os.environ.get("SPECTRUM_LINEAGE_AUTH_SECRET") or DEFAULT_SHARED_SECRET)


def _lineage_key_id() -> str:
    return str(os.environ.get("SPECTRUM_LINEAGE_AUTH_KEY_ID") or DEFAULT_KEY_ID)


def _canonical_payload(artifact: dict[str, Any]) -> dict[str, Any]:
    payload = dict(artifact)
    payload.pop("authenticity", None)
    return payload


def compute_payload_digest(artifact: dict[str, Any]) -> str:
    digest = hashlib.sha256(canonical_json(_canonical_payload(artifact)).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _compute_attestation(*, issuer: str, key_id: str, payload_digest: str, secret: str) -> str:
    message = f"{issuer}|{key_id}|{payload_digest}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def issue_authenticity(*, artifact: dict[str, Any], issuer: str) -> dict[str, str]:
    key_id = _lineage_key_id()
    payload_digest = compute_payload_digest(artifact)
    return {
        "issuer": issuer,
        "key_id": key_id,
        "payload_digest": payload_digest,
        "attestation": _compute_attestation(
            issuer=issuer,
            key_id=key_id,
            payload_digest=payload_digest,
            secret=_lineage_secret(),
        ),
    }


def verify_authenticity(*, artifact: dict[str, Any], expected_issuer: str) -> None:
    authenticity = artifact.get("authenticity")
    if not isinstance(authenticity, dict):
        raise ValueError("authenticity_required")

    issuer = authenticity.get("issuer")
    if issuer != expected_issuer:
        raise ValueError("authenticity_issuer_mismatch")

    key_id = authenticity.get("key_id")
    if not isinstance(key_id, str) or not key_id.strip():
        raise ValueError("authenticity_key_id_required")

    payload_digest = authenticity.get("payload_digest")
    if not isinstance(payload_digest, str) or not payload_digest.strip():
        raise ValueError("authenticity_payload_digest_required")

    expected_payload_digest = compute_payload_digest(artifact)
    if payload_digest != expected_payload_digest:
        raise ValueError("authenticity_payload_digest_mismatch")

    attestation = authenticity.get("attestation")
    if not isinstance(attestation, str) or not attestation.strip():
        raise ValueError("authenticity_attestation_required")

    expected_attestation = _compute_attestation(
        issuer=issuer,
        key_id=key_id,
        payload_digest=payload_digest,
        secret=_lineage_secret(),
    )
    if not hmac.compare_digest(attestation, expected_attestation):
        raise ValueError("authenticity_attestation_mismatch")
