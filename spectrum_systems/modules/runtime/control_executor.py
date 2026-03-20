"""Control Signal Consumption Layer (BN.6).

Consumes BN.5 ``control_signals`` as the single source of truth for runtime
execution behavior. This module does not re-derive gating/enforcement logic;
it only executes the explicit instructions encoded in control signals.

BN.8 integration: validator resolution and execution is delegated entirely to
:mod:`spectrum_systems.modules.runtime.validator_engine`.  No local validator
registry logic is maintained here.
"""

from __future__ import annotations

import copy
from typing import Any, Callable, Dict, List, Optional, Tuple

from jsonschema import Draft202012Validator

from spectrum_systems.contracts import load_schema
from spectrum_systems.modules.runtime.contract_runtime import (
    ContractRuntimeError,
    ensure_contract_runtime_available,
)
from spectrum_systems.modules.runtime.control_signals import (
    CONTINUATION_MODE_CONTINUE,
    CONTINUATION_MODE_CONTINUE_WITH_MONITORING,
    CONTINUATION_MODE_STOP,
    CONTINUATION_MODE_STOP_AND_ESCALATE,
    CONTINUATION_MODE_STOP_AND_REPAIR,
    CONTINUATION_MODE_STOP_AND_RERUN,
)
from spectrum_systems.modules.runtime.validator_engine import (
    run_validators,
    summarize_validator_execution,
)
from spectrum_systems.modules.runtime.slo_evaluator import (
    map_validator_results_to_slis,
    compute_slo_status,
)
from spectrum_systems.modules.runtime.error_budget import (
    ErrorBudgetTracker,
    update_error_budget,
    compute_burn_rate,
)
from spectrum_systems.modules.runtime.slo_enforcer import enforce_slo_policy
ExecutionAction = Dict[str, Any]
ValidatorResult = Dict[str, Any]


def _load_execution_result_schema() -> Dict[str, Any]:
    return load_schema("control_execution_result")


def validate_execution_result(execution_result: Dict[str, Any]) -> List[str]:
    schema = _load_execution_result_schema()
    validator = Draft202012Validator(schema)
    return [
        f"{'.'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
        for e in sorted(validator.iter_errors(execution_result), key=lambda e: list(e.absolute_path))
    ]


def _repair_registry() -> Dict[str, Callable[[str, Any, Dict[str, Any]], Tuple[bool, Dict[str, Any]]]]:
    return {
        "repair_schema_errors": lambda name, _artifact, _context: (
            True,
            {"repair_action": name, "status": "applied", "details": {"mode": "default"}},
        ),
        "repair_missing_inputs": lambda name, _artifact, _context: (
            False,
            {"repair_action": name, "status": "required", "details": {"reason": "manual_input_required"}},
        ),
        "restore_missing_lineage": lambda name, _artifact, _context: (
            False,
            {"repair_action": name, "status": "required", "details": {"reason": "lineage_registry_required"}},
        ),
        "rebuild_with_registry": lambda name, _artifact, _context: (
            False,
            {"repair_action": name, "status": "required", "details": {"reason": "rerun_pipeline_with_registry"}},
        ),
        "rerun_with_strict_validation": lambda name, _artifact, _context: (
            False,
            {"repair_action": name, "status": "required", "details": {"reason": "strict_validation_rerun_required"}},
        ),
        "escalate_for_manual_review": lambda name, _artifact, _context: (
            False,
            {"repair_action": name, "status": "required", "details": {"reason": "manual_review_required"}},
        ),
    }


def enforce_continuation_mode(control_signals: Dict[str, Any], actions_taken: List[ExecutionAction]) -> Dict[str, Any]:
    mode = control_signals.get("continuation_mode")
    allow_execution = mode in {CONTINUATION_MODE_CONTINUE, CONTINUATION_MODE_CONTINUE_WITH_MONITORING}
    blocked = mode in {
        CONTINUATION_MODE_STOP,
        CONTINUATION_MODE_STOP_AND_REPAIR,
        CONTINUATION_MODE_STOP_AND_RERUN,
        CONTINUATION_MODE_STOP_AND_ESCALATE,
    }
    actions_taken.append(
        {
            "action_type": "continuation_mode_enforced",
            "continuation_mode": mode,
            "allow_execution": allow_execution,
            "blocked": blocked,
        }
    )
    return {"continuation_mode": mode, "allow_execution": allow_execution, "blocked": blocked}


def _run_validators_with_result(
    control_signals: Dict[str, Any],
    context: Dict[str, Any],
    actions_taken: List[ExecutionAction],
) -> Tuple[List[str], List[str], bool, Dict[str, Any]]:
    """Execute required validators and return the full validator execution result.

    Returns ``(validators_run, validators_failed, fail_closed, ve_result)``.
    Internal use only; provides the validator execution result for downstream
    SLO pipeline integration.
    """
    required_validators = list(control_signals.get("required_validators") or [])
    ve_result = run_validators(required_validators, context)

    validators_run: List[str] = ve_result.get("validators_run") or []
    validators_failed: List[str] = ve_result.get("validators_failed") or []
    fail_closed = ve_result.get("overall_status") == "blocked"

    for vr in ve_result.get("validator_results") or []:
        vname = vr.get("validator_name", "<unknown>")
        vstatus = vr.get("status", "error")
        if vstatus == "blocked":
            action_type = "validator_missing"
        else:
            action_type = "validator_executed"
        actions_taken.append(
            {
                "action_type": action_type,
                "validator": vname,
                "success": vstatus == "pass",
                "details": vr.get("details") or {},
                "error": (vr.get("errors") or [None])[0],
            }
        )

    return validators_run, validators_failed, fail_closed, ve_result


def run_required_validators(
    control_signals: Dict[str, Any],
    context: Dict[str, Any],
    actions_taken: List[ExecutionAction],
) -> Tuple[List[str], List[str], bool]:
    """Execute required validators via BN.8 validator_engine.

    Delegates resolution, ordering, and structured execution to
    :func:`~spectrum_systems.modules.runtime.validator_engine.run_validators`.
    Returns ``(validators_run, validators_failed, fail_closed)`` for
    backward-compatible integration with the BN.6 execution flow.
    """
    validators_run, validators_failed, fail_closed, _ = _run_validators_with_result(
        control_signals, context, actions_taken
    )
    return validators_run, validators_failed, fail_closed


def apply_repair_actions(
    control_signals: Dict[str, Any],
    context: Dict[str, Any],
    actions_taken: List[ExecutionAction],
) -> List[Dict[str, Any]]:
    artifact = context.get("artifact")
    repair_registry = _repair_registry()
    repair_registry.update(context.get("repair_registry") or {})
    repair_actions_applied: List[Dict[str, Any]] = []

    for repair_action in list(control_signals.get("repair_actions") or []):
        fn = repair_registry.get(repair_action)
        if fn is None:
            item = {
                "repair_action": repair_action,
                "status": "required",
                "details": {"reason": "no_callable_registered"},
            }
            repair_actions_applied.append(item)
            actions_taken.append({"action_type": "repair_required", **item})
            continue

        _, outcome = fn(repair_action, artifact, context)
        repair_actions_applied.append(outcome)
        actions_taken.append({"action_type": "repair_action_processed", **outcome})

    return repair_actions_applied


def enforce_publication_policy(control_signals: Dict[str, Any], actions_taken: List[ExecutionAction]) -> bool:
    blocked = not bool(control_signals.get("publication_allowed"))
    actions_taken.append(
        {
            "action_type": "publication_policy_enforced",
            "publication_allowed": bool(control_signals.get("publication_allowed")),
            "publication_blocked": blocked,
        }
    )
    return blocked


def enforce_decision_grade_policy(control_signals: Dict[str, Any], actions_taken: List[ExecutionAction]) -> bool:
    blocked = not bool(control_signals.get("decision_grade_allowed"))
    actions_taken.append(
        {
            "action_type": "decision_grade_policy_enforced",
            "decision_grade_allowed": bool(control_signals.get("decision_grade_allowed")),
            "decision_blocked": blocked,
        }
    )
    return blocked


def handle_escalation(control_signals: Dict[str, Any], context: Dict[str, Any], actions_taken: List[ExecutionAction]) -> bool:
    should_escalate = bool(control_signals.get("escalation_required")) or (
        control_signals.get("continuation_mode") == CONTINUATION_MODE_STOP_AND_ESCALATE
    )
    if should_escalate:
        actions_taken.append(
            {
                "action_type": "escalation_event_emitted",
                "event": {
                    "event_type": "control_escalation_required",
                    "artifact_id": (context.get("artifact") or {}).get("artifact_id") if isinstance(context.get("artifact"), dict) else None,
                    "stage": context.get("stage"),
                },
            }
        )
    return should_escalate


def handle_human_review(control_signals: Dict[str, Any], context: Dict[str, Any], actions_taken: List[ExecutionAction]) -> bool:
    required = bool(control_signals.get("human_review_required"))
    if required:
        actions_taken.append(
            {
                "action_type": "human_review_required",
                "task": {
                    "task_type": "human_review",
                    "artifact_id": (context.get("artifact") or {}).get("artifact_id") if isinstance(context.get("artifact"), dict) else None,
                    "stage": context.get("stage"),
                },
            }
        )
    return required


def handle_rerun(control_signals: Dict[str, Any], context: Dict[str, Any], actions_taken: List[ExecutionAction]) -> bool:
    rerun = bool(control_signals.get("rerun_recommended")) or (
        control_signals.get("continuation_mode") == CONTINUATION_MODE_STOP_AND_RERUN
    )
    if rerun:
        actions_taken.append(
            {
                "action_type": "rerun_requested",
                "request": {
                    "request_type": "rerun",
                    "artifact_id": (context.get("artifact") or {}).get("artifact_id") if isinstance(context.get("artifact"), dict) else None,
                    "stage": context.get("stage"),
                    "safe_to_execute_immediately": False,
                },
            }
        )
    return rerun


def build_execution_result(
    *,
    execution_status: str,
    actions_taken: List[ExecutionAction],
    validators_run: List[str],
    validators_failed: List[str],
    repair_actions_applied: List[Dict[str, Any]],
    publication_blocked: bool,
    decision_blocked: bool,
    rerun_triggered: bool,
    escalation_triggered: bool,
    human_review_required: bool,
    slo_evaluation: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "execution_status": execution_status,
        "actions_taken": actions_taken,
        "validators_run": validators_run,
        "validators_failed": validators_failed,
        "repair_actions_applied": repair_actions_applied,
        "publication_blocked": publication_blocked,
        "decision_blocked": decision_blocked,
        "rerun_triggered": rerun_triggered,
        "escalation_triggered": escalation_triggered,
        "human_review_required": human_review_required,
    }
    if slo_evaluation is not None:
        result["slo_evaluation"] = slo_evaluation
    return result


def _run_slo_pipeline(
    ve_result: Dict[str, Any],
    actions_taken: List[ExecutionAction],
    tracker: Optional[ErrorBudgetTracker] = None,
) -> Dict[str, Any]:
    """Run the BH–BJ SLO control plane on a validator execution result.

    Steps:
    1. Map validator results to SLIs.
    2. Compute SLO status.
    3. Update error budget.
    4. Enforce SLO policy.
    5. Return a governed SLO evaluation result.

    Fail-closed: any internal error produces ``enforcement_action="block"``.

    When no ``tracker`` is provided a fresh :class:`ErrorBudgetTracker` is
    created for this call so that results are deterministic in isolation.
    This means the burn rate reflects only the current run (window size 1),
    which is useful for stateless or test scenarios.

    For production use where rolling-window history is required, callers
    should pass a persistent tracker via ``context["error_budget_tracker"]``
    in :func:`execute_control_signals`.
    """
    try:
        run_id = ve_result.get("execution_id", "unknown")
        slis = map_validator_results_to_slis(ve_result)
        slo_eval = compute_slo_status(slis)
        slo_status = slo_eval.get("slo_status", "breached")
        violations = slo_eval.get("violations", [])

        t = tracker if tracker is not None else ErrorBudgetTracker()
        update_error_budget(run_id, slo_status, slis, tracker=t)
        burn_rate = compute_burn_rate(tracker=t)

        enforcement = enforce_slo_policy(slo_status, burn_rate)

        slo_result: Dict[str, Any] = {
            "slo_status": slo_status,
            "slis": slis,
            "burn_rate": burn_rate,
            "enforcement_action": enforcement.get("action", "block"),
            "violations": violations,
            "enforcement_reason": enforcement.get("reason", ""),
        }

        actions_taken.append(
            {
                "action_type": "slo_evaluation_completed",
                "slo_status": slo_status,
                "enforcement_action": slo_result["enforcement_action"],
            }
        )
        return slo_result

    except Exception as exc:  # noqa: BLE001 — fail closed
        fallback: Dict[str, Any] = {
            "slo_status": "breached",
            "slis": {
                "completeness": 0.0,
                "timeliness": 0.0,
                "traceability": 0.0,
                "traceability_integrity": 0.0,
            },
            "burn_rate": {"overall": 1.0},
            "enforcement_action": "block",
            "violations": ["completeness", "timeliness", "traceability", "traceability_integrity"],
            "enforcement_reason": f"slo_pipeline_error: {exc}",
        }
        actions_taken.append(
            {
                "action_type": "slo_evaluation_error",
                "error": str(exc),
                "enforcement_action": "block",
            }
        )
        return fallback


def execute_control_signals(control_signals: Any, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    # BN.6.1: Fail closed if contract-validation runtime is unavailable.
    # ContractRuntimeError propagates to the caller — do not catch it here.
    ensure_contract_runtime_available()

    context = dict(context or {})
    if not isinstance(control_signals, dict):
        return build_execution_result(
            execution_status="blocked",
            actions_taken=[{"action_type": "control_signals_missing", "status": "blocked"}],
            validators_run=[],
            validators_failed=[],
            repair_actions_applied=[],
            publication_blocked=True,
            decision_blocked=True,
            rerun_triggered=False,
            escalation_triggered=True,
            human_review_required=True,
        )

    signals = copy.deepcopy(control_signals)
    actions_taken: List[ExecutionAction] = []

    slo_tracker: Optional[ErrorBudgetTracker] = context.get("error_budget_tracker")

    mode_state = enforce_continuation_mode(signals, actions_taken)
    validators_run, validators_failed, validator_missing, ve_result = _run_validators_with_result(
        signals, context, actions_taken
    )
    slo_evaluation = _run_slo_pipeline(ve_result, actions_taken, tracker=slo_tracker)
    repair_actions_applied = apply_repair_actions(signals, context, actions_taken)
    publication_blocked = enforce_publication_policy(signals, actions_taken)
    decision_blocked = enforce_decision_grade_policy(signals, actions_taken)
    escalation_triggered = handle_escalation(signals, context, actions_taken)
    human_review_required = handle_human_review(signals, context, actions_taken)
    rerun_triggered = handle_rerun(signals, context, actions_taken)

    mode = mode_state["continuation_mode"]
    if validator_missing or validators_failed:
        execution_status = "blocked"
    elif mode == CONTINUATION_MODE_STOP_AND_ESCALATE:
        execution_status = "escalated"
    elif mode == CONTINUATION_MODE_STOP_AND_REPAIR:
        execution_status = "repair_required"
    elif mode in {CONTINUATION_MODE_STOP, CONTINUATION_MODE_STOP_AND_RERUN}:
        execution_status = "blocked"
    elif publication_blocked or decision_blocked:
        execution_status = "blocked"
    elif mode in {CONTINUATION_MODE_CONTINUE, CONTINUATION_MODE_CONTINUE_WITH_MONITORING}:
        execution_status = "success"
    else:
        execution_status = "blocked"

    result = build_execution_result(
        execution_status=execution_status,
        actions_taken=actions_taken,
        validators_run=validators_run,
        validators_failed=validators_failed,
        repair_actions_applied=repair_actions_applied,
        publication_blocked=publication_blocked,
        decision_blocked=decision_blocked,
        rerun_triggered=rerun_triggered,
        escalation_triggered=escalation_triggered,
        human_review_required=human_review_required,
        slo_evaluation=slo_evaluation,
    )

    schema_errors = validate_execution_result(result)
    if schema_errors:
        blocked_result = copy.deepcopy(result)
        blocked_result["execution_status"] = "blocked"
        blocked_result["actions_taken"].append(
            {
                "action_type": "execution_result_schema_invalid",
                "errors": schema_errors,
            }
        )
        return blocked_result
    return result


def summarize_execution_result(execution_result: Dict[str, Any]) -> str:
    return "\n".join(
        [
            "Control Execution Result (BN.6)",
            "-----------------------------",
            f"  execution_status      : {execution_result.get('execution_status')}",
            f"  publication_blocked   : {execution_result.get('publication_blocked')}",
            f"  decision_blocked      : {execution_result.get('decision_blocked')}",
            f"  rerun_triggered       : {execution_result.get('rerun_triggered')}",
            f"  escalation_triggered  : {execution_result.get('escalation_triggered')}",
            f"  human_review_required : {execution_result.get('human_review_required')}",
            f"  validators_run        : {execution_result.get('validators_run')}",
            f"  validators_failed     : {execution_result.get('validators_failed')}",
        ]
    )


def explain_execution_path(control_signals: Dict[str, Any], execution_result: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "continuation_mode": control_signals.get("continuation_mode") if isinstance(control_signals, dict) else None,
        "required_validators": list((control_signals or {}).get("required_validators") or []) if isinstance(control_signals, dict) else [],
        "repair_actions": list((control_signals or {}).get("repair_actions") or []) if isinstance(control_signals, dict) else [],
        "execution_status": execution_result.get("execution_status"),
        "publication_blocked": execution_result.get("publication_blocked"),
        "decision_blocked": execution_result.get("decision_blocked"),
        "events_emitted": [a["action_type"] for a in execution_result.get("actions_taken") or []],
    }
