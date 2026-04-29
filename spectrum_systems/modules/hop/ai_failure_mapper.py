"""HOP AI failure pattern → system improvement proposal mapper.

Consumes structured ``hop_harness_ai_failure_pattern`` records describing
recurring AI/coding-agent failures and emits bounded, advisory
``hop_harness_system_improvement_proposal`` artifacts.

Authority boundary (hard):
- HOP proposes only. It never executes, authorizes, or acts.
- CDE/GOV must authorize before any mutation can occur.
- PQX executes authorized implementation slices.
- EVL validates.
- SEL acts on its own signals.

Any proposal artifact that omits or misrepresents this boundary is
rejected by both this module and the schema validator.

Mapping table (deterministic):
    stream_idle_timeout           → execution_budget (PQX) + checkpoint_requirement (HNX)
    ai_over_scoped_execution      → admission_rule (AEX) + execution_budget (RDX split)
    missing_checkpoint            → checkpoint_requirement (HNX) + enforcement_signal (SEL)
    budget_exhausted              → continuation_policy (CDE) + execution_budget (PQX)
    scope_drift                   → eval_case (EVL scope_adherence) + admission_rule (AEX)
    eval_indeterminate            → continuation_policy (CDE fail-closed) + eval_case (EVL)
    architecture_boundary_violation → admission_rule (AEX) + eval_case (EVL architecture)

Each proposal includes at least one required_eval entry proving the guardrail
works, satisfying the eval factory hook requirement.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from spectrum_systems.modules.hop.artifacts import finalize_artifact, make_trace
from spectrum_systems.modules.hop.schemas import HopSchemaError, validate_hop_artifact

_AUTHORITY_BOUNDARY: dict[str, Any] = {
    "hop_role": "proposes_only",
    "review_owners": ["CDE", "GOV"],
    "execution_owner": "PQX",
    "validation_owner": "EVL",
    "enforcement_signal_owner": "SEL",
}

_VALID_FAILURE_TYPES = frozenset({
    "stream_idle_timeout",
    "ai_over_scoped_execution",
    "missing_checkpoint",
    "budget_exhausted",
    "scope_drift",
    "eval_indeterminate",
    "architecture_boundary_violation",
})

_VALID_CHANGE_TYPES = frozenset({
    "admission_rule",
    "execution_budget",
    "checkpoint_requirement",
    "eval_case",
    "continuation_policy",
    "enforcement_signal",
    "observability_signal",
    "prl_prevention_rule",
})


class AIFailureMapperError(Exception):
    """Raised when the mapper cannot produce a valid artifact."""


def _utcnow() -> str:
    return (
        datetime.now(tz=timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


# ---------------------------------------------------------------------------
# Mapping spec: each entry describes one proposal to emit per failure type.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _ProposalSpec:
    change_type: str
    target_systems: tuple[str, ...]
    guardrail: str
    expected_prevention: str
    eval_cases: tuple[dict[str, str], ...]
    required_tests: tuple[str, ...]


_FAILURE_TO_PROPOSALS: dict[str, tuple[_ProposalSpec, ...]] = {
    "stream_idle_timeout": (
        _ProposalSpec(
            change_type="execution_budget",
            target_systems=("PQX",),
            guardrail="Require explicit token/time budget on every broad-scope execution request; reject requests missing a declared budget.",
            expected_prevention="Prevents runaway AI sessions from idling past resource limits without a checkpoint.",
            eval_cases=(
                {
                    "eval_case_id": "hop_eval_budget_required_for_broad_prompt",
                    "description": "A broad prompt without a declared budget must be rejected at admission.",
                    "expected_outcome": "admission_rejected:missing_execution_budget",
                },
                {
                    "eval_case_id": "hop_eval_budget_stop_after_checkpoint",
                    "description": "stop_after_checkpoint flag prevents continuation past the budget boundary.",
                    "expected_outcome": "execution_halted:stop_after_checkpoint_activated",
                },
            ),
            required_tests=(
                "test_broad_prompt_without_budget_is_rejected",
                "test_stop_after_checkpoint_halts_execution",
            ),
        ),
        _ProposalSpec(
            change_type="checkpoint_requirement",
            target_systems=("HNX",),
            guardrail="Require a valid checkpoint artifact before any continuation past the declared budget boundary; block continuation without one.",
            expected_prevention="Prevents continuation after idle timeout by requiring a written checkpoint before proceeding.",
            eval_cases=(
                {
                    "eval_case_id": "hop_eval_keep_going_without_checkpoint_blocked",
                    "description": "Continuation past budget without a checkpoint artifact is blocked.",
                    "expected_outcome": "continuation_blocked:missing_checkpoint",
                },
            ),
            required_tests=(
                "test_continuation_without_checkpoint_is_blocked",
            ),
        ),
    ),
    "ai_over_scoped_execution": (
        _ProposalSpec(
            change_type="admission_rule",
            target_systems=("AEX",),
            guardrail="AEX must reject execution requests whose declared scope (affected_files, modules) exceeds a governed threshold; require explicit split before re-admission.",
            expected_prevention="Prevents AI agents from claiming unbounded file/module scope on a single execution request.",
            eval_cases=(
                {
                    "eval_case_id": "hop_eval_over_scoped_request_rejected_at_aex",
                    "description": "An execution request whose file scope exceeds the allowed threshold is rejected at AEX with a split requirement.",
                    "expected_outcome": "admission_rejected:scope_too_broad",
                },
            ),
            required_tests=(
                "test_over_scoped_request_rejected_by_aex",
            ),
        ),
        _ProposalSpec(
            change_type="execution_budget",
            target_systems=("RDX",),
            guardrail="RDX must require a maximum slice size; any execution request that cannot be split into bounded slices is rejected.",
            expected_prevention="Prevents a single over-scoped execution from escaping decomposition into reviewable slices.",
            eval_cases=(
                {
                    "eval_case_id": "hop_eval_rdx_rejects_unsplittable_request",
                    "description": "RDX rejects an execution request that cannot be split into slices within budget.",
                    "expected_outcome": "rdx_rejected:slice_budget_exceeded",
                },
            ),
            required_tests=(
                "test_rdx_rejects_unsplittable_over_scoped_request",
            ),
        ),
    ),
    "missing_checkpoint": (
        _ProposalSpec(
            change_type="checkpoint_requirement",
            target_systems=("HNX",),
            guardrail="HNX must require a written checkpoint artifact at each declared stage boundary; reject stage advancement without one.",
            expected_prevention="Prevents silent stage advancement without a durable checkpoint, ensuring recovery from mid-run failures.",
            eval_cases=(
                {
                    "eval_case_id": "hop_eval_hnx_blocks_stage_advance_without_checkpoint",
                    "description": "HNX blocks stage advancement when no checkpoint artifact exists for the current stage.",
                    "expected_outcome": "stage_blocked:missing_checkpoint_artifact",
                },
            ),
            required_tests=(
                "test_hnx_blocks_advancement_without_checkpoint",
            ),
        ),
        _ProposalSpec(
            change_type="enforcement_signal",
            target_systems=("SEL",),
            guardrail="SEL must emit a block signal for any continuation request arriving without a corresponding checkpoint artifact.",
            expected_prevention="Prevents continuation past the signal gate: even if a checkpoint requirement is missed upstream, a blocking signal is generated before continuation proceeds.",
            eval_cases=(
                {
                    "eval_case_id": "hop_eval_sel_blocks_continuation_missing_checkpoint",
                    "description": "A block signal is generated for a continuation request that lacks a corresponding checkpoint artifact.",
                    "expected_outcome": "sel_signal_block:continuation_without_checkpoint",
                },
            ),
            required_tests=(
                "test_sel_signal_blocks_checkpointless_continuation",
            ),
        ),
    ),
    "budget_exhausted": (
        _ProposalSpec(
            change_type="continuation_policy",
            target_systems=("CDE",),
            guardrail="CDE must emit a split_followup input signal when budget is exhausted; never allow implicit continuation past budget.",
            expected_prevention="Prevents silent over-run by requiring an explicit CDE split input before any further execution.",
            eval_cases=(
                {
                    "eval_case_id": "hop_eval_cde_emits_split_on_budget_exhaustion",
                    "description": "A split_followup input signal is generated when a budget-exhausted signal arrives.",
                    "expected_outcome": "cde_input:split_followup_emitted",
                },
            ),
            required_tests=(
                "test_cde_emits_split_input_on_budget_exhaustion",
            ),
        ),
        _ProposalSpec(
            change_type="execution_budget",
            target_systems=("PQX",),
            guardrail="PQX must halt and record a budget_exhausted closure artifact when the declared budget is consumed; never continue silently.",
            expected_prevention="Ensures PQX produces a traceable closure record rather than silently overrunning the budget.",
            eval_cases=(
                {
                    "eval_case_id": "hop_eval_pqx_halts_and_records_budget_closure",
                    "description": "PQX records a budget_exhausted closure artifact and halts when the declared budget is consumed.",
                    "expected_outcome": "pqx_closure:budget_exhausted_recorded",
                },
            ),
            required_tests=(
                "test_pqx_records_budget_exhausted_closure",
            ),
        ),
    ),
    "scope_drift": (
        _ProposalSpec(
            change_type="eval_case",
            target_systems=("EVL",),
            guardrail="EVL must include a scope_adherence eval that verifies every execution output stays within the declared allowed_files contract.",
            expected_prevention="Detects scope drift at eval time before any change reaches the merge gate; ensures the eval gate catches out-of-contract writes.",
            eval_cases=(
                {
                    "eval_case_id": "hop_eval_scope_adherence_blocks_out_of_contract_output",
                    "description": "EVL scope_adherence eval rejects an execution output that writes outside the declared allowed_files.",
                    "expected_outcome": "eval_gate_blocked:scope_adherence_violation",
                },
            ),
            required_tests=(
                "test_evl_scope_adherence_blocks_out_of_contract_write",
            ),
        ),
        _ProposalSpec(
            change_type="admission_rule",
            target_systems=("AEX",),
            guardrail="AEX must validate the allowed_files contract at admission time; reject requests whose declared scope does not match a registered contract.",
            expected_prevention="Prevents scope drift from entering the runtime by catching it at admission before any execution starts.",
            eval_cases=(
                {
                    "eval_case_id": "hop_eval_aex_rejects_uncontracted_scope",
                    "description": "AEX rejects an execution request whose allowed_files list is not registered in the contract registry.",
                    "expected_outcome": "admission_rejected:unregistered_allowed_files_contract",
                },
            ),
            required_tests=(
                "test_aex_rejects_uncontracted_scope_at_admission",
            ),
        ),
    ),
    "eval_indeterminate": (
        _ProposalSpec(
            change_type="continuation_policy",
            target_systems=("CDE",),
            guardrail="CDE must apply fail-closed behavior when an eval result is indeterminate: treat indeterminate as block, never as pass.",
            expected_prevention="Prevents silent merge-gate bypass when eval coverage is ambiguous; ensures indeterminate evals block rather than slip through.",
            eval_cases=(
                {
                    "eval_case_id": "hop_eval_indeterminate_treated_as_block_by_cde",
                    "description": "A block input signal is generated when an EVL result arrives with an indeterminate outcome.",
                    "expected_outcome": "cde_input:block:eval_indeterminate",
                },
                {
                    "eval_case_id": "hop_eval_indeterminate_not_treated_as_pass",
                    "description": "CDE must not emit an allow input signal when the EVL result is indeterminate.",
                    "expected_outcome": "cde_input_not_allow:eval_indeterminate",
                },
            ),
            required_tests=(
                "test_cde_blocks_on_indeterminate_eval",
                "test_cde_does_not_pass_on_indeterminate_eval",
            ),
        ),
        _ProposalSpec(
            change_type="eval_case",
            target_systems=("EVL",),
            guardrail="EVL must emit a structured indeterminate record with a reason code when an eval cannot produce a definitive pass/fail; never return an empty or null result.",
            expected_prevention="Ensures CDE always has a structured signal to act on; prevents null/empty eval results from causing silent bypass.",
            eval_cases=(
                {
                    "eval_case_id": "hop_eval_evl_emits_structured_indeterminate_record",
                    "description": "EVL emits a structured indeterminate record with a non-empty reason code when it cannot determine pass/fail.",
                    "expected_outcome": "evl_record:indeterminate_with_reason_code",
                },
            ),
            required_tests=(
                "test_evl_emits_structured_indeterminate_not_null",
            ),
        ),
    ),
    "architecture_boundary_violation": (
        _ProposalSpec(
            change_type="admission_rule",
            target_systems=("AEX",),
            guardrail="AEX must require reviewer_required=true for any request that touches canonical ownership boundaries across more than one 3-letter system.",
            expected_prevention="Prevents automated cross-system changes from entering the runtime without explicit reviewer sign-off.",
            eval_cases=(
                {
                    "eval_case_id": "hop_eval_aex_requires_reviewer_for_cross_boundary",
                    "description": "AEX sets reviewer_required=true when a request crosses canonical 3-letter system ownership boundaries.",
                    "expected_outcome": "admission_record:reviewer_required_true",
                },
            ),
            required_tests=(
                "test_aex_sets_human_review_for_cross_boundary_request",
            ),
        ),
        _ProposalSpec(
            change_type="eval_case",
            target_systems=("EVL",),
            guardrail="EVL must include an architecture_boundary eval that verifies no output modifies artifacts belonging to more than one canonical system without a reviewer_sign_off signal.",
            expected_prevention="Detects architecture boundary violations at eval time; ensures the eval gate catches cross-authority writes.",
            eval_cases=(
                {
                    "eval_case_id": "hop_eval_architecture_boundary_blocks_cross_authority_write",
                    "description": "EVL architecture eval blocks an output that modifies artifacts under two different canonical 3-letter system authorities.",
                    "expected_outcome": "eval_gate_blocked:architecture_boundary_violation",
                },
            ),
            required_tests=(
                "test_evl_architecture_eval_blocks_cross_authority_output",
            ),
        ),
    ),
}


# ---------------------------------------------------------------------------
# Public builders
# ---------------------------------------------------------------------------


def build_ai_failure_pattern(
    *,
    failure_pattern_id: str,
    failure_type: str,
    agent_or_provider: str,
    prompt_pattern: str,
    affected_stage: str,
    recurrence_count: int,
    severity: str,
    observed_symptoms: list[str],
    recommended_preventions: list[str],
    source_refs: list[str],
    trace_id: str = "hop_ai_failure_mapper",
) -> dict[str, Any]:
    """Build and validate a ``hop_harness_ai_failure_pattern`` artifact.

    Fails closed: raises :class:`AIFailureMapperError` if any required field
    is missing or the failure_type is not in the governed enum.
    """
    if not isinstance(failure_pattern_id, str) or not failure_pattern_id:
        raise AIFailureMapperError("hop_ai_failure_mapper:invalid_failure_pattern_id")
    if not isinstance(failure_type, str) or failure_type not in _VALID_FAILURE_TYPES:
        raise AIFailureMapperError(
            f"hop_ai_failure_mapper:unknown_failure_type:{failure_type}"
        )
    if not isinstance(recurrence_count, int) or recurrence_count < 1:
        raise AIFailureMapperError(
            f"hop_ai_failure_mapper:invalid_recurrence_count:{recurrence_count}"
        )
    for field_name, field_val in (
        ("observed_symptoms", observed_symptoms),
        ("recommended_preventions", recommended_preventions),
        ("source_refs", source_refs),
    ):
        if not isinstance(field_val, list):
            raise AIFailureMapperError(
                f"hop_ai_failure_mapper:{field_name}_must_be_list"
            )
    if not observed_symptoms:
        raise AIFailureMapperError("hop_ai_failure_mapper:empty_observed_symptoms")
    if not recommended_preventions:
        raise AIFailureMapperError("hop_ai_failure_mapper:empty_recommended_preventions")
    if not source_refs:
        raise AIFailureMapperError("hop_ai_failure_mapper:empty_source_refs")

    payload: dict[str, Any] = {
        "artifact_type": "hop_harness_ai_failure_pattern",
        "schema_ref": "hop/harness_ai_failure_pattern.schema.json",
        "schema_version": "1.0.0",
        "trace": make_trace(primary=trace_id, related=[failure_pattern_id, failure_type]),
        "failure_pattern_id": failure_pattern_id,
        "failure_type": failure_type,
        "agent_or_provider": agent_or_provider,
        "prompt_pattern": prompt_pattern,
        "affected_stage": affected_stage,
        "recurrence_count": recurrence_count,
        "severity": severity,
        "observed_symptoms": list(observed_symptoms),
        "recommended_preventions": list(recommended_preventions),
        "source_refs": list(source_refs),
        "recorded_at": _utcnow(),
    }
    finalize_artifact(payload, id_prefix="hop_ai_failure_")
    validate_hop_artifact(payload, "hop_harness_ai_failure_pattern")
    return payload


def _build_proposal(
    *,
    failure_pattern_id: str,
    spec: _ProposalSpec,
    proposal_index: int,
    trace_id: str,
) -> dict[str, Any]:
    proposal_id = (
        f"hop_prop_{failure_pattern_id}_{spec.change_type}_{proposal_index:02d}"
    )
    required_eval = [dict(ec) for ec in spec.eval_cases]
    required_tests = list(spec.required_tests)

    payload: dict[str, Any] = {
        "artifact_type": "hop_harness_system_improvement_proposal",
        "schema_ref": "hop/harness_system_improvement_proposal.schema.json",
        "schema_version": "1.0.0",
        "trace": make_trace(
            primary=trace_id,
            related=[failure_pattern_id, spec.change_type] + list(spec.target_systems),
        ),
        "proposal_id": proposal_id,
        "source_failure_pattern_id": failure_pattern_id,
        "target_systems": list(spec.target_systems),
        "proposed_change_type": spec.change_type,
        "proposed_guardrail": spec.guardrail,
        "expected_prevention": spec.expected_prevention,
        "required_eval": required_eval,
        "required_tests": required_tests,
        "authority_boundary": {k: list(v) if isinstance(v, list) else v for k, v in _AUTHORITY_BOUNDARY.items()},
        "advisory_only": True,
        "status": "proposed",
        "generated_at": _utcnow(),
    }
    finalize_artifact(payload, id_prefix="hop_proposal_")
    validate_hop_artifact(payload, "hop_harness_system_improvement_proposal")
    return payload


def map_failure_to_proposals(
    failure_pattern: dict[str, Any],
    *,
    trace_id: str = "hop_ai_failure_mapper",
) -> list[dict[str, Any]]:
    """Deterministically map a failure pattern artifact to a list of proposals.

    Input must be a validated ``hop_harness_ai_failure_pattern`` artifact.
    Returns one or more ``hop_harness_system_improvement_proposal`` artifacts.
    Fails closed: unknown failure_type raises :class:`AIFailureMapperError`.
    """
    if not isinstance(failure_pattern, dict):
        raise AIFailureMapperError("hop_ai_failure_mapper:input_not_dict")
    if failure_pattern.get("artifact_type") != "hop_harness_ai_failure_pattern":
        raise AIFailureMapperError(
            "hop_ai_failure_mapper:input_wrong_artifact_type:"
            f"{failure_pattern.get('artifact_type')}"
        )
    failure_type = failure_pattern.get("failure_type")
    if not isinstance(failure_type, str) or failure_type not in _FAILURE_TO_PROPOSALS:
        raise AIFailureMapperError(
            f"hop_ai_failure_mapper:no_mapping_for_failure_type:{failure_type}"
        )
    try:
        validate_hop_artifact(failure_pattern, "hop_harness_ai_failure_pattern")
    except HopSchemaError as exc:
        raise AIFailureMapperError(
            f"hop_ai_failure_mapper:invalid_input_failure_pattern:{exc}"
        ) from exc
    pattern_id = failure_pattern.get("failure_pattern_id")
    if not isinstance(pattern_id, str) or not pattern_id:
        raise AIFailureMapperError("hop_ai_failure_mapper:missing_failure_pattern_id")

    proposals: list[dict[str, Any]] = []
    for idx, spec in enumerate(_FAILURE_TO_PROPOSALS[failure_type]):
        proposal = _build_proposal(
            failure_pattern_id=pattern_id,
            spec=spec,
            proposal_index=idx,
            trace_id=trace_id,
        )
        proposals.append(proposal)
    return proposals


def validate_proposal_authority_boundary(proposal: dict[str, Any]) -> None:
    """Assert that a proposal does not claim direct mutation or extra authority.

    Raises :class:`AIFailureMapperError` if the authority_boundary is absent,
    malformed, or claims a role other than ``proposes_only``.

    This is a defence-in-depth check: the JSON schema already enforces
    ``hop_role = const "proposes_only"``. This function provides a
    fast-path Python-level check for callers that build proposals inline.
    """
    if not isinstance(proposal, dict):
        raise AIFailureMapperError(
            "hop_ai_failure_mapper:proposal_not_dict"
        )
    if proposal.get("advisory_only") is not True:
        raise AIFailureMapperError(
            "hop_ai_failure_mapper:proposal_advisory_only_not_true"
        )
    boundary = proposal.get("authority_boundary")
    if not isinstance(boundary, dict):
        raise AIFailureMapperError(
            "hop_ai_failure_mapper:proposal_missing_authority_boundary"
        )
    hop_role = boundary.get("hop_role")
    if hop_role != "proposes_only":
        raise AIFailureMapperError(
            f"hop_ai_failure_mapper:proposal_invalid_hop_role:{hop_role}"
        )
    # Reject any payload that smuggles direct mutation / extra authority claims.
    for forbidden_key in ("direct_mutation_authority", "bypass_review", "accept_immediately"):
        if forbidden_key in proposal or forbidden_key in boundary:
            raise AIFailureMapperError(
                f"hop_ai_failure_mapper:proposal_forbidden_authority_key:{forbidden_key}"
            )
    review_owners = boundary.get("review_owners")
    try:
        review_owners_set = set(review_owners or [])
    except TypeError:
        raise AIFailureMapperError("hop_ai_failure_mapper:proposal_invalid_review_owners")
    if review_owners_set != {"CDE", "GOV"}:
        raise AIFailureMapperError("hop_ai_failure_mapper:proposal_invalid_review_owners")
    if boundary.get("execution_owner") != "PQX":
        raise AIFailureMapperError("hop_ai_failure_mapper:proposal_invalid_execution_owner")
    if boundary.get("validation_owner") != "EVL":
        raise AIFailureMapperError("hop_ai_failure_mapper:proposal_invalid_validation_owner")
    if boundary.get("enforcement_signal_owner") != "SEL":
        raise AIFailureMapperError("hop_ai_failure_mapper:proposal_invalid_enforcement_signal_owner")
