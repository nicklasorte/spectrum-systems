"""Operator-focused one-cycle orchestration for bounded roadmap execution and usability artifacts (BATCH-U)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema
from spectrum_systems.modules.runtime.adaptive_execution_observability import (
    build_adaptive_execution_observability,
    build_adaptive_execution_policy_review,
    build_adaptive_execution_trend_report,
)
from spectrum_systems.modules.runtime.roadmap_multi_batch_executor import execute_bounded_roadmap_run
from spectrum_systems.modules.runtime.system_integration_validator import validate_core_system_integration


class SystemCycleOperatorError(ValueError):
    """Raised when a system cycle cannot be produced deterministically."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _validate_schema(instance: dict[str, Any], schema_name: str) -> None:
    validator = Draft202012Validator(load_schema(schema_name), format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda err: list(err.absolute_path))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise SystemCycleOperatorError(f"{schema_name} validation failed: {details}")


def _next_not_started_batch_id(roadmap_artifact: dict[str, Any]) -> str | None:
    for batch in roadmap_artifact.get("batches", []):
        if isinstance(batch, dict) and batch.get("status") == "not_started":
            batch_id = batch.get("batch_id")
            if isinstance(batch_id, str):
                return batch_id
    return None


def _required_reviews(blocking_conditions: list[str]) -> list[str]:
    reviews: set[str] = set()
    for code in blocking_conditions:
        if code.startswith("AUTH_"):
            reviews.add("control_authority_review")
        if code.startswith("PROP_"):
            reviews.add("cross_layer_propagation_review")
        if code.startswith("REPLAY_"):
            reviews.add("replay_chain_review")
        if code.startswith("CERTIFICATION_"):
            reviews.add("certification_gate_review")
        if code.startswith("DETERMINISM_"):
            reviews.add("determinism_review")
    return sorted(reviews)


def _root_cause(stop_reason: str, blocking_conditions: list[str]) -> str:
    if blocking_conditions:
        return f"blocking_condition:{blocking_conditions[0]} (stop_reason={stop_reason})"
    return f"execution_stop_reason:{stop_reason}"


def _root_cause_chain(stop_reason: str, blocking_conditions: list[str]) -> list[dict[str, str]]:
    if not blocking_conditions:
        return [
            {"step": "bounded_execution", "reason": stop_reason},
            {"step": "integration_validation", "reason": "no_blocking_conditions"},
            {"step": "control_outcome", "reason": "proceed_or_continue"},
        ]
    primary = blocking_conditions[0]
    return [
        {"step": "review_or_input_condition", "reason": primary},
        {"step": "evaluation_or_propagation_gap", "reason": "eval_or_propagation_missing"},
        {"step": "control_gate", "reason": "control_block"},
    ]


def _next_action(stop_reason: str, blocking_conditions: list[str]) -> str:
    if blocking_conditions:
        return f"resolve blocker {blocking_conditions[0]} and rerun bounded governed cycle"
    if stop_reason == "max_batches_reached":
        return "run next governed cycle to continue roadmap progression"
    if stop_reason in {"authorization_block", "missing_required_signal", "authorization_freeze"}:
        return "satisfy authorization constraints before rerun"
    if stop_reason == "no_eligible_batch":
        return "refresh roadmap and signal readiness before rerun"
    return "inspect run artifacts and remediate before rerun"


def _watchouts(stop_reason: str, blocking_conditions: list[str], required_reviews: list[str]) -> list[str]:
    watchouts = [
        f"stop_reason={stop_reason}",
        "do_not_bypass_fail_closed_authority_boundaries",
    ]
    if blocking_conditions:
        watchouts.append(f"primary_blocker={blocking_conditions[0]}")
    if required_reviews:
        watchouts.append(f"required_reviews={','.join(required_reviews)}")
    return watchouts


def _resolve_remediation_risk_level(stop_reason: str, blocking_conditions: list[str], required_reviews: list[str]) -> str:
    if blocking_conditions or required_reviews:
        return "high"
    if stop_reason == "max_batches_reached":
        return "low"
    return "medium"


def _build_remediation_steps(
    *,
    stop_reason: str,
    root_cause_chain: list[dict[str, str]],
    blocking_conditions: list[str],
    required_reviews: list[str],
    required_artifacts: list[str],
    review_control_signal: dict[str, Any],
    trace_id: str,
) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    normalized_chain = [item for item in root_cause_chain if isinstance(item, dict)]
    primary_chain_reason = str(normalized_chain[0].get("reason") if normalized_chain else stop_reason)
    repeated_pattern = stop_reason == "repeated_failure_pattern"

    steps.append(
        {
            "step_id": "RMS-01",
            "action": "confirm_root_cause_chain",
            "why": f"stopped_at={stop_reason}; primary_chain_reason={primary_chain_reason}",
            "required_artifacts": sorted(set(required_artifacts + [f"trace:{trace_id}"])),
            "trace_refs": [trace_id, f"stop_reason:{stop_reason}"],
        }
    )

    if required_reviews:
        steps.append(
            {
                "step_id": "RMS-02",
                "action": f"run_required_review:{required_reviews[0]}",
                "why": f"required_reviews={','.join(required_reviews)}",
                "required_artifacts": sorted(set(required_artifacts + [f"review_control_signal:{review_control_signal.get('signal_id', 'missing')}"])),
                "trace_refs": [trace_id, f"review:{required_reviews[0]}"],
            }
        )

    if stop_reason == "contract_precondition_failed":
        steps.append(
            {
                "step_id": "RMS-03",
                "action": "update_contract_or_input_schema",
                "why": "stop_reason indicates contract precondition mismatch",
                "required_artifacts": sorted(set(required_artifacts + ["contracts/schemas/*"])),
                "trace_refs": [trace_id, "contract:precondition_failed"],
            }
        )
    elif stop_reason in {"missing_required_signal", "replay_not_ready"} or blocking_conditions:
        missing_target = blocking_conditions[0] if blocking_conditions else stop_reason
        steps.append(
            {
                "step_id": "RMS-03",
                "action": f"fix_missing_artifact_or_signal:{missing_target}",
                "why": f"bounded run cannot continue until {missing_target} is satisfied",
                "required_artifacts": sorted(set(required_artifacts + [f"blocking_condition:{missing_target}"])),
                "trace_refs": [trace_id, f"missing:{missing_target}"],
            }
        )

    if repeated_pattern:
        steps.append(
            {
                "step_id": "RMS-04",
                "action": "reuse_known_repeated_failure_playbook",
                "why": "repeated_failure_pattern matched deterministic remediation template",
                "required_artifacts": sorted(set(required_artifacts + ["known_failure_pattern:repeated_failure_pattern"])),
                "trace_refs": [trace_id, "pattern:repeated_failure_pattern"],
            }
        )

    steps.append(
        {
            "step_id": "RMS-05",
            "action": "rerun_bounded_batch_cycle",
            "why": "verify remediation resolves stop condition without bypassing governance",
            "required_artifacts": sorted(set(required_artifacts)),
            "trace_refs": [trace_id, "rerun:bounded_cycle"],
        }
    )
    return steps[:5]


def _build_remediation_plan(
    *,
    run_result: dict[str, Any],
    stop_reason: str,
    root_cause: str,
    root_cause_chain: list[dict[str, str]],
    blocking_conditions: list[str],
    required_reviews: list[str],
    integration: dict[str, Any],
    timestamp: str,
    required_artifacts: list[str],
    review_control_signal: dict[str, Any],
) -> dict[str, Any]:
    trace_id = str(integration["trace_id"])
    step_payload = {
        "stop_reason": stop_reason,
        "root_cause_chain": root_cause_chain,
        "blocking_conditions": blocking_conditions,
        "required_reviews": required_reviews,
        "trace_id": trace_id,
    }
    remediation_steps = _build_remediation_steps(
        stop_reason=stop_reason,
        root_cause_chain=root_cause_chain,
        blocking_conditions=blocking_conditions,
        required_reviews=required_reviews,
        required_artifacts=required_artifacts,
        review_control_signal=review_control_signal,
        trace_id=trace_id,
    )
    expected_outcome = (
        "restore bounded continuation readiness"
        if stop_reason != "max_batches_reached"
        else "continue deterministic roadmap progression in next governed cycle"
    )
    return {
        "plan_id": f"RMP-{_canonical_hash({'run_id': run_result['run_id'], 'trace_id': trace_id, 'stop_reason': stop_reason, 'steps': step_payload})[:12].upper()}",
        "root_cause": root_cause,
        "remediation_steps": remediation_steps,
        "required_artifacts": sorted(set(required_artifacts)),
        "expected_outcome": expected_outcome,
        "risk_level": _resolve_remediation_risk_level(stop_reason, blocking_conditions, required_reviews),
        "created_at": timestamp,
        "trace_id": trace_id,
    }


def _candidate_action(candidate_type: str, *, next_batch_id: str | None, blocker: str | None, review: str | None) -> str:
    if candidate_type == "execute_next_batch":
        return f"execute next governed cycle for {next_batch_id}" if next_batch_id else "refresh roadmap eligibility before execution"
    if candidate_type == "resolve_blocker":
        return f"resolve blocker {blocker} and rerun bounded governed cycle"
    if candidate_type == "complete_review":
        return f"complete required review {review} before next execution"
    if candidate_type == "stabilize_repeated_risk":
        return "stabilize repeated risk pattern before continuing roadmap execution"
    return "inspect governed artifacts and remediate before rerun"


def _candidate_required_artifacts(run_id: str, validation_id: str, replay_refs: list[str], *, blocker: str | None) -> list[str]:
    artifacts = {
        f"roadmap_multi_batch_run_result:{run_id}",
        f"core_system_integration_validation:{validation_id}",
    } | set(replay_refs)
    if blocker:
        artifacts.add(f"blocking_condition:{blocker}")
    return sorted(artifacts)


def _replay_entry_points(
    *,
    trace_id: str,
    run_id: str,
    validation_id: str,
    blocker_refs: list[str],
    trace_navigation: dict[str, Any],
) -> dict[str, dict[str, list[str]]]:
    trace_nav_ref = f"trace_navigation:{validation_id}"
    execution_ref = f"roadmap_multi_batch_run_result:{run_id}"
    validation_ref = f"core_system_integration_validation:{validation_id}"
    return {
        "replay_from_context": {
            "required_artifacts": sorted(
                set(
                    [
                        validation_ref,
                        trace_navigation["execution_path"][2],
                        trace_navigation["execution_path"][3],
                    ]
                )
            ),
            "trace_refs": [trace_id, trace_nav_ref],
        },
        "replay_from_plan": {
            "required_artifacts": sorted(
                set(
                    [
                        validation_ref,
                        trace_navigation["execution_path"][0],
                        trace_navigation["execution_path"][1],
                    ]
                )
            ),
            "trace_refs": [trace_id, trace_nav_ref],
        },
        "replay_from_execution": {
            "required_artifacts": sorted(
                set(
                    [
                        execution_ref,
                        validation_ref,
                    ]
                )
            ),
            "trace_refs": [trace_id, execution_ref],
        },
        "replay_from_failure": {
            "required_artifacts": sorted(set([validation_ref] + blocker_refs)),
            "trace_refs": [trace_id, validation_ref],
        },
    }


def _generate_candidates(
    *,
    next_batch_id: str | None,
    run_result: dict[str, Any],
    integration: dict[str, Any],
    required_reviews: list[str],
    blocking_conditions: list[str],
    replay_refs: list[str],
    program_artifact: dict[str, Any],
    context_bundle: dict[str, Any],
    review_control_signal: dict[str, Any],
    control_decision: dict[str, Any],
) -> list[dict[str, Any]]:
    run_id = str(run_result["run_id"])
    validation_id = str(integration["validation_id"])
    deterministic_outcome = str(integration.get("deterministic_outcome", "blocked"))
    authority_status = str(integration.get("authority_boundary_status", "violated"))
    control_state = str(control_decision.get("decision") or run_result.get("stop_reason") or "unknown")
    program_priority = str(program_artifact.get("priority") or "roadmap_progression")
    context_risks = [str(item) for item in (context_bundle.get("risks") or []) if str(item).strip()]
    gate_assessment = str(review_control_signal.get("gate_assessment") or "UNKNOWN")

    candidates: list[dict[str, Any]] = []

    candidates.append(
        {
            "candidate_id": "NSC-EXECUTE-NEXT-BATCH",
            "action": _candidate_action("execute_next_batch", next_batch_id=next_batch_id, blocker=None, review=None),
            "required_artifacts": _candidate_required_artifacts(run_id, validation_id, replay_refs, blocker=None),
            "blockers": sorted(set(blocking_conditions + (["no_eligible_batch"] if next_batch_id is None else []))),
            "risk_profile": {
                "level": "high" if blocking_conditions else ("medium" if next_batch_id is None else "low"),
                "signals": sorted(
                    set(
                        [
                            f"deterministic_outcome={deterministic_outcome}",
                            f"authority_boundary_status={authority_status}",
                            f"control_state={control_state}",
                        ]
                        + [f"context_risk={risk}" for risk in context_risks]
                    )
                ),
            },
            "alignment_with_program": {
                "priority": program_priority,
                "justification": "Advances roadmap progression when eligible and unblocked.",
            },
        }
    )

    for blocker in sorted(set(blocking_conditions)):
        candidates.append(
            {
                "candidate_id": f"NSC-RESOLVE-{blocker}",
                "action": _candidate_action("resolve_blocker", next_batch_id=None, blocker=blocker, review=None),
                "required_artifacts": _candidate_required_artifacts(run_id, validation_id, replay_refs, blocker=blocker),
                "blockers": [blocker],
                "risk_profile": {
                    "level": "high",
                    "signals": [f"blocking_condition={blocker}", f"control_state={control_state}"],
                },
                "alignment_with_program": {
                    "priority": "risk_reduction",
                    "justification": "Unblocks deterministic continuation by removing a current hard blocker.",
                },
            }
        )

    for review in sorted(set(required_reviews)):
        candidates.append(
            {
                "candidate_id": f"NSC-REVIEW-{review}",
                "action": _candidate_action("complete_review", next_batch_id=None, blocker=None, review=review),
                "required_artifacts": _candidate_required_artifacts(run_id, validation_id, replay_refs, blocker=None),
                "blockers": [] if review in required_reviews else [f"review_not_required:{review}"],
                "risk_profile": {
                    "level": "medium",
                    "signals": [f"required_review={review}", f"gate_assessment={gate_assessment}"],
                },
                "alignment_with_program": {
                    "priority": "review_readiness",
                    "justification": "Satisfies mandatory review requirements before execution.",
                },
            }
        )

    repeated_risk = any(code.startswith("PROP_") for code in blocking_conditions) or bool(
        integration.get("repeated_failure_patterns")
    )
    if repeated_risk:
        candidates.append(
            {
                "candidate_id": "NSC-STABILIZE-REPEATED-RISK",
                "action": _candidate_action("stabilize_repeated_risk", next_batch_id=None, blocker=None, review=None),
                "required_artifacts": _candidate_required_artifacts(run_id, validation_id, replay_refs, blocker=None),
                "blockers": sorted(set(blocking_conditions)),
                "risk_profile": {
                    "level": "high",
                    "signals": sorted(set(["repeated_failure_pattern_detected"] + [f"blocker={b}" for b in blocking_conditions])),
                },
                "alignment_with_program": {
                    "priority": "risk_reduction",
                    "justification": "Addresses recurring failure patterns before roadmap expansion.",
                },
            }
        )

    return candidates[:8]


def _score_candidate(candidate: dict[str, Any], *, next_batch_id: str | None, required_reviews: list[str]) -> dict[str, int]:
    blockers = [str(item) for item in candidate.get("blockers", [])]
    risk_level = str(candidate.get("risk_profile", {}).get("level", "medium"))
    priority = str(candidate.get("alignment_with_program", {}).get("priority", ""))
    action = str(candidate.get("action", ""))

    has_active_blockers = bool(blockers)
    program_alignment = 5 if "roadmap_progression" in priority else (4 if "risk_reduction" in priority else 3)
    if next_batch_id is None and "execute next governed cycle" in action:
        program_alignment = 1
    if has_active_blockers and "execute next governed cycle" in action:
        program_alignment = 1

    unblock_potential = 5 if action.startswith("resolve blocker ") else (2 if blockers else 1)
    risk_reduction = 5 if "risk_reduction" in priority else (4 if risk_level == "high" else 2)
    dependency_readiness = 5 if not blockers else 1
    review_readiness = 5 if "complete required review" in action and required_reviews else (3 if not required_reviews else 2)
    return {
        "program_alignment": program_alignment,
        "unblock_potential": unblock_potential,
        "risk_reduction": risk_reduction,
        "dependency_readiness": dependency_readiness,
        "review_readiness": review_readiness,
    }


def _rank_candidates(
    candidates: list[dict[str, Any]], *, next_batch_id: str | None, required_reviews: list[str]
) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for candidate in candidates:
        factors = _score_candidate(candidate, next_batch_id=next_batch_id, required_reviews=required_reviews)
        total = (
            factors["program_alignment"] * 100
            + factors["unblock_potential"] * 10
            + factors["risk_reduction"] * 5
            + factors["dependency_readiness"] * 3
            + factors["review_readiness"]
        )
        ranked.append(
            {
                "candidate": candidate,
                "score": total,
                "ranking_factors": factors,
            }
        )
    return sorted(ranked, key=lambda item: (-item["score"], item["candidate"]["candidate_id"]))


def run_system_cycle(
    *,
    roadmap_artifact: dict[str, Any],
    selection_signals: dict[str, Any],
    authorization_signals: dict[str, Any],
    integration_inputs: dict[str, Any],
    pqx_state_path: Path,
    pqx_runs_root: Path,
    execution_policy: dict[str, Any] | None = None,
    source_refs: list[str] | None = None,
    created_at: str | None = None,
    pqx_execute_fn: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run one full bounded system cycle and emit operator-focused summary artifacts."""
    timestamp = created_at or _utc_now()

    multi_batch = execute_bounded_roadmap_run(
        roadmap_artifact,
        selection_signals,
        authorization_signals,
        pqx_state_path=pqx_state_path,
        pqx_runs_root=pqx_runs_root,
        execution_policy=execution_policy,
        evaluated_at=timestamp,
        executed_at=timestamp,
        validated_at=timestamp,
        run_executed_at=timestamp,
        source_refs=source_refs,
        pqx_execute_fn=pqx_execute_fn,
    )
    run_result = multi_batch["run_result"]
    updated_roadmap = multi_batch["roadmap"]

    if not isinstance(integration_inputs, dict):
        raise SystemCycleOperatorError("integration_inputs must be an object")

    roadmap_loop_validation = dict(integration_inputs.get("roadmap_loop_validation") or {})
    if "validation_id" not in roadmap_loop_validation and run_result.get("loop_validation_refs"):
        roadmap_loop_validation["validation_id"] = str(run_result["loop_validation_refs"][-1])
    if "determinism_status" not in roadmap_loop_validation:
        roadmap_loop_validation["determinism_status"] = "deterministic"

    roadmap_multi_batch_result = dict(run_result)
    overrides = integration_inputs.get("roadmap_multi_batch_result_overrides")
    if isinstance(overrides, dict):
        roadmap_multi_batch_result.update(overrides)
    roadmap_multi_batch_result.setdefault("program_constraints_applied", True)

    integration = validate_core_system_integration(
        program_artifact=dict(integration_inputs.get("program_artifact") or {}),
        review_control_signal=dict(integration_inputs.get("review_control_signal") or {}),
        eval_result=dict(integration_inputs.get("eval_result") or {}),
        context_bundle=dict(integration_inputs.get("context_bundle") or {}),
        tpa_gate=dict(integration_inputs.get("tpa_gate") or {}),
        roadmap_loop_validation=roadmap_loop_validation,
        roadmap_multi_batch_result=roadmap_multi_batch_result,
        control_decision=dict(integration_inputs.get("control_decision") or {}),
        certification_pack=dict(integration_inputs.get("certification_pack") or {}),
        validation_scope=dict(integration_inputs.get("validation_scope") or {}),
        trace_id=str(integration_inputs.get("trace_id") or authorization_signals.get("trace_id") or ""),
        source_refs=dict(integration_inputs.get("source_refs") or {}),
        created_at=timestamp,
    )

    blocking_conditions = [str(item) for item in integration.get("blocking_conditions", [])]
    replay_refs = sorted(set(str(item) for item in run_result.get("loop_validation_refs", [])))
    trace_navigation = dict(integration.get("trace_navigation") or {})
    validation_id = str(integration["validation_id"])
    replay_entry_points = _replay_entry_points(
        trace_id=integration["trace_id"],
        run_id=str(run_result["run_id"]),
        validation_id=validation_id,
        blocker_refs=blocking_conditions,
        trace_navigation=trace_navigation,
    )
    next_batch_id = _next_not_started_batch_id(updated_roadmap)
    required_reviews = _required_reviews(blocking_conditions)
    why = [
        f"bounded_stop_reason={run_result['stop_reason']}",
        f"integration_outcome={integration['deterministic_outcome']}",
        f"authority_boundary_status={integration['authority_boundary_status']}",
    ]
    if next_batch_id is not None:
        why.append(f"next_eligible_candidate={next_batch_id}")
    else:
        why.append("no_remaining_not_started_batch")

    risk_signals = [
        f"determinism_status={integration['determinism_status']}",
        f"replay_status={integration['replay_status']}",
        f"blocking_conditions={len(blocking_conditions)}",
    ]
    risk_level = "high" if blocking_conditions else ("medium" if run_result["stop_reason"] != "max_batches_reached" else "low")

    candidates = _generate_candidates(
        next_batch_id=next_batch_id,
        run_result=run_result,
        integration=integration,
        required_reviews=required_reviews,
        blocking_conditions=blocking_conditions,
        replay_refs=replay_refs,
        program_artifact=dict(integration_inputs.get("program_artifact") or {}),
        context_bundle=dict(integration_inputs.get("context_bundle") or {}),
        review_control_signal=dict(integration_inputs.get("review_control_signal") or {}),
        control_decision=dict(integration_inputs.get("control_decision") or {}),
    )
    ranked_candidates = _rank_candidates(candidates, next_batch_id=next_batch_id, required_reviews=required_reviews)
    selected_candidate = ranked_candidates[0]["candidate"]
    selected_factors = ranked_candidates[0]["ranking_factors"]
    why_not_selected = [
        {
            "candidate_id": item["candidate"]["candidate_id"],
            "reason": (
                "lower_priority"
                if item["score"] < ranked_candidates[0]["score"]
                else "tie_broken_by_candidate_id"
            ),
            "score": item["score"],
        }
        for item in ranked_candidates[1:]
    ]

    adaptive_inputs = integration_inputs.get("adaptive_observability_run_results")
    adaptive_run_results = [dict(item) for item in adaptive_inputs] if isinstance(adaptive_inputs, list) else []
    adaptive_run_results.append(dict(run_result))
    adaptive_observability = build_adaptive_execution_observability(
        adaptive_run_results,
        trace_id=integration["trace_id"],
        source_refs=[
            f"roadmap_multi_batch_run_result:{str(item.get('run_id') or 'unknown')}" for item in adaptive_run_results
        ],
        created_at=timestamp,
    )
    adaptive_trend_report = build_adaptive_execution_trend_report(
        adaptive_run_results,
        observability=adaptive_observability,
        trace_id=integration["trace_id"],
        created_at=timestamp,
    )
    adaptive_policy_review = build_adaptive_execution_policy_review(
        adaptive_run_results,
        observability=adaptive_observability,
        trend_report=adaptive_trend_report,
        trace_id=integration["trace_id"],
        created_at=timestamp,
    )
    adaptive_observability_ref = f"adaptive_execution_observability:{adaptive_observability['observability_id']}"
    adaptive_trend_ref = f"adaptive_execution_trend_report:{adaptive_trend_report['trend_report_id']}"
    adaptive_policy_review_ref = f"adaptive_execution_policy_review:{adaptive_policy_review['review_id']}"

    stop_reason = str(run_result["stop_reason"])
    continuation_sequence = list(run_result.get("continuation_decision_sequence", []))
    last_continuation_decision = (
        str(continuation_sequence[-1].get("decision")) if continuation_sequence else ("stop" if stop_reason != "max_batches_reached" else "continue")
    )
    failure_root_cause = _root_cause(stop_reason, blocking_conditions)
    failure_root_cause_chain = _root_cause_chain(stop_reason, blocking_conditions)
    failure_next_action = _next_action(stop_reason, blocking_conditions)
    remediation_plan = _build_remediation_plan(
        run_result=run_result,
        stop_reason=stop_reason,
        root_cause=failure_root_cause,
        root_cause_chain=failure_root_cause_chain,
        blocking_conditions=blocking_conditions,
        required_reviews=required_reviews,
        integration=integration,
        timestamp=timestamp,
        required_artifacts=selected_candidate["required_artifacts"],
        review_control_signal=dict(integration_inputs.get("review_control_signal") or {}),
    )
    remediation_plan_ref = f"remediation_plan:{remediation_plan['plan_id']}"

    recommendation = {
        "recommendation_id": f"NSR-{_canonical_hash({'run_id': run_result['run_id'], 'at': timestamp})[:12].upper()}",
        "schema_version": "1.5.0",
        "next_batch_id": next_batch_id,
        "continuation_decision": last_continuation_decision,
        "stop_reason": stop_reason,
        "next_batch_candidate": next_batch_id,
        "why": sorted(
            set(
                why
                + [
                    f"adaptive_guardrail_status={adaptive_trend_report['guardrail_status']}",
                    f"adaptive_useful_batches_per_run={adaptive_observability['average_useful_batches_per_run']}",
                    f"adaptive_policy_review={adaptive_policy_review['review_id']}",
                ]
            )
        ),
        "blockers": sorted(set(blocking_conditions)),
        "required_reviews": required_reviews,
        "risk_summary": {
            "level": risk_level,
            "signals": sorted(
                set(
                    risk_signals
                    + [
                        f"adaptive_guardrail_status={adaptive_trend_report['guardrail_status']}",
                        f"adaptive_safety_trend={adaptive_trend_report['safety_trend']}",
                    ]
                )
            ),
        },
        "next_step": {
            "action": selected_candidate["action"],
            "why_now": (
                f"selected {selected_candidate['candidate_id']} via deterministic ranking: "
                f"program_alignment={selected_factors['program_alignment']}, "
                f"unblock_potential={selected_factors['unblock_potential']}, "
                f"risk_reduction={selected_factors['risk_reduction']}, "
                f"dependency_readiness={selected_factors['dependency_readiness']}, "
                f"review_readiness={selected_factors['review_readiness']}"
            ),
            "blocked_by": selected_candidate["blockers"],
            "watchouts": sorted(
                set(
                    _watchouts(str(run_result["stop_reason"]), blocking_conditions, required_reviews)
                    + [f"control_state={integration_inputs.get('control_decision', {}).get('decision', 'unknown')}"]
                )
            ),
            "required_artifacts": selected_candidate["required_artifacts"],
        },
        "remediation_plan_ref": remediation_plan_ref,
        "remediation_steps": remediation_plan["remediation_steps"],
        "remediation_plan": remediation_plan,
        "candidate_evaluation": {
            "ranking_policy": "program_alignment>unblock_potential>risk_reduction>dependency_readiness>review_readiness",
            "candidates": [
                {
                    **item["candidate"],
                    "score": item["score"],
                    "ranking_factors": item["ranking_factors"],
                }
                for item in ranked_candidates
            ],
            "why_not_selected": why_not_selected,
        },
        "artifact_refs": {
            "roadmap_multi_batch_run_result": f"roadmap_multi_batch_run_result:{run_result['run_id']}",
            "core_system_integration_validation": f"core_system_integration_validation:{validation_id}",
            "trace_id": integration["trace_id"],
            "replay_refs": replay_refs,
            "upstream_refs": sorted(set(integration.get("upstream_refs", []))),
            "downstream_refs": [f"build_summary:BSR-{_canonical_hash({'run_id': run_result['run_id'], 'trace_id': integration['trace_id']})[:12].upper()}"],
            "related_artifacts": sorted(
                set(
                    [
                        f"roadmap_multi_batch_run_result:{run_result['run_id']}",
                        f"core_system_integration_validation:{validation_id}",
                        adaptive_observability_ref,
                        adaptive_trend_ref,
                        adaptive_policy_review_ref,
                        remediation_plan_ref,
                    ]
                    + replay_refs
                    + list(integration.get("related_artifacts", []))
                )
            ),
        },
        "trace_navigation": trace_navigation,
        "replay_entry_points": replay_entry_points,
        "quick_links": [
            f"view trace -> trace_navigation:{validation_id}",
            "replay this step -> replay_from_execution",
            "inspect failure chain -> replay_from_failure",
        ],
        "trace_id": integration["trace_id"],
        "created_at": timestamp,
        "source_refs": sorted(
            set(
                [
                    f"roadmap_multi_batch_run_result:{run_result['run_id']}",
                    f"core_system_integration_validation:{validation_id}",
                    adaptive_observability_ref,
                    adaptive_trend_ref,
                    remediation_plan_ref,
                ]
                + list(source_refs or [])
            )
        ),
    }
    _validate_schema(recommendation, "next_step_recommendation")

    summary = {
        "summary_id": f"BSR-{_canonical_hash({'run_id': run_result['run_id'], 'trace_id': integration['trace_id']})[:12].upper()}",
        "schema_version": "1.3.0",
        "run_id": run_result["run_id"],
        "continuation_decision": last_continuation_decision,
        "stop_reason": stop_reason,
        "next_batch_candidate": next_batch_id,
        "what_ran": [
            "roadmap selection",
            "control authorization",
            "bounded execution (RDX-006)",
            "integration validation (BATCH-Z)",
        ],
        "what_changed": [
            f"attempted_batches={','.join(run_result['attempted_batch_ids']) or 'none'}",
            f"completed_batches={','.join(run_result['completed_batch_ids']) or 'none'}",
        ],
        "what_failed": sorted(set(blocking_conditions + ([stop_reason] if stop_reason != "max_batches_reached" else []))),
        "run_outcome": {
            "status": "blocked" if blocking_conditions or stop_reason != "max_batches_reached" else "success",
            "stop_reason": stop_reason,
            "has_blockers": bool(blocking_conditions),
        },
        "watch_next": [
            f"next_batch_id={next_batch_id or 'none'}",
            f"next_action={failure_next_action}",
                f"adaptive_safety_trend={adaptive_trend_report['safety_trend']}",
                f"adaptive_guardrail_status={adaptive_trend_report['guardrail_status']}",
                f"adaptive_tuning_warranted={str(adaptive_trend_report['tuning_warranted']).lower()}",
                f"adaptive_policy_tuning_signal={adaptive_policy_review['operator_tuning_signals'][0]}",
            ],
        "artifact_index": {
            "roadmap_multi_batch_run_result": f"roadmap_multi_batch_run_result:{run_result['run_id']}",
            "core_system_integration_validation": f"core_system_integration_validation:{validation_id}",
            "next_step_recommendation": f"next_step_recommendation:{recommendation['recommendation_id']}",
            "trace_id": integration["trace_id"],
            "replay_refs": replay_refs,
            "upstream_refs": sorted(set(integration.get("upstream_refs", []))),
            "downstream_refs": [f"next_step_recommendation:{recommendation['recommendation_id']}"],
            "related_artifacts": sorted(
                set(
                    [
                        f"roadmap_multi_batch_run_result:{run_result['run_id']}",
                        f"core_system_integration_validation:{validation_id}",
                        f"next_step_recommendation:{recommendation['recommendation_id']}",
                        adaptive_observability_ref,
                        adaptive_trend_ref,
                        adaptive_policy_review_ref,
                        remediation_plan_ref,
                    ]
                    + replay_refs
                    + list(integration.get("related_artifacts", []))
                )
            ),
        },
        "failure_surface": {
            "stop_reason": stop_reason,
            "root_cause": failure_root_cause,
            "root_cause_chain": failure_root_cause_chain,
            "next_action": failure_next_action,
            "blocker_refs": sorted(set(blocking_conditions)),
            "source_refs": sorted(
                {
                    f"core_system_integration_validation:{validation_id}",
                    f"roadmap_multi_batch_run_result:{run_result['run_id']}",
                }
                | set(replay_refs)
            ),
        },
        "trace_navigation": trace_navigation,
        "replay_entry_points": replay_entry_points,
        "quick_links": [
            f"view trace -> trace_navigation:{validation_id}",
            "replay this step -> replay_from_execution",
            "inspect failure chain -> replay_from_failure",
        ],
        "trace_id": integration["trace_id"],
        "created_at": timestamp,
        "source_refs": sorted(
            {
                f"roadmap_multi_batch_run_result:{run_result['run_id']}",
                f"core_system_integration_validation:{integration['validation_id']}",
                f"next_step_recommendation:{recommendation['recommendation_id']}",
                remediation_plan_ref,
                adaptive_observability_ref,
                adaptive_trend_ref,
                adaptive_policy_review_ref,
            }
        ),
    }
    _validate_schema(summary, "build_summary")

    return {
        "updated_roadmap": updated_roadmap,
        "roadmap_multi_batch_run_result": run_result,
        "adaptive_execution_observability": adaptive_observability,
        "adaptive_execution_trend_report": adaptive_trend_report,
        "adaptive_execution_policy_review": adaptive_policy_review,
        "core_system_integration_validation": integration,
        "next_step_recommendation": recommendation,
        "build_summary": summary,
    }


__all__ = ["SystemCycleOperatorError", "run_system_cycle"]
