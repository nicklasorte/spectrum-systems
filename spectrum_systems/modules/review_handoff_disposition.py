"""Thin control/scheduling disposition integration for unresolved review operator handoff artifacts."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema

DISPOSITION_FILE_SUFFIX = "_review_handoff_disposition_artifact.json"


class ReviewHandoffDispositionError(ValueError):
    """Raised when handoff disposition cannot be classified safely."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _validate(instance: dict[str, Any], schema_name: str) -> None:
    schema = load_schema(schema_name)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda error: str(error.path))
    if errors:
        raise ReviewHandoffDispositionError("; ".join(error.message for error in errors))


def validate_review_operator_handoff_artifact(handoff_artifact: dict[str, Any]) -> None:
    _validate(handoff_artifact, "review_operator_handoff_artifact")


def validate_review_handoff_disposition_artifact(disposition_artifact: dict[str, Any]) -> None:
    _validate(disposition_artifact, "review_handoff_disposition_artifact")


def _classify_disposition(handoff_artifact: Mapping[str, Any]) -> tuple[str, str, str, bool, bool, str | None]:
    handoff_reason = handoff_artifact["handoff_reason"]
    verdict = handoff_artifact["post_cycle_verdict"]

    if handoff_reason == "checkpoint_required":
        return (
            "request_checkpoint_decision",
            "checkpoint_missing",
            "checkpoint_decision_required",
            True,
            False,
            "CDE",
        )
    if handoff_reason == "tpa_blocked":
        return ("manual_review_required", "tpa_blocked", "not_permitted", True, False, "SEL")
    if handoff_reason == "execution_failed":
        return ("hold_pending_input", "execution_failed", "not_permitted", True, False, "FRE")
    if handoff_reason == "policy_blocked":
        return ("hold_pending_input", "policy_blocked", "not_permitted", True, False, "SEL")
    if handoff_reason == "unresolved_high_risk_findings":
        return (
            "escalate_to_owner",
            "high_risk_findings_present",
            "not_permitted",
            True,
            False,
            "CDE",
        )

    if verdict == "fix_required" or handoff_reason == "post_cycle_fix_still_required":
        return (
            "schedule_follow_on_cycle",
            "unresolved_fix_required",
            "permitted_with_explicit_operator_action",
            True,
            True,
            None,
        )
    if verdict == "not_safe_to_merge" or handoff_reason == "post_cycle_not_safe_to_merge":
        return ("escalate_to_owner", "not_safe_to_merge", "not_permitted", True, False, "CDE")

    if handoff_reason == "review_incomplete":
        if verdict is not None:
            raise ReviewHandoffDispositionError(
                f"ambiguous handoff disposition for handoff_reason={handoff_reason!r} verdict={verdict!r}"
            )
        return ("manual_review_required", "missing_prerequisite", "not_permitted", True, False, "RQX")

    raise ReviewHandoffDispositionError(f"ambiguous handoff disposition for handoff_reason={handoff_reason!r}")


def build_review_handoff_disposition_artifact(
    handoff_artifact: dict[str, Any],
    *,
    emitted_at: str | None = None,
) -> dict[str, Any]:
    validate_review_operator_handoff_artifact(handoff_artifact)

    disposition, reason_code, permitted_follow_on, required_human_action, scheduling_eligible, escalation_owner_ref = (
        _classify_disposition(handoff_artifact)
    )
    emitted = emitted_at or _utc_now()

    source_handoff_ref = f"review_operator_handoff_artifact:{handoff_artifact['handoff_id']}"
    disposition_artifact = {
        "artifact_type": "review_handoff_disposition_artifact",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": "1.0.0",
        "disposition_id": f"rhda:{handoff_artifact['handoff_id']}",
        "source_handoff_ref": source_handoff_ref,
        "source_review_fix_execution_result_ref": handoff_artifact["source_review_fix_execution_result_ref"],
        "source_review_result_ref": handoff_artifact["source_review_result_ref"],
        "source_review_id": handoff_artifact["review_id"],
        "disposition": disposition,
        "permitted_follow_on": permitted_follow_on,
        "required_human_action": required_human_action,
        "scheduling_eligible": scheduling_eligible,
        "escalation_owner_ref": escalation_owner_ref,
        "reason_code": reason_code,
        "rationale": (
            f"Disposition {disposition} classified from handoff_reason={handoff_artifact['handoff_reason']} "
            f"and post_cycle_verdict={handoff_artifact['post_cycle_verdict']}."
        ),
        "provenance": {
            "classified_by_system": "TLC",
            "execution_triggered": False,
            "rqx_cycle_reentry_triggered": False,
            "closure_authority_transferred": False,
        },
        "trace_linkage": {
            "handoff_id": handoff_artifact["handoff_id"],
            "request_ref": handoff_artifact["trace_linkage"]["request_ref"],
            "fix_slice_ref": handoff_artifact["trace_linkage"]["fix_slice_ref"],
            "tpa_artifact_ref": handoff_artifact["trace_linkage"]["tpa_artifact_ref"],
            "pqx_execution_ref": handoff_artifact["trace_linkage"]["pqx_execution_ref"],
        },
        "emitted_at": emitted,
    }
    validate_review_handoff_disposition_artifact(disposition_artifact)
    return disposition_artifact


def emit_review_handoff_disposition(
    handoff_artifact: dict[str, Any],
    *,
    output_dir: Path,
    emitted_at: str | None = None,
) -> dict[str, Any]:
    disposition_artifact = build_review_handoff_disposition_artifact(handoff_artifact, emitted_at=emitted_at)

    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = output_dir / f"{handoff_artifact['review_id']}{DISPOSITION_FILE_SUFFIX}"
    if artifact_path.exists():
        raise ReviewHandoffDispositionError(
            f"disposition artifact already exists for review_id={handoff_artifact['review_id']} at {artifact_path}"
        )

    artifact_path.write_text(json.dumps(disposition_artifact, indent=2) + "\n", encoding="utf-8")
    return {
        "review_handoff_disposition_artifact": disposition_artifact,
        "review_handoff_disposition_artifact_path": str(artifact_path),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Classify one review_operator_handoff_artifact into a bounded review_handoff_disposition_artifact."
    )
    parser.add_argument("--handoff", required=True, help="Path to review_operator_handoff_artifact JSON.")
    parser.add_argument("--output-dir", default="artifacts/reviews", help="Directory for disposition artifacts.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    handoff_path = Path(args.handoff)
    handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
    result = emit_review_handoff_disposition(handoff, output_dir=Path(args.output_dir))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
