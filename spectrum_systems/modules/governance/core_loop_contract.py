"""CL-01 / CL-03: Core loop contract — pure validator for the canonical
AEX → PQX → EVL → TPA → CDE → SEL handoff chain.

This module is non-owning support. It does not decide, gate, orchestrate,
or enforce. Canonical authority remains with:

  * AEX (admission), PQX (execution), EVL (required-eval registry),
  * TPA (trust/policy), CDE (closure/control), SEL (enforcement).

The validator answers two questions deterministically:

  1. Does a candidate ``core_loop_contract`` artifact have the fields
     required by ``contracts/schemas/core_loop_contract.schema.json``
     (canonical 6-stage order, the 5 transitions, the fixed reason
     precedence, the terminal status set)?

  2. Does a supplied stage / transition payload satisfy the required
     handoff fields and the required input/output references declared
     by the contract for a given transition?

Failures emit a stable canonical reason code and do not raise; the
caller (CLI, test, downstream packet) folds the reason into the wider
core-loop primary-reason policy.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

CANONICAL_STAGE_ORDER: Tuple[str, ...] = ("AEX", "PQX", "EVL", "TPA", "CDE", "SEL")
CANONICAL_TRANSITIONS: Tuple[Tuple[str, str], ...] = (
    ("AEX", "PQX"),
    ("PQX", "EVL"),
    ("EVL", "TPA"),
    ("TPA", "CDE"),
    ("CDE", "SEL"),
)
CANONICAL_TERMINAL_STATUSES: Tuple[str, ...] = ("pass", "block", "freeze")
CANONICAL_REASON_PRECEDENCE: Tuple[str, ...] = (
    "admission",
    "execution",
    "eval",
    "policy",
    "decision",
    "action",
)

REASON_CONTRACT_OK = "CORE_LOOP_CONTRACT_OK"
REASON_CONTRACT_BAD_STAGE_ORDER = "CORE_LOOP_CONTRACT_BAD_STAGE_ORDER"
REASON_CONTRACT_BAD_TRANSITIONS = "CORE_LOOP_CONTRACT_BAD_TRANSITIONS"
REASON_CONTRACT_BAD_TERMINAL = "CORE_LOOP_CONTRACT_BAD_TERMINAL"
REASON_CONTRACT_BAD_PRECEDENCE = "CORE_LOOP_CONTRACT_BAD_PRECEDENCE"
REASON_CONTRACT_MISSING_FIELD = "CORE_LOOP_CONTRACT_MISSING_FIELD"
REASON_HANDOFF_MISSING_FIELD = "CORE_LOOP_HANDOFF_MISSING_FIELD"
REASON_HANDOFF_MISSING_REF = "CORE_LOOP_HANDOFF_MISSING_REF"
REASON_HANDOFF_UNKNOWN_TRANSITION = "CORE_LOOP_HANDOFF_UNKNOWN_TRANSITION"
REASON_HANDOFF_OUT_OF_ORDER = "CORE_LOOP_HANDOFF_OUT_OF_ORDER"


class CoreLoopContractError(ValueError):
    """Raised only on programmer-misuse (e.g. None contract object)."""


def _violation(code: str, **details: Any) -> Dict[str, Any]:
    return {"reason_code": code, **details}


def validate_core_loop_contract(contract: Mapping[str, Any]) -> Dict[str, Any]:
    """Validate that ``contract`` is a well-formed core_loop_contract artifact.

    Returns a dict ``{"ok": bool, "violations": [...], "primary_reason": str}``.
    Never raises for content errors — the caller folds the result into the
    primary-reason policy.
    """
    if not isinstance(contract, Mapping):
        raise CoreLoopContractError("contract must be a mapping")

    violations: List[Dict[str, Any]] = []

    required_fields = (
        "artifact_type",
        "schema_version",
        "contract_id",
        "stage_order",
        "transitions",
        "terminal_statuses",
        "reason_precedence",
        "non_authority_assertions",
    )
    for field in required_fields:
        if field not in contract:
            violations.append(
                _violation(REASON_CONTRACT_MISSING_FIELD, field=field)
            )

    if contract.get("artifact_type") != "core_loop_contract":
        violations.append(
            _violation(
                REASON_CONTRACT_MISSING_FIELD,
                field="artifact_type",
                expected="core_loop_contract",
                got=contract.get("artifact_type"),
            )
        )

    stage_order = contract.get("stage_order")
    if list(stage_order or []) != list(CANONICAL_STAGE_ORDER):
        violations.append(
            _violation(
                REASON_CONTRACT_BAD_STAGE_ORDER,
                expected=list(CANONICAL_STAGE_ORDER),
                got=stage_order,
            )
        )

    transitions = contract.get("transitions") or []
    if not isinstance(transitions, Sequence) or len(transitions) != len(
        CANONICAL_TRANSITIONS
    ):
        violations.append(
            _violation(
                REASON_CONTRACT_BAD_TRANSITIONS,
                expected_count=len(CANONICAL_TRANSITIONS),
                got_count=len(transitions) if isinstance(transitions, Sequence) else 0,
            )
        )
    else:
        for idx, t in enumerate(transitions):
            if not isinstance(t, Mapping):
                violations.append(
                    _violation(REASON_CONTRACT_BAD_TRANSITIONS, index=idx)
                )
                continue
            pair = (t.get("from_stage"), t.get("to_stage"))
            if pair != CANONICAL_TRANSITIONS[idx]:
                violations.append(
                    _violation(
                        REASON_CONTRACT_BAD_TRANSITIONS,
                        index=idx,
                        expected=list(CANONICAL_TRANSITIONS[idx]),
                        got=list(pair),
                    )
                )
            for k in (
                "required_handoff_fields",
                "required_input_refs",
                "required_output_refs",
            ):
                if not isinstance(t.get(k), Sequence):
                    violations.append(
                        _violation(
                            REASON_CONTRACT_BAD_TRANSITIONS,
                            index=idx,
                            missing_key=k,
                        )
                    )

    terminal = contract.get("terminal_statuses")
    if set(terminal or []) != set(CANONICAL_TERMINAL_STATUSES):
        violations.append(
            _violation(
                REASON_CONTRACT_BAD_TERMINAL,
                expected=list(CANONICAL_TERMINAL_STATUSES),
                got=terminal,
            )
        )

    precedence = contract.get("reason_precedence")
    if list(precedence or []) != list(CANONICAL_REASON_PRECEDENCE):
        violations.append(
            _violation(
                REASON_CONTRACT_BAD_PRECEDENCE,
                expected=list(CANONICAL_REASON_PRECEDENCE),
                got=precedence,
            )
        )

    primary_reason = REASON_CONTRACT_OK
    if violations:
        primary_reason = violations[0]["reason_code"]

    return {
        "ok": not violations,
        "violations": violations,
        "primary_reason": primary_reason,
    }


def transition_spec(
    contract: Mapping[str, Any], from_stage: str, to_stage: str
) -> Optional[Mapping[str, Any]]:
    """Return the transition entry for ``from_stage → to_stage`` if present."""
    for t in contract.get("transitions") or ():
        if isinstance(t, Mapping) and t.get("from_stage") == from_stage and t.get(
            "to_stage"
        ) == to_stage:
            return t
    return None


def validate_handoff(
    contract: Mapping[str, Any],
    *,
    from_stage: str,
    to_stage: str,
    handoff_fields: Mapping[str, Any],
    input_refs: Mapping[str, Any],
    output_refs: Mapping[str, Any],
) -> Dict[str, Any]:
    """Validate a candidate handoff payload against the contract.

    Returns ``{"ok": bool, "violations": [...], "primary_reason": str}``.
    A handoff is OK only when:
      * ``(from_stage, to_stage)`` is a canonical transition and appears in
        the contract,
      * every ``required_handoff_field`` is present and non-empty,
      * every ``required_input_ref`` and ``required_output_ref`` resolves to
        a non-empty string in the supplied dict.
    """
    if (from_stage, to_stage) not in CANONICAL_TRANSITIONS:
        return {
            "ok": False,
            "violations": [
                _violation(
                    REASON_HANDOFF_OUT_OF_ORDER,
                    from_stage=from_stage,
                    to_stage=to_stage,
                )
            ],
            "primary_reason": REASON_HANDOFF_OUT_OF_ORDER,
        }

    spec = transition_spec(contract, from_stage, to_stage)
    if spec is None:
        return {
            "ok": False,
            "violations": [
                _violation(
                    REASON_HANDOFF_UNKNOWN_TRANSITION,
                    from_stage=from_stage,
                    to_stage=to_stage,
                )
            ],
            "primary_reason": REASON_HANDOFF_UNKNOWN_TRANSITION,
        }

    violations: List[Dict[str, Any]] = []

    for field in spec.get("required_handoff_fields") or ():
        v = handoff_fields.get(field) if isinstance(handoff_fields, Mapping) else None
        if not isinstance(v, str) or not v.strip():
            violations.append(
                _violation(REASON_HANDOFF_MISSING_FIELD, field=field)
            )

    for ref_key in spec.get("required_input_refs") or ():
        v = input_refs.get(ref_key) if isinstance(input_refs, Mapping) else None
        if not isinstance(v, str) or not v.strip():
            violations.append(
                _violation(REASON_HANDOFF_MISSING_REF, ref=ref_key, side="input")
            )

    for ref_key in spec.get("required_output_refs") or ():
        v = output_refs.get(ref_key) if isinstance(output_refs, Mapping) else None
        if not isinstance(v, str) or not v.strip():
            violations.append(
                _violation(REASON_HANDOFF_MISSING_REF, ref=ref_key, side="output")
            )

    primary_reason = "CORE_LOOP_HANDOFF_OK"
    if violations:
        primary_reason = violations[0]["reason_code"]

    return {
        "ok": not violations,
        "violations": violations,
        "primary_reason": primary_reason,
    }


def build_default_core_loop_contract(contract_id: str = "CL-CORE-LOOP-CONTRACT-01") -> Dict[str, Any]:
    """Return a canonical, in-memory core_loop_contract artifact.

    Useful for tests, CLI defaults, and golden examples.
    """
    return {
        "artifact_type": "core_loop_contract",
        "schema_version": "1.0.0",
        "contract_id": contract_id,
        "description": "Canonical AEX→PQX→EVL→TPA→CDE→SEL meta-contract.",
        "stage_order": list(CANONICAL_STAGE_ORDER),
        "stage_required_refs": {
            "AEX": ["aex_admission_ref"],
            "PQX": ["pqx_execution_envelope_ref"],
            "EVL": ["evl_eval_summary_ref"],
            "TPA": ["tpa_policy_input_ref", "tpa_policy_result_ref"],
            "CDE": ["cde_decision_input_ref", "cde_decision_ref"],
            "SEL": ["sel_action_ref"],
        },
        "transitions": [
            {
                "from_stage": "AEX",
                "to_stage": "PQX",
                "required_handoff_fields": ["admission_class", "trace_id", "run_id"],
                "required_input_refs": ["aex_admission_ref"],
                "required_output_refs": ["aex_admission_ref"],
            },
            {
                "from_stage": "PQX",
                "to_stage": "EVL",
                "required_handoff_fields": ["run_id", "trace_id", "execution_status"],
                "required_input_refs": ["aex_admission_ref"],
                "required_output_refs": ["pqx_execution_envelope_ref"],
            },
            {
                "from_stage": "EVL",
                "to_stage": "TPA",
                "required_handoff_fields": ["trace_id", "eval_summary_status"],
                "required_input_refs": ["pqx_execution_envelope_ref"],
                "required_output_refs": ["evl_eval_summary_ref"],
            },
            {
                "from_stage": "TPA",
                "to_stage": "CDE",
                "required_handoff_fields": ["trace_id", "policy_result_status"],
                "required_input_refs": ["evl_eval_summary_ref", "tpa_policy_input_ref"],
                "required_output_refs": ["tpa_policy_result_ref"],
            },
            {
                "from_stage": "CDE",
                "to_stage": "SEL",
                "required_handoff_fields": ["trace_id", "control_outcome"],
                "required_input_refs": ["tpa_policy_result_ref", "cde_decision_input_ref"],
                "required_output_refs": ["cde_decision_ref"],
            },
        ],
        "terminal_statuses": list(CANONICAL_TERMINAL_STATUSES),
        "reason_precedence": list(CANONICAL_REASON_PRECEDENCE),
        "stage_owners": {s: s for s in CANONICAL_STAGE_ORDER},
        "non_authority_assertions": [
            "preparatory_only",
            "not_admission_authority",
            "not_execution_authority",
            "not_eval_authority",
            "not_policy_authority",
            "not_control_authority",
            "not_enforcement_authority",
        ],
    }


__all__ = [
    "CANONICAL_STAGE_ORDER",
    "CANONICAL_TRANSITIONS",
    "CANONICAL_TERMINAL_STATUSES",
    "CANONICAL_REASON_PRECEDENCE",
    "CoreLoopContractError",
    "REASON_CONTRACT_OK",
    "REASON_CONTRACT_BAD_STAGE_ORDER",
    "REASON_CONTRACT_BAD_TRANSITIONS",
    "REASON_CONTRACT_BAD_TERMINAL",
    "REASON_CONTRACT_BAD_PRECEDENCE",
    "REASON_CONTRACT_MISSING_FIELD",
    "REASON_HANDOFF_MISSING_FIELD",
    "REASON_HANDOFF_MISSING_REF",
    "REASON_HANDOFF_UNKNOWN_TRANSITION",
    "REASON_HANDOFF_OUT_OF_ORDER",
    "validate_core_loop_contract",
    "validate_handoff",
    "transition_spec",
    "build_default_core_loop_contract",
]
