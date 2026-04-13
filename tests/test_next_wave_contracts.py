from spectrum_systems.contracts import load_example, validate_artifact


CONTRACTS = [
    "jdx_judgment_record",
    "jdx_judgment_policy",
    "jdx_judgment_eval_result",
    "jdx_judgment_application_record",
    "jdx_judgment_bundle",
    "rux_reuse_record",
    "rux_boundary_validation_result",
    "rux_freshness_scope_report",
    "rux_reuse_bundle",
    "xpl_artifact_card",
    "xpl_generator_risk_record",
    "xpl_explainability_signal_bundle",
    "rel_release_record",
    "rel_canary_metrics_breakdown",
    "rel_change_freeze_record",
    "rel_release_bundle",
    "dag_dependency_graph_record",
    "dag_cycle_deadlock_report",
    "dag_critical_path_signal",
    "dag_dependency_bundle",
    "ext_runtime_provenance_record",
    "ext_replay_verification_bundle",
    "ext_constraint_enforcement_record",
    "ext_runtime_governance_bundle",
    "mnt_promotion_entrypoint_coverage_report",
    "mnt_enforcement_consistency_result",
    "mnt_real_flow_reliability_result",
]


def test_next_wave_examples_validate() -> None:
    for name in CONTRACTS:
        validate_artifact(load_example(name), name)
