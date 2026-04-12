export type PanelFieldProvenance = {
  panel_id: string
  artifact: string
  fields: string[]
  uncertainty?: string
}

export const PANEL_FIELD_PROVENANCE_MAP: PanelFieldProvenance[] = [
  { panel_id: 'trust_posture', artifact: 'dashboard_freshness_status.json', fields: ['status', 'freshness_window_hours', 'snapshot_last_refreshed_time', 'trace_id'] },
  { panel_id: 'trust_posture', artifact: 'dashboard_publication_sync_audit.json', fields: ['publication_state', 'required_artifact_count', 'records'] },
  { panel_id: 'control_decisions', artifact: 'publication_attempt_record.json', fields: ['decision', 'reason_codes', 'timestamp', 'trace_id'] },
  { panel_id: 'control_decisions', artifact: 'hard_gate_status_record.json', fields: ['gate_name', 'readiness_status', 'pass_fail'] },
  { panel_id: 'judgment_records', artifact: 'judgment_application_artifact.json', fields: ['decision_id', 'judgment_ids', 'consumed_by_control'] },
  { panel_id: 'override_lifecycle', artifact: 'rq_next_24_01__umbrella_1__nx_05_operator_override_capture.json', fields: ['overrides.override_id', 'overrides.reason', 'overrides.operator_action'] },
  { panel_id: 'replay_certification', artifact: 'rq_next_24_01__umbrella_3__nx_13_recommendation_replay_pack.json', fields: ['scenario_ids', 'scenario_basis'] },
  { panel_id: 'replay_certification', artifact: 'serial_bundle_validator_result.json', fields: ['pass', 'pass_through_umbrellas', 'empty_batches'] },
  { panel_id: 'replay_certification', artifact: 'governed_promotion_discipline_gate.json', fields: ['promotion_decision', 'allowed_decisions', 'fail_closed'] },
  { panel_id: 'weighted_coverage', artifact: 'dashboard_public_contract_coverage.json', fields: ['covered_artifacts'] },
  { panel_id: 'weighted_coverage', artifact: 'dashboard_publication_manifest.json', fields: ['required_files'] },
  { panel_id: 'trend_control_charts', artifact: 'dashboard_freshness_status.json', fields: ['snapshot_age_hours', 'freshness_window_hours'], uncertainty: 'No historical series artifact published; single-sample chart only.' },
  { panel_id: 'trend_control_charts', artifact: 'publication_attempt_record.json', fields: ['validation_summary.overall_verdict', 'freshness_summary.overall_verdict'] },
  { panel_id: 'reconciliation', artifact: 'dashboard_freshness_status.json', fields: ['status'] },
  { panel_id: 'reconciliation', artifact: 'publication_attempt_record.json', fields: ['decision'] },
  { panel_id: 'postmortem_outage', artifact: 'refresh_run_record.json', fields: ['outcome', 'failure_class', 'trace_id'] },
  { panel_id: 'tamper_evident_ledger', artifact: 'dashboard_publication_sync_audit.json', fields: ['records.sha256', 'records.artifact'] },
  { panel_id: 'tamper_evident_ledger', artifact: 'serial_bundle_validator_result.json', fields: ['pass'] },
  { panel_id: 'maintain_drift', artifact: 'dashboard_public_contract_coverage.json', fields: ['covered_artifacts'] },
  { panel_id: 'maintain_drift', artifact: 'dashboard_publication_manifest.json', fields: ['required_files'] },
  { panel_id: 'scenario_simulator', artifact: 'rq_next_24_01__umbrella_3__nx_17_failure_hotspot_simulation_pack.json', fields: ['scenario_ids', 'hypotheses'] },
  { panel_id: 'mobile_semantics', artifact: 'publication_attempt_record.json', fields: ['decision', 'reason_codes'] }
]
