"""Control Signal → Runtime Integration Layer (BN.7).

Makes ``control_executor`` the mandatory gate for all runtime operations.
No simulation, pipeline execution, or artifact generation is allowed unless
control signals have been executed and permit continuation.

Core enforcement flow
---------------------
control_chain → control_signals → control_executor → execution_result → work

No module is allowed to:
- skip control execution
- re-interpret signals
- run independently of ``execution_result``

Execution Context Contract
--------------------------
Every call that wants to do real work must supply a context dict::

    {
        "artifact": <any governed artifact>,
        "stage": "<observe | interpret | recommend | synthesis | export | …>",
        "runtime_environment": "<simulation | working_paper | cli | pipeline | …>",
        "execution_id": "<optional unique run identifier>",
    }

Public surface
--------------
``enforce_control_before_execution(context)``
    Mandatory precondition for all runtime entry points.

``run_simulation_with_control(context, run_fn, *args, **kwargs)``
    Adapter: wraps a simulation callable.

``generate_working_paper_with_control(context, gen_fn, *args, **kwargs)``
    Adapter: wraps a working-paper generation callable.

``summarize_control_integration(context, result)``
    Observability: structured log/summary of a control integration result.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple

from spectrum_systems.modules.runtime.control_executor import (
    summarize_execution_result,
)
from spectrum_systems.modules.runtime.contract_runtime import (
    ContractRuntimeError,
    ensure_contract_runtime_available,
)
from spectrum_systems.modules.runtime.control_loop import (
    ControlLoopError,
    build_trace_context_from_replay_artifact,
    run_control_loop,
)
from spectrum_systems.modules.runtime.enforcement_engine import (
    EnforcementError,
    enforce_control_decision,
)
from spectrum_systems.modules.runtime.evaluation_auto_generation import (
    EvalCaseGenerationError,
    generate_failure_eval_case,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Execution-context helpers
# ---------------------------------------------------------------------------

_REQUIRED_CONTEXT_KEYS: Tuple[str, ...] = ("artifact", "stage", "runtime_environment")
_SUPPORTED_GOVERNED_ARTIFACT_TYPES: Tuple[str, ...] = ("replay_result",)


def _validate_context(context: Dict[str, Any]) -> List[str]:
    """Return a list of validation errors for *context*.  Empty list = OK."""
    errors: List[str] = []
    if not isinstance(context, dict):
        return ["context must be a dict"]
    for key in _REQUIRED_CONTEXT_KEYS:
        if key not in context:
            errors.append(f"context missing required key: '{key}'")
    return errors


def _normalize_context(context: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of *context* with ``execution_id`` guaranteed present."""
    ctx = dict(context)
    if not ctx.get("execution_id"):
        ctx["execution_id"] = str(uuid.uuid4())
    return ctx


# ---------------------------------------------------------------------------
# Blocked-execution result helpers
# ---------------------------------------------------------------------------

def _execution_result_from_enforcement_result(enforcement_result: Dict[str, Any]) -> Dict[str, Any]:
    """Translate finalized enforcement_result into BN.7 execution_result shape."""
    final_status = enforcement_result["final_status"]
    if final_status == "allow":
        blocked = False
        review_required = False
        execution_status = "success"
    elif final_status == "deny":
        blocked = True
        review_required = False
        execution_status = "blocked"
    elif final_status == "require_review":
        blocked = True
        review_required = True
        execution_status = "blocked"
    else:
        raise ContractRuntimeError(
            f"unsupported enforcement_result.final_status: {final_status}"
        )

    return {
        "execution_status": execution_status,
        "continuation_allowed": final_status == "allow",
        "publication_blocked": blocked,
        "decision_blocked": blocked,
        "rerun_triggered": False,
        "escalation_triggered": final_status == "deny",
        "human_review_required": review_required,
        "actions_taken": [
            {
                "action_type": "evaluation_enforcement_applied",
                "status": final_status,
                "detail": "bn.7 outcome derived from governed enforcement_result",
                "input_decision_reference": enforcement_result.get("input_decision_reference"),
                "enforcement_result_id": enforcement_result.get("enforcement_result_id"),
            }
        ],
        "validators_run": ["control_loop_engine", "enforcement_engine"],
        "validators_failed": [],
        "repair_actions_applied": [],
    }


def _context_error_result(errors: List[str]) -> Dict[str, Any]:
    return {
        "execution_status": "blocked",
        "continuation_allowed": False,
        "publication_blocked": True,
        "decision_blocked": True,
        "rerun_triggered": False,
        "escalation_triggered": False,
        "human_review_required": True,
        "actions_taken": [
            {
                "action_type": "invalid_context",
                "errors": errors,
                "status": "blocked",
            }
        ],
        "validators_run": [],
        "validators_failed": [],
        "repair_actions_applied": [],
    }


# ---------------------------------------------------------------------------
# Core integration gate
# ---------------------------------------------------------------------------


def enforce_control_before_execution(context: Dict[str, Any]) -> Dict[str, Any]:
    """Mandatory precondition check for all runtime entry points.

    Calls the full control chain (BN.4 → BN.5 → BN.6) and returns an
    *integration result* that includes:

    - ``execution_result``   — raw BN.6 execution result
    - ``continuation_allowed`` — bool derived strictly from ``execution_result``
    - ``execution_status``   — forwarded from ``execution_result``
    - ``publication_blocked`` — forwarded from ``execution_result``
    - ``decision_blocked``   — forwarded from ``execution_result``
    - ``rerun_triggered``    — forwarded from ``execution_result``
    - ``escalation_triggered`` — forwarded from ``execution_result``
    - ``human_review_required`` — forwarded from ``execution_result``
    - ``execution_id``       — unique identifier for this invocation
    - ``stage``              — stage from context
    - ``human_review_task``  — present when ``human_review_required`` is True

    ``continuation_allowed`` is **never** recomputed downstream; it comes
    exclusively from ``execution_result.execution_status``.

    Parameters
    ----------
    context:
        Required keys: ``artifact``, ``stage``, ``runtime_environment``.
        Optional key:  ``execution_id`` (auto-generated if absent).

    Returns
    -------
    dict
        Integration result.  Always call this; never bypass it.
    """
    # BN.6.1 fail-closed: contract runtime must be available before any logic.
    ensure_contract_runtime_available()

    context_errors = _validate_context(context)
    if context_errors:
        result = _context_error_result(context_errors)
        logger.warning("enforce_control_before_execution: invalid context — %s", context_errors)
        return result

    ctx = _normalize_context(context)
    artifact = ctx["artifact"]
    stage = ctx["stage"]
    runtime_environment = ctx["runtime_environment"]
    execution_id = ctx["execution_id"]

    logger.info(
        "enforce_control_before_execution: stage=%s runtime=%s execution_id=%s",
        stage,
        runtime_environment,
        execution_id,
    )

    chain_result: Dict[str, Any] = {}
    control_signals: Dict[str, Any] = {}

    # BAE path: governed evaluation signals are consumed exclusively by
    # the unified control loop engine before runtime execution.
    if not isinstance(artifact, dict):
        raise ContractRuntimeError("artifact must be a dict")
    artifact_type = artifact.get("artifact_type")
    if artifact_type not in _SUPPORTED_GOVERNED_ARTIFACT_TYPES:
        raise ContractRuntimeError(
            "unsupported governed artifact_type; expected one of "
            f"{_SUPPORTED_GOVERNED_ARTIFACT_TYPES}, got {artifact_type!r}"
        )
    if artifact_type == "replay_result" and not isinstance(artifact.get("error_budget_status"), dict):
        raise ContractRuntimeError("replay_result artifact missing required error_budget_status")

    try:
        control_trace_context = build_trace_context_from_replay_artifact(
            artifact,
            base_context={
                "execution_id": execution_id,
                "stage": stage,
                "runtime_environment": runtime_environment,
            },
        )
        loop_result = run_control_loop(
            artifact,
            control_trace_context,
        )
    except ControlLoopError as exc:
        raise ContractRuntimeError(f"control loop evaluation failed: {exc}") from exc
    eval_decision = loop_result["evaluation_control_decision"]
    try:
        enforcement_result = enforce_control_decision(eval_decision)
    except EnforcementError as exc:
        raise ContractRuntimeError(f"enforcement mapping failed: {exc}") from exc

    execution_result = _execution_result_from_enforcement_result(enforcement_result)
    chain_result = {
        "control_chain_decision": {"control_signals": control_signals},
        "execution_result": execution_result,
        "evaluation_control_decision": eval_decision,
        "enforcement_result": enforcement_result,
        "control_trace": loop_result["control_trace"],
    }

    # Derive continuation_allowed from strict positive allowlist:
    # only exact execution_status == "success" may continue.
    exec_status = execution_result.get("execution_status")
    continuation_allowed = exec_status == "success"

    publication_blocked = bool(execution_result.get("publication_blocked", True))
    decision_blocked = bool(execution_result.get("decision_blocked", True))
    rerun_triggered = bool(execution_result.get("rerun_triggered", False))
    escalation_triggered = bool(execution_result.get("escalation_triggered", False))
    human_review_required = bool(execution_result.get("human_review_required", False))

    # Hard enforcement rules (C section of the problem statement)
    # Rule 5: human_review_required → emit structured review task
    human_review_task: Optional[Dict[str, Any]] = None
    if human_review_required:
        artifact_id = artifact.get("artifact_id") if isinstance(artifact, dict) else None
        human_review_task = {
            "task_type": "human_review_required",
            "artifact_id": artifact_id,
            "stage": stage,
            "execution_id": execution_id,
            "runtime_environment": runtime_environment,
            "detail": "Human review is required before execution may proceed",
        }
        logger.warning(
            "enforce_control_before_execution: human_review_required — "
            "review task emitted before continuation is evaluated "
            "(execution_id=%s, stage=%s)",
            execution_id,
            stage,
        )

    integration_result: Dict[str, Any] = {
        "execution_result": execution_result,
        "execution_status": exec_status,
        "continuation_allowed": continuation_allowed,
        "publication_blocked": publication_blocked,
        "decision_blocked": decision_blocked,
        "rerun_triggered": rerun_triggered,
        "escalation_triggered": escalation_triggered,
        "human_review_required": human_review_required,
        "execution_id": execution_id,
        "stage": stage,
        "runtime_environment": runtime_environment,
        "control_signals": control_signals,
    }
    if chain_result.get("evaluation_control_decision") is not None:
        integration_result["evaluation_control_decision"] = chain_result["evaluation_control_decision"]
    if chain_result.get("control_trace") is not None:
        integration_result["control_trace"] = chain_result["control_trace"]
    if chain_result.get("enforcement_result") is not None:
        integration_result["enforcement_result"] = chain_result["enforcement_result"]
    if human_review_task is not None:
        integration_result["human_review_task"] = human_review_task

    if not continuation_allowed:
        source_for_eval = integration_result.get("evaluation_control_decision")
        if not isinstance(source_for_eval, dict):
            source_for_eval = ctx.get("artifact")
        try:
            integration_result["generated_failure_eval_case"] = generate_failure_eval_case(
                source_artifact=source_for_eval,
                source_run_id=str(
                    source_for_eval.get("run_id")
                    or source_for_eval.get("eval_run_id")
                    or execution_id
                ),
                stage=stage,
                runtime_environment=runtime_environment,
                execution_result=integration_result,
            )
        except EvalCaseGenerationError as exc:
            error_payload = {
                "error_type": "EvalCaseGenerationError",
                "message": str(exc),
                "stage": stage,
                "runtime_environment": runtime_environment,
                "execution_id": execution_id,
            }
            integration_result["failure_eval_case_error"] = error_payload
            # Backward-compatible alias for existing consumers/tests.
            integration_result["generated_failure_eval_case_error"] = error_payload
            logger.exception(
                "enforce_control_before_execution: blocked execution failure_eval_case generation failed "
                "(execution_id=%s stage=%s runtime=%s): %s",
                execution_id,
                stage,
                runtime_environment,
                exc,
            )

    # Log outcome for observability (G section)
    _log_integration_outcome(integration_result)

    return integration_result


# ---------------------------------------------------------------------------
# Observability
# ---------------------------------------------------------------------------


def _log_integration_outcome(result: Dict[str, Any]) -> None:
    """Emit structured log lines for every integration decision."""
    status = result.get("execution_status")
    allowed = result.get("continuation_allowed")
    eid = result.get("execution_id")
    stage = result.get("stage")

    if allowed:
        logger.info(
            "control_integration: ALLOWED execution_id=%s stage=%s status=%s",
            eid, stage, status,
        )
    else:
        logger.warning(
            "control_integration: BLOCKED execution_id=%s stage=%s status=%s "
            "publication_blocked=%s decision_blocked=%s rerun=%s escalation=%s",
            eid, stage, status,
            result.get("publication_blocked"),
            result.get("decision_blocked"),
            result.get("rerun_triggered"),
            result.get("escalation_triggered"),
        )


def summarize_control_integration(context: Dict[str, Any], result: Dict[str, Any]) -> str:
    """Return a human-readable summary of a control integration result.

    Parameters
    ----------
    context:
        The context that was passed to ``enforce_control_before_execution``.
    result:
        The dict returned by ``enforce_control_before_execution``.

    Returns
    -------
    str
        A structured multi-line summary suitable for CLI output or log records.
    """
    exec_result = result.get("execution_result") or {}
    exec_summary = summarize_execution_result(exec_result) if exec_result else "  (no execution_result)"

    lines = [
        "Control Integration Result (BN.7)",
        "----------------------------------",
        f"  execution_id          : {result.get('execution_id')}",
        f"  stage                 : {result.get('stage')}",
        f"  runtime_environment   : {result.get('runtime_environment')}",
        f"  continuation_allowed  : {result.get('continuation_allowed')}",
        f"  execution_status      : {result.get('execution_status')}",
        f"  publication_blocked   : {result.get('publication_blocked')}",
        f"  decision_blocked      : {result.get('decision_blocked')}",
        f"  rerun_triggered       : {result.get('rerun_triggered')}",
        f"  escalation_triggered  : {result.get('escalation_triggered')}",
        f"  human_review_required : {result.get('human_review_required')}",
        "",
        exec_summary,
    ]
    if result.get("human_review_task"):
        lines += [
            "",
            "Human Review Task:",
            f"  {result['human_review_task']}",
        ]
    generated_failure_eval_case = result.get("generated_failure_eval_case")
    if isinstance(generated_failure_eval_case, dict):
        lines += [
            "",
            "Failure Eval Artifact:",
            f"  eval_case_id: {generated_failure_eval_case.get('eval_case_id')}",
            f"  source_artifact_ref: {generated_failure_eval_case.get('provenance', {}).get('source_artifact_ref')}",
        ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Integration adapters
# ---------------------------------------------------------------------------


def run_simulation_with_control(
    context: Dict[str, Any],
    run_fn: Callable[..., Any],
    /,
    *args: Any,
    **kwargs: Any,
) -> Tuple[Optional[Any], Dict[str, Any]]:
    """Adapter: run a simulation callable only when control permits.

    Must call ``enforce_control_before_execution`` before forwarding to
    *run_fn*.  If control blocks execution, *run_fn* is never called.

    Parameters
    ----------
    context:
        Execution context (``artifact``, ``stage``, ``runtime_environment``).
    run_fn:
        The simulation callable to invoke when permitted.
    *args, **kwargs:
        Forwarded verbatim to *run_fn* when execution is allowed.

    Returns
    -------
    (result, integration_result)
        *result* is the return value of *run_fn*, or ``None`` when blocked.
        *integration_result* is always the full integration gate dict.
    """
    integration_result = enforce_control_before_execution(context)
    if not integration_result["continuation_allowed"]:
        logger.warning(
            "run_simulation_with_control: simulation BLOCKED (execution_id=%s)",
            integration_result.get("execution_id"),
        )
        return None, integration_result
    logger.info(
        "run_simulation_with_control: simulation PROCEEDING (execution_id=%s)",
        integration_result.get("execution_id"),
    )
    sim_result = run_fn(*args, **kwargs)
    return sim_result, integration_result


def generate_working_paper_with_control(
    context: Dict[str, Any],
    gen_fn: Callable[..., Any],
    /,
    *args: Any,
    **kwargs: Any,
) -> Tuple[Optional[Any], Dict[str, Any]]:
    """Adapter: generate a working paper only when control permits.

    Must call ``enforce_control_before_execution`` before forwarding to
    *gen_fn*.  If control blocks:

    - *gen_fn* is not called.
    - ``publication_blocked`` is honoured (no output published).
    - ``decision_blocked`` is honoured (output must not be decision-grade).

    Parameters
    ----------
    context:
        Execution context (``artifact``, ``stage``, ``runtime_environment``).
    gen_fn:
        The working-paper generation callable to invoke when permitted.
    *args, **kwargs:
        Forwarded verbatim to *gen_fn* when execution is allowed.

    Returns
    -------
    (paper, integration_result)
        *paper* is the return value of *gen_fn*, or ``None`` when blocked.
        *integration_result* is always the full integration gate dict.
    """
    integration_result = enforce_control_before_execution(context)
    if not integration_result["continuation_allowed"]:
        logger.warning(
            "generate_working_paper_with_control: generation BLOCKED (execution_id=%s)",
            integration_result.get("execution_id"),
        )
        return None, integration_result
    logger.info(
        "generate_working_paper_with_control: generation PROCEEDING (execution_id=%s)",
        integration_result.get("execution_id"),
    )
    paper = gen_fn(*args, **kwargs)
    return paper, integration_result
