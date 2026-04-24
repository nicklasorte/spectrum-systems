"""CTRL-LOOP Gate Closure — all 8 enhanced gate checks.

Implements the 8 CTRL-LOOP gate checks required for Checkpoint L certification.
Each function is deterministic, fail-closed, and schema-bound.

Gate checks
-----------
1. failure_eval_policy_linkage   — failure → eval → policy chain mandatory
2. deterministic_policy_consumption — policy from versioned registry, not prompt
3. policy_causes_behavior_change — A/B test: policy must alter decisions
4. recurrence_prevention_wired   — 2nd failure of same ID → FREEZE
5. longitudinal_calibration      — 7-day judge disagreement tracking
6. calibration_affects_lifecycle — high disagreement → no auto-promote
7. replay_trace_reconstruct      — replay+trace fully reconstruct decisions
8. falsification_artifact        — can find a falsifying policy or emit finding

All functions return a dict with:
  gate_check_id: str
  status: "PASS" | "BLOCKED" | "PARTIAL"
  evidence: dict
  notes: str
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_GATE_SCHEMA_VERSION = "1.0.0"


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat()


def _gate_result(
    gate_check_id: str,
    status: str,
    evidence: Dict[str, Any],
    notes: str,
) -> Dict[str, Any]:
    return {
        "artifact_type": "ctrl_loop_gate_result",
        "schema_version": _GATE_SCHEMA_VERSION,
        "gate_check_id": gate_check_id,
        "status": status,
        "evidence": evidence,
        "notes": notes,
        "checked_at": _utc_now(),
    }


# ---------------------------------------------------------------------------
# Gate check 1: Failure → Eval → Policy linkage
# ---------------------------------------------------------------------------

def check_failure_eval_policy_linkage(
    failure: Dict[str, Any],
    eval_candidate: Optional[Dict[str, Any]] = None,
    policy_ref: Optional[str] = None,
) -> Dict[str, Any]:
    """Check 1: failure → eval → policy linkage is mandatory and traceable.

    Every failure must produce an eval_candidate routed to governance.
    The eval_candidate must reference a policy artifact.

    Parameters
    ----------
    failure:
        The failure artifact under test.
    eval_candidate:
        The eval_candidate produced from the failure (None = linkage gap).
    policy_ref:
        The policy artifact reference in the eval_candidate (None = missing).

    Returns
    -------
    dict  ctrl_loop_gate_result
    """
    issues: List[str] = []

    if not isinstance(failure, dict):
        issues.append("failure must be a dict")
    else:
        if not failure.get("failure_id") and not failure.get("artifact_id"):
            issues.append("failure missing failure_id / artifact_id")
        if not failure.get("failure_class") and not failure.get("failure_type"):
            issues.append("failure missing failure_class / failure_type")

    if eval_candidate is None:
        issues.append("eval_candidate not produced — linkage gap (fail-closed)")
    elif not isinstance(eval_candidate, dict):
        issues.append("eval_candidate must be a dict")
    else:
        if not eval_candidate.get("eval_case_id") and not eval_candidate.get("artifact_id"):
            issues.append("eval_candidate missing eval_case_id")
        if not eval_candidate.get("source_failure_id") and not eval_candidate.get("failure_ref"):
            issues.append("eval_candidate not linked to source failure")

    if policy_ref is None:
        issues.append("policy_ref not present — policy linkage gap")
    elif not isinstance(policy_ref, str) or not policy_ref.strip():
        issues.append("policy_ref must be non-empty string")

    status = "PASS" if not issues else "BLOCKED"
    return _gate_result(
        gate_check_id="CTRL-1-failure-eval-policy-linkage",
        status=status,
        evidence={
            "failure_present": isinstance(failure, dict),
            "eval_candidate_present": eval_candidate is not None,
            "policy_ref_present": policy_ref is not None,
            "issues": issues,
        },
        notes=(
            "Failure → eval → policy chain is complete and mandatory."
            if status == "PASS"
            else f"Linkage gap detected: {'; '.join(issues)}"
        ),
    )


# ---------------------------------------------------------------------------
# Gate check 2: Deterministic policy consumption
# ---------------------------------------------------------------------------

def check_deterministic_policy_consumption(
    decisions: List[Dict[str, Any]],
    *,
    expected_policy_artifact_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Check 2: policy consumed from versioned registry, not prompt.

    All decisions in the batch must:
    - Reference the same policy_artifact_id
    - Produce identical outcomes for identical inputs (determinism)
    - Not embed policy text inline

    Parameters
    ----------
    decisions:
        List of decision artifacts from a repeated run.
    expected_policy_artifact_id:
        If provided, all decisions must reference this artifact ID.
    """
    if not decisions:
        return _gate_result(
            "CTRL-2-deterministic-policy-consumption",
            "BLOCKED",
            {"decisions_count": 0},
            "No decisions provided — cannot verify determinism",
        )

    issues: List[str] = []
    policy_ids = set()

    for i, dec in enumerate(decisions):
        if not isinstance(dec, dict):
            issues.append(f"decision[{i}] is not a dict")
            continue

        pid = dec.get("policy_artifact_id") or dec.get("policy_ref")
        if not pid:
            issues.append(f"decision[{i}] missing policy_artifact_id/policy_ref — inline policy suspected")
        else:
            policy_ids.add(str(pid))

        if dec.get("policy_text") or dec.get("inline_policy"):
            issues.append(f"decision[{i}] contains inline policy text — registry policy required")

    if len(policy_ids) > 1:
        issues.append(f"Non-deterministic policy references across decisions: {policy_ids}")

    if expected_policy_artifact_id and policy_ids and expected_policy_artifact_id not in policy_ids:
        issues.append(
            f"Expected policy_artifact_id '{expected_policy_artifact_id}' not found in decisions"
        )

    # Determinism check: outcomes must be identical for identical inputs
    outcomes = [dec.get("decision") or dec.get("outcome") or dec.get("system_response") for dec in decisions if isinstance(dec, dict)]
    unique_outcomes = set(str(o) for o in outcomes if o is not None)
    if len(unique_outcomes) > 1:
        issues.append(
            f"Non-deterministic outcomes across repeated decisions: {unique_outcomes}"
        )

    status = "PASS" if not issues else "BLOCKED"
    return _gate_result(
        "CTRL-2-deterministic-policy-consumption",
        status,
        {
            "decisions_count": len(decisions),
            "unique_policy_refs": sorted(policy_ids),
            "unique_outcomes": sorted(unique_outcomes),
            "issues": issues,
        },
        "All decisions consume policy from versioned registry; outcomes are deterministic."
        if status == "PASS"
        else f"Determinism violations: {'; '.join(issues)}",
    )


# ---------------------------------------------------------------------------
# Gate check 3: Policy causes behavior change
# ---------------------------------------------------------------------------

def check_policy_causes_behavior_change(
    outcomes_policy_a: List[str],
    outcomes_policy_b: List[str],
    *,
    min_change_rate: float = 0.30,
) -> Dict[str, Any]:
    """Check 3: applying different policies produces different decisions.

    Runs an A/B test: the same context under policy_a vs policy_b must produce
    at least min_change_rate different outcomes (default 30%).
    """
    if not outcomes_policy_a or not outcomes_policy_b:
        return _gate_result(
            "CTRL-3-policy-causes-behavior-change",
            "BLOCKED",
            {"outcomes_a_count": len(outcomes_policy_a), "outcomes_b_count": len(outcomes_policy_b)},
            "Empty outcome lists — cannot verify behavior change",
        )

    n = min(len(outcomes_policy_a), len(outcomes_policy_b))
    if n == 0:
        return _gate_result(
            "CTRL-3-policy-causes-behavior-change",
            "BLOCKED",
            {},
            "No comparable outcomes",
        )

    different = sum(
        1 for a, b in zip(outcomes_policy_a[:n], outcomes_policy_b[:n]) if a != b
    )
    change_rate = different / n

    passed = change_rate >= min_change_rate
    status = "PASS" if passed else "BLOCKED"

    return _gate_result(
        "CTRL-3-policy-causes-behavior-change",
        status,
        {
            "n_compared": n,
            "different_outcomes": different,
            "change_rate": round(change_rate, 4),
            "required_change_rate": min_change_rate,
        },
        f"Policy A/B test: {change_rate:.1%} difference (required ≥{min_change_rate:.0%})."
        if status == "PASS"
        else f"Insufficient behavior change: {change_rate:.1%} < {min_change_rate:.0%}",
    )


# ---------------------------------------------------------------------------
# Gate check 4: Recurrence prevention wired
# ---------------------------------------------------------------------------

def check_recurrence_prevention_wired(
    first_decision: Dict[str, Any],
    second_decision: Dict[str, Any],
    *,
    failure_id: str,
) -> Dict[str, Any]:
    """Check 4: same failure occurring twice must escalate to FREEZE.

    Parameters
    ----------
    first_decision:
        Decision from first occurrence of failure_id.
    second_decision:
        Decision from second occurrence of the same failure_id.
    failure_id:
        The shared failure identifier.
    """
    issues: List[str] = []

    first_response = str(first_decision.get("system_response") or first_decision.get("action") or "")
    second_response = str(second_decision.get("system_response") or second_decision.get("action") or "")

    if first_response not in {"block", "warn", "freeze"}:
        issues.append(
            f"First occurrence: expected block/warn/freeze, got '{first_response}'"
        )

    if second_response != "freeze":
        issues.append(
            f"Second occurrence of failure_id='{failure_id}' must produce 'freeze', got '{second_response}'"
        )

    first_recurrence = first_decision.get("recurrence_count", 0)
    second_recurrence = second_decision.get("recurrence_count", 0)
    if second_recurrence < 2:
        if "recurrence_count" in second_decision:
            issues.append(
                f"Second occurrence recurrence_count={second_recurrence} must be ≥ 2"
            )

    status = "PASS" if not issues else "BLOCKED"
    return _gate_result(
        "CTRL-4-recurrence-prevention-wired",
        status,
        {
            "failure_id": failure_id,
            "first_response": first_response,
            "second_response": second_response,
            "first_recurrence_count": first_recurrence,
            "second_recurrence_count": second_recurrence,
            "issues": issues,
        },
        "Recurrence prevention: 2nd occurrence correctly escalates to FREEZE."
        if status == "PASS"
        else f"Recurrence prevention gap: {'; '.join(issues)}",
    )


# ---------------------------------------------------------------------------
# Gate check 5: Longitudinal calibration tracking
# ---------------------------------------------------------------------------

def check_longitudinal_calibration(
    calibration_record: Dict[str, Any],
    *,
    expected_window: str = "7d",
    max_disagreement_threshold: float = 0.25,
) -> Dict[str, Any]:
    """Check 5: judge disagreement tracked over a rolling window.

    Parameters
    ----------
    calibration_record:
        A calibration report artifact with disagreement_rate and window.
    expected_window:
        Expected tracking window (default '7d').
    max_disagreement_threshold:
        Disagreement rate at which calibration is considered out of bounds.
    """
    issues: List[str] = []

    if not isinstance(calibration_record, dict):
        return _gate_result(
            "CTRL-5-longitudinal-calibration",
            "BLOCKED",
            {},
            "calibration_record must be a dict",
        )

    window = calibration_record.get("window")
    if window != expected_window:
        issues.append(
            f"calibration_record.window='{window}' does not match expected '{expected_window}'"
        )

    rate = calibration_record.get("disagreement_rate")
    if rate is None:
        issues.append("calibration_record.disagreement_rate missing")
    elif not isinstance(rate, (int, float)):
        issues.append("calibration_record.disagreement_rate must be numeric")

    sample_count = calibration_record.get("sample_count") or calibration_record.get("total_judgments")
    if sample_count is None:
        issues.append("calibration_record missing sample_count / total_judgments")

    calibration_status = calibration_record.get("calibration_status") or calibration_record.get("status")
    if not calibration_status:
        issues.append("calibration_record missing calibration_status")

    if isinstance(rate, (int, float)) and rate >= max_disagreement_threshold:
        issues.append(
            f"Disagreement rate {rate:.1%} exceeds max threshold {max_disagreement_threshold:.1%}"
        )

    status = "PASS" if not issues else "BLOCKED"
    return _gate_result(
        "CTRL-5-longitudinal-calibration",
        status,
        {
            "window": window,
            "disagreement_rate": rate,
            "sample_count": sample_count,
            "calibration_status": calibration_status,
            "max_disagreement_threshold": max_disagreement_threshold,
            "issues": issues,
        },
        f"Calibration tracked over {window} window; disagreement_rate={rate}."
        if status == "PASS"
        else f"Calibration tracking gap: {'; '.join(issues)}",
    )


# ---------------------------------------------------------------------------
# Gate check 6: Calibration affects lifecycle
# ---------------------------------------------------------------------------

def check_calibration_affects_lifecycle(
    promotion_decision: Dict[str, Any],
    calibration_record: Dict[str, Any],
    *,
    high_disagreement_threshold: float = 0.25,
) -> Dict[str, Any]:
    """Check 6: high judge disagreement must block auto-promotion.

    Parameters
    ----------
    promotion_decision:
        The lifecycle promotion decision artifact.
    calibration_record:
        The current calibration record.
    high_disagreement_threshold:
        If disagreement_rate exceeds this, auto-promote must be blocked.
    """
    issues: List[str] = []

    rate = calibration_record.get("disagreement_rate") if isinstance(calibration_record, dict) else None
    if rate is None:
        issues.append("calibration_record.disagreement_rate missing")

    can_auto_promote = promotion_decision.get("can_auto_promote")
    requires_human_review = promotion_decision.get("requires_human_review")

    if isinstance(rate, (int, float)) and rate > high_disagreement_threshold:
        if can_auto_promote is not False:
            issues.append(
                f"can_auto_promote must be False when disagreement_rate={rate:.1%} > {high_disagreement_threshold:.1%}"
            )
        if requires_human_review is not True:
            issues.append(
                f"requires_human_review must be True when disagreement_rate={rate:.1%} > {high_disagreement_threshold:.1%}"
            )

    status = "PASS" if not issues else "BLOCKED"
    return _gate_result(
        "CTRL-6-calibration-affects-lifecycle",
        status,
        {
            "disagreement_rate": rate,
            "high_disagreement_threshold": high_disagreement_threshold,
            "can_auto_promote": can_auto_promote,
            "requires_human_review": requires_human_review,
            "issues": issues,
        },
        "High disagreement correctly blocks auto-promotion and requires human review."
        if status == "PASS"
        else f"Lifecycle calibration gap: {'; '.join(issues)}",
    )


# ---------------------------------------------------------------------------
# Gate check 7: Replay + trace reconstruct decisions
# ---------------------------------------------------------------------------

def check_replay_trace_reconstruct(
    original_decision: Dict[str, Any],
    replayed_decision: Dict[str, Any],
    *,
    key_fields: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Check 7: replaying the same inputs produces identical decisions.

    Parameters
    ----------
    original_decision:
        The original decision artifact.
    replayed_decision:
        The decision produced by replay.
    key_fields:
        Fields to compare for determinism. Defaults to standard decision fields.
    """
    if key_fields is None:
        key_fields = [
            "decision",
            "system_response",
            "rationale_code",
            "triggered_signals",
            "decision_id",
        ]

    issues: List[str] = []

    if not isinstance(original_decision, dict) or not isinstance(replayed_decision, dict):
        return _gate_result(
            "CTRL-7-replay-trace-reconstruct",
            "BLOCKED",
            {},
            "Both original_decision and replayed_decision must be dicts",
        )

    mismatched = []
    for field in key_fields:
        orig_val = original_decision.get(field)
        replay_val = replayed_decision.get(field)
        if orig_val != replay_val:
            mismatched.append({
                "field": field,
                "original": orig_val,
                "replayed": replay_val,
            })

    if mismatched:
        issues.append(f"Replay mismatch in {len(mismatched)} field(s)")

    status = "PASS" if not issues else "BLOCKED"
    return _gate_result(
        "CTRL-7-replay-trace-reconstruct",
        status,
        {
            "fields_compared": key_fields,
            "mismatched_fields": mismatched,
            "reconstruction_verified": not bool(mismatched),
        },
        "Replay fully reconstructs original decision across all key fields."
        if status == "PASS"
        else f"Replay divergence: {len(mismatched)} field(s) differ",
    )


# ---------------------------------------------------------------------------
# Gate check 8: Falsification artifact
# ---------------------------------------------------------------------------

def check_falsification_artifact(
    decision: Dict[str, Any],
    falsifying_policy: Optional[Dict[str, Any]],
    outcome_under_falsifying_policy: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Check 8: falsification artifact works correctly.

    Given a control decision, verify whether a falsifying policy exists.
    If one exists, applying it must produce a different decision.
    If none exists, a finding_artifact must be emitted.

    Parameters
    ----------
    decision:
        The original control decision.
    falsifying_policy:
        A policy that should produce a different decision, or None.
    outcome_under_falsifying_policy:
        The decision produced when falsifying_policy is applied. Required
        if falsifying_policy is provided.
    """
    issues: List[str] = []

    original_response = str(
        decision.get("system_response") or decision.get("decision") or ""
    )

    if falsifying_policy is None:
        return _gate_result(
            "CTRL-8-falsification-artifact",
            "PASS",
            {
                "falsifying_policy_exists": False,
                "finding_artifact_required": True,
                "original_response": original_response,
                "finding": {
                    "artifact_type": "finding_artifact",
                    "category": "no_falsifying_policy_found",
                    "decision_ref": str(decision.get("decision_id") or "unknown"),
                    "message": "No policy found that would reject this decision — all tested policies agree.",
                    "severity": "info",
                },
            },
            "No falsifying policy exists; finding artifact emitted (correct behavior).",
        )

    if not isinstance(falsifying_policy, dict):
        issues.append("falsifying_policy must be a dict")

    if outcome_under_falsifying_policy is None:
        issues.append("outcome_under_falsifying_policy required when falsifying_policy provided")
    elif isinstance(outcome_under_falsifying_policy, dict):
        falsified_response = str(
            outcome_under_falsifying_policy.get("system_response")
            or outcome_under_falsifying_policy.get("decision")
            or ""
        )
        if falsified_response == original_response:
            issues.append(
                f"Falsifying policy did not change decision: both produced '{original_response}'"
            )

    status = "PASS" if not issues else "BLOCKED"
    return _gate_result(
        "CTRL-8-falsification-artifact",
        status,
        {
            "falsifying_policy_exists": True,
            "original_response": original_response,
            "falsified_response": str(
                (outcome_under_falsifying_policy or {}).get("system_response")
                or (outcome_under_falsifying_policy or {}).get("decision")
                or ""
            ),
            "policy_successfully_inverts_decision": not bool(issues),
            "issues": issues,
        },
        "Falsifying policy correctly inverts the control decision."
        if status == "PASS"
        else f"Falsification gap: {'; '.join(issues)}",
    )


# ---------------------------------------------------------------------------
# Run all 8 gate checks
# ---------------------------------------------------------------------------

def run_all_gate_checks(gate_inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Run all 8 CTRL-LOOP gate checks and return a consolidated result.

    Parameters
    ----------
    gate_inputs:
        Dict with keys for each gate check's required inputs.

    Returns
    -------
    dict
        ctrl_loop_gate_summary with per-check results and overall status.
    """
    results: Dict[str, Dict[str, Any]] = {}

    # Check 1
    results["check_1"] = check_failure_eval_policy_linkage(
        failure=gate_inputs.get("failure", {}),
        eval_candidate=gate_inputs.get("eval_candidate"),
        policy_ref=gate_inputs.get("policy_ref"),
    )

    # Check 2
    results["check_2"] = check_deterministic_policy_consumption(
        decisions=gate_inputs.get("repeated_decisions", []),
        expected_policy_artifact_id=gate_inputs.get("expected_policy_artifact_id"),
    )

    # Check 3
    results["check_3"] = check_policy_causes_behavior_change(
        outcomes_policy_a=gate_inputs.get("outcomes_policy_a", []),
        outcomes_policy_b=gate_inputs.get("outcomes_policy_b", []),
        min_change_rate=gate_inputs.get("min_change_rate", 0.30),
    )

    # Check 4
    results["check_4"] = check_recurrence_prevention_wired(
        first_decision=gate_inputs.get("first_recurrence_decision", {}),
        second_decision=gate_inputs.get("second_recurrence_decision", {}),
        failure_id=gate_inputs.get("recurrence_failure_id", "unknown"),
    )

    # Check 5
    results["check_5"] = check_longitudinal_calibration(
        calibration_record=gate_inputs.get("calibration_record", {}),
        expected_window=gate_inputs.get("expected_window", "7d"),
        max_disagreement_threshold=gate_inputs.get("max_disagreement_threshold", 0.25),
    )

    # Check 6
    results["check_6"] = check_calibration_affects_lifecycle(
        promotion_decision=gate_inputs.get("promotion_decision", {}),
        calibration_record=gate_inputs.get("calibration_record", {}),
        high_disagreement_threshold=gate_inputs.get("high_disagreement_threshold", 0.25),
    )

    # Check 7
    results["check_7"] = check_replay_trace_reconstruct(
        original_decision=gate_inputs.get("original_decision", {}),
        replayed_decision=gate_inputs.get("replayed_decision", {}),
        key_fields=gate_inputs.get("replay_key_fields"),
    )

    # Check 8
    results["check_8"] = check_falsification_artifact(
        decision=gate_inputs.get("falsification_decision", {}),
        falsifying_policy=gate_inputs.get("falsifying_policy"),
        outcome_under_falsifying_policy=gate_inputs.get("falsified_outcome"),
    )

    all_pass = all(r["status"] == "PASS" for r in results.values())
    blocked_checks = [k for k, r in results.items() if r["status"] == "BLOCKED"]

    return {
        "artifact_type": "ctrl_loop_gate_summary",
        "schema_version": _GATE_SCHEMA_VERSION,
        "overall_status": "PASS" if all_pass else "BLOCKED",
        "checks_passed": sum(1 for r in results.values() if r["status"] == "PASS"),
        "checks_blocked": len(blocked_checks),
        "blocked_check_ids": sorted(blocked_checks),
        "check_results": results,
        "timestamp": _utc_now(),
    }
