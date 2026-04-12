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
  }
]
