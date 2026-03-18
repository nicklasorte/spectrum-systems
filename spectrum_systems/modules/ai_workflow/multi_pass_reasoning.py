"""
Multi-Pass Reasoning Layer — spectrum_systems/modules/ai_workflow/multi_pass_reasoning.py

Implements governed, deterministic multi-pass AI reasoning chains.  Each chain
runs typed reasoning passes in sequence, validates intermediate outputs,
enforces pass budgets and circuit breakers, and emits traceable pass-chain
artifacts.

Design principles:
  - Explicit pass ordering: pass types and sequences are declared, not inferred
  - Deterministic: chain_id is derived from context_id and config hash
  - No silent fallback: every failure is recorded; circuit-breaker enforced
  - Confidence method enforcement: reasoning-class passes must use scoring_pass
  - Governed interfaces: model_adapter, prompt_registry, task_router injected
  - No external dependencies beyond the Python standard library

Key types
---------
PassSpec
    Dict describing a single reasoning pass: type, order, prompt, model,
    confidence method, and schema reference.

PassChain
    Dict produced by ``build_pass_chain``.  Contains the full ordered sequence
    of PassSpec dicts, the circuit-breaker policy, and the context bundle.

PassChainState
    Mutable execution state tracked throughout ``execute_pass_chain``.

PassChainRecord
    Final output dict produced by ``finalize_pass_chain``.  Conforms to
    ``contracts/schemas/pass_chain_record.schema.json``.

PassResult
    Dict produced for each executed pass.  Conforms to
    ``contracts/schemas/pass_result.schema.json``.

Injected interfaces
-------------------
model_adapter
    Object with:
      .invoke(prompt_id, prompt_version, model_family, model_name,
              context_bundle, upstream_outputs, pass_config) -> dict
          Must return {"output": <any>, "model_name": str, "model_family": str,
                       "latency_ms": int}
      .invoke_scoring_pass(main_pass_id, main_output, pass_spec,
                           context_bundle, upstream_outputs, pass_config) -> dict
          Must return {"confidence_score": float (0–1), "scoring_pass_id": str,
                       "latency_ms": int}
          Required only when confidence_method is "scoring_pass".

prompt_registry
    Object with:
      .get_prompt(prompt_id, version=None) -> dict | None
          Returns {"prompt_id": str, "version": str, "template": str} or None.

task_router
    Object with:
      .resolve(pass_type, routing_version=None) -> dict
          Returns routing metadata dict.

Public API
----------
build_pass_chain(task_type, context_bundle, config)
execute_pass_chain(pass_chain, model_adapter, prompt_registry, task_router)
execute_single_pass(pass_spec, context_bundle, upstream_outputs, config)
validate_pass_output(pass_spec, output, schema)
apply_circuit_breaker(pass_chain_state)
finalize_pass_chain(pass_chain_state)
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# ─── Pass type definitions ────────────────────────────────────────────────────

#: Reasoning-class passes.  These passes must use ``scoring_pass`` as their
#: confidence method.  Configuring them with ``self_reported`` is permitted
#: only with an explicit override and will produce a warning.
REASONING_CLASS_PASSES = frozenset({
    "decision_extraction",
    "contradiction_detection",
    "gap_detection",
    "adversarial_review",
})

#: Canonical ordered pass sequence for the meeting-minutes task type.
MEETING_MINUTES_PASS_SEQUENCE: List[Dict[str, Any]] = [
    {
        "pass_type": "transcript_extraction",
        "pass_order": 1,
        "prompt_id": "meeting_minutes.transcript_extraction",
        "schema_id": "meeting_minutes/transcript_facts_output",
        "confidence_method": "self_reported",
        "input_refs": ["context_bundle"],
    },
    {
        "pass_type": "decision_extraction",
        "pass_order": 2,
        "prompt_id": "meeting_minutes.decision_extraction",
        "schema_id": "meeting_minutes/decisions_output",
        "confidence_method": "scoring_pass",
        "input_refs": ["context_bundle", "transcript_extraction"],
    },
    {
        "pass_type": "action_item_extraction",
        "pass_order": 3,
        "prompt_id": "meeting_minutes.action_item_extraction",
        "schema_id": "meeting_minutes/action_items_output",
        "confidence_method": "self_reported",
        "input_refs": ["context_bundle", "transcript_extraction", "decision_extraction"],
    },
    {
        "pass_type": "contradiction_detection",
        "pass_order": 4,
        "prompt_id": "meeting_minutes.contradiction_detection",
        "schema_id": "meeting_minutes/contradictions_output",
        "confidence_method": "scoring_pass",
        "input_refs": [
            "context_bundle",
            "transcript_extraction",
            "decision_extraction",
            "action_item_extraction",
        ],
    },
    {
        "pass_type": "gap_detection",
        "pass_order": 5,
        "prompt_id": "meeting_minutes.gap_detection",
        "schema_id": "meeting_minutes/gaps_output",
        "confidence_method": "scoring_pass",
        "input_refs": [
            "context_bundle",
            "transcript_extraction",
            "decision_extraction",
            "action_item_extraction",
            "contradiction_detection",
        ],
    },
    {
        "pass_type": "adversarial_review",
        "pass_order": 6,
        "prompt_id": "meeting_minutes.adversarial_review",
        "schema_id": "meeting_minutes/adversarial_review_output",
        "confidence_method": "scoring_pass",
        "input_refs": [
            "context_bundle",
            "transcript_extraction",
            "decision_extraction",
            "action_item_extraction",
            "contradiction_detection",
            "gap_detection",
        ],
    },
    {
        "pass_type": "synthesis",
        "pass_order": 7,
        "prompt_id": "meeting_minutes.synthesis",
        "schema_id": "meeting_minutes/synthesis_output",
        "confidence_method": "self_reported",
        "input_refs": [
            "context_bundle",
            "transcript_extraction",
            "decision_extraction",
            "action_item_extraction",
            "contradiction_detection",
            "gap_detection",
            "adversarial_review",
        ],
    },
]

#: Pass sequences indexed by task type.
PASS_SEQUENCES: Dict[str, List[Dict[str, Any]]] = {
    "meeting_minutes": MEETING_MINUTES_PASS_SEQUENCE,
}

#: Default circuit-breaker policy applied when none is provided in config.
DEFAULT_CIRCUIT_BREAKER_POLICY: Dict[str, Any] = {
    "max_passes": 10,
    "max_failed_passes": 3,
    "consecutive_failure_limit": 2,
    "persistent_validation_failure_limit": 3,
    "escalation_policy": "escalate_after_persistent_failure",
}


# ─── Public API ───────────────────────────────────────────────────────────────

def build_pass_chain(
    task_type: str,
    context_bundle: Dict[str, Any],
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a governed pass chain for the given task type and context bundle.

    Resolves the canonical pass sequence for *task_type*, applies any caller-
    supplied overrides from *config*, and returns a complete PassChain dict
    ready for ``execute_pass_chain``.

    Confidence method enforcement
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Reasoning-class passes (``decision_extraction``, ``contradiction_detection``,
    ``gap_detection``, ``adversarial_review``) default to ``scoring_pass``.
    If a caller explicitly overrides one to ``self_reported``, the pass is
    accepted but a warning is recorded in the chain's ``warnings`` list.

    Parameters
    ----------
    task_type:
        Task type identifying which pass sequence to use (e.g.,
        ``"meeting_minutes"``).
    context_bundle:
        Governed context bundle produced by ``context_assembly.build_context_bundle``.
        Must contain a ``context_id`` field.
    config:
        Optional configuration dict.  Recognised keys:

        - ``routing_table_version`` (str | None): version to pin in routing.
        - ``circuit_breaker_policy`` (dict): overrides DEFAULT_CIRCUIT_BREAKER_POLICY.
        - ``pass_overrides`` (dict): maps pass_type → partial PassSpec dict for
          per-pass customisation (e.g., ``{"decision_extraction": {"prompt_version": "v2"}}``)

    Returns
    -------
    dict
        PassChain dict with keys: ``chain_id``, ``chain_type``, ``task_type``,
        ``context_id``, ``context_bundle``, ``routing_table_version``,
        ``pass_sequence``, ``circuit_breaker_policy``, ``warnings``.

    Raises
    ------
    UnsupportedTaskTypeError
        If *task_type* has no registered pass sequence.
    InvalidCircuitBreakerPolicyError
        If the supplied circuit-breaker policy is invalid.
    """
    if task_type not in PASS_SEQUENCES:
        raise UnsupportedTaskTypeError(
            f"No pass sequence registered for task_type '{task_type}'. "
            f"Supported types: {sorted(PASS_SEQUENCES.keys())}"
        )

    cfg = config or {}
    routing_version: Optional[str] = cfg.get("routing_table_version")
    pass_overrides: Dict[str, Any] = cfg.get("pass_overrides") or {}

    cb_policy = {**DEFAULT_CIRCUIT_BREAKER_POLICY}
    if "circuit_breaker_policy" in cfg:
        cb_policy.update(cfg["circuit_breaker_policy"])
    _validate_circuit_breaker_policy(cb_policy)

    warnings: List[str] = []
    pass_sequence: List[Dict[str, Any]] = []

    for template in PASS_SEQUENCES[task_type]:
        spec = dict(template)
        # Apply caller overrides for this pass_type.
        overrides = pass_overrides.get(spec["pass_type"], {})
        spec.update(overrides)
        # Assign a deterministic pass_id.
        spec["pass_id"] = _make_pass_id(task_type, spec["pass_type"], spec["pass_order"])
        # Default model fields if not provided.
        spec.setdefault("prompt_version", None)
        spec.setdefault("model_family", None)
        spec.setdefault("model_name", None)
        # Enforce confidence method for reasoning-class passes.
        if spec["pass_type"] in REASONING_CLASS_PASSES:
            if spec["confidence_method"] != "scoring_pass":
                warnings.append(
                    f"Pass '{spec['pass_type']}' is a reasoning-class pass and "
                    f"should use confidence_method='scoring_pass', but "
                    f"'{spec['confidence_method']}' was configured. Proceeding with "
                    f"explicit override — confidence traceability is reduced."
                )
        pass_sequence.append(spec)

    context_id: str = context_bundle.get("context_id", "")
    chain_id = _make_chain_id(task_type, context_id, routing_version, cfg)

    return {
        "chain_id": chain_id,
        "chain_type": task_type,
        "task_type": task_type,
        "context_id": context_id,
        "context_bundle": context_bundle,
        "routing_table_version": routing_version,
        "pass_sequence": pass_sequence,
        "circuit_breaker_policy": cb_policy,
        "warnings": warnings,
    }


def execute_pass_chain(
    pass_chain: Dict[str, Any],
    model_adapter: Any,
    prompt_registry: Any,
    task_router: Any,
) -> Dict[str, Any]:
    """Execute all passes in the chain in order, enforcing circuit-breaker rules.

    Iterates through ``pass_chain["pass_sequence"]``, executing each pass via
    ``execute_single_pass``.  After each pass the circuit-breaker state is
    evaluated via ``apply_circuit_breaker``.  Execution stops if the circuit
    breaker trips.

    All intermediate outputs are accumulated in the state.  Failed chains
    preserve all intermediate outputs for debugging.

    Parameters
    ----------
    pass_chain:
        PassChain dict produced by ``build_pass_chain``.
    model_adapter:
        Injected model adapter (see module docstring for required interface).
    prompt_registry:
        Injected prompt registry (see module docstring for required interface).
    task_router:
        Injected task router (see module docstring for required interface).

    Returns
    -------
    dict
        PassChainRecord dict (see ``finalize_pass_chain``).
    """
    state = _init_chain_state(pass_chain)
    context_bundle = pass_chain["context_bundle"]
    routing_version = pass_chain.get("routing_table_version")

    for pass_spec in pass_chain["pass_sequence"]:
        # Check circuit breaker before each pass.
        apply_circuit_breaker(state)
        if state["status"] in ("terminated", "escalated"):
            break

        # Resolve prompt — no silent fallback; missing prompt is a hard failure.
        prompt_id = pass_spec["prompt_id"]
        prompt_version = pass_spec.get("prompt_version")
        prompt = prompt_registry.get_prompt(prompt_id, version=prompt_version)
        if prompt is None:
            _record_hard_failure(
                state,
                pass_spec,
                f"Prompt '{prompt_id}' (version={prompt_version!r}) not found "
                f"in prompt_registry. No silent fallback.",
            )
            apply_circuit_breaker(state)
            if state["status"] in ("terminated", "escalated"):
                break
            continue

        # Pin prompt version from registry if not already pinned.
        resolved_version = prompt.get("version") or prompt_version
        spec_for_execution = {**pass_spec, "prompt_version": resolved_version}

        # Resolve routing — version-pinned.
        routing_meta = task_router.resolve(
            pass_spec["pass_type"], routing_version=routing_version
        )

        # Collect upstream structured outputs for this pass.
        upstream_outputs = _collect_upstream_outputs(state, pass_spec)

        # Execute the pass.
        pass_config = {
            "model_adapter": model_adapter,
            "prompt_registry": prompt_registry,
            "task_router": task_router,
            "routing_meta": routing_meta,
            "prompt": prompt,
        }
        pass_result = execute_single_pass(
            spec_for_execution, context_bundle, upstream_outputs, pass_config
        )

        # Record result and update counters.
        state["pass_results"].append(pass_result)
        _update_state_counters(state, pass_result)

        # Store intermediate artifact.
        if pass_result.get("output_ref"):
            state["intermediate_artifacts"][pass_spec["pass_type"]] = {
                "pass_id": pass_result["pass_id"],
                "output_ref": pass_result["output_ref"],
                "output": pass_result.get("_raw_output"),
            }

        # Check circuit breaker after this pass.
        apply_circuit_breaker(state)

    return finalize_pass_chain(state)


def execute_single_pass(
    pass_spec: Dict[str, Any],
    context_bundle: Dict[str, Any],
    upstream_outputs: Dict[str, Any],
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Execute a single reasoning pass and return a PassResult dict.

    Calls the model adapter, validates the output against the declared schema,
    and enforces confidence method rules.  When ``confidence_method`` is
    ``"scoring_pass"``, the adapter's ``invoke_scoring_pass`` method is called
    to produce a traceable confidence score.

    Parameters
    ----------
    pass_spec:
        PassSpec dict describing this pass.
    context_bundle:
        The assembled context bundle for the chain.
    upstream_outputs:
        Dict mapping pass_type → output dict for passes that ran before this one.
    config:
        Must contain ``"model_adapter"`` and optionally ``"prompt"``,
        ``"schemas"`` (dict of schema_id → schema dict).

    Returns
    -------
    dict
        PassResult dict conforming to ``contracts/schemas/pass_result.schema.json``.
        The private ``_raw_output`` key carries the raw model output for
        in-memory intermediate storage; it is stripped from the final record.

    Raises
    ------
    PassChainError
        If ``model_adapter`` is missing from *config*.
    """
    cfg = config or {}
    model_adapter = cfg.get("model_adapter")
    if model_adapter is None:
        raise PassChainError(
            "execute_single_pass requires 'model_adapter' in config."
        )

    pass_id = pass_spec.get("pass_id") or str(uuid.uuid4())
    pass_type = pass_spec["pass_type"]
    pass_order = pass_spec["pass_order"]
    prompt_id = pass_spec["prompt_id"]
    prompt_version = pass_spec.get("prompt_version")
    confidence_method = pass_spec.get("confidence_method", "self_reported")
    schema_id = pass_spec.get("schema_id")
    schemas = cfg.get("schemas") or {}

    started_at = _utc_now()
    warnings: List[str] = []
    raw_output: Any = None
    output_ref: Optional[str] = None
    scoring_pass_ref: Optional[str] = None
    confidence_score: Optional[float] = None
    model_name: Optional[str] = pass_spec.get("model_name")
    model_family: Optional[str] = pass_spec.get("model_family")
    latency_ms: Optional[int] = None

    try:
        # Call model adapter.
        invoke_result = model_adapter.invoke(
            prompt_id=prompt_id,
            prompt_version=prompt_version,
            model_family=model_family,
            model_name=model_name,
            context_bundle=context_bundle,
            upstream_outputs=upstream_outputs,
            pass_config=cfg,
        )
        raw_output = invoke_result.get("output")
        model_name = invoke_result.get("model_name") or model_name
        model_family = invoke_result.get("model_family") or model_family
        latency_ms = invoke_result.get("latency_ms")

        # Assign a deterministic artifact reference.
        output_ref = _make_artifact_ref(pass_id, pass_type)

        # Validate output against schema.
        schema = schemas.get(schema_id) if schema_id else None
        validation_result = validate_pass_output(pass_spec, raw_output, schema)

        # Enforce confidence method.
        if confidence_method == "scoring_pass":
            if not hasattr(model_adapter, "invoke_scoring_pass"):
                raise PassChainError(
                    f"Pass '{pass_type}' requires confidence_method='scoring_pass' "
                    f"but model_adapter has no 'invoke_scoring_pass' method."
                )
            scoring_result = model_adapter.invoke_scoring_pass(
                main_pass_id=pass_id,
                main_output=raw_output,
                pass_spec=pass_spec,
                context_bundle=context_bundle,
                upstream_outputs=upstream_outputs,
                pass_config=cfg,
            )
            confidence_score = float(scoring_result.get("confidence_score", 0.0))
            scoring_pass_ref = scoring_result.get("scoring_pass_id")
            if scoring_pass_ref is None:
                warnings.append(
                    "invoke_scoring_pass did not return 'scoring_pass_id'; "
                    "scoring traceability is incomplete."
                )
        elif confidence_method == "heuristic":
            confidence_score = _heuristic_confidence(raw_output)
        else:
            # self_reported: model output may include confidence or we leave it None.
            confidence_score = _extract_self_reported_confidence(raw_output)

        # Determine final pass status.
        if validation_result["status"] == "failed":
            pass_status = "failed"
            warnings.extend(validation_result.get("errors", []))
        else:
            pass_status = "completed"

    except PassChainError:
        raise
    except Exception as exc:  # noqa: BLE001
        completed_at = _utc_now()
        return _build_failed_pass_result(
            pass_id=pass_id,
            pass_type=pass_type,
            pass_order=pass_order,
            prompt_id=prompt_id,
            prompt_version=prompt_version,
            model_family=model_family,
            model_name=model_name,
            confidence_method=confidence_method,
            schema_id=schema_id,
            started_at=started_at,
            completed_at=completed_at,
            error_message=str(exc),
        )

    completed_at = _utc_now()
    result: Dict[str, Any] = {
        "pass_id": pass_id,
        "pass_type": pass_type,
        "pass_order": pass_order,
        "prompt_id": prompt_id,
        "prompt_version": prompt_version,
        "model_family": model_family,
        "model_name": model_name,
        "input_refs": list(pass_spec.get("input_refs") or []),
        "output_ref": output_ref,
        "schema_validation": validation_result,
        "confidence_method": confidence_method,
        "confidence_score": confidence_score,
        "scoring_pass_ref": scoring_pass_ref,
        "status": pass_status,
        "latency_ms": latency_ms,
        "warnings": warnings,
        "started_at": started_at,
        "completed_at": completed_at,
        # Private: carries the raw output in-memory for intermediate storage.
        # Stripped by finalize_pass_chain before producing the chain record.
        "_raw_output": raw_output,
    }
    return result


def validate_pass_output(
    pass_spec: Dict[str, Any],
    output: Any,
    schema: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Validate *output* against *schema* and return a schema_validation dict.

    When *schema* is None (no schema registered for this pass), validation is
    skipped and ``status`` is set to ``"skipped"``.  A missing schema is not
    treated as a failure, but the caller should ensure schemas are registered
    for all governed pass types.

    Parameters
    ----------
    pass_spec:
        PassSpec dict (used for error messages and schema_id lookup).
    output:
        Raw output returned by the model adapter.
    schema:
        Optional JSON Schema dict.  When supplied, output must be a dict and
        must conform to the schema.

    Returns
    -------
    dict
        ``{"schema_id": str | None, "status": "passed"|"failed"|"skipped",
           "errors": list[str]}``
    """
    schema_id = pass_spec.get("schema_id")

    if schema is None:
        return {"schema_id": schema_id, "status": "skipped", "errors": []}

    if not isinstance(output, dict):
        return {
            "schema_id": schema_id,
            "status": "failed",
            "errors": [
                f"Pass '{pass_spec['pass_type']}' output must be a dict "
                f"when a schema is provided; got {type(output).__name__}."
            ],
        }

    errors = _jsonschema_validate(output, schema)
    return {
        "schema_id": schema_id,
        "status": "failed" if errors else "passed",
        "errors": errors,
    }


def apply_circuit_breaker(pass_chain_state: Dict[str, Any]) -> None:
    """Evaluate circuit-breaker conditions and mutate *pass_chain_state* if tripped.

    Called after each pass (and before the first pass) to check whether the
    chain should be terminated.  When tripped, sets ``status`` to either
    ``"terminated"`` or ``"escalated"`` and writes ``termination_reason``.

    Conditions checked (in priority order):
    1. ``max_passes`` reached — terminate.
    2. ``max_failed_passes`` reached — terminate (possibly escalate).
    3. ``consecutive_failure_limit`` reached — terminate (possibly escalate).
    4. ``persistent_validation_failure_limit`` reached — terminate + escalate.

    Already-terminated chains are not re-evaluated.

    Parameters
    ----------
    pass_chain_state:
        Mutable state dict as initialised by ``execute_pass_chain``.
        Modified in place.
    """
    if pass_chain_state["status"] in ("terminated", "escalated", "completed"):
        return

    policy = pass_chain_state["circuit_breaker_policy"]
    max_passes = policy["max_passes"]
    max_failed = policy["max_failed_passes"]
    consec_limit = policy["consecutive_failure_limit"]
    validation_limit = policy["persistent_validation_failure_limit"]
    escalation_policy = policy["escalation_policy"]
    executed = len(pass_chain_state["pass_results"])
    failed = pass_chain_state["failed_count"]
    consecutive = pass_chain_state["consecutive_failures"]
    validation_failures = pass_chain_state["validation_failure_count"]

    def _trip(reason: str, escalate: bool) -> None:
        pass_chain_state["status"] = "escalated" if escalate else "terminated"
        pass_chain_state["termination_reason"] = reason
        pass_chain_state["escalation_required"] = escalate

    should_escalate = escalation_policy == "escalate_after_persistent_failure"

    if executed >= max_passes:
        _trip(
            f"max_passes limit ({max_passes}) reached after {executed} passes.",
            escalate=False,
        )
    elif failed >= max_failed:
        _trip(
            f"max_failed_passes limit ({max_failed}) reached "
            f"({failed} failed passes).",
            escalate=should_escalate,
        )
    elif consecutive >= consec_limit:
        _trip(
            f"consecutive_failure_limit ({consec_limit}) reached "
            f"({consecutive} consecutive failures).",
            escalate=should_escalate,
        )
    elif validation_failures >= validation_limit:
        _trip(
            f"persistent_validation_failure_limit ({validation_limit}) reached "
            f"({validation_failures} validation failures).",
            escalate=True,  # Always escalate on persistent validation failures.
        )


def finalize_pass_chain(pass_chain_state: Dict[str, Any]) -> Dict[str, Any]:
    """Produce the final PassChainRecord from *pass_chain_state*.

    Marks the chain as ``"completed"`` if still running, sets ``completed_at``,
    strips private ``_raw_output`` keys from pass results, and collects all
    intermediate artifact references.

    Parameters
    ----------
    pass_chain_state:
        Mutable state dict from ``execute_pass_chain``.

    Returns
    -------
    dict
        PassChainRecord dict conforming to
        ``contracts/schemas/pass_chain_record.schema.json``.
    """
    if pass_chain_state["status"] == "running":
        pass_chain_state["status"] = "completed"

    pass_chain_state["completed_at"] = _utc_now()

    chain = pass_chain_state["chain"]
    # Strip private _raw_output from each pass result.
    cleaned_results = []
    for pr in pass_chain_state["pass_results"]:
        cleaned = {k: v for k, v in pr.items() if k != "_raw_output"}
        cleaned_results.append(cleaned)

    # Collect intermediate artifact refs.
    intermediate_refs = [
        v["output_ref"]
        for v in pass_chain_state["intermediate_artifacts"].values()
        if v.get("output_ref")
    ]

    return {
        "chain_id": chain["chain_id"],
        "chain_type": chain["chain_type"],
        "task_type": chain["task_type"],
        "context_id": chain["context_id"],
        "routing_table_version": chain.get("routing_table_version"),
        "pass_sequence": chain["pass_sequence"],
        "pass_results": cleaned_results,
        "intermediate_artifact_refs": intermediate_refs,
        "status": pass_chain_state["status"],
        "started_at": pass_chain_state["started_at"],
        "completed_at": pass_chain_state["completed_at"],
        "circuit_breaker_policy": pass_chain_state["circuit_breaker_policy"],
        "termination_reason": pass_chain_state["termination_reason"],
        "escalation_required": pass_chain_state["escalation_required"],
        "warnings": pass_chain_state["warnings"],
    }


# ─── Exceptions ───────────────────────────────────────────────────────────────

class PassChainError(Exception):
    """Base exception for multi-pass reasoning errors."""


class UnsupportedTaskTypeError(PassChainError):
    """Raised when build_pass_chain is called with an unregistered task type."""


class InvalidCircuitBreakerPolicyError(PassChainError):
    """Raised when a circuit-breaker policy dict is invalid."""


# ─── Private helpers ──────────────────────────────────────────────────────────

def _utc_now() -> str:
    """Return current UTC time as ISO-8601 string (seconds precision)."""
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat()


def _make_chain_id(
    task_type: str,
    context_id: str,
    routing_version: Optional[str],
    config: Dict[str, Any],
) -> str:
    """Derive a deterministic chain_id from chain-level inputs."""
    canonical = json.dumps(
        {
            "task_type": task_type,
            "context_id": context_id,
            "routing_table_version": routing_version,
            "pass_overrides": config.get("pass_overrides") or {},
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    digest = hashlib.sha256(canonical.encode()).hexdigest()[:16]
    return f"chain-{digest}"


def _make_pass_id(task_type: str, pass_type: str, pass_order: int) -> str:
    """Derive a deterministic pass_id."""
    raw = f"{task_type}:{pass_type}:{pass_order}"
    digest = hashlib.sha256(raw.encode()).hexdigest()[:12]
    return f"pass-{digest}"


def _make_artifact_ref(pass_id: str, pass_type: str) -> str:
    """Return a deterministic artifact reference for a pass output."""
    return f"artifact:{pass_id}:{pass_type}"


def _validate_circuit_breaker_policy(policy: Dict[str, Any]) -> None:
    """Raise InvalidCircuitBreakerPolicyError if *policy* is malformed."""
    required = {
        "max_passes",
        "max_failed_passes",
        "consecutive_failure_limit",
        "persistent_validation_failure_limit",
        "escalation_policy",
    }
    missing = required - policy.keys()
    if missing:
        raise InvalidCircuitBreakerPolicyError(
            f"Circuit-breaker policy missing required keys: {sorted(missing)}"
        )
    valid_policies = {"escalate_after_persistent_failure", "terminate_only"}
    if policy["escalation_policy"] not in valid_policies:
        raise InvalidCircuitBreakerPolicyError(
            f"Unknown escalation_policy '{policy['escalation_policy']}'. "
            f"Valid values: {sorted(valid_policies)}"
        )
    for int_field in (
        "max_passes",
        "max_failed_passes",
        "consecutive_failure_limit",
        "persistent_validation_failure_limit",
    ):
        if not isinstance(policy[int_field], int) or policy[int_field] < 1:
            raise InvalidCircuitBreakerPolicyError(
                f"Circuit-breaker policy '{int_field}' must be a positive integer."
            )


def _init_chain_state(pass_chain: Dict[str, Any]) -> Dict[str, Any]:
    """Initialise the mutable execution state for a chain run."""
    return {
        "chain": pass_chain,
        "pass_results": [],
        "intermediate_artifacts": {},
        "status": "running",
        "termination_reason": None,
        "escalation_required": False,
        "warnings": list(pass_chain.get("warnings") or []),
        "started_at": _utc_now(),
        "completed_at": None,
        "failed_count": 0,
        "consecutive_failures": 0,
        "validation_failure_count": 0,
        "circuit_breaker_policy": pass_chain["circuit_breaker_policy"],
    }


def _update_state_counters(
    state: Dict[str, Any],
    pass_result: Dict[str, Any],
) -> None:
    """Update failure counters in *state* based on *pass_result*."""
    if pass_result["status"] == "failed":
        state["failed_count"] += 1
        state["consecutive_failures"] += 1
        if pass_result.get("schema_validation", {}).get("status") == "failed":
            state["validation_failure_count"] += 1
    else:
        state["consecutive_failures"] = 0


def _collect_upstream_outputs(
    state: Dict[str, Any],
    pass_spec: Dict[str, Any],
) -> Dict[str, Any]:
    """Return a dict mapping pass_type → raw output for upstream inputs."""
    result: Dict[str, Any] = {}
    for ref in pass_spec.get("input_refs") or []:
        if ref == "context_bundle":
            continue
        if ref in state["intermediate_artifacts"]:
            result[ref] = state["intermediate_artifacts"][ref].get("output")
    return result


def _record_hard_failure(
    state: Dict[str, Any],
    pass_spec: Dict[str, Any],
    error_message: str,
) -> None:
    """Record a hard failure pass result for a pass that could not begin."""
    now = _utc_now()
    result = _build_failed_pass_result(
        pass_id=pass_spec.get("pass_id") or str(uuid.uuid4()),
        pass_type=pass_spec["pass_type"],
        pass_order=pass_spec["pass_order"],
        prompt_id=pass_spec["prompt_id"],
        prompt_version=pass_spec.get("prompt_version"),
        model_family=pass_spec.get("model_family"),
        model_name=pass_spec.get("model_name"),
        confidence_method=pass_spec.get("confidence_method", "self_reported"),
        schema_id=pass_spec.get("schema_id"),
        started_at=now,
        completed_at=now,
        error_message=error_message,
    )
    state["pass_results"].append(result)
    _update_state_counters(state, result)
    state["warnings"].append(f"Hard failure on pass '{pass_spec['pass_type']}': {error_message}")


def _build_failed_pass_result(
    pass_id: str,
    pass_type: str,
    pass_order: int,
    prompt_id: str,
    prompt_version: Optional[str],
    model_family: Optional[str],
    model_name: Optional[str],
    confidence_method: str,
    schema_id: Optional[str],
    started_at: str,
    completed_at: str,
    error_message: str,
) -> Dict[str, Any]:
    """Build a failed PassResult dict."""
    return {
        "pass_id": pass_id,
        "pass_type": pass_type,
        "pass_order": pass_order,
        "prompt_id": prompt_id,
        "prompt_version": prompt_version,
        "model_family": model_family,
        "model_name": model_name,
        "input_refs": [],
        "output_ref": None,
        "schema_validation": {
            "schema_id": schema_id,
            "status": "skipped",
            "errors": [],
        },
        "confidence_method": confidence_method,
        "confidence_score": None,
        "scoring_pass_ref": None,
        "status": "failed",
        "latency_ms": None,
        "warnings": [error_message],
        "started_at": started_at,
        "completed_at": completed_at,
        "_raw_output": None,
    }


def _heuristic_confidence(output: Any) -> Optional[float]:
    """Derive a heuristic confidence score from the output dict structure.

    Simple heuristic: score is proportional to the fraction of expected top-
    level keys that are present and non-empty.  Returns None if output is not
    a dict.
    """
    if not isinstance(output, dict):
        return None
    non_empty = sum(1 for v in output.values() if v not in (None, "", [], {}))
    total = len(output)
    if total == 0:
        return 0.0
    return round(non_empty / total, 2)


def _extract_self_reported_confidence(output: Any) -> Optional[float]:
    """Extract a self-reported confidence score from the output dict.

    Looks for a top-level ``"confidence"`` or ``"confidence_score"`` key.
    Returns None if not present or not a valid float in [0, 1].
    """
    if not isinstance(output, dict):
        return None
    raw = output.get("confidence") or output.get("confidence_score")
    if raw is None:
        return None
    try:
        score = float(raw)
        return max(0.0, min(1.0, score))
    except (TypeError, ValueError):
        return None


def _jsonschema_validate(instance: Any, schema: Dict[str, Any]) -> List[str]:
    """Validate *instance* against *schema* and return a list of error messages.

    Uses jsonschema if available; falls back to a minimal structural check
    when jsonschema is not installed.  The fallback only checks that the
    instance is a dict (i.e., the structural check is best-effort when the
    full validator is absent).
    """
    try:
        import jsonschema  # type: ignore[import]
        validator = jsonschema.Draft202012Validator(schema)
        errors = sorted(validator.iter_errors(instance), key=lambda e: e.path)
        return [e.message for e in errors]
    except ImportError:
        if not isinstance(instance, dict):
            return [f"Expected a dict; got {type(instance).__name__}"]
        return []
