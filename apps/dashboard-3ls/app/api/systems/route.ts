import { NextResponse } from 'next/server';
import { loadArtifact } from '@/lib/artifactLoader';
import { deriveSystemSignals } from '@/lib/systemSignals';
import { buildSourceEnvelope } from '@/lib/sourceClassification';
import type { RepoSnapshot, SystemState } from '@/lib/types';

const ARTIFACT_PATHS = {
  repoSnapshot: 'artifacts/dashboard/repo_snapshot.json',
  systemState: 'artifacts/roadmap/latest/system_state.json',
};

export async function GET() {
  const repoSnapshot = loadArtifact<RepoSnapshot>(ARTIFACT_PATHS.repoSnapshot);
  const systemState = loadArtifact<SystemState>(ARTIFACT_PATHS.systemState);

  const signals = deriveSystemSignals({ repoSnapshot, systemState });

  // The systems endpoint exposes both raw counts (artifact_store) and a
  // derived breakdown (schema/test/docs splits). Treat the response envelope
  // as artifact_store when complete and derived_estimate when partial — the
  // breakdown is meaningless without the system_state file.
  const envelope = buildSourceEnvelope({
    slots: [
      { path: ARTIFACT_PATHS.repoSnapshot, loaded: repoSnapshot !== null },
      { path: ARTIFACT_PATHS.systemState, loaded: systemState !== null },
    ],
    isComputed: true,
    warnings: signals.warnings,
  });

  const systems = systemState
    ? systemState.repo_reality.schema_backed_components.map((sc) => {
        const testBacked = systemState.repo_reality.test_backed_systems.some(
          (t) => t.system_id === sc.system_id
        );
        const docsOnly = systemState.repo_reality.docs_only_systems.some(
          (d) => d.system_id === sc.system_id
        );
        return {
          system_id: sc.system_id,
          system_name: sc.system,
          schema_backed: true,
          test_backed: testBacked,
          docs_only: docsOnly,
          schema_files: sc.schema_files,
        };
      })
    : [];

  return NextResponse.json({
    ...envelope,
    systems,
    repo_stats: {
      total_files: signals.total_files,
      runtime_modules: signals.runtime_modules,
      test_count: signals.test_count,
      schema_count: signals.schema_count,
    },
    operational_signals: signals.operational_signals,
    hard_gate_status: signals.hard_gate_status,
    schema_backed_systems: signals.schema_backed_systems,
    test_backed_systems: signals.test_backed_systems,
    docs_only_systems: signals.docs_only_systems,
    domain_state: signals.domain_state,
  });
}
