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
  minimalLoop: 'artifacts/dashboard_seed/minimal_loop_snapshot.json',
  evalSummary: 'artifacts/dashboard_seed/eval_summary_record.json',
  lineage: 'artifacts/dashboard_seed/lineage_record.json',
  controlDecision: 'artifacts/dashboard_seed/control_decision_record.json',
  enforcementAction: 'artifacts/dashboard_seed/enforcement_action_record.json',
  replay: 'artifacts/dashboard_seed/replay_record.json',
  observability: 'artifacts/dashboard_seed/observability_metrics_record.json',
  slo: 'artifacts/dashboard_seed/slo_status_record.json',
  failureModes: 'artifacts/dashboard_seed/failure_mode_dashboard_record.json',
  nearMisses: 'artifacts/dashboard_seed/near_miss_record.json',
  bottleneck: 'artifacts/dashboard_metrics/bottleneck_record.json',
  leverageQueue: 'artifacts/dashboard_metrics/leverage_queue_record.json',
  riskSummary: 'artifacts/dashboard_metrics/risk_summary_record.json',
  failureFeedback: 'artifacts/dashboard_metrics/failure_feedback_record.json',
  evalCandidates: 'artifacts/dashboard_metrics/eval_candidate_record.json',
  policyCandidateSignals: 'artifacts/dashboard_metrics/policy_candidate_signal_record.json',
  feedbackLoopSnapshot: 'artifacts/dashboard_metrics/feedback_loop_snapshot.json',
  failureExplanationPackets: 'artifacts/dashboard_metrics/failure_explanation_packets.json',
  overrideAuditLog: 'artifacts/dashboard_metrics/override_audit_log_record.json',
  evalMaterializationPath: 'artifacts/dashboard_metrics/eval_materialization_path_record.json',
  caseIndex: 'artifacts/dashboard_cases/case_index_record.json',
  replayLineageHardening: 'artifacts/dashboard_metrics/replay_lineage_hardening_record.json',
  fallbackReductionPlan: 'artifacts/dashboard_metrics/fallback_reduction_plan_record.json',
  selComplianceSignalInput: 'artifacts/dashboard_metrics/sel_compliance_signal_input_record.json',
  candidateClosureLedger: 'artifacts/dashboard_metrics/candidate_closure_ledger_record.json',
  metArtifactDependencyIndex: 'artifacts/dashboard_metrics/met_artifact_dependency_index_record.json',
  trendFrequencyHonestyGate: 'artifacts/dashboard_metrics/trend_frequency_honesty_gate_record.json',
  evlHandoffObservationTracker: 'artifacts/dashboard_metrics/evl_handoff_observation_tracker_record.json',
  overrideEvidenceIntake: 'artifacts/dashboard_metrics/override_evidence_intake_record.json',
  debugExplanationIndex: 'artifacts/dashboard_metrics/debug_explanation_index_record.json',
  metGeneratedArtifactClassification:
    'artifacts/dashboard_metrics/met_generated_artifact_classification_record.json',
  ownerReadObservationLedger:
    'artifacts/dashboard_metrics/owner_read_observation_ledger_record.json',
  materializationObservationMapper:
    'artifacts/dashboard_metrics/materialization_observation_mapper_record.json',
  comparableCaseQualificationGate:
    'artifacts/dashboard_metrics/comparable_case_qualification_gate_record.json',
  trendReadyCasePack: 'artifacts/dashboard_metrics/trend_ready_case_pack_record.json',
  overrideEvidenceSourceAdapter:
    'artifacts/dashboard_metrics/override_evidence_source_adapter_record.json',
  foldCandidateProofCheck:
    'artifacts/dashboard_metrics/fold_candidate_proof_check_record.json',
  operatorDebuggabilityDrill:
    'artifacts/dashboard_metrics/operator_debuggability_drill_record.json',
  generatedArtifactPolicyHandoff:
    'artifacts/dashboard_metrics/generated_artifact_policy_handoff_record.json',
  // MET-FULL-ROADMAP — registry, closure pressure, outcome attribution, calibration,
  // cross-run consistency, error-budget observation, action bundles, counterfactuals,
  // recurrence, debug SLA, and signal integrity. All blocks are MET observations only;
  // CDE/SEL/GOV remain canonical owners.
  staleCandidatePressure:
    'artifacts/dashboard_metrics/stale_candidate_pressure_record.json',
  outcomeAttribution: 'artifacts/dashboard_metrics/outcome_attribution_record.json',
  failureReductionSignal:
    'artifacts/dashboard_metrics/failure_reduction_signal_record.json',
  recommendationAccuracy:
    'artifacts/dashboard_metrics/recommendation_accuracy_record.json',
  calibrationDrift: 'artifacts/dashboard_metrics/calibration_drift_record.json',
  signalConfidence: 'artifacts/dashboard_metrics/signal_confidence_record.json',
  crossRunConsistency:
    'artifacts/dashboard_metrics/cross_run_consistency_record.json',
  divergenceDetection:
    'artifacts/dashboard_metrics/divergence_detection_record.json',
  metErrorBudgetObservation:
    'artifacts/dashboard_metrics/met_error_budget_observation_record.json',
  metFreezeRecommendationSignal:
    'artifacts/dashboard_metrics/met_freeze_recommendation_signal_record.json',
  nextBestSliceRecommendation:
    'artifacts/dashboard_metrics/next_best_slice_recommendation_record.json',
  pqxCandidateActionBundle:
    'artifacts/dashboard_metrics/pqx_candidate_action_bundle_record.json',
  counterfactualReconstruction:
    'artifacts/dashboard_metrics/counterfactual_reconstruction_record.json',
  earlierInterventionSignal:
    'artifacts/dashboard_metrics/earlier_intervention_signal_record.json',
  recurringFailureCluster:
    'artifacts/dashboard_metrics/recurring_failure_cluster_record.json',
  recurrenceSeveritySignal:
    'artifacts/dashboard_metrics/recurrence_severity_signal_record.json',
  timeToExplain: 'artifacts/dashboard_metrics/time_to_explain_record.json',
  debugReadinessSla:
    'artifacts/dashboard_metrics/debug_readiness_sla_record.json',
  metricGamingDetection:
    'artifacts/dashboard_metrics/metric_gaming_detection_record.json',
  misleadingSignalDetection:
    'artifacts/dashboard_metrics/misleading_signal_detection_record.json',
  signalIntegrityCheck:
    'artifacts/dashboard_metrics/signal_integrity_check_record.json',
};

interface BottleneckRecord {
  data_source?: string;
  source_artifacts_used?: string[];
  warnings?: string[];
  payload?: {
    dominant_bottleneck_system?: string;
    constrained_loop_leg?: string;
    loop_legs_evaluated?: string[];
    warning_counts_by_system?: Record<string, number>;
    block_counts_by_system?: Record<string, number>;
    supporting_evidence?: Array<{ kind: string; source: string; detail: string }>;
    bottleneck_priority_rule?: string;
    bottleneck_confidence?: string;
    confidence_rationale?: string;
  };
}

interface LeverageItem {
  id: string;
  title: string;
  failure_prevented: string;
  signal_improved: string;
  systems_affected: string[];
  severity: 'high' | 'medium' | 'low';
  frequency: 'high' | 'medium' | 'low' | 'unknown';
  estimated_effort: 'high' | 'medium' | 'low' | 'unknown';
  blocks_promotion?: boolean;
  affects_governance_legs?: boolean;
  repeat_failure?: boolean;
  reduces_fallback_or_unknown?: boolean;
  leverage_score: number;
  data_source: string;
  source_artifacts_used: string[];
  confidence: string;
}

interface LeverageQueueRecord {
  data_source?: string;
  source_artifacts_used?: string[];
  warnings?: string[];
  leverage_formula?: string;
  weights?: unknown;
  items?: LeverageItem[];
}

interface RiskSummaryRecord {
  data_source?: string;
  source_artifacts_used?: string[];
  warnings?: string[];
  payload?: {
    fallback_signal_count?: number;
    fallback_signal_systems?: string[];
    unknown_signal_count?: number;
    missing_eval_count?: number | 'unknown';
    missing_eval_dimensions?: string[];
    missing_trace_count?: number | 'unknown';
    override_count?: number | 'unknown';
    proof_chain_coverage?: {
      total?: number;
      present?: number;
      partial?: number;
      missing_or_unknown?: number;
      percent_present_or_partial?: number;
      percent_present_only?: number;
    };
    top_risks?: Array<{
      id: string;
      title: string;
      severity: string;
      systems_affected: string[];
      evidence_artifact: string;
    }>;
  };
}

export async function GET() {
  const checkpointSummary = loadArtifact<CheckpointSummary>(ARTIFACT_PATHS.checkpointSummary);
  const repoSnapshot = loadArtifact<RepoSnapshot>(ARTIFACT_PATHS.repoSnapshot);
  const systemState = loadArtifact<SystemState>(ARTIFACT_PATHS.systemState);
  const gapAnalysis = loadArtifact<GapAnalysis>(ARTIFACT_PATHS.gapAnalysis);
  const provenance = loadArtifact<Provenance>(ARTIFACT_PATHS.provenance);

  const minimalLoop = loadArtifact<{
    proof_chain?: Array<{ stage: string; status: string; data_source: string }>;
    minimal_loop_status?: string;
    source_artifacts_used?: string[];
    warnings?: string[];
  }>(ARTIFACT_PATHS.minimalLoop);
  const evalSummary = loadArtifact<{ status?: string; data_source?: string; warnings?: string[] }>(
    ARTIFACT_PATHS.evalSummary
  );
  const lineage = loadArtifact<{ status?: string }>(ARTIFACT_PATHS.lineage);
  const controlDecision = loadArtifact<{ status?: string }>(ARTIFACT_PATHS.controlDecision);
  const enforcementAction = loadArtifact<{ status?: string }>(ARTIFACT_PATHS.enforcementAction);
  const replay = loadArtifact<{ status?: string }>(ARTIFACT_PATHS.replay);
  const observability = loadArtifact<{ status?: string }>(ARTIFACT_PATHS.observability);
  const slo = loadArtifact<{ status?: string }>(ARTIFACT_PATHS.slo);
  const failureModes = loadArtifact<{
    failure_modes?: Array<{
      id: string;
      title: string;
      severity: string;
      frequency?: string;
      systems_affected?: string[];
      trend?: string;
      evidence?: string[];
    }>;
  }>(ARTIFACT_PATHS.failureModes);
  const nearMisses = loadArtifact<{ near_misses?: unknown[] }>(ARTIFACT_PATHS.nearMisses);

  const bottleneck = loadArtifact<BottleneckRecord>(ARTIFACT_PATHS.bottleneck);
  const leverageQueue = loadArtifact<LeverageQueueRecord>(ARTIFACT_PATHS.leverageQueue);
  const riskSummary = loadArtifact<RiskSummaryRecord>(ARTIFACT_PATHS.riskSummary);

  // MET-04-18 — learning loop, debuggability, and fallback reduction artifacts.
  // Each block degrades to 'unknown' rather than substituting 0 or PASS when
  // the artifact is missing.
  const failureFeedback = loadArtifact<{
    data_source?: string;
    source_artifacts_used?: string[];
    warnings?: string[];
    failure_prevented?: string;
    signal_improved?: string;
    feedback_items?: Array<Record<string, unknown>>;
  }>(ARTIFACT_PATHS.failureFeedback);
  const evalCandidates = loadArtifact<{
    data_source?: string;
    source_artifacts_used?: string[];
    warnings?: string[];
    failure_prevented?: string;
    signal_improved?: string;
    candidates_summary?: Record<string, unknown>;
    candidates?: Array<Record<string, unknown>>;
  }>(ARTIFACT_PATHS.evalCandidates);
  const policyCandidateSignals = loadArtifact<{
    data_source?: string;
    source_artifacts_used?: string[];
    warnings?: string[];
    failure_prevented?: string;
    signal_improved?: string;
    candidates?: Array<Record<string, unknown>>;
  }>(ARTIFACT_PATHS.policyCandidateSignals);
  const feedbackLoopSnapshot = loadArtifact<{
    data_source?: string;
    source_artifacts_used?: string[];
    warnings?: string[];
    failure_prevented?: string;
    signal_improved?: string;
    feedback_items_count?: number;
    eval_candidates_count?: number;
    policy_candidate_signals_count?: number;
    unresolved_feedback_count?: number;
    expired_feedback_count?: number;
    top_feedback_themes?: Array<Record<string, unknown>>;
    next_recommended_improvement_inputs?: string[];
    loop_status?: string;
  }>(ARTIFACT_PATHS.feedbackLoopSnapshot);
  const failureExplanationPackets = loadArtifact<{
    data_source?: string;
    source_artifacts_used?: string[];
    warnings?: string[];
    failure_prevented?: string;
    signal_improved?: string;
    packets?: Array<Record<string, unknown>>;
  }>(ARTIFACT_PATHS.failureExplanationPackets);
  const overrideAuditLog = loadArtifact<{
    data_source?: string;
    source_artifacts_used?: string[];
    warnings?: string[];
    failure_prevented?: string;
    signal_improved?: string;
    override_count?: number | 'unknown';
    overrides?: Array<Record<string, unknown>>;
    next_recommended_input?: string;
    reason_codes?: string[];
  }>(ARTIFACT_PATHS.overrideAuditLog);
  const evalMaterializationPath = loadArtifact<{
    data_source?: string;
    source_artifacts_used?: string[];
    warnings?: string[];
    failure_prevented?: string;
    signal_improved?: string;
    path_id?: string;
    source_eval_candidates?: string[];
    owner_recommendation?: string;
    required_authority_inputs?: string[];
    required_artifacts_before_materialization?: string[];
    required_tests?: string[];
    materialization_status?: string;
    next_recommended_input?: string;
  }>(ARTIFACT_PATHS.evalMaterializationPath);
  const caseIndex = loadArtifact<{
    data_source?: string;
    source_artifacts_used?: string[];
    warnings?: string[];
    failure_prevented?: string;
    signal_improved?: string;
    cases?: string[];
  }>(ARTIFACT_PATHS.caseIndex);
  const replayLineageHardening = loadArtifact<{
    data_source?: string;
    source_artifacts_used?: string[];
    warnings?: string[];
    failure_prevented?: string;
    signal_improved?: string;
    affected_systems?: string[];
    replay_dimensions_checked?: Array<Record<string, unknown>>;
    lineage_links_checked?: Array<Record<string, unknown>>;
    gaps_observed?: string[];
    hardening_recommendations?: Array<Record<string, unknown>>;
  }>(ARTIFACT_PATHS.replayLineageHardening);
  const fallbackReductionPlan = loadArtifact<{
    data_source?: string;
    source_artifacts_used?: string[];
    warnings?: string[];
    failure_prevented?: string;
    signal_improved?: string;
    total_fallback_count?: number | 'unknown';
    high_leverage_fallback_count?: number | 'unknown';
    fallback_items?: Array<Record<string, unknown>>;
  }>(ARTIFACT_PATHS.fallbackReductionPlan);
  const selComplianceSignalInput = loadArtifact<{
    data_source?: string;
    source_artifacts_used?: string[];
    warnings?: string[];
    failure_prevented?: string;
    signal_improved?: string;
    signal_input_id?: string;
    suggested_owner_system?: string;
    observed_gap?: string;
    compliance_signal_needed?: string;
    next_recommended_input?: string;
    status_label?: string;
  }>(ARTIFACT_PATHS.selComplianceSignalInput);

  // MET-19-33 — closure, dependency, debuggability, and integrity blocks.
  // Each block degrades to 'unknown' rather than substituting 0 or PASS when
  // the artifact is missing.
  const candidateClosureLedger = loadArtifact<{
    data_source?: string;
    source_artifacts_used?: string[];
    warnings?: string[];
    failure_prevented?: string;
    signal_improved?: string;
    candidate_items?: Array<Record<string, unknown>>;
  }>(ARTIFACT_PATHS.candidateClosureLedger);
  const metArtifactDependencyIndex = loadArtifact<{
    data_source?: string;
    source_artifacts_used?: string[];
    warnings?: string[];
    failure_prevented?: string;
    signal_improved?: string;
    artifact_dependencies?: Array<Record<string, unknown>>;
  }>(ARTIFACT_PATHS.metArtifactDependencyIndex);
  const trendFrequencyHonestyGate = loadArtifact<{
    data_source?: string;
    source_artifacts_used?: string[];
    warnings?: string[];
    failure_prevented?: string;
    signal_improved?: string;
    comparable_case_count?: number | 'unknown';
    required_case_count_for_trend?: number;
    trend_state?: string;
    frequency_state?: string;
    cases_needed?: number | 'unknown';
    comparable_cases?: Array<Record<string, unknown>>;
    blocked_trend_fields?: Array<Record<string, unknown>>;
    shape_breakdown?: Array<Record<string, unknown>>;
  }>(ARTIFACT_PATHS.trendFrequencyHonestyGate);
  const evlHandoffObservationTracker = loadArtifact<{
    data_source?: string;
    source_artifacts_used?: string[];
    warnings?: string[];
    failure_prevented?: string;
    signal_improved?: string;
    handoff_items?: Array<Record<string, unknown>>;
  }>(ARTIFACT_PATHS.evlHandoffObservationTracker);
  const overrideEvidenceIntake = loadArtifact<{
    data_source?: string;
    source_artifacts_used?: string[];
    warnings?: string[];
    failure_prevented?: string;
    signal_improved?: string;
    override_evidence_count?: number | 'unknown';
    override_evidence_items?: Array<Record<string, unknown>>;
    evidence_status?: string;
    next_recommended_input?: string;
    reason_codes?: string[];
    intake_shape_recommendation?: Record<string, unknown>;
  }>(ARTIFACT_PATHS.overrideEvidenceIntake);
  const debugExplanationIndex = loadArtifact<{
    data_source?: string;
    source_artifacts_used?: string[];
    warnings?: string[];
    failure_prevented?: string;
    signal_improved?: string;
    debug_target_minutes?: number;
    explanation_entries?: Array<Record<string, unknown>>;
  }>(ARTIFACT_PATHS.debugExplanationIndex);
  const metGeneratedArtifactClassification = loadArtifact<{
    data_source?: string;
    source_artifacts_used?: string[];
    warnings?: string[];
    failure_prevented?: string;
    signal_improved?: string;
    classified_paths?: Array<Record<string, unknown>>;
  }>(ARTIFACT_PATHS.metGeneratedArtifactClassification);

  const ownerReadObservationLedger = loadArtifact<{
    data_source?: string;
    source_artifacts_used?: string[];
    warnings?: string[];
    owner_read_items?: Array<Record<string, unknown>>;
  }>(ARTIFACT_PATHS.ownerReadObservationLedger);
  const materializationObservationMapper = loadArtifact<{
    data_source?: string;
    source_artifacts_used?: string[];
    warnings?: string[];
    materialization_observations?: Array<Record<string, unknown>>;
  }>(ARTIFACT_PATHS.materializationObservationMapper);
  const comparableCaseQualificationGate = loadArtifact<{
    data_source?: string;
    source_artifacts_used?: string[];
    warnings?: string[];
    qualification_rules?: Record<string, unknown>;
    qualified_case_groups?: Array<Record<string, unknown>>;
  }>(ARTIFACT_PATHS.comparableCaseQualificationGate);
  const trendReadyCasePack = loadArtifact<{
    data_source?: string;
    source_artifacts_used?: string[];
    warnings?: string[];
    case_packs?: Array<Record<string, unknown>>;
  }>(ARTIFACT_PATHS.trendReadyCasePack);
  const overrideEvidenceSourceAdapter = loadArtifact<{
    data_source?: string;
    source_artifacts_used?: string[];
    warnings?: string[];
    override_source_state?: string;
    override_evidence_count?: number | 'unknown';
    override_evidence_refs?: string[];
    next_recommended_input?: string;
  }>(ARTIFACT_PATHS.overrideEvidenceSourceAdapter);
  const foldCandidateProofCheck = loadArtifact<{
    data_source?: string;
    source_artifacts_used?: string[];
    warnings?: string[];
    fold_candidates?: Array<Record<string, unknown>>;
  }>(ARTIFACT_PATHS.foldCandidateProofCheck);
  const operatorDebuggabilityDrill = loadArtifact<{
    data_source?: string;
    source_artifacts_used?: string[];
    warnings?: string[];
    target_minutes?: number;
    drill_items?: Array<Record<string, unknown>>;
  }>(ARTIFACT_PATHS.operatorDebuggabilityDrill);
  const generatedArtifactPolicyHandoff = loadArtifact<{
    data_source?: string;
    source_artifacts_used?: string[];
    warnings?: string[];
    central_policy_path?: string;
    central_policy_state?: string;
    policy_alignment_items?: Array<Record<string, unknown>>;
  }>(ARTIFACT_PATHS.generatedArtifactPolicyHandoff);

  // MET-FULL-ROADMAP — non-owning observation, attribution, calibration, cross-run,
  // error budget, action bundle, counterfactual, recurrence, debug SLA, integrity.
  type GenericMetEnvelope = {
    data_source?: string;
    source_artifacts_used?: string[];
    warnings?: string[];
    failure_prevented?: string;
    signal_improved?: string;
  };
  const staleCandidatePressure = loadArtifact<GenericMetEnvelope & {
    pressure_summary?: Record<string, unknown>;
    pressure_by_loop_leg?: Array<Record<string, unknown>>;
  }>(ARTIFACT_PATHS.staleCandidatePressure);
  const outcomeAttribution = loadArtifact<GenericMetEnvelope & {
    outcome_entries?: Array<Record<string, unknown>>;
  }>(ARTIFACT_PATHS.outcomeAttribution);
  const failureReductionSignal = loadArtifact<GenericMetEnvelope & {
    failure_reduction_signals?: Array<Record<string, unknown>>;
  }>(ARTIFACT_PATHS.failureReductionSignal);
  const recommendationAccuracy = loadArtifact<GenericMetEnvelope & {
    recommendation_entries?: Array<Record<string, unknown>>;
  }>(ARTIFACT_PATHS.recommendationAccuracy);
  const calibrationDrift = loadArtifact<GenericMetEnvelope & {
    minimum_paired_outcomes_per_bucket?: number;
    calibration_buckets?: Array<Record<string, unknown>>;
  }>(ARTIFACT_PATHS.calibrationDrift);
  const signalConfidence = loadArtifact<GenericMetEnvelope & {
    minimum_evidence_count_for_high_confidence?: number;
    signal_entries?: Array<Record<string, unknown>>;
  }>(ARTIFACT_PATHS.signalConfidence);
  const crossRunConsistency = loadArtifact<GenericMetEnvelope & {
    non_material_fields_ignored?: string[];
    consistency_entries?: Array<Record<string, unknown>>;
  }>(ARTIFACT_PATHS.crossRunConsistency);
  const divergenceDetection = loadArtifact<GenericMetEnvelope & {
    divergence_entries?: Array<Record<string, unknown>>;
  }>(ARTIFACT_PATHS.divergenceDetection);
  const metErrorBudgetObservation = loadArtifact<GenericMetEnvelope & {
    budget_observations?: Array<Record<string, unknown>>;
  }>(ARTIFACT_PATHS.metErrorBudgetObservation);
  const metFreezeRecommendationSignal = loadArtifact<GenericMetEnvelope & {
    recommendation_signals?: Array<Record<string, unknown>>;
  }>(ARTIFACT_PATHS.metFreezeRecommendationSignal);
  const nextBestSliceRecommendation = loadArtifact<GenericMetEnvelope & {
    slice_candidates?: Array<Record<string, unknown>>;
  }>(ARTIFACT_PATHS.nextBestSliceRecommendation);
  const pqxCandidateActionBundle = loadArtifact<GenericMetEnvelope & {
    bundle_candidates?: Array<Record<string, unknown>>;
  }>(ARTIFACT_PATHS.pqxCandidateActionBundle);
  const counterfactualReconstruction = loadArtifact<GenericMetEnvelope & {
    counterfactual_entries?: Array<Record<string, unknown>>;
  }>(ARTIFACT_PATHS.counterfactualReconstruction);
  const earlierInterventionSignal = loadArtifact<GenericMetEnvelope & {
    intervention_signals?: Array<Record<string, unknown>>;
  }>(ARTIFACT_PATHS.earlierInterventionSignal);
  const recurringFailureCluster = loadArtifact<GenericMetEnvelope & {
    minimum_comparable_cases_for_recurrence?: number;
    clusters?: Array<Record<string, unknown>>;
  }>(ARTIFACT_PATHS.recurringFailureCluster);
  const recurrenceSeveritySignal = loadArtifact<GenericMetEnvelope & {
    severity_signals?: Array<Record<string, unknown>>;
  }>(ARTIFACT_PATHS.recurrenceSeveritySignal);
  const timeToExplain = loadArtifact<GenericMetEnvelope & {
    target_minutes?: number;
    questions_required?: string[];
    time_to_explain_entries?: Array<Record<string, unknown>>;
  }>(ARTIFACT_PATHS.timeToExplain);
  const debugReadinessSla = loadArtifact<GenericMetEnvelope & {
    target_minutes?: number;
    readiness_states_allowed?: string[];
    readiness_entries?: Array<Record<string, unknown>>;
  }>(ARTIFACT_PATHS.debugReadinessSla);
  const metricGamingDetection = loadArtifact<GenericMetEnvelope & {
    rules_checked?: string[];
    gaming_observations?: Array<Record<string, unknown>>;
  }>(ARTIFACT_PATHS.metricGamingDetection);
  const misleadingSignalDetection = loadArtifact<GenericMetEnvelope & {
    rules_checked?: string[];
    misleading_signal_observations?: Array<Record<string, unknown>>;
  }>(ARTIFACT_PATHS.misleadingSignalDetection);
  const signalIntegrityCheck = loadArtifact<GenericMetEnvelope & {
    integrity_summary?: Record<string, unknown>;
    integrity_checks?: Array<Record<string, unknown>>;
  }>(ARTIFACT_PATHS.signalIntegrityCheck);

  const allSlots = [
    { path: ARTIFACT_PATHS.checkpointSummary, loaded: checkpointSummary !== null },
    { path: ARTIFACT_PATHS.repoSnapshot, loaded: repoSnapshot !== null },
    { path: ARTIFACT_PATHS.systemState, loaded: systemState !== null },
    { path: ARTIFACT_PATHS.gapAnalysis, loaded: gapAnalysis !== null },
    { path: ARTIFACT_PATHS.provenance, loaded: provenance !== null },
    { path: ARTIFACT_PATHS.minimalLoop, loaded: minimalLoop !== null },
    { path: ARTIFACT_PATHS.evalSummary, loaded: evalSummary !== null },
    { path: ARTIFACT_PATHS.lineage, loaded: lineage !== null },
    { path: ARTIFACT_PATHS.controlDecision, loaded: controlDecision !== null },
    { path: ARTIFACT_PATHS.enforcementAction, loaded: enforcementAction !== null },
    { path: ARTIFACT_PATHS.replay, loaded: replay !== null },
    { path: ARTIFACT_PATHS.observability, loaded: observability !== null },
    { path: ARTIFACT_PATHS.slo, loaded: slo !== null },
    { path: ARTIFACT_PATHS.failureModes, loaded: failureModes !== null },
    { path: ARTIFACT_PATHS.nearMisses, loaded: nearMisses !== null },
    { path: ARTIFACT_PATHS.bottleneck, loaded: bottleneck !== null },
    { path: ARTIFACT_PATHS.leverageQueue, loaded: leverageQueue !== null },
    { path: ARTIFACT_PATHS.riskSummary, loaded: riskSummary !== null },
    { path: ARTIFACT_PATHS.failureFeedback, loaded: failureFeedback !== null },
    { path: ARTIFACT_PATHS.evalCandidates, loaded: evalCandidates !== null },
    { path: ARTIFACT_PATHS.policyCandidateSignals, loaded: policyCandidateSignals !== null },
    { path: ARTIFACT_PATHS.feedbackLoopSnapshot, loaded: feedbackLoopSnapshot !== null },
    { path: ARTIFACT_PATHS.failureExplanationPackets, loaded: failureExplanationPackets !== null },
    { path: ARTIFACT_PATHS.overrideAuditLog, loaded: overrideAuditLog !== null },
    { path: ARTIFACT_PATHS.evalMaterializationPath, loaded: evalMaterializationPath !== null },
    { path: ARTIFACT_PATHS.caseIndex, loaded: caseIndex !== null },
    { path: ARTIFACT_PATHS.replayLineageHardening, loaded: replayLineageHardening !== null },
    { path: ARTIFACT_PATHS.fallbackReductionPlan, loaded: fallbackReductionPlan !== null },
    { path: ARTIFACT_PATHS.selComplianceSignalInput, loaded: selComplianceSignalInput !== null },
    { path: ARTIFACT_PATHS.candidateClosureLedger, loaded: candidateClosureLedger !== null },
    { path: ARTIFACT_PATHS.metArtifactDependencyIndex, loaded: metArtifactDependencyIndex !== null },
    { path: ARTIFACT_PATHS.trendFrequencyHonestyGate, loaded: trendFrequencyHonestyGate !== null },
    { path: ARTIFACT_PATHS.evlHandoffObservationTracker, loaded: evlHandoffObservationTracker !== null },
    { path: ARTIFACT_PATHS.overrideEvidenceIntake, loaded: overrideEvidenceIntake !== null },
    { path: ARTIFACT_PATHS.debugExplanationIndex, loaded: debugExplanationIndex !== null },
    {
      path: ARTIFACT_PATHS.metGeneratedArtifactClassification,
      loaded: metGeneratedArtifactClassification !== null,
    },
    { path: ARTIFACT_PATHS.ownerReadObservationLedger, loaded: ownerReadObservationLedger !== null },
    { path: ARTIFACT_PATHS.materializationObservationMapper, loaded: materializationObservationMapper !== null },
    { path: ARTIFACT_PATHS.comparableCaseQualificationGate, loaded: comparableCaseQualificationGate !== null },
    { path: ARTIFACT_PATHS.trendReadyCasePack, loaded: trendReadyCasePack !== null },
    { path: ARTIFACT_PATHS.overrideEvidenceSourceAdapter, loaded: overrideEvidenceSourceAdapter !== null },
    { path: ARTIFACT_PATHS.foldCandidateProofCheck, loaded: foldCandidateProofCheck !== null },
    { path: ARTIFACT_PATHS.operatorDebuggabilityDrill, loaded: operatorDebuggabilityDrill !== null },
    { path: ARTIFACT_PATHS.generatedArtifactPolicyHandoff, loaded: generatedArtifactPolicyHandoff !== null },
    { path: ARTIFACT_PATHS.staleCandidatePressure, loaded: staleCandidatePressure !== null },
    { path: ARTIFACT_PATHS.outcomeAttribution, loaded: outcomeAttribution !== null },
    { path: ARTIFACT_PATHS.failureReductionSignal, loaded: failureReductionSignal !== null },
    { path: ARTIFACT_PATHS.recommendationAccuracy, loaded: recommendationAccuracy !== null },
    { path: ARTIFACT_PATHS.calibrationDrift, loaded: calibrationDrift !== null },
    { path: ARTIFACT_PATHS.signalConfidence, loaded: signalConfidence !== null },
    { path: ARTIFACT_PATHS.crossRunConsistency, loaded: crossRunConsistency !== null },
    { path: ARTIFACT_PATHS.divergenceDetection, loaded: divergenceDetection !== null },
    { path: ARTIFACT_PATHS.metErrorBudgetObservation, loaded: metErrorBudgetObservation !== null },
    { path: ARTIFACT_PATHS.metFreezeRecommendationSignal, loaded: metFreezeRecommendationSignal !== null },
    { path: ARTIFACT_PATHS.nextBestSliceRecommendation, loaded: nextBestSliceRecommendation !== null },
    { path: ARTIFACT_PATHS.pqxCandidateActionBundle, loaded: pqxCandidateActionBundle !== null },
    { path: ARTIFACT_PATHS.counterfactualReconstruction, loaded: counterfactualReconstruction !== null },
    { path: ARTIFACT_PATHS.earlierInterventionSignal, loaded: earlierInterventionSignal !== null },
    { path: ARTIFACT_PATHS.recurringFailureCluster, loaded: recurringFailureCluster !== null },
    { path: ARTIFACT_PATHS.recurrenceSeveritySignal, loaded: recurrenceSeveritySignal !== null },
    { path: ARTIFACT_PATHS.timeToExplain, loaded: timeToExplain !== null },
    { path: ARTIFACT_PATHS.debugReadinessSla, loaded: debugReadinessSla !== null },
    { path: ARTIFACT_PATHS.metricGamingDetection, loaded: metricGamingDetection !== null },
    { path: ARTIFACT_PATHS.misleadingSignalDetection, loaded: misleadingSignalDetection !== null },
    { path: ARTIFACT_PATHS.signalIntegrityCheck, loaded: signalIntegrityCheck !== null },
  ];

  const envelope = buildSourceEnvelope({
    slots: allSlots,
    isComputed: true,
    warnings: [
      ...(minimalLoop?.warnings ?? []),
      ...(evalSummary?.warnings ?? []),
      ...(bottleneck?.warnings ?? []),
      ...(leverageQueue?.warnings ?? []),
      ...(riskSummary?.warnings ?? []),
      ...(failureFeedback?.warnings ?? []),
      ...(evalCandidates?.warnings ?? []),
      ...(policyCandidateSignals?.warnings ?? []),
      ...(feedbackLoopSnapshot?.warnings ?? []),
      ...(failureExplanationPackets?.warnings ?? []),
      ...(overrideAuditLog?.warnings ?? []),
      ...(evalMaterializationPath?.warnings ?? []),
      ...(caseIndex?.warnings ?? []),
      ...(replayLineageHardening?.warnings ?? []),
      ...(fallbackReductionPlan?.warnings ?? []),
      ...(selComplianceSignalInput?.warnings ?? []),
      ...(candidateClosureLedger?.warnings ?? []),
      ...(metArtifactDependencyIndex?.warnings ?? []),
      ...(trendFrequencyHonestyGate?.warnings ?? []),
      ...(evlHandoffObservationTracker?.warnings ?? []),
      ...(overrideEvidenceIntake?.warnings ?? []),
      ...(debugExplanationIndex?.warnings ?? []),
      ...(metGeneratedArtifactClassification?.warnings ?? []),
      ...(ownerReadObservationLedger?.warnings ?? []),
      ...(materializationObservationMapper?.warnings ?? []),
      ...(comparableCaseQualificationGate?.warnings ?? []),
      ...(trendReadyCasePack?.warnings ?? []),
      ...(overrideEvidenceSourceAdapter?.warnings ?? []),
      ...(foldCandidateProofCheck?.warnings ?? []),
      ...(operatorDebuggabilityDrill?.warnings ?? []),
      ...(generatedArtifactPolicyHandoff?.warnings ?? []),
      ...(staleCandidatePressure?.warnings ?? []),
      ...(outcomeAttribution?.warnings ?? []),
      ...(failureReductionSignal?.warnings ?? []),
      ...(recommendationAccuracy?.warnings ?? []),
      ...(calibrationDrift?.warnings ?? []),
      ...(signalConfidence?.warnings ?? []),
      ...(crossRunConsistency?.warnings ?? []),
      ...(divergenceDetection?.warnings ?? []),
      ...(metErrorBudgetObservation?.warnings ?? []),
      ...(metFreezeRecommendationSignal?.warnings ?? []),
      ...(nextBestSliceRecommendation?.warnings ?? []),
      ...(pqxCandidateActionBundle?.warnings ?? []),
      ...(counterfactualReconstruction?.warnings ?? []),
      ...(earlierInterventionSignal?.warnings ?? []),
      ...(recurringFailureCluster?.warnings ?? []),
      ...(recurrenceSeveritySignal?.warnings ?? []),
      ...(timeToExplain?.warnings ?? []),
      ...(debugReadinessSla?.warnings ?? []),
      ...(metricGamingDetection?.warnings ?? []),
      ...(misleadingSignalDetection?.warnings ?? []),
      ...(signalIntegrityCheck?.warnings ?? []),
      'Dashboard seed artifacts are minimal and partial; unknown coverage remains visible by design.',
    ],
  });

  const proofChain = minimalLoop?.proof_chain ?? [];
  const proofPresent = proofChain.filter((s) => s.status === 'present').length;
  const proofPartial = proofChain.filter((s) => s.status === 'partial').length;
  const proofTotal = proofChain.length;
  const artifactBackedSignalCount = allSlots.filter(
    (s) => s.loaded && (s.path.includes('dashboard_seed') || s.path.includes('dashboard_metrics'))
  ).length;
  const fallbackSignalCount = allSlots.filter((s) => !s.loaded).length;
  const unknownSignalCount = Math.max(0, proofTotal - proofPresent - proofPartial);

  // Bottleneck block — fail-closed: if the artifact is missing, expose unknown
  // and a derived_estimate fallback that names the constrained leg the seed
  // loop already shows is partial. No fake precision.
  const bottleneckBlock = bottleneck?.payload
    ? {
        dominant_bottleneck_system: bottleneck.payload.dominant_bottleneck_system ?? 'unknown',
        constrained_loop_leg: bottleneck.payload.constrained_loop_leg ?? 'unknown',
        supporting_evidence: bottleneck.payload.supporting_evidence ?? [],
        warning_counts_by_system: bottleneck.payload.warning_counts_by_system ?? {},
        block_counts_by_system: bottleneck.payload.block_counts_by_system ?? {},
        priority_rule: bottleneck.payload.bottleneck_priority_rule ?? null,
        confidence_rationale: bottleneck.payload.confidence_rationale ?? null,
        data_source: bottleneck.data_source ?? 'unknown',
        source_artifacts_used: bottleneck.source_artifacts_used ?? [],
        warnings: bottleneck.warnings ?? [],
      }
    : {
        dominant_bottleneck_system: 'unknown',
        constrained_loop_leg: 'unknown',
        supporting_evidence: [],
        warning_counts_by_system: {},
        block_counts_by_system: {},
        priority_rule: null,
        confidence_rationale: null,
        data_source: 'unknown',
        source_artifacts_used: [],
        warnings: [`${ARTIFACT_PATHS.bottleneck} unavailable; bottleneck reported as unknown.`],
      };

  const bottleneckConfidence: 'artifact_backed' | 'derived_estimate' | 'unknown' =
    bottleneck?.payload?.bottleneck_confidence === 'artifact_backed'
      ? 'artifact_backed'
      : bottleneck?.payload
      ? 'derived_estimate'
      : 'unknown';

  // Leverage queue block — never recommend without source, failure_prevented,
  // signal_improved, or a non-empty systems_affected array. The systems
  // check both enforces the contract rule and protects the render path
  // (which calls .join on the array) from partial-schema items.
  const filteredLeverage = (leverageQueue?.items ?? []).filter(
    (item) =>
      item.title &&
      item.failure_prevented &&
      item.signal_improved &&
      Array.isArray(item.source_artifacts_used) &&
      item.source_artifacts_used.length > 0 &&
      Array.isArray(item.systems_affected) &&
      item.systems_affected.length > 0
  );
  // Provenance is fail-closed: when the leverage artifact omits
  // data_source (partial write or schema drift), default to 'unknown'
  // rather than 'artifact_store' so the dashboard never overstates the
  // queue's sourcing.
  const leverageBlock = {
    items: filteredLeverage.sort((a, b) => b.leverage_score - a.leverage_score),
    formula: leverageQueue?.leverage_formula ?? null,
    data_source: leverageQueue?.data_source ?? 'unknown',
    source_artifacts_used: leverageQueue?.source_artifacts_used ?? [],
    warnings: leverageQueue
      ? leverageQueue.warnings ?? []
      : [`${ARTIFACT_PATHS.leverageQueue} unavailable; leverage queue reported as empty.`],
  };

  // Fail-closed counts: when a field is absent, never substitute 0 just
  // because the artifact wrapper exists. A partial-write or older-schema
  // artifact must surface 'unknown' so the dashboard cannot under-report
  // risk. Only when the entire risk_summary artifact is missing do we
  // fall back to the API-derived loader counts (which are themselves
  // artifact-backed and computed against the same slot list).
  const riskBlock = {
    fallback_signal_count:
      riskSummary?.payload?.fallback_signal_count ??
      (riskSummary ? 'unknown' : fallbackSignalCount),
    unknown_signal_count:
      riskSummary?.payload?.unknown_signal_count ??
      (riskSummary ? 'unknown' : unknownSignalCount),
    missing_eval_count: riskSummary?.payload?.missing_eval_count ?? 'unknown',
    missing_trace_count: riskSummary?.payload?.missing_trace_count ?? 'unknown',
    override_count: riskSummary?.payload?.override_count ?? 'unknown',
    proof_chain_coverage:
      riskSummary?.payload?.proof_chain_coverage ?? {
        total: proofTotal,
        present: proofPresent,
        partial: proofPartial,
        missing_or_unknown: unknownSignalCount,
        percent_present_or_partial:
          proofTotal > 0 ? Math.round(((proofPresent + proofPartial) / proofTotal) * 100) : 0,
      },
    top_risks: riskSummary?.payload?.top_risks ?? [],
    data_source: riskSummary?.data_source ?? 'unknown',
    source_artifacts_used: riskSummary?.source_artifacts_used ?? [],
    warnings: riskSummary
      ? riskSummary.warnings ?? []
      : [
          `${ARTIFACT_PATHS.riskSummary} unavailable; missing_eval_count and missing_trace_count reported as unknown to preserve fail-closed posture.`,
        ],
  };

  // MET-04 — feedback loop block. Fail-closed: if the artifact is missing,
  // expose 'unknown' counts and a missing-artifact warning rather than 0.
  const feedbackLoopBlock = feedbackLoopSnapshot
    ? {
        feedback_items_count: feedbackLoopSnapshot.feedback_items_count ?? 'unknown',
        eval_candidates_count: feedbackLoopSnapshot.eval_candidates_count ?? 'unknown',
        policy_candidate_signals_count:
          feedbackLoopSnapshot.policy_candidate_signals_count ?? 'unknown',
        unresolved_feedback_count:
          feedbackLoopSnapshot.unresolved_feedback_count ?? 'unknown',
        expired_feedback_count: feedbackLoopSnapshot.expired_feedback_count ?? 'unknown',
        top_feedback_themes: feedbackLoopSnapshot.top_feedback_themes ?? [],
        next_recommended_improvement_inputs:
          feedbackLoopSnapshot.next_recommended_improvement_inputs ?? [],
        loop_status: feedbackLoopSnapshot.loop_status ?? 'unknown',
        data_source: feedbackLoopSnapshot.data_source ?? 'unknown',
        source_artifacts_used: feedbackLoopSnapshot.source_artifacts_used ?? [],
        warnings: feedbackLoopSnapshot.warnings ?? [],
      }
    : {
        feedback_items_count: 'unknown',
        eval_candidates_count: 'unknown',
        policy_candidate_signals_count: 'unknown',
        unresolved_feedback_count: 'unknown',
        expired_feedback_count: 'unknown',
        top_feedback_themes: [],
        next_recommended_improvement_inputs: [],
        loop_status: 'unknown',
        data_source: 'unknown',
        source_artifacts_used: [],
        warnings: [
          `${ARTIFACT_PATHS.feedbackLoopSnapshot} unavailable; feedback loop reported as unknown.`,
        ],
      };

  // MET-04 — eval candidates block. Filter entries missing source/failure/signal
  // so the dashboard never renders an unsourced recommendation.
  const filteredEvalCandidates = (evalCandidates?.candidates ?? []).filter(
    (c) =>
      typeof c.title === 'string' &&
      typeof c.failure_prevented === 'string' &&
      typeof c.signal_improved === 'string' &&
      Array.isArray(c.source_artifacts_used) &&
      (c.source_artifacts_used as unknown[]).length > 0,
  );
  const evalCandidatesBlock = {
    candidates: filteredEvalCandidates,
    candidates_summary: evalCandidates?.candidates_summary ?? null,
    failure_prevented: evalCandidates?.failure_prevented ?? null,
    signal_improved: evalCandidates?.signal_improved ?? null,
    data_source: evalCandidates?.data_source ?? 'unknown',
    source_artifacts_used: evalCandidates?.source_artifacts_used ?? [],
    warnings: evalCandidates
      ? evalCandidates.warnings ?? []
      : [`${ARTIFACT_PATHS.evalCandidates} unavailable; eval candidates reported as empty.`],
  };

  // MET-04 — policy candidate signals block.
  const filteredPolicySignals = (policyCandidateSignals?.candidates ?? []).filter(
    (c) =>
      typeof c.title === 'string' &&
      typeof c.failure_prevented === 'string' &&
      typeof c.signal_improved === 'string' &&
      Array.isArray(c.source_artifacts_used) &&
      (c.source_artifacts_used as unknown[]).length > 0,
  );
  const policyCandidateSignalsBlock = {
    candidates: filteredPolicySignals,
    failure_prevented: policyCandidateSignals?.failure_prevented ?? null,
    signal_improved: policyCandidateSignals?.signal_improved ?? null,
    data_source: policyCandidateSignals?.data_source ?? 'unknown',
    source_artifacts_used: policyCandidateSignals?.source_artifacts_used ?? [],
    warnings: policyCandidateSignals
      ? policyCandidateSignals.warnings ?? []
      : [
          `${ARTIFACT_PATHS.policyCandidateSignals} unavailable; policy candidate signals reported as empty.`,
        ],
  };

  // MET-05 — failure explanation packets block.
  const filteredPackets = (failureExplanationPackets?.packets ?? []).filter(
    (p) =>
      typeof p.title === 'string' &&
      typeof p.failure_prevented === 'string' &&
      typeof p.signal_improved === 'string' &&
      Array.isArray(p.source_artifacts_used) &&
      (p.source_artifacts_used as unknown[]).length > 0,
  );
  const failureExplanationPacketsBlock = {
    packets: filteredPackets,
    failure_prevented: failureExplanationPackets?.failure_prevented ?? null,
    signal_improved: failureExplanationPackets?.signal_improved ?? null,
    data_source: failureExplanationPackets?.data_source ?? 'unknown',
    source_artifacts_used: failureExplanationPackets?.source_artifacts_used ?? [],
    warnings: failureExplanationPackets
      ? failureExplanationPackets.warnings ?? []
      : [
          `${ARTIFACT_PATHS.failureExplanationPackets} unavailable; failure explanation packets reported as empty.`,
        ],
  };

  // MET-06 — override audit block. override_count must remain 'unknown' when
  // the field is absent or the artifact is missing — never 0.
  const overrideAuditBlock = overrideAuditLog
    ? {
        override_count: overrideAuditLog.override_count ?? 'unknown',
        overrides: overrideAuditLog.overrides ?? [],
        next_recommended_input: overrideAuditLog.next_recommended_input ?? null,
        reason_codes: overrideAuditLog.reason_codes ?? [],
        failure_prevented: overrideAuditLog.failure_prevented ?? null,
        signal_improved: overrideAuditLog.signal_improved ?? null,
        data_source: overrideAuditLog.data_source ?? 'unknown',
        source_artifacts_used: overrideAuditLog.source_artifacts_used ?? [],
        warnings: overrideAuditLog.warnings ?? [],
      }
    : {
        override_count: 'unknown',
        overrides: [],
        next_recommended_input: null,
        reason_codes: ['override_history_missing'],
        failure_prevented: null,
        signal_improved: null,
        data_source: 'unknown',
        source_artifacts_used: [],
        warnings: [
          `${ARTIFACT_PATHS.overrideAuditLog} unavailable; override_count reported as unknown.`,
        ],
      };

  // MET-09 — eval materialization path block.
  const evalMaterializationPathBlock = evalMaterializationPath
    ? {
        path_id: evalMaterializationPath.path_id ?? 'unknown',
        source_eval_candidates: evalMaterializationPath.source_eval_candidates ?? [],
        owner_recommendation: evalMaterializationPath.owner_recommendation ?? 'unknown',
        required_authority_inputs:
          evalMaterializationPath.required_authority_inputs ?? [],
        required_artifacts_before_materialization:
          evalMaterializationPath.required_artifacts_before_materialization ?? [],
        required_tests: evalMaterializationPath.required_tests ?? [],
        materialization_status:
          evalMaterializationPath.materialization_status ?? 'unknown',
        next_recommended_input: evalMaterializationPath.next_recommended_input ?? null,
        failure_prevented: evalMaterializationPath.failure_prevented ?? null,
        signal_improved: evalMaterializationPath.signal_improved ?? null,
        data_source: evalMaterializationPath.data_source ?? 'unknown',
        source_artifacts_used: evalMaterializationPath.source_artifacts_used ?? [],
        warnings: evalMaterializationPath.warnings ?? [],
      }
    : {
        path_id: 'unknown',
        source_eval_candidates: [],
        owner_recommendation: 'unknown',
        required_authority_inputs: [],
        required_artifacts_before_materialization: [],
        required_tests: [],
        materialization_status: 'unknown',
        next_recommended_input: null,
        failure_prevented: null,
        signal_improved: null,
        data_source: 'unknown',
        source_artifacts_used: [],
        warnings: [
          `${ARTIFACT_PATHS.evalMaterializationPath} unavailable; materialization path reported as unknown.`,
        ],
      };

  // MET-10 — additional cases summary. Trend remains unknown unless at
  // least 3 comparable artifact-backed cases exist.
  const caseCount = (caseIndex?.cases ?? []).length;
  const additionalCasesSummaryBlock = {
    case_count: caseIndex ? caseCount : 'unknown',
    cases: caseIndex?.cases ?? [],
    trend: caseCount >= 3 ? 'comparable_set_present' : 'unknown',
    failure_prevented: caseIndex?.failure_prevented ?? null,
    signal_improved: caseIndex?.signal_improved ?? null,
    data_source: caseIndex?.data_source ?? 'unknown',
    source_artifacts_used: caseIndex?.source_artifacts_used ?? [],
    warnings: caseIndex
      ? caseIndex.warnings ?? []
      : [`${ARTIFACT_PATHS.caseIndex} unavailable; case index reported as unknown.`],
  };

  // MET-11 — replay/lineage hardening block.
  const replayLineageHardeningBlock = replayLineageHardening
    ? {
        replay_dimensions_checked:
          replayLineageHardening.replay_dimensions_checked ?? [],
        lineage_links_checked: replayLineageHardening.lineage_links_checked ?? [],
        gaps_observed: replayLineageHardening.gaps_observed ?? [],
        hardening_recommendations:
          replayLineageHardening.hardening_recommendations ?? [],
        affected_systems: replayLineageHardening.affected_systems ?? [],
        failure_prevented: replayLineageHardening.failure_prevented ?? null,
        signal_improved: replayLineageHardening.signal_improved ?? null,
        data_source: replayLineageHardening.data_source ?? 'unknown',
        source_artifacts_used: replayLineageHardening.source_artifacts_used ?? [],
        warnings: replayLineageHardening.warnings ?? [],
      }
    : {
        replay_dimensions_checked: [],
        lineage_links_checked: [],
        gaps_observed: [],
        hardening_recommendations: [],
        affected_systems: [],
        failure_prevented: null,
        signal_improved: null,
        data_source: 'unknown',
        source_artifacts_used: [],
        warnings: [
          `${ARTIFACT_PATHS.replayLineageHardening} unavailable; replay/lineage hardening reported as unknown.`,
        ],
      };

  // MET-12 — fallback reduction plan block.
  const filteredFallbackItems = (fallbackReductionPlan?.fallback_items ?? []).filter(
    (i) =>
      typeof i.system_id === 'string' &&
      typeof i.replacement_signal_needed === 'string' &&
      typeof i.failure_prevented === 'string' &&
      typeof i.signal_improved === 'string' &&
      Array.isArray(i.source_artifacts_used) &&
      (i.source_artifacts_used as unknown[]).length > 0,
  );
  const fallbackReductionPlanBlock = fallbackReductionPlan
    ? {
        total_fallback_count: fallbackReductionPlan.total_fallback_count ?? 'unknown',
        high_leverage_fallback_count:
          fallbackReductionPlan.high_leverage_fallback_count ?? 'unknown',
        fallback_items: filteredFallbackItems,
        failure_prevented: fallbackReductionPlan.failure_prevented ?? null,
        signal_improved: fallbackReductionPlan.signal_improved ?? null,
        data_source: fallbackReductionPlan.data_source ?? 'unknown',
        source_artifacts_used: fallbackReductionPlan.source_artifacts_used ?? [],
        warnings: fallbackReductionPlan.warnings ?? [],
      }
    : {
        total_fallback_count: 'unknown',
        high_leverage_fallback_count: 'unknown',
        fallback_items: [],
        failure_prevented: null,
        signal_improved: null,
        data_source: 'unknown',
        source_artifacts_used: [],
        warnings: [
          `${ARTIFACT_PATHS.fallbackReductionPlan} unavailable; fallback reduction plan reported as empty.`,
        ],
      };

  // MET-13 — SEL compliance signal input block.
  const selComplianceSignalInputBlock = selComplianceSignalInput
    ? {
        signal_input_id: selComplianceSignalInput.signal_input_id ?? 'unknown',
        suggested_owner_system:
          selComplianceSignalInput.suggested_owner_system ?? 'unknown',
        observed_gap: selComplianceSignalInput.observed_gap ?? null,
        compliance_signal_needed:
          selComplianceSignalInput.compliance_signal_needed ?? null,
        next_recommended_input:
          selComplianceSignalInput.next_recommended_input ?? null,
        status_label: selComplianceSignalInput.status_label ?? 'unknown',
        failure_prevented: selComplianceSignalInput.failure_prevented ?? null,
        signal_improved: selComplianceSignalInput.signal_improved ?? null,
        data_source: selComplianceSignalInput.data_source ?? 'unknown',
        source_artifacts_used:
          selComplianceSignalInput.source_artifacts_used ?? [],
        warnings: selComplianceSignalInput.warnings ?? [],
      }
    : {
        signal_input_id: 'unknown',
        suggested_owner_system: 'unknown',
        observed_gap: null,
        compliance_signal_needed: null,
        next_recommended_input: null,
        status_label: 'unknown',
        failure_prevented: null,
        signal_improved: null,
        data_source: 'unknown',
        source_artifacts_used: [],
        warnings: [
          `${ARTIFACT_PATHS.selComplianceSignalInput} unavailable; SEL compliance signal input reported as unknown.`,
        ],
      };

  // MET-19 — candidate closure ledger block. Fail-closed: missing artifact
  // degrades to unknown counts and an explicit warning rather than 0 items.
  const filteredCandidateItems = (candidateClosureLedger?.candidate_items ?? []).filter(
    (i) =>
      typeof i.candidate_id === 'string' &&
      typeof i.candidate_type === 'string' &&
      typeof i.current_state === 'string' &&
      Array.isArray(i.source_artifacts_used) &&
      (i.source_artifacts_used as unknown[]).length > 0,
  );
  const candidateClosureBlock = candidateClosureLedger
    ? {
        candidate_items: filteredCandidateItems,
        candidate_item_count: filteredCandidateItems.length,
        stale_candidate_signal_count: filteredCandidateItems.filter(
          (i) => i.current_state === 'stale_candidate_signal',
        ).length,
        failure_prevented: candidateClosureLedger.failure_prevented ?? null,
        signal_improved: candidateClosureLedger.signal_improved ?? null,
        data_source: candidateClosureLedger.data_source ?? 'unknown',
        source_artifacts_used: candidateClosureLedger.source_artifacts_used ?? [],
        warnings: candidateClosureLedger.warnings ?? [],
      }
    : {
        candidate_items: [],
        candidate_item_count: 'unknown',
        stale_candidate_signal_count: 'unknown',
        failure_prevented: null,
        signal_improved: null,
        data_source: 'unknown',
        source_artifacts_used: [],
        warnings: [
          `${ARTIFACT_PATHS.candidateClosureLedger} unavailable; candidate closure ledger reported as unknown.`,
        ],
      };

  // MET-20 — MET artifact dependency index block.
  const metArtifactDependencyIndexBlock = metArtifactDependencyIndex
    ? {
        artifact_dependencies: metArtifactDependencyIndex.artifact_dependencies ?? [],
        failure_prevented: metArtifactDependencyIndex.failure_prevented ?? null,
        signal_improved: metArtifactDependencyIndex.signal_improved ?? null,
        data_source: metArtifactDependencyIndex.data_source ?? 'unknown',
        source_artifacts_used: metArtifactDependencyIndex.source_artifacts_used ?? [],
        warnings: metArtifactDependencyIndex.warnings ?? [],
      }
    : {
        artifact_dependencies: [],
        failure_prevented: null,
        signal_improved: null,
        data_source: 'unknown',
        source_artifacts_used: [],
        warnings: [
          `${ARTIFACT_PATHS.metArtifactDependencyIndex} unavailable; dependency index reported as unknown.`,
        ],
      };

  // MET-22 — trend/frequency honesty gate. trend_state and frequency_state
  // remain 'unknown' until the comparable_case threshold is met.
  const trendFrequencyHonestyGateBlock = trendFrequencyHonestyGate
    ? {
        comparable_case_count:
          trendFrequencyHonestyGate.comparable_case_count ?? 'unknown',
        required_case_count_for_trend:
          trendFrequencyHonestyGate.required_case_count_for_trend ?? 3,
        trend_state: trendFrequencyHonestyGate.trend_state ?? 'unknown',
        frequency_state: trendFrequencyHonestyGate.frequency_state ?? 'unknown',
        cases_needed: trendFrequencyHonestyGate.cases_needed ?? 'unknown',
        comparable_cases: trendFrequencyHonestyGate.comparable_cases ?? [],
        blocked_trend_fields: trendFrequencyHonestyGate.blocked_trend_fields ?? [],
        shape_breakdown: trendFrequencyHonestyGate.shape_breakdown ?? [],
        failure_prevented: trendFrequencyHonestyGate.failure_prevented ?? null,
        signal_improved: trendFrequencyHonestyGate.signal_improved ?? null,
        data_source: trendFrequencyHonestyGate.data_source ?? 'unknown',
        source_artifacts_used: trendFrequencyHonestyGate.source_artifacts_used ?? [],
        warnings: trendFrequencyHonestyGate.warnings ?? [],
      }
    : {
        comparable_case_count: 'unknown',
        required_case_count_for_trend: 3,
        trend_state: 'unknown',
        frequency_state: 'unknown',
        cases_needed: 'unknown',
        comparable_cases: [],
        blocked_trend_fields: [],
        shape_breakdown: [],
        failure_prevented: null,
        signal_improved: null,
        data_source: 'unknown',
        source_artifacts_used: [],
        warnings: [
          `${ARTIFACT_PATHS.trendFrequencyHonestyGate} unavailable; trend/frequency honesty gate reported as unknown.`,
        ],
      };

  // MET-23 — EVL handoff observation tracker block.
  const filteredHandoffItems = (evlHandoffObservationTracker?.handoff_items ?? []).filter(
    (i) =>
      typeof i.handoff_signal_id === 'string' &&
      typeof i.source_eval_candidate_id === 'string' &&
      Array.isArray(i.source_artifacts_used) &&
      (i.source_artifacts_used as unknown[]).length > 0,
  );
  const evlHandoffObservationsBlock = evlHandoffObservationTracker
    ? {
        handoff_items: filteredHandoffItems,
        handoff_item_count: filteredHandoffItems.length,
        failure_prevented: evlHandoffObservationTracker.failure_prevented ?? null,
        signal_improved: evlHandoffObservationTracker.signal_improved ?? null,
        data_source: evlHandoffObservationTracker.data_source ?? 'unknown',
        source_artifacts_used: evlHandoffObservationTracker.source_artifacts_used ?? [],
        warnings: evlHandoffObservationTracker.warnings ?? [],
      }
    : {
        handoff_items: [],
        handoff_item_count: 'unknown',
        failure_prevented: null,
        signal_improved: null,
        data_source: 'unknown',
        source_artifacts_used: [],
        warnings: [
          `${ARTIFACT_PATHS.evlHandoffObservationTracker} unavailable; EVL handoff observations reported as unknown.`,
        ],
      };

  // MET-24 — override evidence intake block. override_evidence_count must
  // remain 'unknown' when no canonical override log exists; never 0.
  const overrideEvidenceIntakeBlock = overrideEvidenceIntake
    ? {
        override_evidence_count: overrideEvidenceIntake.override_evidence_count ?? 'unknown',
        override_evidence_items: overrideEvidenceIntake.override_evidence_items ?? [],
        evidence_status: overrideEvidenceIntake.evidence_status ?? 'unknown',
        next_recommended_input: overrideEvidenceIntake.next_recommended_input ?? null,
        reason_codes: overrideEvidenceIntake.reason_codes ?? [],
        intake_shape_recommendation:
          overrideEvidenceIntake.intake_shape_recommendation ?? null,
        failure_prevented: overrideEvidenceIntake.failure_prevented ?? null,
        signal_improved: overrideEvidenceIntake.signal_improved ?? null,
        data_source: overrideEvidenceIntake.data_source ?? 'unknown',
        source_artifacts_used: overrideEvidenceIntake.source_artifacts_used ?? [],
        warnings: overrideEvidenceIntake.warnings ?? [],
      }
    : {
        override_evidence_count: 'unknown',
        override_evidence_items: [],
        evidence_status: 'absent',
        next_recommended_input: null,
        reason_codes: ['override_evidence_missing'],
        intake_shape_recommendation: null,
        failure_prevented: null,
        signal_improved: null,
        data_source: 'unknown',
        source_artifacts_used: [],
        warnings: [
          `${ARTIFACT_PATHS.overrideEvidenceIntake} unavailable; override_evidence_count reported as unknown.`,
        ],
      };

  // MET-25 — debug explanation index block.
  const filteredExplanationEntries = (
    debugExplanationIndex?.explanation_entries ?? []
  ).filter(
    (e) =>
      typeof e.explanation_id === 'string' &&
      typeof e.what_failed === 'string' &&
      typeof e.next_recommended_input === 'string' &&
      Array.isArray(e.source_evidence) &&
      (e.source_evidence as unknown[]).length > 0,
  );
  const debugExplanationIndexBlock = debugExplanationIndex
    ? {
        debug_target_minutes: debugExplanationIndex.debug_target_minutes ?? 15,
        explanation_entries: filteredExplanationEntries,
        explanation_entry_count: filteredExplanationEntries.length,
        failure_prevented: debugExplanationIndex.failure_prevented ?? null,
        signal_improved: debugExplanationIndex.signal_improved ?? null,
        data_source: debugExplanationIndex.data_source ?? 'unknown',
        source_artifacts_used: debugExplanationIndex.source_artifacts_used ?? [],
        warnings: debugExplanationIndex.warnings ?? [],
      }
    : {
        debug_target_minutes: 15,
        explanation_entries: [],
        explanation_entry_count: 'unknown',
        failure_prevented: null,
        signal_improved: null,
        data_source: 'unknown',
        source_artifacts_used: [],
        warnings: [
          `${ARTIFACT_PATHS.debugExplanationIndex} unavailable; debug explanation index reported as unknown.`,
        ],
      };

  // MET-26 — generated artifact classification block.
  const metGeneratedArtifactClassificationBlock = metGeneratedArtifactClassification
    ? {
        classified_paths: metGeneratedArtifactClassification.classified_paths ?? [],
        classified_path_count:
          (metGeneratedArtifactClassification.classified_paths ?? []).length,
        failure_prevented: metGeneratedArtifactClassification.failure_prevented ?? null,
        signal_improved: metGeneratedArtifactClassification.signal_improved ?? null,
        data_source: metGeneratedArtifactClassification.data_source ?? 'unknown',
        source_artifacts_used:
          metGeneratedArtifactClassification.source_artifacts_used ?? [],
        warnings: metGeneratedArtifactClassification.warnings ?? [],
      }
    : {
        classified_paths: [],
        classified_path_count: 'unknown',
        failure_prevented: null,
        signal_improved: null,
        data_source: 'unknown',
        source_artifacts_used: [],
        warnings: [
          `${ARTIFACT_PATHS.metGeneratedArtifactClassification} unavailable; classification reported as unknown.`,
        ],
      };


  // MET-34-41 — owner-read/materialization/trend/fold/debug/policy handoff.
  const ownerReadObservationsBlock = ownerReadObservationLedger
    ? {
        owner_read_items: ownerReadObservationLedger.owner_read_items ?? [],
        data_source: ownerReadObservationLedger.data_source ?? 'unknown',
        source_artifacts_used: ownerReadObservationLedger.source_artifacts_used ?? [],
        warnings: ownerReadObservationLedger.warnings ?? [],
      }
    : {
        owner_read_items: [],
        data_source: 'unknown',
        source_artifacts_used: [],
        warnings: [`${ARTIFACT_PATHS.ownerReadObservationLedger} unavailable; owner read observations reported as unknown.`],
      };

  const materializationObservationMapperBlock = materializationObservationMapper
    ? {
        materialization_observations:
          materializationObservationMapper.materialization_observations ?? [],
        data_source: materializationObservationMapper.data_source ?? 'unknown',
        source_artifacts_used: materializationObservationMapper.source_artifacts_used ?? [],
        warnings: materializationObservationMapper.warnings ?? [],
      }
    : {
        materialization_observations: [],
        data_source: 'unknown',
        source_artifacts_used: [],
        warnings: [`${ARTIFACT_PATHS.materializationObservationMapper} unavailable; materialization observations reported as unknown.`],
      };

  const comparableCaseQualificationGateBlock = comparableCaseQualificationGate
    ? {
        qualification_rules: comparableCaseQualificationGate.qualification_rules ?? null,
        qualified_case_groups: comparableCaseQualificationGate.qualified_case_groups ?? [],
        data_source: comparableCaseQualificationGate.data_source ?? 'unknown',
        source_artifacts_used: comparableCaseQualificationGate.source_artifacts_used ?? [],
        warnings: comparableCaseQualificationGate.warnings ?? [],
      }
    : {
        qualification_rules: null,
        qualified_case_groups: [],
        data_source: 'unknown',
        source_artifacts_used: [],
        warnings: [`${ARTIFACT_PATHS.comparableCaseQualificationGate} unavailable; comparable-case gate reported as unknown.`],
      };

  const trendReadyCasePackBlock = trendReadyCasePack
    ? {
        case_packs: trendReadyCasePack.case_packs ?? [],
        data_source: trendReadyCasePack.data_source ?? 'unknown',
        source_artifacts_used: trendReadyCasePack.source_artifacts_used ?? [],
        warnings: trendReadyCasePack.warnings ?? [],
      }
    : {
        case_packs: [],
        data_source: 'unknown',
        source_artifacts_used: [],
        warnings: [`${ARTIFACT_PATHS.trendReadyCasePack} unavailable; trend-ready case pack reported as unknown.`],
      };

  const overrideEvidenceSourceAdapterBlock = overrideEvidenceSourceAdapter
    ? {
        override_source_state: overrideEvidenceSourceAdapter.override_source_state ?? 'unknown',
        override_evidence_count: overrideEvidenceSourceAdapter.override_evidence_count ?? 'unknown',
        override_evidence_refs: overrideEvidenceSourceAdapter.override_evidence_refs ?? [],
        next_recommended_input: overrideEvidenceSourceAdapter.next_recommended_input ?? null,
        data_source: overrideEvidenceSourceAdapter.data_source ?? 'unknown',
        source_artifacts_used: overrideEvidenceSourceAdapter.source_artifacts_used ?? [],
        warnings: overrideEvidenceSourceAdapter.warnings ?? [],
      }
    : {
        override_source_state: 'unknown',
        override_evidence_count: 'unknown',
        override_evidence_refs: [],
        next_recommended_input: null,
        data_source: 'unknown',
        source_artifacts_used: [],
        warnings: [`${ARTIFACT_PATHS.overrideEvidenceSourceAdapter} unavailable; override evidence source state reported as unknown.`],
      };

  const foldCandidateProofCheckBlock = foldCandidateProofCheck
    ? {
        fold_candidates: foldCandidateProofCheck.fold_candidates ?? [],
        data_source: foldCandidateProofCheck.data_source ?? 'unknown',
        source_artifacts_used: foldCandidateProofCheck.source_artifacts_used ?? [],
        warnings: foldCandidateProofCheck.warnings ?? [],
      }
    : {
        fold_candidates: [],
        data_source: 'unknown',
        source_artifacts_used: [],
        warnings: [`${ARTIFACT_PATHS.foldCandidateProofCheck} unavailable; fold candidate proof check reported as unknown.`],
      };

  const operatorDebuggabilityDrillBlock = operatorDebuggabilityDrill
    ? {
        target_minutes: operatorDebuggabilityDrill.target_minutes ?? 15,
        drill_items: operatorDebuggabilityDrill.drill_items ?? [],
        data_source: operatorDebuggabilityDrill.data_source ?? 'unknown',
        source_artifacts_used: operatorDebuggabilityDrill.source_artifacts_used ?? [],
        warnings: operatorDebuggabilityDrill.warnings ?? [],
      }
    : {
        target_minutes: 15,
        drill_items: [],
        data_source: 'unknown',
        source_artifacts_used: [],
        warnings: [`${ARTIFACT_PATHS.operatorDebuggabilityDrill} unavailable; operator debuggability drill reported as unknown.`],
      };

  const generatedArtifactPolicyHandoffBlock = generatedArtifactPolicyHandoff
    ? {
        central_policy_path: generatedArtifactPolicyHandoff.central_policy_path ?? 'unknown',
        central_policy_state: generatedArtifactPolicyHandoff.central_policy_state ?? 'unknown',
        policy_alignment_items: generatedArtifactPolicyHandoff.policy_alignment_items ?? [],
        data_source: generatedArtifactPolicyHandoff.data_source ?? 'unknown',
        source_artifacts_used: generatedArtifactPolicyHandoff.source_artifacts_used ?? [],
        warnings: generatedArtifactPolicyHandoff.warnings ?? [],
      }
    : {
        central_policy_path: 'unknown',
        central_policy_state: 'unknown',
        policy_alignment_items: [],
        data_source: 'unknown',
        source_artifacts_used: [],
        warnings: [`${ARTIFACT_PATHS.generatedArtifactPolicyHandoff} unavailable; generated-artifact policy handoff reported as unknown.`],
      };

  // MET-FULL-ROADMAP — generic builder. Each block degrades to 'unknown'/empty
  // arrays when the artifact is missing and never substitutes 0 for unknown.
  function metBlock(
    artifact: (GenericMetEnvelope & Record<string, unknown>) | null,
    artifactPath: string,
    extraDefaults: Record<string, unknown>,
  ): Record<string, unknown> {
    if (artifact) {
      return {
        ...extraDefaults,
        ...(artifact as Record<string, unknown>),
        data_source: artifact.data_source ?? 'unknown',
        source_artifacts_used: artifact.source_artifacts_used ?? [],
        warnings: artifact.warnings ?? [],
      };
    }
    return {
      ...extraDefaults,
      data_source: 'unknown',
      source_artifacts_used: [],
      warnings: [`${artifactPath} unavailable; block reported as unknown.`],
      status: 'unknown',
    };
  }

  const staleCandidatePressureBlock = metBlock(staleCandidatePressure, ARTIFACT_PATHS.staleCandidatePressure, {
    pressure_summary: {} as Record<string, unknown>,
    pressure_by_loop_leg: [] as Array<Record<string, unknown>>,
  });
  const outcomeAttributionBlock = metBlock(outcomeAttribution, ARTIFACT_PATHS.outcomeAttribution, {
    outcome_entries: [] as Array<Record<string, unknown>>,
  });
  const failureReductionSignalBlock = metBlock(failureReductionSignal, ARTIFACT_PATHS.failureReductionSignal, {
    failure_reduction_signals: [] as Array<Record<string, unknown>>,
  });
  const recommendationAccuracyBlock = metBlock(recommendationAccuracy, ARTIFACT_PATHS.recommendationAccuracy, {
    recommendation_entries: [] as Array<Record<string, unknown>>,
  });
  const calibrationDriftBlock = metBlock(calibrationDrift, ARTIFACT_PATHS.calibrationDrift, {
    calibration_buckets: [] as Array<Record<string, unknown>>,
  });
  const signalConfidenceBlock = metBlock(signalConfidence, ARTIFACT_PATHS.signalConfidence, {
    signal_entries: [] as Array<Record<string, unknown>>,
  });
  const crossRunConsistencyBlock = metBlock(crossRunConsistency, ARTIFACT_PATHS.crossRunConsistency, {
    consistency_entries: [] as Array<Record<string, unknown>>,
  });
  const divergenceDetectionBlock = metBlock(divergenceDetection, ARTIFACT_PATHS.divergenceDetection, {
    divergence_entries: [] as Array<Record<string, unknown>>,
  });
  const metErrorBudgetObservationBlock = metBlock(metErrorBudgetObservation, ARTIFACT_PATHS.metErrorBudgetObservation, {
    budget_observations: [] as Array<Record<string, unknown>>,
  });
  const metFreezeRecommendationSignalBlock = metBlock(metFreezeRecommendationSignal, ARTIFACT_PATHS.metFreezeRecommendationSignal, {
    recommendation_signals: [] as Array<Record<string, unknown>>,
  });
  const nextBestSliceRecommendationBlock = metBlock(nextBestSliceRecommendation, ARTIFACT_PATHS.nextBestSliceRecommendation, {
    slice_candidates: [] as Array<Record<string, unknown>>,
  });
  const pqxCandidateActionBundleBlock = metBlock(pqxCandidateActionBundle, ARTIFACT_PATHS.pqxCandidateActionBundle, {
    bundle_candidates: [] as Array<Record<string, unknown>>,
  });
  const counterfactualReconstructionBlock = metBlock(counterfactualReconstruction, ARTIFACT_PATHS.counterfactualReconstruction, {
    counterfactual_entries: [] as Array<Record<string, unknown>>,
  });
  const earlierInterventionSignalBlock = metBlock(earlierInterventionSignal, ARTIFACT_PATHS.earlierInterventionSignal, {
    intervention_signals: [] as Array<Record<string, unknown>>,
  });
  const recurringFailureClusterBlock = metBlock(recurringFailureCluster, ARTIFACT_PATHS.recurringFailureCluster, {
    clusters: [] as Array<Record<string, unknown>>,
  });
  const recurrenceSeveritySignalBlock = metBlock(recurrenceSeveritySignal, ARTIFACT_PATHS.recurrenceSeveritySignal, {
    severity_signals: [] as Array<Record<string, unknown>>,
  });
  const timeToExplainBlock = metBlock(timeToExplain, ARTIFACT_PATHS.timeToExplain, {
    time_to_explain_entries: [] as Array<Record<string, unknown>>,
  });
  const debugReadinessSlaBlock = metBlock(debugReadinessSla, ARTIFACT_PATHS.debugReadinessSla, {
    readiness_entries: [] as Array<Record<string, unknown>>,
  });
  const metricGamingDetectionBlock = metBlock(metricGamingDetection, ARTIFACT_PATHS.metricGamingDetection, {
    gaming_observations: [] as Array<Record<string, unknown>>,
  });
  const misleadingSignalDetectionBlock = metBlock(misleadingSignalDetection, ARTIFACT_PATHS.misleadingSignalDetection, {
    misleading_signal_observations: [] as Array<Record<string, unknown>>,
  });
  const signalIntegrityCheckBlock = metBlock(signalIntegrityCheck, ARTIFACT_PATHS.signalIntegrityCheck, {
    integrity_summary: {} as Record<string, unknown>,
    integrity_checks: [] as Array<Record<string, unknown>>,
  });

  // MET-FULL-ROADMAP — registry status block. Sourced from system_registry.md.
  // Authority must remain NONE; if MET produces an authority outcome, block.
  const metRegistryStatusBlock = {
    registry_id: 'MET',
    status: 'active_non_owning',
    authority: 'NONE',
    forbidden: [
      'decision_ownership',
      'approval_ownership',
      'enforcement_ownership',
      'certification_ownership',
      'promotion_ownership',
      'execution_ownership',
      'admission_ownership',
    ],
    invariant: 'if_met_produces_authority_outcome_block',
    failure_prevented: [
      'undetected_bottlenecks',
      'unclear_failure_causes',
      'stale_candidates',
      'fake_trends',
      'unverified_improvements',
      'overconfident_recommendations',
      'recurring_failures',
      'metric_gaming',
    ],
    signal_improved: [
      'debuggability',
      'bottleneck_clarity',
      'closure_visibility',
      'outcome_attribution',
      'recommendation_calibration',
      'signal_integrity',
    ],
    upstream_dependencies: ['EVL', 'LIN', 'REP', 'OBS', 'SLO', 'TPA', 'CDE', 'SEL'],
    downstream_consumers: ['AEX', 'PQX', 'EVL', 'TPA', 'CDE', 'SEL', 'GOV', 'dashboard-3ls'],
    data_source: 'artifact_store',
    source_artifacts_used: ['docs/architecture/system_registry.md'],
    warnings: [],
  };

  // MET-FULL-ROADMAP — Top 3 next inputs aggregated from MET signals (observation only).
  const topNextInputsBlock = {
    items: (nextBestSliceRecommendation?.slice_candidates ?? []).slice(0, 3).map((slice) => ({
      slice_candidate_id: slice.slice_candidate_id,
      affected_systems: slice.affected_systems ?? [],
      recommended_owner_system: slice.recommended_owner_system ?? 'unknown',
      readiness_state: slice.readiness_state ?? 'unknown',
      next_recommended_input: slice.scope_boundary ?? null,
      source_artifacts_used: slice.source_artifacts_used ?? [],
    })),
    data_source: nextBestSliceRecommendation?.data_source ?? 'unknown',
    source_artifacts_used: nextBestSliceRecommendation?.source_artifacts_used ?? [],
    warnings: nextBestSliceRecommendation?.warnings ?? [
      `${ARTIFACT_PATHS.nextBestSliceRecommendation} unavailable; top next inputs reported as unknown.`,
    ],
    status: nextBestSliceRecommendation ? 'warn' : 'unknown',
  };

  // MET-FULL-ROADMAP — owner handoff queue surfaces stale/none_observed/unknown
  // owner read items; canonical owners adjudicate.
  const ownerHandoffQueueBlock = {
    items: (ownerReadObservationLedger?.owner_read_items ?? [])
      .filter((item) => {
        const state = String(item.read_observation_state ?? '');
        return state === 'stale_candidate_signal' || state === 'none_observed' || state === 'unknown';
      })
      .slice(0, 5)
      .map((item) => ({
        owner_read_observation_id: item.owner_read_observation_id,
        source_candidate_id: item.source_candidate_id,
        recommended_owner_system: item.recommended_owner_system ?? 'unknown',
        read_observation_state: item.read_observation_state ?? 'unknown',
        next_recommended_input: item.next_recommended_input ?? null,
        source_artifacts_used: item.source_artifacts_used ?? [],
      })),
    data_source: ownerReadObservationLedger?.data_source ?? 'unknown',
    source_artifacts_used: ownerReadObservationLedger?.source_artifacts_used ?? [],
    warnings: ownerReadObservationLedger?.warnings ?? [
      `${ARTIFACT_PATHS.ownerReadObservationLedger} unavailable; owner handoff queue reported as unknown.`,
    ],
    status: ownerReadObservationLedger ? 'warn' : 'unknown',
  };

  // MET-FULL-ROADMAP — overall MET cockpit summary card.
  // Counts and aggregate states are derived from artifact content; missing
  // artifacts surface as 'unknown' rather than 0 / 'insufficient_cases'.
  const topNextInputCount: number | 'unknown' = nextBestSliceRecommendation
    ? topNextInputsBlock.items.length
    : 'unknown';
  const ownerHandoffQueueCount: number | 'unknown' = ownerReadObservationLedger
    ? ownerHandoffQueueBlock.items.length
    : 'unknown';

  // Aggregate calibration drift across buckets. Surface the strongest observed
  // state (drifting > stable > insufficient_cases > unknown) so the cockpit
  // moves with artifact content, not file presence.
  function aggregateState(
    states: Array<string | undefined>,
    rank: Record<string, number>,
    fallback: string,
  ): string {
    let best: string | null = null;
    let bestRank = -Infinity;
    for (const raw of states) {
      const s = (raw ?? '').toString();
      if (!(s in rank)) continue;
      if (rank[s] > bestRank) {
        bestRank = rank[s];
        best = s;
      }
    }
    return best ?? fallback;
  }

  const calibrationBucketStates = (
    (calibrationDrift?.calibration_buckets as Array<Record<string, unknown>> | undefined) ?? []
  ).map((b) => (b.drift_state as string | undefined));
  const confidenceCalibrationState: string = calibrationDrift
    ? aggregateState(
        calibrationBucketStates,
        {
          unknown: 0,
          insufficient_cases: 1,
          stable: 2,
          drifting: 3,
        },
        'unknown',
      )
    : 'unknown';

  const recurrenceClusterStates = (
    (recurringFailureCluster?.clusters as Array<Record<string, unknown>> | undefined) ?? []
  ).map((c) => (c.recurrence_state as string | undefined));
  const recurrenceState: string = recurringFailureCluster
    ? aggregateState(
        recurrenceClusterStates,
        {
          unknown: 0,
          insufficient_cases: 1,
          observed: 2,
          recurring: 3,
        },
        'unknown',
      )
    : 'unknown';

  // Outcome attribution aggregate: surface the strongest observed status.
  const outcomeStatuses = (
    (outcomeAttributionBlock.outcome_entries as Array<Record<string, unknown>>) ?? []
  ).map((e) => (e.status as string | undefined));
  const outcomeAttributionState: string = outcomeAttribution
    ? aggregateState(
        outcomeStatuses,
        {
          unknown: 0,
          insufficient_evidence: 1,
          partial: 2,
          observed: 3,
        },
        'unknown',
      )
    : 'unknown';

  // Debug readiness aggregate: surface the strongest observed readiness.
  const debugReadinessStates = (
    (debugReadinessSlaBlock.readiness_entries as Array<Record<string, unknown>>) ?? []
  ).map((e) => (e.readiness_state as string | undefined));
  const debugReadinessState: string = debugReadinessSla
    ? aggregateState(
        debugReadinessStates,
        {
          unknown: 0,
          insufficient: 1,
          partial: 2,
          sufficient: 3,
        },
        'unknown',
      )
    : 'unknown';

  const metCockpitBlock = {
    trust_observation: 'see_trust_pulse',
    weakest_loop_leg: bottleneck?.payload?.constrained_loop_leg ?? 'unknown',
    top_next_input_count: topNextInputCount,
    owner_handoff_queue_count: ownerHandoffQueueCount,
    stale_candidate_pressure_state:
      (staleCandidatePressureBlock as { pressure_summary?: Record<string, unknown> }).pressure_summary?.stale_count ?? 'unknown',
    trend_readiness_state:
      trendFrequencyHonestyGate?.trend_state ?? 'unknown',
    debug_readiness_state: debugReadinessState,
    artifact_integrity_state:
      (signalIntegrityCheckBlock as { integrity_summary?: { overall_integrity_state?: string } }).integrity_summary?.overall_integrity_state ?? 'unknown',
    outcome_attribution_state: outcomeAttributionState,
    confidence_calibration_state: confidenceCalibrationState,
    recurrence_state: recurrenceState,
    anti_gaming_state:
      (signalIntegrityCheckBlock as { integrity_summary?: { overall_integrity_state?: string } }).integrity_summary?.overall_integrity_state ?? 'unknown',
    data_source: 'artifact_store',
    source_artifacts_used: [
      ARTIFACT_PATHS.nextBestSliceRecommendation,
      ARTIFACT_PATHS.ownerReadObservationLedger,
      ARTIFACT_PATHS.staleCandidatePressure,
      ARTIFACT_PATHS.signalIntegrityCheck,
      ARTIFACT_PATHS.outcomeAttribution,
      ARTIFACT_PATHS.calibrationDrift,
      ARTIFACT_PATHS.recurringFailureCluster,
      ARTIFACT_PATHS.debugReadinessSla,
    ],
    warnings: [
      'MET cockpit values are observations only; CDE/SEL/GOV remain canonical owners.',
    ],
    status: 'warn',
  };

  // MET-04 — feedback items list (filter to sourced items only).
  const feedbackItems = (failureFeedback?.feedback_items ?? []).filter(
    (i) =>
      typeof i.id === 'string' &&
      typeof i.failure_prevented === 'string' &&
      typeof i.signal_improved === 'string' &&
      Array.isArray(i.source_artifacts_used) &&
      (i.source_artifacts_used as unknown[]).length > 0,
  );
  const unresolvedFeedbackCount =
    feedbackLoopSnapshot?.unresolved_feedback_count ??
    (failureFeedback ? feedbackItems.length : 'unknown');
  const feedbackLoopStatus = feedbackLoopSnapshot?.loop_status ?? 'unknown';

  return NextResponse.json({
    ...envelope,
    seed_artifacts_present: minimalLoop !== null,
    proof_chain_coverage: {
      total: proofTotal,
      present: proofPresent,
      partial: proofPartial,
      missing_or_unknown: unknownSignalCount,
      percent_present_or_partial:
        proofTotal > 0 ? Math.round(((proofPresent + proofPartial) / proofTotal) * 100) : 0,
    },
    artifact_backed_signal_count: artifactBackedSignalCount,
    fallback_signal_count: fallbackSignalCount,
    unknown_signal_count: unknownSignalCount,
    failure_modes: failureModes?.failure_modes ?? [],
    near_misses: nearMisses?.near_misses ?? [],
    minimal_loop_status: minimalLoop?.minimal_loop_status ?? 'unknown',
    bottleneck: bottleneckBlock,
    bottleneck_confidence: bottleneckConfidence,
    leverage_queue: leverageBlock,
    risk_summary: riskBlock,
    feedback_loop: feedbackLoopBlock,
    feedback_items: feedbackItems,
    eval_candidates: evalCandidatesBlock,
    policy_candidate_signals: policyCandidateSignalsBlock,
    feedback_loop_status: feedbackLoopStatus,
    unresolved_feedback_count: unresolvedFeedbackCount,
    failure_explanation_packets: failureExplanationPacketsBlock,
    override_audit: overrideAuditBlock,
    eval_materialization_path: evalMaterializationPathBlock,
    additional_cases_summary: additionalCasesSummaryBlock,
    replay_lineage_hardening: replayLineageHardeningBlock,
    fallback_reduction_plan: fallbackReductionPlanBlock,
    sel_compliance_signal_input: selComplianceSignalInputBlock,
    candidate_closure: candidateClosureBlock,
    met_artifact_dependency_index: metArtifactDependencyIndexBlock,
    trend_frequency_honesty_gate: trendFrequencyHonestyGateBlock,
    evl_handoff_observations: evlHandoffObservationsBlock,
    override_evidence_intake: overrideEvidenceIntakeBlock,
    debug_explanation_index: debugExplanationIndexBlock,
    met_generated_artifact_classification: metGeneratedArtifactClassificationBlock,
    owner_read_observations: ownerReadObservationsBlock,
    materialization_observation_mapper: materializationObservationMapperBlock,
    comparable_case_qualification_gate: comparableCaseQualificationGateBlock,
    trend_ready_case_pack: trendReadyCasePackBlock,
    override_evidence_source_adapter: overrideEvidenceSourceAdapterBlock,
    fold_candidate_proof_check: foldCandidateProofCheckBlock,
    operator_debuggability_drill: operatorDebuggabilityDrillBlock,
    generated_artifact_policy_handoff: generatedArtifactPolicyHandoffBlock,
    met_registry_status: metRegistryStatusBlock,
    met_cockpit: metCockpitBlock,
    top_next_inputs: topNextInputsBlock,
    owner_handoff: ownerHandoffQueueBlock,
    stale_candidate_pressure: staleCandidatePressureBlock,
    trend_readiness: trendReadyCasePackBlock,
    override_evidence: overrideEvidenceSourceAdapterBlock,
    fold_safety: foldCandidateProofCheckBlock,
    outcome_attribution: outcomeAttributionBlock,
    failure_reduction_signal: failureReductionSignalBlock,
    recommendation_accuracy: recommendationAccuracyBlock,
    calibration_drift: calibrationDriftBlock,
    signal_confidence: signalConfidenceBlock,
    cross_run_consistency: crossRunConsistencyBlock,
    divergence_detection: divergenceDetectionBlock,
    error_budget_observation: metErrorBudgetObservationBlock,
    freeze_recommendation_signal: metFreezeRecommendationSignalBlock,
    next_best_slice: nextBestSliceRecommendationBlock,
    pqx_candidate_action_bundle: pqxCandidateActionBundleBlock,
    counterfactuals: counterfactualReconstructionBlock,
    earlier_intervention_signal: earlierInterventionSignalBlock,
    recurring_failures: recurringFailureClusterBlock,
    recurrence_severity_signal: recurrenceSeveritySignalBlock,
    debug_readiness: debugReadinessSlaBlock,
    time_to_explain: timeToExplainBlock,
    metric_gaming_detection: metricGamingDetectionBlock,
    misleading_signal_detection: misleadingSignalDetectionBlock,
    signal_integrity: signalIntegrityCheckBlock,
    source_artifacts_used: Array.from(
      new Set([
        ...(envelope.source_artifacts_used ?? []),
        ...(minimalLoop?.source_artifacts_used ?? []),
        ...(bottleneck?.source_artifacts_used ?? []),
        ...(leverageQueue?.source_artifacts_used ?? []),
        ...(riskSummary?.source_artifacts_used ?? []),
        ...(failureFeedback?.source_artifacts_used ?? []),
        ...(evalCandidates?.source_artifacts_used ?? []),
        ...(policyCandidateSignals?.source_artifacts_used ?? []),
        ...(feedbackLoopSnapshot?.source_artifacts_used ?? []),
        ...(failureExplanationPackets?.source_artifacts_used ?? []),
        ...(overrideAuditLog?.source_artifacts_used ?? []),
        ...(evalMaterializationPath?.source_artifacts_used ?? []),
        ...(caseIndex?.source_artifacts_used ?? []),
        ...(replayLineageHardening?.source_artifacts_used ?? []),
        ...(fallbackReductionPlan?.source_artifacts_used ?? []),
        ...(selComplianceSignalInput?.source_artifacts_used ?? []),
        ...(candidateClosureLedger?.source_artifacts_used ?? []),
        ...(metArtifactDependencyIndex?.source_artifacts_used ?? []),
        ...(trendFrequencyHonestyGate?.source_artifacts_used ?? []),
        ...(evlHandoffObservationTracker?.source_artifacts_used ?? []),
        ...(overrideEvidenceIntake?.source_artifacts_used ?? []),
        ...(debugExplanationIndex?.source_artifacts_used ?? []),
        ...(metGeneratedArtifactClassification?.source_artifacts_used ?? []),
        ...(ownerReadObservationLedger?.source_artifacts_used ?? []),
        ...(materializationObservationMapper?.source_artifacts_used ?? []),
        ...(comparableCaseQualificationGate?.source_artifacts_used ?? []),
        ...(trendReadyCasePack?.source_artifacts_used ?? []),
        ...(overrideEvidenceSourceAdapter?.source_artifacts_used ?? []),
        ...(foldCandidateProofCheck?.source_artifacts_used ?? []),
        ...(operatorDebuggabilityDrill?.source_artifacts_used ?? []),
        ...(generatedArtifactPolicyHandoff?.source_artifacts_used ?? []),
        ...(staleCandidatePressure?.source_artifacts_used ?? []),
        ...(outcomeAttribution?.source_artifacts_used ?? []),
        ...(failureReductionSignal?.source_artifacts_used ?? []),
        ...(recommendationAccuracy?.source_artifacts_used ?? []),
        ...(calibrationDrift?.source_artifacts_used ?? []),
        ...(signalConfidence?.source_artifacts_used ?? []),
        ...(crossRunConsistency?.source_artifacts_used ?? []),
        ...(divergenceDetection?.source_artifacts_used ?? []),
        ...(metErrorBudgetObservation?.source_artifacts_used ?? []),
        ...(metFreezeRecommendationSignal?.source_artifacts_used ?? []),
        ...(nextBestSliceRecommendation?.source_artifacts_used ?? []),
        ...(pqxCandidateActionBundle?.source_artifacts_used ?? []),
        ...(counterfactualReconstruction?.source_artifacts_used ?? []),
        ...(earlierInterventionSignal?.source_artifacts_used ?? []),
        ...(recurringFailureCluster?.source_artifacts_used ?? []),
        ...(recurrenceSeveritySignal?.source_artifacts_used ?? []),
        ...(timeToExplain?.source_artifacts_used ?? []),
        ...(debugReadinessSla?.source_artifacts_used ?? []),
        ...(metricGamingDetection?.source_artifacts_used ?? []),
        ...(misleadingSignalDetection?.source_artifacts_used ?? []),
        ...(signalIntegrityCheck?.source_artifacts_used ?? []),
      ])
    ),
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
