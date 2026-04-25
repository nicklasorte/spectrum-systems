import type {
  CheckpointSummary,
  RunSummary,
  LiveTruthBundle,
  RegistryCrossCheck,
  LearningDebtBundle,
  GapAnalysis,
  SystemState,
} from './types';

export interface RGESignals {
  rge_can_operate: boolean;
  context_maturity_level: number | 'unknown';
  wave_status: number | 'unknown';
  mg_kernel_status: string;
  mg_kernel_run_id: string;
  manual_residue_steps: number | 'unknown';
  dashboard_truth_status: string;
  registry_alignment_status: string;
  entropy_vectors: Record<string, string>;
  active_drift_legs: string[];
  rge_max_autonomy: string;
  warnings: string[];
}

export function deriveRGESignals(args: {
  checkpointSummary: CheckpointSummary | null;
  runSummary: RunSummary | null;
  liveTruth: LiveTruthBundle | null;
  registryCrossCheck: RegistryCrossCheck | null;
  learningDebt: LearningDebtBundle | null;
  gapAnalysis: GapAnalysis | null;
  systemState: SystemState | null;
}): RGESignals {
  const warnings: string[] = [];

  let mg_kernel_status = 'unknown';
  let mg_kernel_run_id = 'unknown';
  if (args.checkpointSummary) {
    mg_kernel_status = args.checkpointSummary.status === 'PASS' ? 'pass' : 'fail';
    mg_kernel_run_id = args.checkpointSummary.run_id;
  } else {
    warnings.push('mg_kernel status unavailable: checkpoint_summary.json not found');
  }

  let manual_residue_steps: number | 'unknown' = 'unknown';
  if (args.runSummary) {
    manual_residue_steps = args.runSummary.manual_residue_steps;
  } else if (args.learningDebt) {
    manual_residue_steps = args.learningDebt.governance_debt_register.manual_residue_steps;
    warnings.push('manual_residue_steps sourced from learning_and_debt_bundle (run_summary.json not found)');
  } else {
    warnings.push(
      'manual_residue_steps unavailable: run_summary.json and learning_and_debt_bundle.json not found'
    );
  }

  let dashboard_truth_status = 'unknown';
  if (args.liveTruth) {
    const probe = args.liveTruth.production_dashboard_truth_probe;
    dashboard_truth_status =
      probe.status === 'PASS' && probe.matches_artifact_truth ? 'verified' : 'unverified';
  } else {
    warnings.push('dashboard_truth_status unavailable: live_truth_and_risk_bundle.json not found');
  }

  let registry_alignment_status = 'unknown';
  if (args.registryCrossCheck) {
    registry_alignment_status =
      args.registryCrossCheck.status === 'PASS' ? 'aligned' : 'misaligned';
  } else {
    warnings.push('registry_alignment_status unavailable: registry_cross_check.json not found');
  }

  const entropy_vectors: Record<string, string> = {};
  let active_drift_legs: string[] = [];
  if (args.gapAnalysis) {
    const gc = args.gapAnalysis.gap_classes;
    entropy_vectors.foundation_gaps = (gc.A_foundation?.length ?? 0) > 0 ? 'warn' : 'clean';
    entropy_vectors.governed_operation = (gc.B_governed_operation?.length ?? 0) > 0 ? 'warn' : 'clean';
    entropy_vectors.learning_gaps = (gc.C_learning?.length ?? 0) > 0 ? 'warn' : 'clean';
    entropy_vectors.control_gaps = (gc.D_control?.length ?? 0) > 0 ? 'warn' : 'clean';
    entropy_vectors.application_gaps = (gc.E_application?.length ?? 0) > 0 ? 'warn' : 'clean';
    entropy_vectors.hardening_gaps = (gc.F_hardening?.length ?? 0) > 0 ? 'warn' : 'clean';
    entropy_vectors.constitutional_alignment =
      (gc.G_constitutional_alignment?.length ?? 0) > 0 ? 'warn' : 'clean';
    if (args.gapAnalysis.dominant_bottleneck?.id === 'BN-006') {
      active_drift_legs = ['EVL'];
    }
  } else {
    warnings.push('entropy_vectors unavailable: gap_analysis.json not found');
  }

  let context_maturity_level: number | 'unknown' = 'unknown';
  let wave_status: number | 'unknown' = 'unknown';
  if (args.systemState) {
    const domains = Object.values(args.systemState.domain_state);
    const governed = domains.filter((d) => d.status === 'present_and_governed').length;
    const partial = domains.filter((d) => d.status === 'partial').length;
    context_maturity_level = Math.min(10, Math.round((governed * 10 + partial * 5) / 7));
    wave_status = governed >= 5 ? 3 : governed >= 3 ? 2 : 1;
  } else {
    warnings.push(
      'context_maturity_level and wave_status unavailable: system_state.json not found'
    );
  }

  const rge_can_operate =
    mg_kernel_status === 'pass' && registry_alignment_status !== 'misaligned';
  const rge_max_autonomy = active_drift_legs.length > 0 ? 'warn_gated' : 'full';

  return {
    rge_can_operate,
    context_maturity_level,
    wave_status,
    mg_kernel_status,
    mg_kernel_run_id,
    manual_residue_steps,
    dashboard_truth_status,
    registry_alignment_status,
    entropy_vectors,
    active_drift_legs,
    rge_max_autonomy,
    warnings,
  };
}
