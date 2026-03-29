"""QUEUE-12 deterministic fail-closed policy backtesting for prompt queue runs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.prompt_queue.prompt_queue_transition_artifact_io import (
    validate_prompt_queue_transition_decision_artifact,
)
from spectrum_systems.modules.prompt_queue.step_decision import validate_step_decision_artifact
from spectrum_systems.modules.runtime.policy_registry import (
    PolicyRegistryError,
    get_policy_profile,
    load_slo_policy_registry,
    validate_policy_name,
)
from spectrum_systems.modules.runtime.replay_engine import compare_replay_outputs


class QueuePolicyBacktestingError(ValueError):
    """Raised when queue policy backtesting cannot complete deterministically."""


def _stable_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _read_json_object(ref: str, *, label: str) -> dict[str, Any]:
    path = Path(ref)
    if not path.is_file():
        raise QueuePolicyBacktestingError(f"missing replay data: {label} not found: {ref}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise QueuePolicyBacktestingError(f"{label} must be a JSON object: {ref}")
    return payload


def _parse_policy_ref(input_refs: dict[str, Any], *, field: str, registry: dict[str, Any]) -> dict[str, str]:
    value = input_refs.get(field)
    if not isinstance(value, dict):
        raise QueuePolicyBacktestingError(f"missing policy ref: {field}")

    policy_id = value.get("policy_id")
    policy_version = value.get("policy_version")
    if not isinstance(policy_id, str) or not policy_id.strip():
        raise QueuePolicyBacktestingError(f"{field}.policy_id must be a non-empty string")
    if not isinstance(policy_version, str) or not policy_version.strip():
        raise QueuePolicyBacktestingError(f"{field}.policy_version must be a non-empty string")

    try:
        validate_policy_name(policy_id)
        get_policy_profile(policy_id, registry=registry)
    except PolicyRegistryError as exc:
        raise QueuePolicyBacktestingError(f"{field} is not resolvable in policy_registry: {exc}") from exc

    return {
        "policy_id": policy_id,
        "policy_version": policy_version,
    }


def _collect_steps_from_replay_ref(replay_ref: str) -> tuple[list[str], dict[str, str], str | None]:
    payload = _read_json_object(replay_ref, label="replay run")

    step_decision_refs = payload.get("step_decision_refs")
    transition_decision_refs = payload.get("transition_decision_refs")

    if not isinstance(step_decision_refs, list) or not step_decision_refs:
        raise QueuePolicyBacktestingError(
            f"missing replay data: replay_run_ref must include non-empty step_decision_refs: {replay_ref}"
        )
    if not isinstance(transition_decision_refs, list) or not transition_decision_refs:
        raise QueuePolicyBacktestingError(
            f"missing replay data: replay_run_ref must include non-empty transition_decision_refs: {replay_ref}"
        )

    transitions_by_step: dict[str, dict[str, Any]] = {}
    for transition_ref in transition_decision_refs:
        transition = _read_json_object(str(transition_ref), label="transition decision")
        validate_prompt_queue_transition_decision_artifact(transition)
        step_id = transition.get("step_id")
        if not isinstance(step_id, str) or not step_id:
            raise QueuePolicyBacktestingError(f"transition decision missing step_id: {transition_ref}")
        if step_id in transitions_by_step:
            raise QueuePolicyBacktestingError(f"ambiguous comparison: duplicate transition decision for {step_id}")
        transitions_by_step[step_id] = transition

    step_decisions: dict[str, str] = {}
    derived_trace_id: str | None = None
    for step_ref in step_decision_refs:
        step_decision = _read_json_object(str(step_ref), label="step decision")
        validate_step_decision_artifact(step_decision)

        step_id = step_decision.get("step_id")
        observed_decision = step_decision.get("decision")
        if not isinstance(step_id, str) or not step_id:
            raise QueuePolicyBacktestingError(f"step decision missing step_id: {step_ref}")
        if not isinstance(observed_decision, str) or observed_decision not in {"allow", "warn", "block"}:
            raise QueuePolicyBacktestingError(f"step decision has unsupported decision value: {step_ref}")
        if step_id in step_decisions:
            raise QueuePolicyBacktestingError(f"ambiguous comparison: duplicate step decision for {step_id}")

        transition = transitions_by_step.get(step_id)
        if transition is None:
            raise QueuePolicyBacktestingError(f"missing replay data: missing transition decision for step {step_id}")

        transition_status = transition.get("transition_status")
        transition_action = transition.get("transition_action")
        if observed_decision == "block" and (transition_status != "blocked" or transition_action != "block"):
            raise QueuePolicyBacktestingError(
                f"inconsistent replay evidence: blocked step {step_id} missing blocked transition"
            )

        trace_linkage = step_decision.get("trace_linkage") or transition.get("trace_linkage")
        if trace_linkage is not None and not isinstance(trace_linkage, str):
            raise QueuePolicyBacktestingError(f"inconsistent replay evidence: invalid trace_linkage on {step_id}")
        if isinstance(trace_linkage, str) and trace_linkage:
            if derived_trace_id is None:
                derived_trace_id = trace_linkage
            elif derived_trace_id != trace_linkage:
                raise QueuePolicyBacktestingError("ambiguous comparison: inconsistent trace_id across step decisions")

        step_decisions[step_id] = observed_decision

    return sorted(step_decisions), step_decisions, derived_trace_id


def _apply_policy_to_decision(observed_decision: str, *, policy_profile: dict[str, Any], policy_id: str) -> tuple[str, str | None]:
    warnings_permitted = policy_profile.get("warnings_permitted")
    if not isinstance(warnings_permitted, bool):
        raise QueuePolicyBacktestingError(f"policy registry inconsistent: {policy_id} missing warnings_permitted")

    if observed_decision == "warn" and not warnings_permitted:
        return "block", "candidate policy converted warn to block because warnings are not permitted"
    return observed_decision, None


def run_queue_policy_backtest(input_refs: dict) -> dict:
    """Run deterministic fail-closed queue policy backtesting over replay artifacts."""
    if not isinstance(input_refs, dict):
        raise QueuePolicyBacktestingError("input_refs must be an object")

    replay_run_refs = input_refs.get("replay_run_refs")
    if not isinstance(replay_run_refs, list) or not replay_run_refs:
        raise QueuePolicyBacktestingError("missing replay data: replay_run_refs must be a non-empty array")
    if not all(isinstance(item, str) and item.strip() for item in replay_run_refs):
        raise QueuePolicyBacktestingError("replay_run_refs must contain non-empty string refs")

    registry = load_slo_policy_registry()
    baseline_policy_ref = _parse_policy_ref(input_refs, field="baseline_policy_ref", registry=registry)
    candidate_policy_ref = _parse_policy_ref(input_refs, field="policy_under_test_ref", registry=registry)

    baseline_profile = get_policy_profile(baseline_policy_ref["policy_id"], registry=registry)
    candidate_profile = get_policy_profile(candidate_policy_ref["policy_id"], registry=registry)

    observed_steps: dict[str, str] = {}
    trace_id: str | None = None
    for replay_ref in sorted(set(replay_run_refs)):
        step_ids, decision_map, replay_trace_id = _collect_steps_from_replay_ref(replay_ref)
        for step_id in step_ids:
            observed_decision = decision_map[step_id]
            if step_id in observed_steps and observed_steps[step_id] != observed_decision:
                raise QueuePolicyBacktestingError(f"ambiguous comparison: conflicting observed decisions for {step_id}")
            observed_steps[step_id] = observed_decision

        if replay_trace_id is not None:
            if trace_id is None:
                trace_id = replay_trace_id
            elif trace_id != replay_trace_id:
                raise QueuePolicyBacktestingError("ambiguous comparison: replay refs contain multiple trace_id values")

    if not observed_steps:
        raise QueuePolicyBacktestingError("missing replay data: no historical step decisions found")

    comparison_results: list[dict[str, Any]] = []
    mismatches = 0

    for step_id in sorted(observed_steps):
        observed_decision = observed_steps[step_id]
        baseline_decision, _ = _apply_policy_to_decision(
            observed_decision,
            policy_profile=baseline_profile,
            policy_id=baseline_policy_ref["policy_id"],
        )
        candidate_decision, candidate_reason = _apply_policy_to_decision(
            observed_decision,
            policy_profile=candidate_profile,
            policy_id=candidate_policy_ref["policy_id"],
        )

        comparison = compare_replay_outputs(
            [{"span_id": step_id, "status": baseline_decision}],
            [{"original_span_id": step_id, "status": candidate_decision}],
        )
        is_match = bool(comparison.get("matched"))
        parity_status = "match" if is_match else "mismatch"

        difference_summary: str | None = None
        if parity_status == "mismatch":
            mismatches += 1
            if candidate_reason:
                difference_summary = candidate_reason
            else:
                difference_summary = f"decision changed from {baseline_decision} to {candidate_decision}"
            if not difference_summary:
                raise QueuePolicyBacktestingError(f"mismatch without explanation for step {step_id}")

        comparison_results.append(
            {
                "step_id": step_id,
                "baseline_decision": baseline_decision,
                "candidate_decision": candidate_decision,
                "parity_status": parity_status,
                "difference_summary": difference_summary,
            }
        )

    total_steps = len(comparison_results)
    matches = total_steps - mismatches
    mismatch_rate = round(mismatches / total_steps, 6)

    if mismatches == 0:
        recommendation = "promote"
    elif mismatch_rate <= 0.25:
        recommendation = "hold"
    else:
        recommendation = "reject"

    normalized_refs = sorted(set(replay_run_refs))
    trace_id_value = trace_id or "queue-policy-backtest-trace"

    backtest_seed = {
        "baseline": baseline_policy_ref,
        "candidate": candidate_policy_ref,
        "replay_run_refs": normalized_refs,
        "comparison_results": comparison_results,
        "trace_id": trace_id_value,
    }

    result = {
        "backtest_id": f"queue-policy-backtest-{_stable_hash(backtest_seed)}",
        "policy_under_test_ref": candidate_policy_ref,
        "baseline_policy_ref": baseline_policy_ref,
        "replay_run_refs": normalized_refs,
        "comparison_results": comparison_results,
        "aggregate_summary": {
            "total_steps": total_steps,
            "matches": matches,
            "mismatches": mismatches,
            "mismatch_rate": mismatch_rate,
        },
        "recommendation": recommendation,
        "trace_id": trace_id_value,
        "timestamp": input_refs.get("timestamp") if isinstance(input_refs.get("timestamp"), str) else "2026-03-29T00:00:00Z",
    }

    validate_artifact(result, "prompt_queue_policy_backtest_report")
    return result
