"""
Context Assembly Layer — spectrum_systems/modules/ai_workflow/context_assembly.py

Builds governed, deterministic context bundles that represent the exact inputs
provided to every AI task.  All AI calls must flow through this layer; raw
inputs must never be sent directly to a model.

Design principles:
  - Deterministic: identical inputs produce identical bundles
  - No silent fallback: every truncation or overflow action is logged
  - Explicit prioritization: section ordering is fixed and testable
  - Retrieval is stubbed: no embeddings or vector-DB are used here
  - No external dependencies beyond the Python standard library

Key types
---------
ContextBundle
    Dict produced by ``build_context_bundle``.  Conforms to
    ``contracts/schemas/context_bundle.schema.json``.

ContextAssemblyRecord
    Dict produced alongside every bundle.  Conforms to
    ``contracts/schemas/context_assembly_record.schema.json``.

ContextBudgetPolicy
    Dict that governs token allocation and overflow behaviour.

Public API
----------
build_context_bundle(task_type, input_payload, source_artifacts, config)
apply_context_budget(bundle, policy)
prioritize_context_elements(bundle)
enforce_overflow_policy(bundle, policy)
estimate_tokens(text)
estimate_bundle_tokens(bundle)
retrieve_context(query, task_type, filters)        # stub only
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

# ─── Constants ────────────────────────────────────────────────────────────────

#: Deterministic priority ordering for context sections (1 = highest priority).
PRIORITY_ORDER: List[str] = [
    "primary_input",
    "policy_constraints",
    "prior_artifacts",
    "retrieved_context",
    "glossary_terms",
    "unresolved_questions",
]

#: Overflow actions understood by the budget enforcer.
OVERFLOW_ACTIONS = frozenset({"truncate_retrieval", "reject_call", "escalate"})

#: Approximate characters-per-token ratio used for lightweight estimation.
_CHARS_PER_TOKEN: float = 4.0


# ─── Token estimation ─────────────────────────────────────────────────────────

def estimate_tokens(text: str) -> int:
    """Return a lightweight, consistent token estimate for *text*.

    The estimate uses a fixed characters-per-token ratio (``_CHARS_PER_TOKEN``).
    It is intentionally approximate but consistent: calling this function twice
    with the same string always returns the same value.

    Parameters
    ----------
    text:
        Plain text whose token count is to be estimated.

    Returns
    -------
    int
        Non-negative estimated token count.
    """
    if not text:
        return 0
    return max(1, int(len(text) / _CHARS_PER_TOKEN))


def estimate_bundle_tokens(bundle: Dict[str, Any]) -> Dict[str, int]:
    """Estimate token counts for each major section of *bundle*.

    Returns a dict that mirrors the ``token_estimates`` field in the context
    bundle schema, keyed by section name.

    Parameters
    ----------
    bundle:
        A context bundle dict (not necessarily fully populated).

    Returns
    -------
    dict
        ``{section_name: estimated_token_count, ..., "total": int}``
    """
    def _text_of(value: Any) -> str:
        """Flatten a section value to a string for estimation purposes."""
        if isinstance(value, str):
            return value
        if isinstance(value, (dict, list)):
            import json as _json
            return _json.dumps(value, ensure_ascii=False)
        return str(value) if value is not None else ""

    estimates: Dict[str, int] = {}
    for section in PRIORITY_ORDER:
        estimates[section] = estimate_tokens(_text_of(bundle.get(section)))

    estimates["total"] = sum(estimates.values())
    return estimates


# ─── Prioritization ───────────────────────────────────────────────────────────

def prioritize_context_elements(bundle: Dict[str, Any]) -> Dict[str, Any]:
    """Return a new bundle with sections sorted in canonical priority order.

    Sections not listed in ``PRIORITY_ORDER`` are placed after the prioritized
    sections in their original relative order.  The ``metadata``,
    ``token_estimates``, and ``truncation_log`` keys are always preserved and
    placed at the end.

    Parameters
    ----------
    bundle:
        A context bundle dict.

    Returns
    -------
    dict
        A shallow copy of *bundle* with a ``priority_order`` key that records
        the final section ordering.
    """
    result: Dict[str, Any] = {}

    reserved = {"metadata", "token_estimates", "truncation_log", "context_id", "task_type",
                "priority_order"}

    # Fixed-order priority sections first.
    for section in PRIORITY_ORDER:
        if section in bundle:
            result[section] = bundle[section]

    # Remaining content sections in original order.
    for key, value in bundle.items():
        if key not in result and key not in reserved:
            result[key] = value

    # Reserved/administrative keys last.
    for key in reserved:
        if key in bundle:
            result[key] = bundle[key]

    result["priority_order"] = [s for s in PRIORITY_ORDER if s in bundle]
    return result


# ─── Budget enforcement ───────────────────────────────────────────────────────

def _validate_policy(policy: Dict[str, Any]) -> None:
    """Raise ``ValueError`` if *policy* contains an invalid configuration.

    Validates:
    - Required fields are present.
    - ``overflow_action`` is a recognised value.
    - All token reservations are non-negative integers.
    - The sum of reservations does not exceed ``total_budget_tokens``.
    """
    required = {
        "total_budget_tokens",
        "input_reservation",
        "policy_constraint_reservation",
        "retrieval_reservation",
        "output_reservation",
        "overflow_action",
    }
    missing = required - set(policy.keys())
    if missing:
        raise ValueError(f"Context budget policy is missing required keys: {sorted(missing)}")

    action = policy["overflow_action"]
    if action not in OVERFLOW_ACTIONS:
        raise ValueError(
            f"Invalid overflow_action '{action}'. Must be one of: {sorted(OVERFLOW_ACTIONS)}"
        )

    reservation_keys = [
        "input_reservation",
        "policy_constraint_reservation",
        "retrieval_reservation",
        "output_reservation",
    ]
    total = policy["total_budget_tokens"]
    reserved_sum = 0
    for key in reservation_keys:
        val = policy[key]
        if not isinstance(val, int) or val < 0:
            raise ValueError(f"Policy key '{key}' must be a non-negative integer; got {val!r}")
        reserved_sum += val

    if reserved_sum > total:
        raise ValueError(
            f"Sum of reservations ({reserved_sum}) exceeds total_budget_tokens ({total})"
        )


def apply_context_budget(
    bundle: Dict[str, Any],
    policy: Dict[str, Any],
) -> Dict[str, Any]:
    """Apply token budget constraints from *policy* to *bundle*.

    Updates ``token_estimates`` and ``truncation_log`` in-place (well, returns
    a modified copy) according to the policy.  Does NOT enforce the overflow
    action — call ``enforce_overflow_policy`` afterwards if needed.

    Rules
    -----
    1. ``primary_input`` is always included; it is never truncated here.
    2. ``policy_constraints`` may be truncated to ``policy_constraint_reservation``.
    3. ``retrieved_context`` may be truncated to ``retrieval_reservation``.
    4. ``token_estimates`` is recalculated after budget is applied.

    Parameters
    ----------
    bundle:
        A context bundle dict (modified copy is returned).
    policy:
        A context budget policy dict.

    Returns
    -------
    dict
        Modified bundle with ``token_estimates`` and ``truncation_log`` updated.

    Raises
    ------
    ValueError
        If the policy is invalid (missing keys, bad types, conflicting values).
    """
    _validate_policy(policy)

    result = dict(bundle)
    truncation_log: List[Dict[str, Any]] = list(result.get("truncation_log") or [])

    def _truncate_section(
        section_key: str,
        reservation_tokens: int,
        content: Any,
    ) -> Any:
        """Truncate *content* to approximately *reservation_tokens* tokens.

        Truncation is performed on the serialised text representation.  The
        original type is preserved (str → str; anything else → str of truncated
        JSON).  A truncation log entry is always appended when truncation occurs.
        """
        import json as _json

        if isinstance(content, str):
            text = content
        else:
            text = _json.dumps(content, ensure_ascii=False)

        current_tokens = estimate_tokens(text)
        if current_tokens <= reservation_tokens:
            return content  # nothing to do

        # Truncate to the character budget that corresponds to the token limit.
        char_limit = int(reservation_tokens * _CHARS_PER_TOKEN)
        truncated_text = text[:char_limit]

        truncation_log.append(
            {
                "section": section_key,
                "original_tokens": current_tokens,
                "allowed_tokens": reservation_tokens,
                "chars_removed": len(text) - len(truncated_text),
                "action": "truncated",
            }
        )

        # Return the same type the caller expects.
        if isinstance(content, str):
            return truncated_text

        # Best-effort: return the truncated text as a string so downstream
        # consumers can still use the data even if JSON is no longer valid.
        return truncated_text

    # Apply reservations to bounded sections.
    if "policy_constraints" in result:
        result["policy_constraints"] = _truncate_section(
            "policy_constraints",
            policy["policy_constraint_reservation"],
            result["policy_constraints"],
        )

    if "retrieved_context" in result:
        result["retrieved_context"] = _truncate_section(
            "retrieved_context",
            policy["retrieval_reservation"],
            result["retrieved_context"],
        )

    result["truncation_log"] = truncation_log
    result["token_estimates"] = estimate_bundle_tokens(result)
    return result


def enforce_overflow_policy(
    bundle: Dict[str, Any],
    policy: Dict[str, Any],
) -> Dict[str, Any]:
    """Enforce the overflow action when the bundle exceeds the total token budget.

    Must be called AFTER ``apply_context_budget``.

    Actions
    -------
    truncate_retrieval
        Remove ``retrieved_context`` entirely and log the action.
    reject_call
        Raise ``ContextBudgetExceededError``.
    escalate
        Raise ``ContextBudgetExceededError`` with ``escalation_required=True``.

    Parameters
    ----------
    bundle:
        A context bundle that has already had ``apply_context_budget`` applied.
    policy:
        The same budget policy used with ``apply_context_budget``.

    Returns
    -------
    dict
        Possibly modified bundle (if overflow action was ``truncate_retrieval``).

    Raises
    ------
    ContextBudgetExceededError
        When the overflow action is ``reject_call`` or ``escalate`` and the
        bundle still exceeds the budget.
    ValueError
        If the policy is invalid.
    """
    _validate_policy(policy)

    estimates = bundle.get("token_estimates") or estimate_bundle_tokens(bundle)
    total_used = estimates.get("total", 0)
    total_allowed = policy["total_budget_tokens"]

    if total_used <= total_allowed:
        return bundle  # budget satisfied — nothing to do

    action = policy["overflow_action"]
    result = dict(bundle)
    truncation_log: List[Dict[str, Any]] = list(result.get("truncation_log") or [])

    if action == "truncate_retrieval":
        # Remove retrieved context and log.
        original_tokens = estimates.get("retrieved_context", 0)
        result["retrieved_context"] = []
        truncation_log.append(
            {
                "section": "retrieved_context",
                "original_tokens": original_tokens,
                "allowed_tokens": 0,
                "chars_removed": None,
                "action": "overflow_truncate_retrieval",
            }
        )
        result["truncation_log"] = truncation_log
        result["token_estimates"] = estimate_bundle_tokens(result)
        return result

    if action == "reject_call":
        raise ContextBudgetExceededError(
            f"Context bundle token count ({total_used}) exceeds budget "
            f"({total_allowed}).  overflow_action=reject_call.",
            escalation_required=False,
            token_usage=total_used,
            token_budget=total_allowed,
        )

    # action == "escalate"
    raise ContextBudgetExceededError(
        f"Context bundle token count ({total_used}) exceeds budget "
        f"({total_allowed}).  Escalation required.",
        escalation_required=True,
        token_usage=total_used,
        token_budget=total_allowed,
    )


# ─── Retrieval stub ───────────────────────────────────────────────────────────

def retrieve_context(
    query: str,
    task_type: str,
    filters: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Retrieval interface stub.

    This function defines the retrieval contract.  No embeddings or vector
    databases are implemented here.  Callers should treat a return value of
    ``[]`` as a signal that no retrieval is available and set
    ``retrieval_status`` to ``"unavailable"`` in the assembly record.

    Return schema (each item)
    -------------------------
    artifact_id : str
    content     : str
    relevance_score : float  (0.0–1.0)
    provenance  : dict

    Parameters
    ----------
    query:
        Natural-language retrieval query.
    task_type:
        Task type string used to scope retrieval (e.g., ``"meeting_minutes"``).
    filters:
        Optional key/value filters to narrow retrieval scope.

    Returns
    -------
    list
        Always ``[]`` in this stub implementation.
    """
    # Stub: retrieval is not yet implemented.
    return []


# ─── Bundle builder ───────────────────────────────────────────────────────────

def build_context_bundle(
    task_type: str,
    input_payload: Dict[str, Any],
    source_artifacts: Optional[List[Dict[str, Any]]] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a governed context bundle for an AI task.

    The bundle contains all information the AI task needs, structured in the
    canonical section order.  The caller may supply a budget policy inside
    *config* under the ``budget_policy`` key; when present, the policy is
    applied via ``apply_context_budget`` and ``enforce_overflow_policy``.

    Parameters
    ----------
    task_type:
        Identifies the AI task that will consume the bundle (e.g.,
        ``"meeting_minutes"``, ``"gap_analysis"``).
    input_payload:
        Primary input for the task.  Must be a non-empty dict.  This is always
        included in the bundle regardless of budget constraints.
    source_artifacts:
        Optional list of artifact dicts that provide additional context
        (decisions, prior outputs, etc.).  Each item should carry an
        ``artifact_id`` key for traceability.
    config:
        Optional configuration dict.  Recognised keys:

        ``budget_policy``
            Budget policy dict (see ``apply_context_budget``).  When absent,
            no budget enforcement is performed.
        ``policy_constraints``
            Governing constraints/rules relevant to the task (string or dict).
        ``glossary_terms``
            Domain glossary entries (list of strings or dicts).
        ``unresolved_questions``
            Open questions to be provided as context (list of strings).

    Returns
    -------
    dict
        Context bundle conforming to ``context_bundle.schema.json``.

    Raises
    ------
    ValueError
        If *task_type* is empty or *input_payload* is empty.
    ContextBudgetExceededError
        When a budget policy is supplied and the bundle cannot fit within
        the budget using the configured overflow action.
    """
    if not task_type:
        raise ValueError("task_type must be a non-empty string")
    if not input_payload:
        raise ValueError("input_payload must be a non-empty dict")

    cfg = config or {}
    artifacts = source_artifacts or []

    context_id = _make_context_id(task_type, input_payload)

    # Build retrieval context (stub always returns []).
    retrieved = retrieve_context(query=task_type, task_type=task_type)
    retrieval_status = "unavailable" if not retrieved else "available"

    bundle: Dict[str, Any] = {
        "context_id": context_id,
        "task_type": task_type,
        "primary_input": input_payload,
        "policy_constraints": cfg.get("policy_constraints") or {},
        "retrieved_context": retrieved,
        "prior_artifacts": artifacts,
        "glossary_terms": cfg.get("glossary_terms") or [],
        "unresolved_questions": cfg.get("unresolved_questions") or [],
        "metadata": {
            "created_at": _utc_now(),
            "retrieval_status": retrieval_status,
            "source_artifact_ids": [a.get("artifact_id", "") for a in artifacts],
        },
        "token_estimates": {},
        "truncation_log": [],
    }

    # Apply budget policy if supplied.
    policy = cfg.get("budget_policy")
    if policy:
        bundle = apply_context_budget(bundle, policy)
        bundle = enforce_overflow_policy(bundle, policy)

    # Always recalculate token estimates.
    bundle["token_estimates"] = estimate_bundle_tokens(bundle)

    # Apply canonical prioritization.
    bundle = prioritize_context_elements(bundle)

    return bundle


# ─── Assembly record ──────────────────────────────────────────────────────────

def build_assembly_record(
    bundle: Dict[str, Any],
    policy: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a context assembly record for traceability and debugging.

    The record captures which sections were included or excluded, the token
    budget and usage, any overflow actions, and the retrieval status.

    Parameters
    ----------
    bundle:
        A fully assembled context bundle.
    policy:
        Optional budget policy that was applied to the bundle.

    Returns
    -------
    dict
        Context assembly record conforming to
        ``context_assembly_record.schema.json``.
    """
    estimates = bundle.get("token_estimates") or estimate_bundle_tokens(bundle)
    truncation_log = bundle.get("truncation_log") or []
    metadata = bundle.get("metadata") or {}

    included = [s for s in PRIORITY_ORDER if bundle.get(s)]
    excluded = [s for s in PRIORITY_ORDER if not bundle.get(s)]

    overflow_actions_taken = [
        entry["action"] for entry in truncation_log
    ]

    warnings: List[str] = []
    if metadata.get("retrieval_status") == "unavailable":
        warnings.append("retrieval_unavailable: no retrieved context was injected")
    if truncation_log:
        warnings.append(
            f"truncation_occurred: {len(truncation_log)} section(s) were truncated"
        )

    return {
        "context_id": bundle.get("context_id", ""),
        "task_type": bundle.get("task_type", ""),
        "source_artifact_ids": metadata.get("source_artifact_ids", []),
        "included_sections": included,
        "excluded_sections": excluded,
        "token_budget": (policy or {}).get("total_budget_tokens"),
        "token_usage": estimates.get("total", 0),
        "overflow_actions_taken": overflow_actions_taken,
        "retrieval_status": metadata.get("retrieval_status", "unavailable"),
        "warnings": warnings,
        "timestamp": _utc_now(),
    }


# ─── Exceptions ───────────────────────────────────────────────────────────────

class ContextBudgetExceededError(Exception):
    """Raised when a context bundle cannot satisfy the configured token budget.

    Attributes
    ----------
    escalation_required : bool
        ``True`` when the overflow action is ``escalate``.
    token_usage : int
        Actual estimated token count of the bundle.
    token_budget : int
        Configured total token budget.
    """

    def __init__(
        self,
        message: str,
        *,
        escalation_required: bool = False,
        token_usage: int = 0,
        token_budget: int = 0,
    ) -> None:
        super().__init__(message)
        self.escalation_required = escalation_required
        self.token_usage = token_usage
        self.token_budget = token_budget


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _utc_now() -> str:
    """Return current UTC time as ISO-8601 string (seconds precision)."""
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat()


def _make_context_id(task_type: str, input_payload: Dict[str, Any]) -> str:
    """Derive a deterministic context_id from task_type and input_payload.

    Uses a SHA-256 digest of the canonical JSON representation.
    """
    import json as _json

    canonical = _json.dumps(
        {"task_type": task_type, "input_payload": input_payload},
        sort_keys=True,
        ensure_ascii=False,
    )
    digest = hashlib.sha256(canonical.encode()).hexdigest()[:16]
    return f"ctx-{digest}"
