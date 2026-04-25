import { NextResponse } from 'next/server';
import { loadArtifact } from '@/lib/artifactLoader';
import { buildSourceEnvelope } from '@/lib/sourceClassification';
import type {
  CheckpointSummary,
  RepoSnapshot,
  SystemState,
  GapAnalysis,
  Provenance,
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

  const envelope = buildSourceEnvelope({
    slots: [
      { path: ARTIFACT_PATHS.checkpointSummary, loaded: checkpointSummary !== null },
      { path: ARTIFACT_PATHS.repoSnapshot, loaded: repoSnapshot !== null },
      { path: ARTIFACT_PATHS.systemState, loaded: systemState !== null },
      { path: ARTIFACT_PATHS.gapAnalysis, loaded: gapAnalysis !== null },
      { path: ARTIFACT_PATHS.provenance, loaded: provenance !== null },
    ],
    // Intelligence summary is a digest aggregated from multiple artifacts;
    // partial coverage degrades to derived_estimate.
    isComputed: true,
  });

  return NextResponse.json({
    ...envelope,
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
