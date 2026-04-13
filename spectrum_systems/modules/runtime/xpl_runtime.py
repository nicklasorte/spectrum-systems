"""XPL explainability signal runtime."""
from __future__ import annotations

from typing import Any

from spectrum_systems.contracts import validate_artifact


class XPLRuntimeError(ValueError):
    pass


def create_artifact_card(*, artifact_family: str, generator: str, intended_use: str, limitations: list[str], evaluation_status: str, known_risks: list[str], created_at: str, artifact_id: str = "xpl-card-001") -> dict[str, Any]:
    if not limitations or not known_risks:
        raise XPLRuntimeError("missing_limitations_or_risks")
    card = {
        "artifact_type": "xpl_artifact_card",
        "artifact_id": artifact_id,
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": "1.3.130",
        "created_at": created_at,
        "artifact_family": artifact_family,
        "generator": generator,
        "intended_use": intended_use,
        "limitations": limitations,
        "evaluation_status": evaluation_status,
        "known_risks": known_risks,
        "non_authoritative": True,
    }
    validate_artifact(card, "xpl_artifact_card")
    return card


def create_generator_risk_record(*, generator: str, limitations: list[str], stale_status: str, uncertainty_statement: str, created_at: str, artifact_id: str = "xpl-risk-001") -> dict[str, Any]:
    if stale_status == "unknown" and not uncertainty_statement:
        raise XPLRuntimeError("missing_uncertainty_statement")
    rec = {
        "artifact_type": "xpl_generator_risk_record",
        "artifact_id": artifact_id,
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": "1.3.130",
        "created_at": created_at,
        "generator": generator,
        "risk_level": "high" if stale_status != "fresh" else "medium",
        "limitations": limitations,
        "stale_status": stale_status,
        "uncertainty_statement": uncertainty_statement,
    }
    validate_artifact(rec, "xpl_generator_risk_record")
    return rec
