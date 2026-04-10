"""Bounded fail-closed merge/promotion gate integration for RQX review outcomes."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema

PROMOTION_GATE_FILE_SUFFIX = "_review_promotion_gate_artifact.json"


class ReviewPromotionGateError(ValueError):
    """Raised when promotion gate evaluation cannot classify safely."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _validate(instance: dict[str, Any], schema_name: str) -> None:
    schema = load_schema(schema_name)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda error: str(error.path))
    if errors:
        raise ReviewPromotionGateError("; ".join(error.message for error in errors))


def validate_review_result_artifact(review_result_artifact: dict[str, Any]) -> None:
    _validate(review_result_artifact, "review_result_artifact")


def validate_review_merge_readiness_artifact(merge_readiness_artifact: dict[str, Any]) -> None:
    _validate(merge_readiness_artifact, "review_merge_readiness_artifact")


def validate_review_operator_handoff_artifact(handoff_artifact: dict[str, Any]) -> None:
    _validate(handoff_artifact, "review_operator_handoff_artifact")


def validate_review_handoff_disposition_artifact(disposition_artifact: dict[str, Any]) -> None:
    _validate(disposition_artifact, "review_handoff_disposition_artifact")


def validate_review_promotion_gate_artifact(gate_artifact: dict[str, Any]) -> None:
    _validate(gate_artifact, "review_promotion_gate_artifact")


def validate_closure_decision_artifact(closure_decision_artifact: dict[str, Any]) -> None:
    _validate(closure_decision_artifact, "closure_decision_artifact")


def _deterministic_gate_id(
    review_result_artifact: dict[str, Any],
    merge_readiness_artifact: dict[str, Any],
    handoff_artifact: dict[str, Any] | None,
    disposition_artifact: dict[str, Any] | None,
) -> str:
    seed_parts = [
        review_result_artifact["review_id"],
        review_result_artifact["verdict"],
        str(merge_readiness_artifact["readiness_signal"]),
        merge_readiness_artifact["verdict"],
        handoff_artifact["handoff_id"] if handoff_artifact else "none",
        disposition_artifact["disposition_id"] if disposition_artifact else "none",
    ]
    digest = hashlib.sha256("|".join(seed_parts).encode("utf-8")).hexdigest()
    return f"rpga:{review_result_artifact['review_id']}:{digest[:12]}"


def _reason_from_disposition(disposition_artifact: dict[str, Any]) -> str:
    reason_code = disposition_artifact["reason_code"]
    disposition = disposition_artifact["disposition"]

    if reason_code == "policy_blocked":
        return "policy_blocked"
    if reason_code == "not_safe_to_merge":
        return "unresolved_not_safe_to_merge"
    if reason_code == "unresolved_fix_required":
        return "unresolved_fix_required"
    if disposition == "escalate_to_owner":
        return "disposition_escalated"
    if disposition in {"manual_review_required", "hold_pending_input", "request_checkpoint_decision"}:
        return "disposition_requires_manual_review"

    return "ambiguous_review_state"


def build_review_promotion_gate_artifact(
    *,
    review_result_artifact: dict[str, Any] | None,
    review_merge_readiness_artifact: dict[str, Any] | None,
    closure_decision_artifact: dict[str, Any] | None,
    review_operator_handoff_artifact: dict[str, Any] | None = None,
    review_handoff_disposition_artifact: dict[str, Any] | None = None,
    emitted_at: str | None = None,
) -> dict[str, Any]:
    emitted = emitted_at or _utc_now()
    blocking_refs: list[str] = []

    source_review_result_ref: str | None = None
    source_review_merge_readiness_ref: str | None = None
    source_review_operator_handoff_ref: str | None = None
    source_review_handoff_disposition_ref: str | None = None
    source_closure_decision_ref: str | None = None

    if review_result_artifact is None or review_merge_readiness_artifact is None or closure_decision_artifact is None:
        gate_artifact = {
            "artifact_type": "review_promotion_gate_artifact",
            "artifact_version": "1.0.0",
            "schema_version": "1.0.0",
            "standards_version": "1.0.0",
            "gate_id": "rpga:missing-required-review-artifacts",
            "source_review_result_ref": source_review_result_ref,
            "source_review_merge_readiness_ref": source_review_merge_readiness_ref,
            "source_review_operator_handoff_ref": source_review_operator_handoff_ref,
            "source_review_handoff_disposition_ref": source_review_handoff_disposition_ref,
            "source_closure_decision_ref": source_closure_decision_ref,
            "signal_status": "invalid",
            "gate_reason_code": "missing_required_review_artifact",
            "blocking_refs": [],
            "required_manual_action": True,
            "provenance": {
                "classified_by_system": "TLC",
                "automatic_promotion_triggered": False,
                "automatic_merge_triggered": False,
                "closure_authority_transferred": False,
            },
            "trace_linkage": {
                "review_id": "missing",
                "review_result_ref": None,
                "review_merge_readiness_ref": None,
            },
            "emitted_at": emitted,
        }
        validate_review_promotion_gate_artifact(gate_artifact)
        return gate_artifact

    validate_review_result_artifact(review_result_artifact)
    validate_review_merge_readiness_artifact(review_merge_readiness_artifact)
    validate_closure_decision_artifact(closure_decision_artifact)

    source_review_result_ref = f"review_result_artifact:{review_result_artifact['review_id']}"
    source_review_merge_readiness_ref = (
        f"review_merge_readiness_artifact:{review_merge_readiness_artifact['review_id']}"
    )
    source_closure_decision_ref = (
        f"closure_decision_artifact:{closure_decision_artifact['closure_decision_id']}"
    )
    blocking_refs.append(source_closure_decision_ref)

    if review_operator_handoff_artifact is not None:
        validate_review_operator_handoff_artifact(review_operator_handoff_artifact)
        source_review_operator_handoff_ref = (
            f"review_operator_handoff_artifact:{review_operator_handoff_artifact['handoff_id']}"
        )
        blocking_refs.append(source_review_operator_handoff_ref)

    if review_handoff_disposition_artifact is not None:
        validate_review_handoff_disposition_artifact(review_handoff_disposition_artifact)
        source_review_handoff_disposition_ref = (
            f"review_handoff_disposition_artifact:{review_handoff_disposition_artifact['disposition_id']}"
        )
        blocking_refs.append(source_review_handoff_disposition_ref)

    signal_status = "invalid"
    gate_reason_code = "ambiguous_review_state"
    required_manual_action = True

    review_id = review_result_artifact["review_id"]
    review_verdict = review_result_artifact["verdict"]
    merge_verdict = review_merge_readiness_artifact["verdict"]
    readiness_signal = review_merge_readiness_artifact["readiness_signal"]

    if review_merge_readiness_artifact["review_id"] != review_id:
        gate_reason_code = "ambiguous_review_state"
    elif review_merge_readiness_artifact["review_result_ref"] != source_review_result_ref:
        gate_reason_code = "ambiguous_review_state"
    elif merge_verdict != review_verdict:
        gate_reason_code = "ambiguous_review_state"
    elif (
        (review_verdict == "safe_to_merge" and readiness_signal != "review_safe")
        or (review_verdict == "fix_required" and readiness_signal != "review_fix_required")
        or (review_verdict == "not_safe_to_merge" and readiness_signal != "review_not_safe")
    ):
        gate_reason_code = "ambiguous_review_state"
    elif review_merge_readiness_artifact["cde_decision_required"] is not True:
        gate_reason_code = "ambiguous_review_state"
    elif review_handoff_disposition_artifact is not None and review_operator_handoff_artifact is None:
        gate_reason_code = "ambiguous_review_state"
    elif review_operator_handoff_artifact is not None and review_operator_handoff_artifact["review_id"] != review_id:
        gate_reason_code = "ambiguous_review_state"
    elif (
        review_handoff_disposition_artifact is not None
        and review_handoff_disposition_artifact["source_review_id"] != review_id
    ):
        gate_reason_code = "ambiguous_review_state"
    elif (
        review_handoff_disposition_artifact is not None
        and review_operator_handoff_artifact is not None
        and review_handoff_disposition_artifact["source_handoff_ref"] != source_review_operator_handoff_ref
    ):
        gate_reason_code = "ambiguous_review_state"
    elif closure_decision_artifact["provenance"]["engine"] != "closure_decision_engine":
        gate_reason_code = "missing_required_review_artifact"
    elif not str(closure_decision_artifact["provenance"]["decision_rules_version"]).startswith("cde-"):
        gate_reason_code = "missing_required_review_artifact"
    elif not isinstance(closure_decision_artifact.get("trace_id"), str) or not closure_decision_artifact["trace_id"]:
        gate_reason_code = "missing_required_review_artifact"
    elif review_verdict == "safe_to_merge" and review_operator_handoff_artifact is None and review_handoff_disposition_artifact is None:
        signal_status = "clean"
        gate_reason_code = "safe_to_merge"
        required_manual_action = False
    elif review_operator_handoff_artifact is not None and review_handoff_disposition_artifact is None:
        signal_status = "manual_review_required"
        gate_reason_code = "handoff_pending"
        required_manual_action = True
    elif review_handoff_disposition_artifact is not None:
        gate_reason_code = _reason_from_disposition(review_handoff_disposition_artifact)
        signal_status = "manual_review_required"
        required_manual_action = True
    elif review_verdict == "fix_required":
        signal_status = "manual_review_required"
        gate_reason_code = "unresolved_fix_required"
    elif review_verdict == "not_safe_to_merge":
        signal_status = "manual_review_required"
        gate_reason_code = "unresolved_not_safe_to_merge"
    else:
        gate_reason_code = "ambiguous_review_state"

    gate_artifact = {
        "artifact_type": "review_promotion_gate_artifact",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": "1.0.0",
        "gate_id": _deterministic_gate_id(
            review_result_artifact,
            review_merge_readiness_artifact,
            review_operator_handoff_artifact,
            review_handoff_disposition_artifact,
        ),
        "source_review_result_ref": source_review_result_ref,
        "source_review_merge_readiness_ref": source_review_merge_readiness_ref,
        "source_review_operator_handoff_ref": source_review_operator_handoff_ref,
        "source_review_handoff_disposition_ref": source_review_handoff_disposition_ref,
        "source_closure_decision_ref": source_closure_decision_ref,
        "signal_status": signal_status,
        "gate_reason_code": gate_reason_code,
        "blocking_refs": blocking_refs,
        "required_manual_action": required_manual_action,
        "provenance": {
            "classified_by_system": "TLC",
            "automatic_promotion_triggered": False,
            "automatic_merge_triggered": False,
            "closure_authority_transferred": False,
        },
        "trace_linkage": {
            "review_id": review_id,
            "review_result_ref": source_review_result_ref,
            "review_merge_readiness_ref": source_review_merge_readiness_ref,
        },
        "emitted_at": emitted,
    }
    validate_review_promotion_gate_artifact(gate_artifact)
    return gate_artifact


def emit_review_promotion_gate(
    *,
    review_result_artifact: dict[str, Any] | None,
    review_merge_readiness_artifact: dict[str, Any] | None,
    closure_decision_artifact: dict[str, Any] | None,
    output_dir: Path,
    review_operator_handoff_artifact: dict[str, Any] | None = None,
    review_handoff_disposition_artifact: dict[str, Any] | None = None,
    emitted_at: str | None = None,
) -> dict[str, Any]:
    gate_artifact = build_review_promotion_gate_artifact(
        review_result_artifact=review_result_artifact,
        review_merge_readiness_artifact=review_merge_readiness_artifact,
        closure_decision_artifact=closure_decision_artifact,
        review_operator_handoff_artifact=review_operator_handoff_artifact,
        review_handoff_disposition_artifact=review_handoff_disposition_artifact,
        emitted_at=emitted_at,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    review_id = (
        review_result_artifact["review_id"]
        if isinstance(review_result_artifact, dict) and "review_id" in review_result_artifact
        else "missing"
    )
    artifact_path = output_dir / f"{review_id}{PROMOTION_GATE_FILE_SUFFIX}"
    if artifact_path.exists():
        raise ReviewPromotionGateError(
            f"promotion gate artifact already exists for review_id={review_id} at {artifact_path}"
        )

    artifact_path.write_text(json.dumps(gate_artifact, indent=2) + "\n", encoding="utf-8")
    return {
        "review_promotion_gate_artifact": gate_artifact,
        "review_promotion_gate_artifact_path": str(artifact_path),
    }


def _read_json(path: str | None) -> dict[str, Any] | None:
    if path is None:
        return None
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate one bounded machine-readable merge/promotion gate from structured RQX review artifacts."
    )
    parser.add_argument("--review-result", help="Path to review_result_artifact JSON.")
    parser.add_argument("--merge-readiness", help="Path to review_merge_readiness_artifact JSON.")
    parser.add_argument("--closure-decision", help="Path to closure_decision_artifact JSON.")
    parser.add_argument("--handoff", help="Optional path to review_operator_handoff_artifact JSON.")
    parser.add_argument("--disposition", help="Optional path to review_handoff_disposition_artifact JSON.")
    parser.add_argument("--output-dir", default="artifacts/reviews", help="Directory for gate artifacts.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    result = emit_review_promotion_gate(
        review_result_artifact=_read_json(args.review_result),
        review_merge_readiness_artifact=_read_json(args.merge_readiness),
        closure_decision_artifact=_read_json(args.closure_decision),
        review_operator_handoff_artifact=_read_json(args.handoff),
        review_handoff_disposition_artifact=_read_json(args.disposition),
        output_dir=Path(args.output_dir),
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
