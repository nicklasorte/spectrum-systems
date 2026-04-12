export type SurfaceStatus = 'renderable' | 'blocked' | 'warning'

export type DashboardSurfaceContract = {
  panel_id: string
  title: string
  artifact_family: string
  contract_source: string
  owning_system: 'RIL' | 'CDE' | 'TLC' | 'PQX' | 'FRE' | 'SEL' | 'PRG'
  render_gate_dependency: string[]
  freshness_dependency: string[]
  provenance_requirements: string[]
  blocked_state_behavior: 'hide_panel' | 'render_blocked_diagnostic'
  allowed_statuses: SurfaceStatus[]
  certification_relevant: boolean
  high_risk: boolean
}

export const DASHBOARD_SURFACE_CONTRACT_REGISTRY: DashboardSurfaceContract[] = [
  {
    panel_id: 'trust_posture',
    title: 'Trust posture',
    artifact_family: 'dashboard_freshness_status + dashboard_publication_sync_audit',
    contract_source: 'dashboard/public/dashboard_freshness_status.json',
    owning_system: 'SEL',
    render_gate_dependency: ['dashboard_freshness_status.json', 'dashboard_publication_manifest.json'],
    freshness_dependency: ['dashboard_freshness_status.json'],
    provenance_requirements: ['field-level trace for freshness, validation, provenance, replay, renderability'],
    blocked_state_behavior: 'render_blocked_diagnostic',
    allowed_statuses: ['renderable', 'blocked'],
    certification_relevant: true,
    high_risk: true
  },
  {
    panel_id: 'control_decisions',
    title: 'Control decisions',
    artifact_family: 'publication_attempt_record + hard_gate_status_record',
    contract_source: 'dashboard/public/publication_attempt_record.json',
    owning_system: 'SEL',
    render_gate_dependency: ['publication_attempt_record.json', 'hard_gate_status_record.json'],
    freshness_dependency: ['publication_attempt_record.json'],
    provenance_requirements: ['decision code and reason_codes trace'],
    blocked_state_behavior: 'render_blocked_diagnostic',
    allowed_statuses: ['renderable', 'blocked'],
    certification_relevant: true,
    high_risk: true
  },
  {
    panel_id: 'judgment_records',
    title: 'Judgment records',
    artifact_family: 'judgment_application_artifact',
    contract_source: 'dashboard/public/judgment_application_artifact.json',
    owning_system: 'RIL',
    render_gate_dependency: ['judgment_application_artifact.json'],
    freshness_dependency: ['judgment_application_artifact.json'],
    provenance_requirements: ['judgment_ids and decision_id trace'],
    blocked_state_behavior: 'render_blocked_diagnostic',
    allowed_statuses: ['renderable', 'blocked'],
    certification_relevant: true,
    high_risk: true
  },
  {
    panel_id: 'override_lifecycle',
    title: 'Override lifecycle',
    artifact_family: 'operator_override_capture',
    contract_source: 'dashboard/public/rq_next_24_01__umbrella_1__nx_05_operator_override_capture.json',
    owning_system: 'SEL',
    render_gate_dependency: ['rq_next_24_01__umbrella_1__nx_05_operator_override_capture.json'],
    freshness_dependency: ['rq_next_24_01__umbrella_1__nx_05_operator_override_capture.json'],
    provenance_requirements: ['override_id and reason trace'],
    blocked_state_behavior: 'render_blocked_diagnostic',
    allowed_statuses: ['renderable', 'blocked'],
    certification_relevant: true,
    high_risk: true
  },
  {
    panel_id: 'replay_certification',
    title: 'Replay and certification',
    artifact_family: 'recommendation_replay_pack + serial_bundle_validator_result + governed_promotion_discipline_gate',
    contract_source: 'dashboard/public/rq_next_24_01__umbrella_3__nx_13_recommendation_replay_pack.json',
    owning_system: 'CDE',
    render_gate_dependency: ['rq_next_24_01__umbrella_3__nx_13_recommendation_replay_pack.json', 'serial_bundle_validator_result.json'],
    freshness_dependency: ['serial_bundle_validator_result.json'],
    provenance_requirements: ['scenario ids and pass/fail trace'],
    blocked_state_behavior: 'render_blocked_diagnostic',
    allowed_statuses: ['renderable', 'blocked'],
    certification_relevant: true,
    high_risk: true
  },
  {
    panel_id: 'weighted_coverage',
    title: 'Weighted coverage',
    artifact_family: 'dashboard_public_contract_coverage + dashboard_publication_manifest',
    contract_source: 'dashboard/public/dashboard_public_contract_coverage.json',
    owning_system: 'PRG',
    render_gate_dependency: ['dashboard_public_contract_coverage.json', 'dashboard_publication_manifest.json'],
    freshness_dependency: ['dashboard_public_contract_coverage.json'],
    provenance_requirements: ['covered_artifacts and required_files trace'],
    blocked_state_behavior: 'render_blocked_diagnostic',
    allowed_statuses: ['renderable', 'blocked', 'warning'],
    certification_relevant: true,
    high_risk: true
  },
  {
    panel_id: 'trend_control_charts',
    title: 'Trend control charts',
    artifact_family: 'dashboard_freshness_status + refresh_run_record + publication_attempt_record',
    contract_source: 'dashboard/public/dashboard_freshness_status.json',
    owning_system: 'TLC',
    render_gate_dependency: ['dashboard_freshness_status.json', 'refresh_run_record.json'],
    freshness_dependency: ['dashboard_freshness_status.json'],
    provenance_requirements: ['threshold + observed values trace'],
    blocked_state_behavior: 'render_blocked_diagnostic',
    allowed_statuses: ['renderable', 'blocked'],
    certification_relevant: false,
    high_risk: false
  },
  {
    panel_id: 'reconciliation',
    title: 'High-risk reconciliation',
    artifact_family: 'dashboard_freshness_status + publication_attempt_record',
    contract_source: 'dashboard/public/publication_attempt_record.json',
    owning_system: 'SEL',
    render_gate_dependency: ['dashboard_freshness_status.json', 'publication_attempt_record.json'],
    freshness_dependency: ['dashboard_freshness_status.json'],
    provenance_requirements: ['dual-source verdict disagreement trace'],
    blocked_state_behavior: 'render_blocked_diagnostic',
    allowed_statuses: ['renderable', 'blocked'],
    certification_relevant: true,
    high_risk: true
  },
  {
    panel_id: 'postmortem_outage',
    title: 'Postmortem and outage',
    artifact_family: 'refresh_run_record + publication_attempt_record + drift_trend_continuity_artifact',
    contract_source: 'dashboard/public/refresh_run_record.json',
    owning_system: 'FRE',
    render_gate_dependency: ['refresh_run_record.json', 'publication_attempt_record.json'],
    freshness_dependency: ['refresh_run_record.json'],
    provenance_requirements: ['failure class and trace link'],
    blocked_state_behavior: 'render_blocked_diagnostic',
    allowed_statuses: ['renderable', 'blocked'],
    certification_relevant: false,
    high_risk: false
  },
  {
    panel_id: 'tamper_evident_ledger',
    title: 'Tamper-evident publication ledger',
    artifact_family: 'dashboard_publication_sync_audit + serial_bundle_validator_result',
    contract_source: 'dashboard/public/dashboard_publication_sync_audit.json',
    owning_system: 'CDE',
    render_gate_dependency: ['dashboard_publication_sync_audit.json', 'serial_bundle_validator_result.json'],
    freshness_dependency: ['dashboard_publication_sync_audit.json'],
    provenance_requirements: ['record-level verification flags trace'],
    blocked_state_behavior: 'render_blocked_diagnostic',
    allowed_statuses: ['renderable', 'blocked'],
    certification_relevant: true,
    high_risk: true
  },
  {
    panel_id: 'maintain_drift',
    title: 'Maintain and drift',
    artifact_family: 'dashboard_publication_manifest + dashboard_public_contract_coverage + operator_override_capture',
    contract_source: 'dashboard/public/dashboard_publication_manifest.json',
    owning_system: 'PRG',
    render_gate_dependency: ['dashboard_publication_manifest.json', 'dashboard_public_contract_coverage.json'],
    freshness_dependency: ['dashboard_publication_manifest.json'],
    provenance_requirements: ['dead panel and mismatch signals trace'],
    blocked_state_behavior: 'render_blocked_diagnostic',
    allowed_statuses: ['renderable', 'blocked', 'warning'],
    certification_relevant: false,
    high_risk: true
  },
  {
    panel_id: 'scenario_simulator',
    title: 'Governed scenario simulator',
    artifact_family: 'governed fixture bundle',
    contract_source: 'dashboard/public/rq_next_24_01__umbrella_3__nx_17_failure_hotspot_simulation_pack.json',
    owning_system: 'PQX',
    render_gate_dependency: ['rq_next_24_01__umbrella_3__nx_17_failure_hotspot_simulation_pack.json'],
    freshness_dependency: ['rq_next_24_01__umbrella_3__nx_17_failure_hotspot_simulation_pack.json'],
    provenance_requirements: ['fixture scenario identifiers trace'],
    blocked_state_behavior: 'render_blocked_diagnostic',
    allowed_statuses: ['renderable', 'blocked'],
    certification_relevant: false,
    high_risk: true
  },
  {
    panel_id: 'mobile_semantics',
    title: 'Mobile operator semantics',
    artifact_family: 'read-model diagnostics',
    contract_source: 'dashboard/lib/read_model/dashboard_read_model_compiler.ts',
    owning_system: 'TLC',
    render_gate_dependency: ['dashboard_freshness_status.json', 'publication_attempt_record.json'],
    freshness_dependency: ['dashboard_freshness_status.json'],
    provenance_requirements: ['blocked-state and high-risk cues trace'],
    blocked_state_behavior: 'render_blocked_diagnostic',
    allowed_statuses: ['renderable', 'blocked'],
    certification_relevant: true,
    high_risk: true
  }
]
