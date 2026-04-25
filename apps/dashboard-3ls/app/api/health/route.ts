import { loadArtifact } from '@/lib/artifactLoader';
import type { RepoSnapshot } from '@/lib/types';

const SNAPSHOT_PATH = 'artifacts/dashboard/repo_snapshot.json';

// Health scores are governed system estimates; no live telemetry artifact exists.
// data_source is 'stub_fallback' for individual scores; 'artifact_store' for snapshot metadata.
const SYSTEMS = [
  { system_id: 'PQX', system_name: 'Bounded Execution', system_type: 'execution', health_score: 92, status: 'healthy' as const, incidents_week: 0, contract_violations: [] },
  { system_id: 'RDX', system_name: 'Roadmap Execution Loop', system_type: 'execution', health_score: 88, status: 'warning' as const, incidents_week: 2, contract_violations: [{ rule: 'sequence_check', detail: 'Batch out of order' }] },
  { system_id: 'TPA', system_name: 'Trust/Policy Gate', system_type: 'governance', health_score: 95, status: 'healthy' as const, incidents_week: 0, contract_violations: [] },
  { system_id: 'MAP', system_name: 'Review Artifact Mediation', system_type: 'governance', health_score: 90, status: 'healthy' as const, incidents_week: 0, contract_violations: [] },
  { system_id: 'TLC', system_name: 'Top-Level Orchestration', system_type: 'orchestration', health_score: 91, status: 'healthy' as const, incidents_week: 0, contract_violations: [] },
  { system_id: 'RQX', system_name: 'Review Queue Execution', system_type: 'execution', health_score: 87, status: 'warning' as const, incidents_week: 1, contract_violations: [] },
  { system_id: 'HNX', system_name: 'Stage Harness', system_type: 'execution', health_score: 93, status: 'healthy' as const, incidents_week: 0, contract_violations: [] },
  { system_id: 'GOV', system_name: 'Governance Authority', system_type: 'governance', health_score: 96, status: 'healthy' as const, incidents_week: 0, contract_violations: [] },
  { system_id: 'FRE', system_name: 'Failure Diagnosis & Repair', system_type: 'governance', health_score: 85, status: 'healthy' as const, incidents_week: 3, contract_violations: [] },
  { system_id: 'RIL', system_name: 'Review Interpretation', system_type: 'governance', health_score: 89, status: 'warning' as const, incidents_week: 1, contract_violations: [] },
  { system_id: 'AEX', system_name: 'Admission Exchange', system_type: 'orchestration', health_score: 88, status: 'warning' as const, incidents_week: 2, contract_violations: [] },
  { system_id: 'DBB', system_name: 'Data Backbone', system_type: 'data', health_score: 94, status: 'healthy' as const, incidents_week: 0, contract_violations: [] },
  { system_id: 'DEM', system_name: 'Decision Economics', system_type: 'data', health_score: 86, status: 'healthy' as const, incidents_week: 1, contract_violations: [] },
  { system_id: 'MCL', system_name: 'Memory Compaction', system_type: 'data', health_score: 90, status: 'healthy' as const, incidents_week: 0, contract_violations: [] },
  { system_id: 'BRM', system_name: 'Blast Radius Manager', system_type: 'data', health_score: 92, status: 'healthy' as const, incidents_week: 0, contract_violations: [] },
  { system_id: 'XRL', system_name: 'External Reality Loop', system_type: 'data', health_score: 80, status: 'warning' as const, incidents_week: 4, contract_violations: [{ rule: 'latency_sla', detail: 'P99 latency exceeded' }] },
  { system_id: 'NSX', system_name: 'Next-Step Extraction', system_type: 'planning', health_score: 89, status: 'warning' as const, incidents_week: 1, contract_violations: [] },
  { system_id: 'PRG', system_name: 'Program Planning', system_type: 'planning', health_score: 91, status: 'healthy' as const, incidents_week: 0, contract_violations: [] },
  { system_id: 'RSM', system_name: 'Reconciliation State', system_type: 'planning', health_score: 87, status: 'warning' as const, incidents_week: 2, contract_violations: [] },
  { system_id: 'PRA', system_name: 'PR Anchor Discovery', system_type: 'planning', health_score: 84, status: 'healthy' as const, incidents_week: 2, contract_violations: [] },
  { system_id: 'LCE', system_name: 'Lifecycle Transition', system_type: 'placeholder', health_score: 75, status: 'warning' as const, incidents_week: 5, contract_violations: [{ rule: 'throughput', detail: 'Below baseline' }] },
  { system_id: 'ABX', system_name: 'Artifact Bus', system_type: 'placeholder', health_score: 88, status: 'warning' as const, incidents_week: 1, contract_violations: [] },
  { system_id: 'DCL', system_name: 'Doctrine Compilation', system_type: 'placeholder', health_score: 92, status: 'healthy' as const, incidents_week: 0, contract_violations: [] },
  { system_id: 'SAL', system_name: 'Source Authority', system_type: 'placeholder', health_score: 95, status: 'healthy' as const, incidents_week: 0, contract_violations: [] },
  { system_id: 'SAS', system_name: 'Source Authority Sync', system_type: 'placeholder', health_score: 86, status: 'healthy' as const, incidents_week: 1, contract_violations: [] },
  { system_id: 'SHA', system_name: 'Shared Authority', system_type: 'placeholder', health_score: 89, status: 'warning' as const, incidents_week: 1, contract_violations: [] },
];

export async function GET() {
  const snapshot = loadArtifact<RepoSnapshot>(SNAPSHOT_PATH);

  const warnings = [
    'System health scores are static estimates; no live telemetry artifact exists.',
  ];
  const source_artifacts_used: string[] = [];

  if (snapshot) {
    source_artifacts_used.push(SNAPSHOT_PATH);
  } else {
    warnings.push('repo_snapshot.json not found; snapshot metadata unavailable.');
  }

  return Response.json({
    status: 'success',
    data_source: snapshot ? 'artifact_store' : 'stub_fallback',
    generated_at: new Date().toISOString(),
    source_artifacts_used,
    warnings,
    systems: SYSTEMS,
    repo_snapshot_at: snapshot?.freshness_timestamp_utc ?? null,
    refreshed_at: new Date().toISOString(),
  });
}
