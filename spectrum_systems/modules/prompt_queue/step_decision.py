"""Deterministic fail-closed step decision builder for parsed queue findings."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema
from spectrum_systems.modules.prompt_queue.queue_models import iso_now, utc_now

DECISION_GENERATOR_VERSION = "prompt_queue_step_decision.v1"
_ALLOWED_DECISIONS = {"allow", "warn", "block"}


class StepDecisionError(ValueError):
    """Raised when step decision generation or validation fails."""


def validate_step_decision_artifact(artifact: dict) -> None:
    if not isinstance(artifact, dict):
        raise StepDecisionError("Step decision artifact must be an object.")
    schema = load_schema("prompt_queue_step_decision")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(artifact), key=lambda error: str(error.path))
    if errors:
        raise StepDecisionError("; ".join(error.message for error in errors))


def default_step_decision_path(*, step_id: str, root_dir: Path) -> Path:
    return root_dir / "artifacts" / "prompt_queue" / "step_decisions" / f"{step_id}.step_decision.json"


def _decision_id(step_id: str, generated_at: str) -> str:
    stamp = generated_at.replace("-", "").replace(":", "")
    return f"step-decision-{step_id}-{stamp}"


def build_step_decision(findings: dict, *, clock: Callable = utc_now) -> dict:
    if not isinstance(findings, dict):
        raise StepDecisionError("Findings must be an object.")

    required = (
        "step_id",
        "queue_id",
        "trace_linkage",
        "source_execution_result_artifact_id",
        "validation_status",
        "findings",
        "severity_summary",
        "validation_result_refs",
        "review_evidence_ref",
        "preflight_decision",
    )
    missing = [field for field in required if field not in findings]
    if missing:
        raise StepDecisionError(f"Findings missing required fields: {', '.join(missing)}")

    if findings["validation_status"] != "valid":
        decision = "block"
        reason_codes = ["invalid_report"]
    elif findings.get("preflight_decision") != "ALLOW":
        decision = "block"
        reason_codes = ["invalid_report"]
    elif not findings.get("validation_result_refs"):
        decision = "block"
        reason_codes = ["invalid_report"]
    elif not findings.get("review_evidence_ref"):
        decision = "block"
        reason_codes = ["invalid_report"]
    else:
        severities = findings["severity_summary"]
        if severities.get("error", 0) > 0:
            decision = "block"
            reason_codes = ["errors_detected"]
        elif severities.get("ambiguous", 0) > 0:
            decision = "block"
            reason_codes = ["ambiguity_detected"]
        elif severities.get("warning", 0) > 0:
            decision = "warn"
            reason_codes = ["warnings_detected"]
        elif severities.get("info", 0) >= 0:
            decision = "allow"
            reason_codes = ["clean_findings"]
        else:
            raise StepDecisionError("Unable to derive decision from findings severity_summary.")

    if decision not in _ALLOWED_DECISIONS:
        raise StepDecisionError("Unsupported decision generated.")

    blocking_reasons: list[str] = []
    if decision == "block":
        blocking_reasons = sorted(
            {
                finding.get("finding_type", "validation")
                for finding in findings["findings"]
                if finding.get("severity") in {"error", "ambiguous"}
            }
        )
        if not blocking_reasons:
            blocking_reasons = ["fail_closed"]

    generated_at = iso_now(clock)
    artifact = {
        "decision_id": _decision_id(findings["step_id"], generated_at),
        "step_id": findings["step_id"],
        "queue_id": findings.get("queue_id"),
        "trace_linkage": findings.get("trace_linkage"),
        "decision": decision,
        "reason_codes": reason_codes,
        "blocking_reasons": blocking_reasons,
        "derived_from_artifacts": [
            findings["source_execution_result_artifact_id"],
            findings["review_evidence_ref"],
            *list(findings["validation_result_refs"]),
        ],
        "review_evidence_ref": findings["review_evidence_ref"],
        "validation_result_refs": list(findings["validation_result_refs"]),
        "preflight_decision": findings["preflight_decision"],
        "timestamp": generated_at,
        "generator_version": DECISION_GENERATOR_VERSION,
    }
    validate_step_decision_artifact(artifact)
    return artifact
