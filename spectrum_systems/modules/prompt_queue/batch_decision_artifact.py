"""BRF batch decision artifact builder and validator."""

from __future__ import annotations

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema
from spectrum_systems.modules.prompt_queue.queue_models import iso_now, utc_now


class BatchDecisionArtifactError(ValueError):
    """Raised when governed BRF decision artifact generation fails closed."""


def validate_batch_decision_artifact(artifact: dict) -> None:
    if not isinstance(artifact, dict):
        raise BatchDecisionArtifactError("batch decision artifact must be an object")

    schema = load_schema("batch_decision_artifact")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(artifact), key=lambda error: str(error.path))
    if errors:
        raise BatchDecisionArtifactError("; ".join(error.message for error in errors))


_ALLOWED_DECISIONS = {
    "allow": ("SAFE_TO_MOVE_ON", "ADVANCE"),
    "warn": ("MOVE_ON_AFTER_ONE_FIX_BATCH", "FIX"),
    "block": ("DO_NOT_MOVE_ON", "STOP"),
}


def build_batch_decision_artifact(*, step_decision: dict, clock=utc_now) -> dict:
    if not isinstance(step_decision, dict):
        raise BatchDecisionArtifactError("step_decision is required")

    decision = step_decision.get("decision")
    if decision not in _ALLOWED_DECISIONS:
        raise BatchDecisionArtifactError("unsupported step decision for batch decision artifact")

    validation_refs = step_decision.get("validation_result_refs")
    if not isinstance(validation_refs, list) or not validation_refs:
        raise BatchDecisionArtifactError("validation_result_refs required before decision emission")
    if any(not isinstance(ref, str) or not ref.startswith("validation_result_record:") for ref in validation_refs):
        raise BatchDecisionArtifactError("validation_result_refs must reference validation_result_record artifacts")

    review_ref = step_decision.get("review_evidence_ref")
    if not isinstance(review_ref, str) or not review_ref:
        raise BatchDecisionArtifactError("review evidence required before decision emission")
    if not review_ref.startswith("review_result_artifact:"):
        raise BatchDecisionArtifactError("review evidence must reference review_result_artifact")

    preflight = step_decision.get("preflight_decision")
    if preflight != "ALLOW":
        raise BatchDecisionArtifactError("preflight must be ALLOW before decision emission")

    decision_status, next_action = _ALLOWED_DECISIONS[decision]
    emitted_at = iso_now(clock)

    reason_codes = step_decision.get("reason_codes") or ["decision_emitted"]
    artifact = {
        "artifact_type": "batch_decision_artifact",
        "batch_id": f"{step_decision.get('queue_id') or step_decision.get('trace_linkage')}:{step_decision.get('step_id')}",
        "decision_status": decision_status,
        "decision_reason": ",".join(reason_codes),
        "decision_owner": "TLC",
        "next_action": next_action,
        "supporting_refs": [*validation_refs, review_ref, step_decision.get("decision_id", "unknown")],
        "emitted_at": emitted_at,
    }
    validate_batch_decision_artifact(artifact)
    return artifact
