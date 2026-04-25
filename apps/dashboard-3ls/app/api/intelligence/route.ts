import { NextResponse } from 'next/server';
import { loadArtifact } from '@/lib/artifactLoader';
import type {
  CheckpointSummary,
  RepoSnapshot,
  SystemState,
  GapAnalysis,
  Provenance,
  DataSource,
} from '@/lib/types';

const ARTIFACT_PATHS = {
  checkpointSummary: 'artifacts/mg_kernel_24_01/checkpoint_summary.json',
  repoSnapshot: 'artifacts/dashboard/repo_snapshot.json',
  systemState: 'artifacts/roadmap/latest/system_state.json',
  gapAnalysis: 'artifacts/roadmap/latest/gap_analysis.json',
  provenance: 'artifacts/roadmap/latest/provenance.json',
};

export async function GET() {
  const checkpointSummary = loadArtifact<CheckpointSummary>(ARTIFACT_PATHS.checkpointSummary);
  const repoSnapshot = loadArtifact<RepoSnapshot>(ARTIFACT_PATHS.repoSnapshot);
  const systemState = loadArtifact<SystemState>(ARTIFACT_PATHS.systemState);
  const gapAnalysis = loadArtifact<GapAnalysis>(ARTIFACT_PATHS.gapAnalysis);
  const provenance = loadArtifact<Provenance>(ARTIFACT_PATHS.provenance);

  const loaded = [checkpointSummary, repoSnapshot, systemState, gapAnalysis, provenance];
  const source_artifacts_used = Object.values(ARTIFACT_PATHS).filter(
    (_, i) => loaded[i] !== null
  );
  const loadedCount = source_artifacts_used.length;

  const warnings: string[] = [];
  if (!checkpointSummary) warnings.push('mg_kernel checkpoint unavailable');
  if (!repoSnapshot) warnings.push('repo_snapshot unavailable');
  if (!systemState) warnings.push('system_state unavailable');
  if (!gapAnalysis) warnings.push('gap_analysis unavailable');
  if (!provenance) warnings.push('roadmap provenance unavailable');

  let data_source: DataSource;
  if (loadedCount === 0) {
    data_source = 'stub_fallback';
  } else if (loadedCount === loaded.length) {
    data_source = 'artifact_store';
  } else {
    data_source = 'derived';
  }

  return NextResponse.json({
    data_source,
    generated_at: new Date().toISOString(),
    source_artifacts_used,
    warnings,
    intelligence_summary: {
      mg_kernel: checkpointSummary
        ? {
            status: checkpointSummary.status,
            run_id: checkpointSummary.run_id,
            umbrella_count: checkpointSummary.checkpoints.length,
            all_pass: checkpointSummary.checkpoints.every((c) => c.status === 'PASS'),
          }
        : { status: 'unknown' },
      roadmap: gapAnalysis
        ? {
            dominant_bottleneck: gapAnalysis.dominant_bottleneck.id,
            bottleneck_statement: gapAnalysis.dominant_bottleneck.statement,
            highest_risk_trust_gap: gapAnalysis.highest_risk_trust_gap.id,
            top_risks: gapAnalysis.top_risks,
            gap_class_count: Object.keys(gapAnalysis.gap_classes).length,
          }
        : { status: 'unknown' },
      repo: repoSnapshot
        ? {
            total_files: repoSnapshot.root_counts.files_total,
            runtime_modules: repoSnapshot.root_counts.runtime_modules,
            hard_gate: repoSnapshot.key_state.hard_gate_status_record.pass_fail,
            freshness: repoSnapshot.freshness_timestamp_utc,
            operational_signals: repoSnapshot.operational_signals,
          }
        : { status: 'unknown' },
      system_state: systemState
        ? {
            authority_precheck: systemState.authority_precheck.status,
            schema_backed_components: systemState.repo_reality.schema_backed_components.length,
            test_backed_systems: systemState.repo_reality.test_backed_systems.length,
            docs_only_systems: systemState.repo_reality.docs_only_systems.length,
            domain_state: Object.fromEntries(
              Object.entries(systemState.domain_state).map(([k, v]) => [k, v.status])
            ),
          }
        : { status: 'unknown' },
      provenance: provenance
        ? {
            mode: provenance.mode,
            deterministic_ordering: provenance.deterministic_ordering,
            authority_precheck_valid: provenance.validation.authority_precheck_valid,
            step_count_exactly_24: provenance.validation.step_count_exactly_24,
          }
        : { status: 'unknown' },
    },
  });
}
