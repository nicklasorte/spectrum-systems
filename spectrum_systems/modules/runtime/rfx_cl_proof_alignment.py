"""RFX-N16 — RFX ↔ CL proof alignment check.

Verifies that the RFX proof shape matches the core loop (CL) proof shape
declared in system artifacts. When the shapes diverge, downstream consumers
of the proof (EVL, TPA, CDE) may interpret the evidence incorrectly.

This module is a non-owning phase-label support helper. It does not own
the proof schema or control-loop authority — CDE, EVL, and TPA own those as
declared in ``docs/architecture/system_registry.md``. This check emits
alignment findings as inputs to those systems.

Failure prevented: RFX proof artifacts diverging from the CL proof shape,
causing silent misalignment when consumed by downstream systems.

Signal improved: RFX↔CL proof shape alignment rate; field-presence coverage.

Reason codes:
  rfx_cl_proof_missing_rfx_field    — RFX proof is missing a required CL field
  rfx_cl_proof_type_mismatch        — shared field has incompatible types in RFX vs CL
  rfx_cl_proof_empty_rfx            — RFX proof payload is empty or absent
  rfx_cl_proof_empty_cl             — CL proof schema is empty or absent
  rfx_cl_proof_extra_authority_field — RFX proof contains an authority-claiming field not in CL
"""

from __future__ import annotations

from typing import Any

# Fields that signal an authority claim; RFX must not add these unilaterally.
_AUTHORITY_FIELD_PREFIXES: tuple[str, ...] = (
    "decision_",
    "enforcement_",
    "certification_",
    "promotion_",
    "approval_",
)


def _is_authority_field(field: str) -> bool:
    return any(field.lower().startswith(p) for p in _AUTHORITY_FIELD_PREFIXES)


def check_rfx_cl_proof_alignment(
    *,
    rfx_proof: dict[str, Any] | None,
    cl_proof_schema: dict[str, Any] | None,
) -> dict[str, Any]:
    """Compare an RFX proof payload against the CL proof schema.

    ``cl_proof_schema`` is a dict mapping field names to expected Python types
    (as type names: ``"str"``, ``"int"``, ``"float"``, ``"bool"``, ``"dict"``,
    ``"list"``, ``"any"``).
    """
    reason: list[str] = []
    missing_fields: list[str] = []
    mismatched_fields: list[str] = []
    extra_authority_fields: list[str] = []

    if not rfx_proof:
        reason.append("rfx_cl_proof_empty_rfx")
    if not cl_proof_schema:
        reason.append("rfx_cl_proof_empty_cl")

    if not rfx_proof or not cl_proof_schema:
        return {
            "artifact_type": "rfx_cl_proof_alignment_result",
            "schema_version": "1.0.0",
            "missing_fields": missing_fields,
            "mismatched_fields": mismatched_fields,
            "extra_authority_fields": extra_authority_fields,
            "reason_codes_emitted": sorted(set(reason)),
            "status": "misaligned",
            "signals": {
                "required_field_count": 0,
                "present_field_count": 0,
                "alignment_rate": 0.0,
            },
        }

    _TYPE_MAP: dict[str, type] = {
        "str": str, "int": int, "float": float,
        "bool": bool, "dict": dict, "list": list,
    }

    present_count = 0
    for field, expected_type_name in cl_proof_schema.items():
        if field not in rfx_proof:
            reason.append("rfx_cl_proof_missing_rfx_field")
            missing_fields.append(field)
        else:
            present_count += 1
            if expected_type_name != "any":
                expected_type = _TYPE_MAP.get(expected_type_name)
                if expected_type and not isinstance(rfx_proof[field], expected_type):
                    reason.append("rfx_cl_proof_type_mismatch")
                    mismatched_fields.append(field)

    # Check for authority-claiming fields added by RFX but not in CL schema.
    for field in rfx_proof:
        if field not in cl_proof_schema and _is_authority_field(field):
            reason.append("rfx_cl_proof_extra_authority_field")
            extra_authority_fields.append(field)

    total = len(cl_proof_schema)
    unique_reasons = sorted(set(reason))
    return {
        "artifact_type": "rfx_cl_proof_alignment_result",
        "schema_version": "1.0.0",
        "missing_fields": missing_fields,
        "mismatched_fields": mismatched_fields,
        "extra_authority_fields": extra_authority_fields,
        "reason_codes_emitted": unique_reasons,
        "status": "aligned" if not unique_reasons else "misaligned",
        "signals": {
            "required_field_count": total,
            "present_field_count": present_count,
            "alignment_rate": present_count / max(total, 1),
        },
    }
