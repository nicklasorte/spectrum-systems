from spectrum_systems.contracts import load_example, validate_artifact


CONTRACTS = [
    'rdx_roadmap_execution_contract_v2','rdx_roadmap_contract_normalization_record','rdx_roadmap_invalidation_graph','rdx_umbrella_dependency_seal','rdx_advancement_precondition_bundle','rdx_unsafe_breadth_report',
    'hnx_phase_window_continuity_record','hnx_stale_resume_hazard_report','hnx_checkpoint_density_policy_record','hnx_handoff_semantic_completeness_score','hnx_future_invalidity_warning_record','hnx_delayed_invalidity_report',
    'dag_edge_class_taxonomy_record','dag_undeclared_dependency_evidence_bundle','dag_late_stage_insertion_risk_record','dag_cross_umbrella_mutation_report',
    'dep_chain_break_replay_probe_pack','dep_dependency_regression_debt_record','dep_cross_fix_chain_interference_report',
    'crs_cross_owner_consistency_lattice','crs_phase_contradiction_escalation_band_record','crs_control_vs_judgment_mismatch_report','crs_active_rule_ambiguity_report',
    'lin_promotion_lineage_gap_classifier','lin_lineage_survivability_after_fix_report',
    'rep_replay_sufficiency_profile_by_phase','rep_replay_baseline_drift_score_record',
    'evl_route_by_route_eval_debt_map','evl_eval_freshness_expiration_record','evl_red_team_to_eval_conversion_ledger','evl_roadmap_untested_surface_report',
    'evd_evidence_source_fragility_report','evd_evidence_contradiction_density_map','evd_commentary_vs_authority_evidence_split_record',
    'obs_trace_join_failure_report','obs_observability_survival_after_repair_loop_report','obs_missing_span_hotspot_record',
    'prg_signal_conflict_arbitration_policy_record','prg_halt_recut_continue_recommendation_bundle','prg_roadmap_batch_shrink_recommendation','prg_bottleneck_severity_rank_record','prg_minimal_safe_replan_artifact',
    'ail_recurring_blocker_family_record','ail_roadmap_debt_trend_record','ail_fix_effectiveness_trend_record',
    'jdx_judgment_contradiction_feedback_record','jdx_judgment_to_policy_compilation_debt_record',
    'pol_canary_cohort_drift_report','pol_policy_degradation_hotspot_record','prx_stale_precedent_pressure_report','prx_precedent_misuse_pattern_record',
    'slo_roadmap_quality_budget_posture','slo_umbrella_boundary_budget_breach_forecast','cap_operator_review_saturation_forecast','cap_parallelism_risk_cap_by_phase','qos_retry_accumulation_hazard_report','qos_backlog_aging_hotspot_record',
    'ctx_roadmap_context_bundle_hardening_report','ctx_recipe_drift_block_report','con_hidden_coupling_severity_record','con_contract_evolution_pressure_map',
    'cde_roadmap_continuation_readiness_bundle_contract','cde_phase_boundary_continue_halt_escalate_decision','cde_debt_threshold_stop_decision','cde_recut_required_decision','cde_partial_continuation_decision',
    'tst_long_roadmap_fixture_governance_pack','tst_adversarial_fixture_freshness_record','tst_long_window_replay_fixture_bank','dat_roadmap_dataset_slice_registry_record','dat_dataset_drift_visibility_record',
    'syn_synthesized_trust_signal_record','syn_synthesized_halt_pressure_signal_record','ent_long_roadmap_entropy_accumulation_report','ent_correction_backlog_pressure_record','hnd_roadmap_handoff_package_validation_result','hnd_semantic_handoff_debt_report',
    'ril_roadmap_contract_structure_red_team_report','ril_temporal_resume_red_team_report','ril_dependency_critical_path_red_team_report','ril_coherence_lineage_replay_red_team_report','ril_eval_evidence_observability_red_team_report','ril_signal_overload_prioritization_red_team_report','ril_budget_capacity_queue_red_team_report',
    'fre_tpa_sel_pqx_fix_pack_e1','fre_tpa_sel_pqx_fix_pack_e2','fre_tpa_sel_pqx_fix_pack_e3','fre_tpa_sel_pqx_fix_pack_e4','fre_tpa_sel_pqx_fix_pack_e5','fre_tpa_sel_pqx_fix_pack_e6','fre_tpa_sel_pqx_fix_pack_e7',
    'final_100_step_synthetic_scenario_pack','final_umbrella_boundary_continue_halt_test_matrix','final_impacted_suite_rerun_report'
]


def test_r100_np001_examples_validate() -> None:
    for name in CONTRACTS:
        validate_artifact(load_example(name), name)
