import { NextRequest, NextResponse } from 'next/server';
import { loadArtifact } from '@/lib/artifactLoader';
import { deriveRGESignals } from '@/lib/rgeSignals';
import { buildSourceEnvelope } from '@/lib/sourceClassification';
import type {
  CheckpointSummary,
  RunSummary,
  LiveTruthBundle,
  RegistryCrossCheck,
  LearningDebtBundle,
  GapAnalysis,
  SystemState,
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

    const signals = deriveRGESignals({
      checkpointSummary,
      runSummary,
      liveTruth,
      registryCrossCheck,
      learningDebt,
      gapAnalysis,
      systemState,
    });

    // RGE analysis values are computed (entropy_vectors, maturity, etc.) so
    // partial-artifact responses are derived_estimate, not derived. The
    // classifier helper enforces that rule centrally.
    const envelope = buildSourceEnvelope({
      slots: [
        { path: ARTIFACT_PATHS.checkpointSummary, loaded: checkpointSummary !== null },
        { path: ARTIFACT_PATHS.runSummary, loaded: runSummary !== null },
        { path: ARTIFACT_PATHS.liveTruth, loaded: liveTruth !== null },
        { path: ARTIFACT_PATHS.registryCrossCheck, loaded: registryCrossCheck !== null },
        { path: ARTIFACT_PATHS.learningDebt, loaded: learningDebt !== null },
        { path: ARTIFACT_PATHS.gapAnalysis, loaded: gapAnalysis !== null },
        { path: ARTIFACT_PATHS.systemState, loaded: systemState !== null },
      ],
      isComputed: true,
      warnings: signals.warnings,
    });

    return NextResponse.json({
      artifact_type: 'rge_analysis_record',
      schema_version: '1.0.0',
      record_id: `ANA-${signals.mg_kernel_run_id}`,
      run_id: signals.mg_kernel_run_id,
      data_source: envelope.data_source,
      generated_at: envelope.generated_at,
      source_artifacts_used: envelope.source_artifacts_used,
      warnings: envelope.warnings,
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
    return NextResponse.json(
      { error: 'Failed to fetch analysis', data_source: 'stub_fallback' },
      { status: 500 }
    );
  }
}
