import { loadArtifact } from '@/lib/artifactLoader';
import { buildSourceEnvelope } from '@/lib/sourceClassification';
import { safeCardStatus } from '@/lib/signalStatus';
import { authorityRoleFor, groupForSystem } from '@/lib/displayGroups';
import type { RepoSnapshot, DataSource } from '@/lib/types';

const SNAPSHOT_PATH = 'artifacts/dashboard/repo_snapshot.json';
const SEED_PATHS = {
  minimalLoop: 'artifacts/dashboard_seed/minimal_loop_snapshot.json',
  evalSummary: 'artifacts/dashboard_seed/eval_summary_record.json',
  lineage: 'artifacts/dashboard_seed/lineage_record.json',
  controlDecision: 'artifacts/dashboard_seed/control_signal_record.json',
  enforcementAction: 'artifacts/dashboard_seed/sel_signal_record.json',
  replay: 'artifacts/dashboard_seed/replay_record.json',
  observability: 'artifacts/dashboard_seed/observability_metrics_record.json',
  slo: 'artifacts/dashboard_seed/slo_status_record.json',
};

const SYSTEMS_RAW = [
  { system_id: 'PQX', system_name: 'Bounded Execution', system_type: 'execution', health_score: 92, status: 'healthy' as const, incidents_week: 0, contract_violations: [], data_source: 'stub_fallback' as DataSource },
  { system_id: 'RDX', system_name: 'Roadmap Execution Loop', system_type: 'execution', health_score: 88, status: 'warning' as const, incidents_week: 2, contract_violations: [{ rule: 'sequence_check', detail: 'Batch out of order' }], data_source: 'stub_fallback' as DataSource },
  { system_id: 'TPA', system_name: 'Trust/Policy Gate', system_type: 'governance', health_score: 95, status: 'healthy' as const, incidents_week: 0, contract_violations: [], data_source: 'stub_fallback' as DataSource },
  { system_id: 'MAP', system_name: 'Review Artifact Mediation', system_type: 'governance', health_score: 90, status: 'healthy' as const, incidents_week: 0, contract_violations: [], data_source: 'stub_fallback' as DataSource },
  { system_id: 'TLC', system_name: 'Top-Level Orchestration', system_type: 'orchestration', health_score: 91, status: 'healthy' as const, incidents_week: 0, contract_violations: [], data_source: 'stub_fallback' as DataSource },
  { system_id: 'RQX', system_name: 'Review Queue Execution', system_type: 'execution', health_score: 87, status: 'warning' as const, incidents_week: 1, contract_violations: [], data_source: 'stub_fallback' as DataSource },
  { system_id: 'HNX', system_name: 'Stage Harness', system_type: 'execution', health_score: 93, status: 'healthy' as const, incidents_week: 0, contract_violations: [], data_source: 'stub_fallback' as DataSource },
  { system_id: 'GOV', system_name: 'Governance Authority', system_type: 'governance', health_score: 96, status: 'healthy' as const, incidents_week: 0, contract_violations: [], data_source: 'stub_fallback' as DataSource },
  { system_id: 'FRE', system_name: 'Failure Diagnosis & Repair', system_type: 'governance', health_score: 85, status: 'healthy' as const, incidents_week: 3, contract_violations: [], data_source: 'stub_fallback' as DataSource },
  { system_id: 'RIL', system_name: 'Review Interpretation', system_type: 'governance', health_score: 89, status: 'warning' as const, incidents_week: 1, contract_violations: [], data_source: 'stub_fallback' as DataSource },
  { system_id: 'AEX', system_name: 'Admission Exchange', system_type: 'orchestration', health_score: 88, status: 'warning' as const, incidents_week: 2, contract_violations: [], data_source: 'stub_fallback' as DataSource },
  { system_id: 'EVL', system_name: 'Evaluation Layer', system_type: 'governance', health_score: 82, status: 'warning' as const, incidents_week: 1, contract_violations: [{ rule: 'coverage_partial', detail: 'Seed eval is partial coverage' }], data_source: 'stub_fallback' as DataSource },
  { system_id: 'CDE', system_name: 'Control Decision Engine', system_type: 'governance', health_score: 84, status: 'warning' as const, incidents_week: 1, contract_violations: [{ rule: 'observe_only_mode', detail: 'Control decision remains warn-gated' }], data_source: 'stub_fallback' as DataSource },
  { system_id: 'SEL', system_name: 'Selector Enforcement Layer', system_type: 'governance', health_score: 83, status: 'warning' as const, incidents_week: 1, contract_violations: [{ rule: 'certification_incomplete', detail: 'Observe-only action due to incomplete certification' }], data_source: 'stub_fallback' as DataSource },
  { system_id: 'REP', system_name: 'Replay Engine', system_type: 'governance', health_score: 81, status: 'warning' as const, incidents_week: 1, contract_violations: [{ rule: 'replay_partial', detail: 'Replay evidence is partial' }], data_source: 'stub_fallback' as DataSource },
  { system_id: 'LIN', system_name: 'Lineage Tracker', system_type: 'governance', health_score: 86, status: 'warning' as const, incidents_week: 0, contract_violations: [], data_source: 'stub_fallback' as DataSource },
  { system_id: 'OBS', system_name: 'Observability Layer', system_type: 'data', health_score: 87, status: 'warning' as const, incidents_week: 0, contract_violations: [{ rule: 'limited_sample_size', detail: 'Single seeded case only' }], data_source: 'stub_fallback' as DataSource },
  { system_id: 'SLO', system_name: 'SLO Budgeting', system_type: 'data', health_score: 82, status: 'warning' as const, incidents_week: 1, contract_violations: [{ rule: 'budget_context_incomplete', detail: 'Budget status warning with partial context' }], data_source: 'stub_fallback' as DataSource },
  { system_id: 'DBB', system_name: 'Data Backbone', system_type: 'data', health_score: 94, status: 'healthy' as const, incidents_week: 0, contract_violations: [], data_source: 'stub_fallback' as DataSource },
  { system_id: 'DEM', system_name: 'Decision Economics', system_type: 'data', health_score: 86, status: 'healthy' as const, incidents_week: 1, contract_violations: [], data_source: 'stub_fallback' as DataSource },
  { system_id: 'MCL', system_name: 'Memory Compaction', system_type: 'data', health_score: 90, status: 'healthy' as const, incidents_week: 0, contract_violations: [], data_source: 'stub_fallback' as DataSource },
  { system_id: 'BRM', system_name: 'Blast Radius Manager', system_type: 'data', health_score: 92, status: 'healthy' as const, incidents_week: 0, contract_violations: [], data_source: 'stub_fallback' as DataSource },
  { system_id: 'XRL', system_name: 'External Reality Loop', system_type: 'data', health_score: 80, status: 'warning' as const, incidents_week: 4, contract_violations: [{ rule: 'latency_sla', detail: 'P99 latency exceeded' }], data_source: 'stub_fallback' as DataSource },
  { system_id: 'NSX', system_name: 'Next-Step Extraction', system_type: 'planning', health_score: 89, status: 'warning' as const, incidents_week: 1, contract_violations: [], data_source: 'stub_fallback' as DataSource },
  { system_id: 'PRG', system_name: 'Program Planning', system_type: 'planning', health_score: 91, status: 'healthy' as const, incidents_week: 0, contract_violations: [], data_source: 'stub_fallback' as DataSource },
  { system_id: 'RSM', system_name: 'Reconciliation State', system_type: 'planning', health_score: 87, status: 'warning' as const, incidents_week: 2, contract_violations: [], data_source: 'stub_fallback' as DataSource },
  { system_id: 'PRA', system_name: 'PR Anchor Discovery', system_type: 'planning', health_score: 84, status: 'healthy' as const, incidents_week: 2, contract_violations: [], data_source: 'stub_fallback' as DataSource },
  { system_id: 'LCE', system_name: 'Lifecycle Transition', system_type: 'placeholder', health_score: 75, status: 'warning' as const, incidents_week: 5, contract_violations: [{ rule: 'throughput', detail: 'Below baseline' }], data_source: 'stub_fallback' as DataSource },
  { system_id: 'ABX', system_name: 'Artifact Bus', system_type: 'placeholder', health_score: 88, status: 'warning' as const, incidents_week: 1, contract_violations: [], data_source: 'stub_fallback' as DataSource },
  { system_id: 'DCL', system_name: 'Doctrine Compilation', system_type: 'placeholder', health_score: 92, status: 'healthy' as const, incidents_week: 0, contract_violations: [], data_source: 'stub_fallback' as DataSource },
  { system_id: 'SAL', system_name: 'Source Authority', system_type: 'placeholder', health_score: 95, status: 'healthy' as const, incidents_week: 0, contract_violations: [], data_source: 'stub_fallback' as DataSource },
  { system_id: 'SAS', system_name: 'Source Authority Sync', system_type: 'placeholder', health_score: 86, status: 'healthy' as const, incidents_week: 1, contract_violations: [], data_source: 'stub_fallback' as DataSource },
  { system_id: 'SHA', system_name: 'Shared Authority', system_type: 'placeholder', health_score: 89, status: 'warning' as const, incidents_week: 1, contract_violations: [], data_source: 'stub_fallback' as DataSource },
];

export async function GET() {
  const snapshot = loadArtifact<RepoSnapshot>(SNAPSHOT_PATH);
  const minimalLoop = loadArtifact<{ proof_chain?: Array<{ stage: string; status: string }>; warnings?: string[] }>(SEED_PATHS.minimalLoop);
  const evalSummary = loadArtifact<{ status?: string }>(SEED_PATHS.evalSummary);
  const lineage = loadArtifact<{ status?: string }>(SEED_PATHS.lineage);
  const controlDecision = loadArtifact<{ status?: string }>(SEED_PATHS.controlDecision);
  const enforcementAction = loadArtifact<{ status?: string }>(SEED_PATHS.enforcementAction);
  const replay = loadArtifact<{ status?: string }>(SEED_PATHS.replay);
  const observability = loadArtifact<{ status?: string }>(SEED_PATHS.observability);
  const slo = loadArtifact<{ status?: string }>(SEED_PATHS.slo);

  const seededStatusBySystem: Record<string, 'healthy' | 'warning' | 'critical'> = {
    AEX: 'warning',
    PQX: 'warning',
    EVL: evalSummary?.status === 'pass' ? 'healthy' : 'warning',
    TPA: 'warning',
    CDE: controlDecision?.status === 'pass' ? 'healthy' : 'warning',
    SEL: enforcementAction?.status === 'pass' ? 'healthy' : 'warning',
    REP: replay?.status === 'pass' ? 'healthy' : 'warning',
    LIN: lineage?.status === 'pass' ? 'healthy' : 'warning',
    OBS: observability?.status === 'pass' ? 'healthy' : 'warning',
    SLO: slo?.status === 'pass' ? 'healthy' : 'warning',
  };

  const envelope = buildSourceEnvelope({
    slots: [
      { path: SNAPSHOT_PATH, loaded: snapshot !== null },
      { path: SEED_PATHS.minimalLoop, loaded: minimalLoop !== null },
      { path: SEED_PATHS.evalSummary, loaded: evalSummary !== null },
      { path: SEED_PATHS.lineage, loaded: lineage !== null },
      { path: SEED_PATHS.controlDecision, loaded: controlDecision !== null },
      { path: SEED_PATHS.enforcementAction, loaded: enforcementAction !== null },
      { path: SEED_PATHS.replay, loaded: replay !== null },
      { path: SEED_PATHS.observability, loaded: observability !== null },
      { path: SEED_PATHS.slo, loaded: slo !== null },
    ],
    isComputed: true,
    warnings: [
      'System health remains partially seeded; non-seeded systems still use static fallback estimates.',
      ...(minimalLoop?.warnings ?? []),
    ],
  });

  const systems = SYSTEMS_RAW.map((s) => {
    const seedStatus = seededStatusBySystem[s.system_id];
    const data_source = seedStatus ? ('artifact_store' as DataSource) : s.data_source;
    const status = seedStatus ?? s.status;
    return {
      ...s,
      data_source,
      status: safeCardStatus(status, data_source),
      authority_role: authorityRoleFor(s.system_id),
      display_group: groupForSystem(s.system_id)?.id ?? null,
    };
  });

  return Response.json({
    status: 'success',
    data_source: envelope.data_source,
    generated_at: envelope.generated_at,
    source_artifacts_used: envelope.source_artifacts_used,
    warnings: envelope.warnings,
    systems: systems,
    seed_artifacts_present: minimalLoop !== null,
    minimal_loop_stage_count: minimalLoop?.proof_chain?.length ?? 0,
    repo_snapshot_at: snapshot?.freshness_timestamp_utc ?? null,
    refreshed_at: new Date().toISOString(),
  });
}
