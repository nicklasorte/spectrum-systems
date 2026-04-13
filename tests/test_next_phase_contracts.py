from __future__ import annotations

from spectrum_systems.contracts import load_example, validate_artifact


NEXT_PHASE_CONTRACTS = [
    'context_bundle_record','context_source_admission_record','context_conflict_record','context_recipe_spec','context_preflight_result','eval_registry_entry','eval_dataset_record','eval_slice_definition','eval_slice_summary','failure_derived_eval_case','judgment_record','judgment_policy','judgment_eval_result','judgment_application_record','evidence_sufficiency_result','abstention_record','route_candidate_set','routing_decision_record','comparison_run_record','comparison_result_record','guardrail_event','cost_budget_status','latency_budget_status','error_budget_status','override_record','review_outcome_record','handoff_package','handoff_validation_result','cross_artifact_consistency_report','migration_plan_record','risk_classification_record','supersession_record','retirement_record','active_set_snapshot','query_index_manifest','trust_posture_snapshot','synthesized_trust_signal'
]


def test_next_phase_contract_examples_validate() -> None:
    for name in NEXT_PHASE_CONTRACTS:
        instance = load_example(name)
        validate_artifact(instance, name)
