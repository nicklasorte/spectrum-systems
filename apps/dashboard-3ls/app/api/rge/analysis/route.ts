import { NextRequest, NextResponse } from 'next/server';
import { loadArtifact } from '@/lib/artifactLoader';
import { deriveRGESignals } from '@/lib/rgeSignals';
import type {
  CheckpointSummary,
  RunSummary,
  LiveTruthBundle,
  RegistryCrossCheck,
  LearningDebtBundle,
  GapAnalysis,
  SystemState,
  DataSource,
} from '@/lib/types';

const ARTIFACT_PATHS = {
  checkpointSummary: 'artifacts/mg_kernel_24_01/checkpoint_summary.json',
  runSummary: 'artifacts/mg_kernel_24_01/run_summary.json',
  liveTruth: 'artifacts/mg_kernel_24_01/live_truth_and_risk_bundle.json',
  registryCrossCheck: 'artifacts/mg_kernel_24_01/registry_cross_check.json',
  learningDebt: 'artifacts/mg_kernel_24_01/learning_and_debt_bundle.json',
  gapAnalysis: 'artifacts/roadmap/latest/gap_analysis.json',
  systemState: 'artifacts/roadmap/latest/system_state.json',
};

export async function GET(_req: NextRequest) {
  try {
    const checkpointSummary = loadArtifact<CheckpointSummary>(ARTIFACT_PATHS.checkpointSummary);
    const runSummary = loadArtifact<RunSummary>(ARTIFACT_PATHS.runSummary);
    const liveTruth = loadArtifact<LiveTruthBundle>(ARTIFACT_PATHS.liveTruth);
    const registryCrossCheck = loadArtifact<RegistryCrossCheck>(ARTIFACT_PATHS.registryCrossCheck);
    const learningDebt = loadArtifact<LearningDebtBundle>(ARTIFACT_PATHS.learningDebt);
    const gapAnalysis = loadArtifact<GapAnalysis>(ARTIFACT_PATHS.gapAnalysis);
    const systemState = loadArtifact<SystemState>(ARTIFACT_PATHS.systemState);

    const loaded = [
      checkpointSummary,
      runSummary,
      liveTruth,
      registryCrossCheck,
      learningDebt,
      gapAnalysis,
      systemState,
    ];
    const artifactPaths = Object.values(ARTIFACT_PATHS);
    const source_artifacts_used = artifactPaths.filter((_, i) => loaded[i] !== null);
    const loadedCount = loaded.filter(Boolean).length;

    const signals = deriveRGESignals({
      checkpointSummary,
      runSummary,
      liveTruth,
      registryCrossCheck,
      learningDebt,
      gapAnalysis,
      systemState,
    });

    let data_source: DataSource;
    if (loadedCount === 0) {
      data_source = 'stub_fallback';
    } else if (loadedCount === loaded.length) {
      data_source = 'artifact_store';
    } else {
      data_source = 'derived';
    }

    return NextResponse.json({
      artifact_type: 'rge_analysis_record',
      schema_version: '1.0.0',
      record_id: `ANA-${signals.mg_kernel_run_id}`,
      run_id: signals.mg_kernel_run_id,
      data_source,
      generated_at: new Date().toISOString(),
      source_artifacts_used,
      warnings: signals.warnings,
      rge_can_operate: signals.rge_can_operate,
      context_maturity_level: signals.context_maturity_level,
      wave_status: signals.wave_status,
      mg_kernel_status: signals.mg_kernel_status,
      mg_kernel_run_id: signals.mg_kernel_run_id,
      manual_residue_steps: signals.manual_residue_steps,
      dashboard_truth_status: signals.dashboard_truth_status,
      registry_alignment_status: signals.registry_alignment_status,
      entropy_vectors: signals.entropy_vectors,
      active_drift_legs: signals.active_drift_legs,
      rge_max_autonomy: signals.rge_max_autonomy,
    });
  } catch (error) {
    console.error('Error fetching analysis:', error);
    return NextResponse.json({ error: 'Failed to fetch analysis' }, { status: 500 });
  }
}
