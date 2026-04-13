"""TAX — Termination Authority eXecutor."""

from __future__ import annotations

from typing import Any


TAX_DECISIONS = (
    "complete",
    "continue",
    "repair_required",
    "freeze_required",
    "block_required",
    "await_async_signal",
)


def build_termination_signals(*, signal_record: dict[str, Any]) -> dict[str, Any]:
    required = (
        "required_artifacts_present",
        "required_evals_present",
        "required_evals_passed",
        "trace_complete",
        "blocking_contradiction_present",
        "human_review_outstanding",
        "replay_consistent",
        "policy_rejected",
        "bax_decision",
    )
    missing = [field for field in required if field not in signal_record]
    if missing:
        raise ValueError(f"missing termination signal fields: {', '.join(sorted(missing))}")
    return dict(signal_record)


def compute_information_sufficiency(*, signals: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not signals.get("required_artifacts_present", False):
        reasons.append("missing_required_artifacts")
    if not signals.get("required_evals_present", False):
        reasons.append("missing_required_evals")
    if not signals.get("required_evals_passed", False):
        reasons.append("required_evals_failed_or_indeterminate")
    if not signals.get("trace_complete", False):
        reasons.append("trace_incomplete")
    if signals.get("blocking_contradiction_present", False):
        reasons.append("blocking_contradiction_present")
    if signals.get("human_review_outstanding", False):
        reasons.append("required_human_review_outstanding")
    if not signals.get("replay_consistent", False):
        reasons.append("replay_inconsistency")
    if signals.get("policy_rejected", False):
        reasons.append("policy_rejection")
    return len(reasons) == 0, reasons


def decide_termination(*, signals: dict[str, Any], allow_async_wait: bool = True) -> tuple[str, list[str]]:
    sufficient, reasons = compute_information_sufficiency(signals=signals)
    bax_decision = str(signals.get("bax_decision") or "").strip().lower()

    if bax_decision == "block":
        return "block_required", sorted(set(reasons + ["bax_block"]))
    if bax_decision == "freeze":
        return "freeze_required", sorted(set(reasons + ["bax_freeze"]))
    if signals.get("policy_rejected", False):
        return "block_required", sorted(set(reasons + ["policy_rejection"]))
    if not signals.get("required_artifacts_present", False) or not signals.get("required_evals_present", False):
        return "block_required", sorted(set(reasons))
    if not signals.get("trace_complete", False):
        return "block_required", sorted(set(reasons))
    if signals.get("blocking_contradiction_present", False):
        return "freeze_required", sorted(set(reasons))
    if signals.get("human_review_outstanding", False):
        return ("await_async_signal" if allow_async_wait else "freeze_required"), sorted(set(reasons))
    if not signals.get("required_evals_passed", False) or not signals.get("replay_consistent", False):
        return "repair_required", sorted(set(reasons))
    if sufficient and bax_decision in {"allow", "warn"}:
        return "complete", ["termination_conditions_satisfied"]
    return "continue", sorted(set(reasons or ["continue_pending_signals"]))


def emit_termination_decision(*, run_id: str, trace_id: str, policy_version: str, input_refs: dict[str, str], signals: dict[str, Any]) -> dict[str, Any]:
    decision, reason_codes = decide_termination(signals=signals)
    return {
        "artifact_type": "termination_decision",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "decision_id": f"TDEC-{run_id}-{trace_id}",
        "run_id": run_id,
        "trace_id": trace_id,
        "decision": decision,
        "reason_codes": reason_codes,
        "policy_version": policy_version,
        "input_refs": input_refs,
    }
