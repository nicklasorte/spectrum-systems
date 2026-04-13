export type PanelCapability = {
  panel_id: string
  reads_from_artifacts: string[]
  owning_system: string
  decision_authority: 'read_only'
  prohibited_local_authority: Array<'control' | 'judgment' | 'replay' | 'override' | 'eval' | 'publication'>
}

export const PANEL_CAPABILITY_MAP: PanelCapability[] = [
  {
    panel_id: 'trust_posture',
    reads_from_artifacts: ['dashboard_freshness_status.json', 'dashboard_publication_sync_audit.json', 'dashboard_publication_manifest.json'],
    owning_system: 'SEL',
    decision_authority: 'read_only',
    prohibited_local_authority: ['control', 'judgment', 'replay', 'override', 'eval', 'publication']
  },
  {
    panel_id: 'causal_chain',
    reads_from_artifacts: ['publication_attempt_record.json', 'judgment_application_artifact.json', 'hard_gate_status_record.json', 'serial_bundle_validator_result.json'],
    owning_system: 'TLC',
    decision_authority: 'read_only',
    prohibited_local_authority: ['control', 'judgment', 'replay', 'override', 'eval', 'publication']
  },
  {
    panel_id: 'decision_trace',
    reads_from_artifacts: ['publication_attempt_record.json', 'judgment_application_artifact.json', 'hard_gate_status_record.json'],
    owning_system: 'RIL',
    decision_authority: 'read_only',
    prohibited_local_authority: ['control', 'judgment', 'replay', 'override', 'eval', 'publication']
  },
  {
    panel_id: 'multi_artifact_correlation',
    reads_from_artifacts: ['current_bottleneck_record.json', 'current_run_state_record.json', 'hard_gate_status_record.json', 'judgment_application_artifact.json', 'serial_bundle_validator_result.json'],
    owning_system: 'PRG',
    decision_authority: 'read_only',
    prohibited_local_authority: ['control', 'judgment', 'replay', 'override', 'eval', 'publication']
  },
  {
    panel_id: 'evidence_strength',
    reads_from_artifacts: ['dashboard_freshness_status.json', 'dashboard_publication_sync_audit.json', 'serial_bundle_validator_result.json', 'dashboard_public_contract_coverage.json'],
    owning_system: 'CDE',
    decision_authority: 'read_only',
    prohibited_local_authority: ['control', 'judgment', 'replay', 'override', 'eval', 'publication']
  },
  {
    panel_id: 'control_decisions',
    reads_from_artifacts: ['publication_attempt_record.json', 'hard_gate_status_record.json'],
    owning_system: 'SEL',
    decision_authority: 'read_only',
    prohibited_local_authority: ['control', 'judgment', 'replay', 'override', 'eval', 'publication']
  },
  {
    panel_id: 'judgment_records',
    reads_from_artifacts: ['judgment_application_artifact.json'],
    owning_system: 'RIL',
    decision_authority: 'read_only',
    prohibited_local_authority: ['control', 'judgment', 'replay', 'override', 'eval', 'publication']
  },
  {
    panel_id: 'override_lifecycle',
    reads_from_artifacts: ['rq_next_24_01__umbrella_1__nx_05_operator_override_capture.json'],
    owning_system: 'SEL',
    decision_authority: 'read_only',
    prohibited_local_authority: ['control', 'judgment', 'replay', 'override', 'eval', 'publication']
  },
  {
    panel_id: 'replay_certification',
    reads_from_artifacts: ['rq_next_24_01__umbrella_3__nx_13_recommendation_replay_pack.json', 'serial_bundle_validator_result.json', 'governed_promotion_discipline_gate.json'],
    owning_system: 'CDE',
    decision_authority: 'read_only',
    prohibited_local_authority: ['control', 'judgment', 'replay', 'override', 'eval', 'publication']
  },
  {
    panel_id: 'weighted_coverage',
    reads_from_artifacts: ['dashboard_public_contract_coverage.json', 'dashboard_publication_manifest.json'],
    owning_system: 'PRG',
    decision_authority: 'read_only',
    prohibited_local_authority: ['control', 'judgment', 'replay', 'override', 'eval', 'publication']
  },
  {
    panel_id: 'trend_control_charts',
    reads_from_artifacts: ['dashboard_freshness_status.json', 'publication_attempt_record.json', 'refresh_run_record.json'],
    owning_system: 'TLC',
    decision_authority: 'read_only',
    prohibited_local_authority: ['control', 'judgment', 'replay', 'override', 'eval', 'publication']
  },
  {
    panel_id: 'reconciliation',
    reads_from_artifacts: ['dashboard_freshness_status.json', 'publication_attempt_record.json'],
    owning_system: 'SEL',
    decision_authority: 'read_only',
    prohibited_local_authority: ['control', 'judgment', 'replay', 'override', 'eval', 'publication']
  },
  {
    panel_id: 'postmortem_outage',
    reads_from_artifacts: ['refresh_run_record.json', 'publication_attempt_record.json', 'drift_trend_continuity_artifact.json'],
    owning_system: 'FRE',
    decision_authority: 'read_only',
    prohibited_local_authority: ['control', 'judgment', 'replay', 'override', 'eval', 'publication']
  },
  {
    panel_id: 'tamper_evident_ledger',
    reads_from_artifacts: ['dashboard_publication_sync_audit.json', 'serial_bundle_validator_result.json'],
    owning_system: 'CDE',
    decision_authority: 'read_only',
    prohibited_local_authority: ['control', 'judgment', 'replay', 'override', 'eval', 'publication']
  },
  {
    panel_id: 'maintain_drift',
    reads_from_artifacts: ['dashboard_publication_manifest.json', 'dashboard_public_contract_coverage.json', 'rq_next_24_01__umbrella_1__nx_05_operator_override_capture.json'],
    owning_system: 'PRG',
    decision_authority: 'read_only',
    prohibited_local_authority: ['control', 'judgment', 'replay', 'override', 'eval', 'publication']
  },
  {
    panel_id: 'scenario_simulator',
    reads_from_artifacts: ['rq_next_24_01__umbrella_3__nx_17_failure_hotspot_simulation_pack.json'],
    owning_system: 'PQX',
    decision_authority: 'read_only',
    prohibited_local_authority: ['control', 'judgment', 'replay', 'override', 'eval', 'publication']
  },
  {
    panel_id: 'mobile_semantics',
    reads_from_artifacts: ['dashboard_freshness_status.json', 'publication_attempt_record.json'],
    owning_system: 'TLC',
    decision_authority: 'read_only',
    prohibited_local_authority: ['control', 'judgment', 'replay', 'override', 'eval', 'publication']
  },
  {
    panel_id: 'policy_visibility',
    reads_from_artifacts: ['hard_gate_status_record.json', 'governed_promotion_discipline_gate.json'],
    owning_system: 'SEL',
    decision_authority: 'read_only',
    prohibited_local_authority: ['control', 'judgment', 'replay', 'override', 'eval', 'publication']
  },
  {
    panel_id: 'audit_trail',
    reads_from_artifacts: ['publication_attempt_record.json', 'judgment_application_artifact.json', 'refresh_run_record.json', 'serial_bundle_validator_result.json'],
    owning_system: 'CDE',
    decision_authority: 'read_only',
    prohibited_local_authority: ['control', 'judgment', 'replay', 'override', 'eval', 'publication']
  },
  {
    panel_id: 'action_surface',
    reads_from_artifacts: ['refresh_run_record.json', 'rq_next_24_01__umbrella_3__nx_13_recommendation_replay_pack.json', 'recommendation_review_surface.json'],
    owning_system: 'TLC',
    decision_authority: 'read_only',
    prohibited_local_authority: ['control', 'judgment', 'replay', 'override', 'eval', 'publication']
  },
  {
    panel_id: 'review_queue_surface',
    reads_from_artifacts: ['recommendation_review_surface.json', 'hard_gate_status_record.json'],
    owning_system: 'RIL',
    decision_authority: 'read_only',
    prohibited_local_authority: ['control', 'judgment', 'replay', 'override', 'eval', 'publication']
  },
  {
    panel_id: 'misinterpretation_guard',
    reads_from_artifacts: ['dashboard_freshness_status.json', 'serial_bundle_validator_result.json', 'publication_attempt_record.json'],
    owning_system: 'FRE',
    decision_authority: 'read_only',
    prohibited_local_authority: ['control', 'judgment', 'replay', 'override', 'eval', 'publication']
  },
  { panel_id: 'operator_coordination_layer', reads_from_artifacts: ['dashboard_publication_manifest.json', 'dashboard_freshness_status.json'], owning_system: 'TLC', decision_authority: 'read_only', prohibited_local_authority: ['control', 'judgment', 'replay', 'override', 'eval', 'publication'] },
  { panel_id: 'decision_change_conditions', reads_from_artifacts: ['judgment_application_artifact.json'], owning_system: 'RIL', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'evidence_gap_hotspots', reads_from_artifacts: ['readiness_to_expand_validator.json'], owning_system: 'CDE', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'override_hotspots', reads_from_artifacts: ['rq_next_24_01__umbrella_1__nx_05_operator_override_capture.json'], owning_system: 'SEL', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'trust_posture_timeline', reads_from_artifacts: ['operator_trust_closeout_artifact.json'], owning_system: 'FRE', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'judge_disagreement', reads_from_artifacts: ['cycle_comparator_03_05.json'], owning_system: 'RIL', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'policy_regression', reads_from_artifacts: ['cycle_comparator_03_05.json'], owning_system: 'PRG', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'capability_readiness', reads_from_artifacts: ['readiness_to_expand_validator.json'], owning_system: 'SEL', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'route_efficiency', reads_from_artifacts: ['operator_trust_closeout_artifact.json'], owning_system: 'FRE', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'failure_derived_eval', reads_from_artifacts: ['next_action_outcome_record.json'], owning_system: 'PQX', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'correction_patterns', reads_from_artifacts: ['rq_next_24_01__umbrella_1__nx_05_operator_override_capture.json'], owning_system: 'TLC', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'review_outcomes', reads_from_artifacts: ['recommendation_review_surface.json'], owning_system: 'RIL', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'escalation_triggers', reads_from_artifacts: ['hard_gate_status_record.json', 'publication_attempt_record.json'], owning_system: 'SEL', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'cross_run_intelligence', reads_from_artifacts: ['cycle_comparator_03_05.json'], owning_system: 'CDE', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'high_risk_claim_board', reads_from_artifacts: ['readiness_to_expand_validator.json'], owning_system: 'PRG', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'governed_exports', reads_from_artifacts: ['operator_surface_snapshot_export.json', 'dashboard_publication_manifest.json', 'dashboard_freshness_status.json'], owning_system: 'CDE', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'trust_posture_artifact_browser', reads_from_artifacts: ['operator_trust_closeout_artifact.json'], owning_system: 'SEL', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'trust_posture_diff', reads_from_artifacts: ['operator_trust_closeout_artifact.json'], owning_system: 'SEL', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'capability_readiness_timeline', reads_from_artifacts: ['readiness_to_expand_validator.json'], owning_system: 'SEL', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'capability_expansion_blockers', reads_from_artifacts: ['readiness_to_expand_validator.json'], owning_system: 'SEL', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'improvement_recommendation', reads_from_artifacts: ['next_action_recommendation_record.json'], owning_system: 'PRG', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'improvement_recommendation_outcomes', reads_from_artifacts: ['next_action_outcome_record.json'], owning_system: 'PRG', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'artifact_family_health', reads_from_artifacts: ['dashboard_publication_sync_audit.json'], owning_system: 'CDE', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'artifact_family_health_trend', reads_from_artifacts: ['dashboard_publication_sync_audit.json'], owning_system: 'CDE', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'evidence_coverage_density', reads_from_artifacts: ['readiness_to_expand_validator.json'], owning_system: 'CDE', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'evidence_sufficiency_change', reads_from_artifacts: ['next_action_outcome_record.json'], owning_system: 'CDE', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'judge_calibration', reads_from_artifacts: ['confidence_calibration_artifact.json'], owning_system: 'RIL', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'judge_drift', reads_from_artifacts: ['cycle_comparator_03_05.json'], owning_system: 'RIL', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'human_correction_magnitude', reads_from_artifacts: ['rq_next_24_01__umbrella_1__nx_05_operator_override_capture.json'], owning_system: 'TLC', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'correction_absorption', reads_from_artifacts: ['next_action_outcome_record.json'], owning_system: 'TLC', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'policy_deviation', reads_from_artifacts: ['rq_next_24_01__umbrella_4__nx_20_governance_exception_register.json'], owning_system: 'PRG', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'policy_change_impact', reads_from_artifacts: ['cycle_comparator_03_05.json'], owning_system: 'PRG', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'route_distribution', reads_from_artifacts: ['operator_trust_closeout_artifact.json'], owning_system: 'FRE', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'quality_vs_cost', reads_from_artifacts: ['operator_trust_closeout_artifact.json'], owning_system: 'FRE', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'latency_vs_quality', reads_from_artifacts: ['operator_trust_closeout_artifact.json'], owning_system: 'FRE', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'retry_validation_failure', reads_from_artifacts: ['serial_bundle_validator_result.json'], owning_system: 'CDE', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'prompt_version_impact', reads_from_artifacts: ['rq_next_24_01__umbrella_3__nx_14_decision_backtest_harness.json'], owning_system: 'TLC', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'context_recipe_comparison', reads_from_artifacts: ['rq_next_24_01__umbrella_3__nx_15_counterfactual_recommendation_evaluator.json'], owning_system: 'TLC', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'context_source_reliability', reads_from_artifacts: ['rq_next_24_01__umbrella_3__nx_18_simulation_outcome_summary.json'], owning_system: 'FRE', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'context_exclusion_rationale', reads_from_artifacts: ['rq_next_24_01__umbrella_2__nx_08_operator_action_admissibility_check.json'], owning_system: 'RIL', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'contradiction_type', reads_from_artifacts: ['cycle_comparator_03_05.json'], owning_system: 'FRE', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'cross_artifact_consistency', reads_from_artifacts: ['dashboard_publication_sync_audit.json'], owning_system: 'CDE', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'schema_drift', reads_from_artifacts: ['dashboard_public_contract_coverage.json'], owning_system: 'CDE', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'provenance_coverage', reads_from_artifacts: ['dashboard_publication_sync_audit.json'], owning_system: 'CDE', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'lineage_coverage', reads_from_artifacts: ['serial_bundle_validator_result.json'], owning_system: 'CDE', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'trace_integrity', reads_from_artifacts: ['refresh_run_record.json'], owning_system: 'CDE', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'openlineage_trace_correlation', reads_from_artifacts: ['refresh_run_record.json'], owning_system: 'CDE', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'run_bundle_audit', reads_from_artifacts: ['serial_bundle_validator_result.json'], owning_system: 'CDE', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'promotion_readiness', reads_from_artifacts: ['governed_promotion_discipline_gate.json'], owning_system: 'SEL', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'promotion_failure', reads_from_artifacts: ['governed_promotion_discipline_gate.json'], owning_system: 'SEL', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'certification_failure', reads_from_artifacts: ['serial_bundle_validator_result.json'], owning_system: 'SEL', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'replay_mismatch_root_cause', reads_from_artifacts: ['rq_next_24_01__umbrella_3__nx_13_recommendation_replay_pack.json'], owning_system: 'PQX', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'replay_stability', reads_from_artifacts: ['rq_next_24_01__umbrella_3__nx_13_recommendation_replay_pack.json'], owning_system: 'PQX', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'non_determinism_hotspot', reads_from_artifacts: ['drift_trend_continuity_artifact.json'], owning_system: 'PQX', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'error_budget_burn', reads_from_artifacts: ['error_budget_enforcement_outcome.json'], owning_system: 'FRE', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'budget_breach_history', reads_from_artifacts: ['error_budget_enforcement_outcome.json'], owning_system: 'FRE', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'incident_correlation', reads_from_artifacts: ['refresh_run_record.json'], owning_system: 'FRE', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'alert_quality', reads_from_artifacts: ['hard_gate_status_record.json'], owning_system: 'FRE', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'review_queue_load', reads_from_artifacts: ['recommendation_review_surface.json'], owning_system: 'RIL', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'review_queue_routing_quality', reads_from_artifacts: ['recommendation_review_surface.json'], owning_system: 'RIL', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'review_debt', reads_from_artifacts: ['recommendation_review_surface.json'], owning_system: 'RIL', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'review_to_eval_closure', reads_from_artifacts: ['next_action_outcome_record.json'], owning_system: 'RIL', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'hitl_override_quality', reads_from_artifacts: ['rq_next_24_01__umbrella_1__nx_05_operator_override_capture.json'], owning_system: 'SEL', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'human_review_reason', reads_from_artifacts: ['recommendation_review_surface.json'], owning_system: 'RIL', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'decision_log_integrity', reads_from_artifacts: ['judgment_application_artifact.json'], owning_system: 'RIL', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'decision_alternative', reads_from_artifacts: ['judgment_application_artifact.json'], owning_system: 'RIL', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'decision_fragility', reads_from_artifacts: ['rq_next_24_01__umbrella_3__nx_15_counterfactual_recommendation_evaluator.json'], owning_system: 'RIL', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'counterfactual_study_index', reads_from_artifacts: ['rq_next_24_01__umbrella_3__nx_15_counterfactual_recommendation_evaluator.json'], owning_system: 'RIL', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'route_canary', reads_from_artifacts: ['rq_next_24_01__umbrella_4__nx_23_controlled_expansion_canary_gate.json'], owning_system: 'FRE', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'model_tournament', reads_from_artifacts: ['rq_next_24_01__umbrella_3__nx_18_simulation_outcome_summary.json'], owning_system: 'FRE', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'slice_severity', reads_from_artifacts: ['readiness_to_expand_validator.json'], owning_system: 'PRG', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'missing_eval_slice', reads_from_artifacts: ['next_action_outcome_record.json'], owning_system: 'PRG', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'blocking_bottleneck', reads_from_artifacts: ['current_bottleneck_record.json'], owning_system: 'PRG', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'roadmap_feed', reads_from_artifacts: ['canonical_roadmap_state_artifact.json'], owning_system: 'PRG', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'control_vs_roadmap_split', reads_from_artifacts: ['canonical_roadmap_state_artifact.json'], owning_system: 'PRG', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'human_review_consumption', reads_from_artifacts: ['recommendation_review_surface.json'], owning_system: 'RIL', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'quality_sli', reads_from_artifacts: ['dashboard_freshness_status.json'], owning_system: 'CDE', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'reliability_sli', reads_from_artifacts: ['refresh_run_record.json'], owning_system: 'CDE', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'capacity_cost_sli', reads_from_artifacts: ['error_budget_enforcement_outcome.json'], owning_system: 'CDE', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'time_to_insight', reads_from_artifacts: ['operator_trust_closeout_artifact.json'], owning_system: 'TLC', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'link_integrity', reads_from_artifacts: ['dashboard_publication_manifest.json'], owning_system: 'CDE', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'dashboard_self_health', reads_from_artifacts: ['dashboard_public_contract_coverage.json'], owning_system: 'CDE', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'operator_session_path', reads_from_artifacts: ['operator_surface_snapshot_export.json'], owning_system: 'TLC', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'cognitive_load', reads_from_artifacts: ['operator_surface_snapshot_export.json'], owning_system: 'TLC', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'panel_materiality_ranking', reads_from_artifacts: ['dashboard_publication_sync_audit.json'], owning_system: 'PRG', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'panel_retirement_candidate', reads_from_artifacts: ['dashboard_public_contract_coverage.json'], owning_system: 'PRG', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
  { panel_id: 'certification_gate_reinforcement', reads_from_artifacts: ['governed_promotion_discipline_gate.json'], owning_system: 'SEL', decision_authority: 'read_only', prohibited_local_authority: ['control','judgment','replay','override','eval','publication'] },
]
