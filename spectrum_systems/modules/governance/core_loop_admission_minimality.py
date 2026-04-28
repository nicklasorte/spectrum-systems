"""CL-04 / CL-06: AEX admission minimality — pure validator.

Defines the minimal admission packet that AEX must surface for any work
that mutates the repo. Non-mutating work must still declare an explicit
admission class drawn from a bounded enum. The validator does not grant
or deny admission; AEX retains canonical admission authority. The
validator simply detects:

  * missing admission_class;
  * unknown admission_class (not in the bounded set);
  * repo_mutation == True without an aex_admission_ref proof;
  * admission_class declared but trace_id / run_id missing.

Failures emit stable canonical reason codes consumed by the primary
reason policy under the ``admission`` precedence class.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Tuple

ALLOWED_ADMISSION_CLASSES: Tuple[str, ...] = (
    "repo_mutation",
    "non_mutating_query",
    "non_mutating_replay",
    "non_mutating_eval",
    "non_mutating_observability",
)
MUTATING_CLASSES: Tuple[str, ...] = ("repo_mutation",)

REQUIRED_FIELDS_ANY = ("admission_class", "trace_id", "run_id")

REASON_OK = "ADMISSION_OK"
REASON_MISSING_CLASS = "ADMISSION_CLASS_MISSING"
REASON_UNKNOWN_CLASS = "ADMISSION_CLASS_UNKNOWN"
REASON_MISSING_PROOF = "ADMISSION_REPO_MUTATION_WITHOUT_PROOF"
REASON_MISSING_FIELD = "ADMISSION_MISSING"
REASON_BYPASS_ATTEMPT = "ADMISSION_BYPASS_ATTEMPT"


class AdmissionMinimalityError(ValueError):
    """Raised only on programmer-misuse."""


def _violation(code: str, **details: Any) -> Dict[str, Any]:
    return {"reason_code": code, **details}


def validate_admission_packet(packet: Mapping[str, Any]) -> Dict[str, Any]:
    """Return ``{"ok": bool, "violations": [...], "primary_reason": str}``.

    Always returns; never raises for content errors. The first detected
    violation is the primary reason; subsequent violations are returned
    so downstream policy can preserve supporting reasons.
    """
    if not isinstance(packet, Mapping):
        raise AdmissionMinimalityError("packet must be a mapping")

    violations: List[Dict[str, Any]] = []

    admission_class = packet.get("admission_class")
    if not isinstance(admission_class, str) or not admission_class.strip():
        violations.append(_violation(REASON_MISSING_CLASS))
    elif admission_class not in ALLOWED_ADMISSION_CLASSES:
        violations.append(
            _violation(
                REASON_UNKNOWN_CLASS,
                admission_class=admission_class,
                allowed=list(ALLOWED_ADMISSION_CLASSES),
            )
        )

    for field in REQUIRED_FIELDS_ANY:
        v = packet.get(field)
        if field == "admission_class":
            continue
        if not isinstance(v, str) or not v.strip():
            violations.append(_violation(REASON_MISSING_FIELD, field=field))

    if isinstance(admission_class, str) and admission_class in MUTATING_CLASSES:
        proof = packet.get("aex_admission_ref")
        if not isinstance(proof, str) or not proof.strip():
            violations.append(_violation(REASON_MISSING_PROOF))

    primary_reason = REASON_OK
    if violations:
        primary_reason = violations[0]["reason_code"]

    return {
        "ok": not violations,
        "violations": violations,
        "primary_reason": primary_reason,
    }


def detect_admission_bypass(
    packet: Mapping[str, Any], *, downstream_stage: str
) -> Dict[str, Any]:
    """Detect a downstream stage being entered without a valid AEX packet.

    ``downstream_stage`` is the stage name that is about to consume the
    admission packet (typically ``PQX``). If the packet is missing,
    malformed, or claims repo_mutation without a proof, the call returns
    a non-OK result with reason ``ADMISSION_BYPASS_ATTEMPT`` and the
    underlying admission violation as a supporting reason.
    """
    if not isinstance(downstream_stage, str) or not downstream_stage.strip():
        raise AdmissionMinimalityError("downstream_stage must be a non-empty string")

    if not isinstance(packet, Mapping) or not packet:
        return {
            "ok": False,
            "violations": [
                _violation(
                    REASON_BYPASS_ATTEMPT,
                    downstream_stage=downstream_stage,
                    detail="missing_admission_packet",
                )
            ],
            "primary_reason": REASON_BYPASS_ATTEMPT,
        }

    inner = validate_admission_packet(packet)
    if inner["ok"]:
        return {
            "ok": True,
            "violations": [],
            "primary_reason": REASON_OK,
        }

    return {
        "ok": False,
        "violations": [
            _violation(
                REASON_BYPASS_ATTEMPT,
                downstream_stage=downstream_stage,
                supporting_reason=inner["primary_reason"],
            ),
            *inner["violations"],
        ],
        "primary_reason": REASON_BYPASS_ATTEMPT,
    }


def build_minimal_admission_packet(
    *,
    admission_class: str,
    trace_id: str,
    run_id: str,
    aex_admission_ref: str = "",
) -> Dict[str, Any]:
    """Produce a minimal valid admission packet for tests / CLIs."""
    packet: Dict[str, Any] = {
        "admission_class": admission_class,
        "trace_id": trace_id,
        "run_id": run_id,
    }
    if aex_admission_ref:
        packet["aex_admission_ref"] = aex_admission_ref
    return packet


__all__ = [
    "ALLOWED_ADMISSION_CLASSES",
    "MUTATING_CLASSES",
    "AdmissionMinimalityError",
    "REASON_OK",
    "REASON_MISSING_CLASS",
    "REASON_UNKNOWN_CLASS",
    "REASON_MISSING_PROOF",
    "REASON_MISSING_FIELD",
    "REASON_BYPASS_ATTEMPT",
    "validate_admission_packet",
    "detect_admission_bypass",
    "build_minimal_admission_packet",
]
