"""AEX SEL admission signal emitter.

AEX is admission-only. SEL owns enforcement. This module emits an
``admission_policy_observation`` that SEL/ENF and POL can consume as
*input* to their own enforcement / policy decisions. AEX never invokes
SEL, never blocks, and never asserts enforcement authority.

The module path intentionally contains the ``sel_`` token so the TLS-03
trust-gap detector can observe the AEX→SEL signal surface as evidence
under AEX. No SEL code is executed here.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Mapping

from spectrum_systems.contracts import validate_artifact


_NON_AUTHORITY_ASSERTIONS_REQUIRED: tuple[str, ...] = (
    "aex_does_not_own_enforcement_authority",
    "aex_does_not_own_promotion_authority",
    "aex_does_not_own_certification_authority",
    "aex_does_not_own_control_decision_authority",
    "aex_does_not_own_governance_readiness_authority",
)


def _utc(now: datetime | None = None) -> str:
    return (now or datetime.now(tz=timezone.utc)).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _hash16(parts: list[str]) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


def _hash64(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_sel_admission_input(
    *,
    admission_outcome: str,
    request_id: str,
    trace_id: str,
    run_id: str,
    source_request_ref: str,
    admission_artifact_ref: str,
    normalized_execution_request_ref: str,
    reason_codes: list[str],
    consumer_systems: list[str] | None = None,
    policy_refs: list[str] | None = None,
    evidence_refs: list[str] | None = None,
    input_hash: str,
    output_hash: str,
    replay_command_ref: str,
    created_at: str | None = None,
    produced_by: str = "AEXSelAdmissionSignal",
) -> dict[str, Any]:
    """Emit a contract-valid admission_policy_observation.

    The observation enumerates downstream consumers (default: SEL, ENF, POL)
    and the AEX non-authority assertions. SEL/ENF read the observation as
    enforcement *input*; AEX does not enforce.
    """
    if admission_outcome not in {"admitted", "rejected", "indeterminate"}:
        raise ValueError("admission_outcome must be admitted|rejected|indeterminate")
    if not reason_codes:
        raise ValueError("reason_codes must be non-empty (admission decisions must explain themselves)")

    consumers = list(consumer_systems or ["SEL", "ENF", "POL"])
    # SEL must always be present in the consumer set so the enforcement
    # signal surface exists.
    if "SEL" not in consumers:
        consumers.insert(0, "SEL")

    record = {
        "artifact_type": "admission_policy_observation",
        "schema_version": "1.0.0",
        "observation_id": f"apo-{_hash16([request_id, trace_id, 'observation'])}",
        "request_id": request_id,
        "trace_id": trace_id,
        "run_id": run_id,
        "created_at": created_at or _utc(),
        "produced_by": produced_by,
        "producer_authority": "AEX",
        "admission_outcome": admission_outcome,
        "reason_codes": list(reason_codes),
        "input_refs": [source_request_ref],
        "output_refs": [admission_artifact_ref, normalized_execution_request_ref],
        "downstream_refs": {
            "consumer_systems": consumers,
            "handoff_refs": [
                f"sel_enforcement_input:{admission_artifact_ref}",
                f"policy_observation_inbox:{admission_artifact_ref}",
            ],
        },
        "evidence_refs": list(evidence_refs or []),
        "replay_refs": {
            "input_hash": input_hash,
            "output_hash": output_hash,
            "replay_command_ref": replay_command_ref,
        },
        "policy_refs": list(policy_refs or ["policy_registry_record:aex_admission_policy_v1"]),
        "non_authority_assertions": list(_NON_AUTHORITY_ASSERTIONS_REQUIRED),
    }
    validate_artifact(record, "admission_policy_observation")
    return record


def assert_no_enforcement_authority_claim(observation: Mapping[str, Any]) -> None:
    """Fail-closed check: AEX must declare non-authority over enforcement.

    SEL/ENF consumers SHOULD invoke this assertion before treating the
    observation as enforcement input.
    """
    assertions = list(observation.get("non_authority_assertions") or [])
    missing = [a for a in _NON_AUTHORITY_ASSERTIONS_REQUIRED if a not in assertions]
    if missing:
        raise ValueError(
            "admission_policy_observation missing required non-authority assertions: "
            + ", ".join(missing)
        )
    if observation.get("producer_authority") != "AEX":
        raise ValueError("admission_policy_observation producer_authority must be 'AEX'")
    consumers = (observation.get("downstream_refs") or {}).get("consumer_systems") or []
    if "SEL" not in consumers:
        raise ValueError("admission_policy_observation must surface SEL as a consumer")


__all__ = [
    "build_sel_admission_input",
    "assert_no_enforcement_authority_claim",
]
