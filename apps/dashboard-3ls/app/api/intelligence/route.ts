import { NextResponse } from 'next/server';
import { loadArtifact } from '@/lib/artifactLoader';
import { buildSourceEnvelope } from '@/lib/sourceClassification';
import {
  computeCoreLoopSummary,
  type AiProgrammingGovernedPathRecord,
} from '@/lib/aiProgrammingCoreLoop';
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
  // AEX-PQX-DASH-02 — governance violation panel + core-loop compliance.
  governanceViolation: 'artifacts/dashboard_metrics/governance_violation_record.json',
  // AEX-PQX-DASH-01-REFINE — AI programming governed path (per-work-item).
  aiProgrammingGovernedPath:
    'artifacts/dashboard_metrics/ai_programming_governed_path_record.json',
};

// AEX-PQX-DASH-02 — fixed core-loop legs the dashboard reports compliance over.
const CORE_LOOP_LEGS = ['AEX', 'PQX', 'EVL', 'TPA', 'CDE', 'SEL'] as const;
type CoreLoopLeg = (typeof CORE_LOOP_LEGS)[number];
type LegState = 'present' | 'partial' | 'missing' | 'unknown';

interface GovernanceViolationEntry {
  violation_id?: string;
  work_item_id?: string;
  agent_type?: 'codex' | 'claude' | 'unknown_ai_agent' | string;
  violation_type?: string;
  missing_leg?: string;
  repo_mutating?: boolean | 'unknown';
  source_artifacts_used?: string[];
  why_it_matters?: string;
  next_recommended_input?: string;
}

interface GovernanceViolationRecord {
  artifact_type?: string;
  schema_version?: string;
  record_id?: string;
  created_at?: string;
  owner_system?: string;
  data_source?: string;
  status?: 'pass' | 'warn' | 'block' | 'unknown' | string;
  violation_count?: number;
  source_artifacts_used?: string[];
  warnings?: string[];
  reason_codes?: string[];
  failure_prevented?: string;
  signal_improved?: string;
  violations?: GovernanceViolationEntry[];
}

interface AIProgrammingGovernedPathRecord {
  artifact_type?: string;
  schema_version?: string;
  record_id?: string;
  created_at?: string;
  owner_system?: string;
  data_source?: string;
  status?: 'pass' | 'warn' | 'block' | 'unknown' | string;
  source_artifacts_used?: string[];
  warnings?: string[];
  reason_codes?: string[];
  failure_prevented?: string;
  signal_improved?: string;
  core_loop_compliance?: Partial<Record<CoreLoopLeg, LegState>>;
  core_loop_complete?: boolean;
  first_missing_leg?: string | null;
  weakest_leg?: string | null;
  compliance_score?: number;
  total_legs?: number;
  repo_mutating?: boolean | 'unknown';
  missing_legs?: string[];
  partial_legs?: string[];
  next_recommended_input?: string | null;
}

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

  // AEX-PQX-DASH-02 — governance violation panel.
  const governanceViolation = loadArtifact<GovernanceViolationRecord>(
    ARTIFACT_PATHS.governanceViolation,
  );
  // AEX-PQX-DASH-01-REFINE — AI Programming Governed Path observation record.
  // Per-work-item core-loop observations (AEX → PQX → EVL → TPA → CDE → SEL).
  // AEX-PQX-DASH-02 also reads the same artifact for its aggregate
  // core_loop_compliance roll-up. MET observes only.
  const aiProgrammingGovernedPath = loadArtifact<
    AiProgrammingGovernedPathRecord & AIProgrammingGovernedPathRecord
  >(ARTIFACT_PATHS.aiProgrammingGovernedPath);

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
    { path: ARTIFACT_PATHS.governanceViolation, loaded: governanceViolation !== null },
    { path: ARTIFACT_PATHS.aiProgrammingGovernedPath, loaded: aiProgrammingGovernedPath !== null },
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
      ...(governanceViolation?.warnings ?? []),
      ...(aiProgrammingGovernedPath?.warnings ?? []),
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

  // AEX-PQX-DASH-01-REFINE — Compute the AI programming core-loop proof
  // summary. The dashboard surfaces counts by leg, missing-by-leg counts,
  // weakest leg, and blocked work items derived only from artifact-backed
  // observations. No authority outcome is claimed by MET.
  const aiProgrammingCoreLoopSummary = computeCoreLoopSummary(
    aiProgrammingGovernedPath,
    `${ARTIFACT_PATHS.aiProgrammingGovernedPath} unavailable; AI programming core-loop proof reported as unknown.`,
  );
  const aiProgrammingGovernedPathBlock = {
    overall_status: aiProgrammingCoreLoopSummary.overall_status,
    core_loop_summary: aiProgrammingCoreLoopSummary,
    aex_present_count: aiProgrammingCoreLoopSummary.counts_by_leg.aex_present_count,
    pqx_present_count: aiProgrammingCoreLoopSummary.counts_by_leg.pqx_present_count,
    evl_present_count: aiProgrammingCoreLoopSummary.counts_by_leg.evl_present_count,
    tpa_present_count: aiProgrammingCoreLoopSummary.counts_by_leg.tpa_present_count,
    cde_present_count: aiProgrammingCoreLoopSummary.counts_by_leg.cde_present_count,
    sel_present_count: aiProgrammingCoreLoopSummary.counts_by_leg.sel_present_count,
    missing_by_leg: aiProgrammingCoreLoopSummary.missing_by_leg,
    blocked_work_items: aiProgrammingCoreLoopSummary.blocked_work_items,
    weakest_leg: aiProgrammingCoreLoopSummary.weakest_leg,
    codex_count: aiProgrammingCoreLoopSummary.codex_work_item_count,
    claude_count: aiProgrammingCoreLoopSummary.claude_work_item_count,
    core_loop_complete_count: aiProgrammingCoreLoopSummary.core_loop_complete_count,
    work_items: aiProgrammingCoreLoopSummary.work_items,
    data_source: aiProgrammingCoreLoopSummary.data_source,
    source_artifacts_used: aiProgrammingCoreLoopSummary.source_artifacts_used,
    warnings: aiProgrammingCoreLoopSummary.warnings,
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

  // AEX-PQX-DASH-02 — governance violations block. Fail-closed: missing
  // artifact degrades to unknown rather than 0; warning explicitly names the
  // missing file. MET observes only — no authority claim.
  const rawViolations = Array.isArray(governanceViolation?.violations)
    ? governanceViolation!.violations!
    : [];
  const filteredViolations = rawViolations.filter(
    (v) =>
      typeof v.violation_id === 'string' &&
      typeof v.work_item_id === 'string' &&
      typeof v.missing_leg === 'string' &&
      typeof v.violation_type === 'string',
  );
  const malformedViolationCount = rawViolations.length - filteredViolations.length;
  const declaredViolationCount = governanceViolation?.violation_count;
  // Fail-closed against data-shape drift: count BOTH well-formed and malformed
  // rows. A malformed violation entry is still concrete evidence of a
  // violation; dropping it from the count would let a stale
  // `violation_count: 0` paired with a malformed row fall through to PASS.
  const rawViolationsTotal = rawViolations.length;
  // Fail-closed: a stale or under-counted declared `violation_count` (e.g.
  // declared 0 with non-empty violations[]) must NOT cause the panel to fall
  // through to PASS. Use max(declared, observed_raw) so any concrete violation
  // entry surfaces as BLOCK regardless of the declared scalar OR row shape.
  const violationCountValue: number | 'unknown' = governanceViolation
    ? typeof declaredViolationCount === 'number'
      ? Math.max(declaredViolationCount, rawViolationsTotal)
      : rawViolationsTotal
    : 'unknown';
  // Fail-closed: violation_count > 0 forces BLOCK regardless of the declared
  // status. A stale `status: 'pass'` with non-empty violations cannot
  // downgrade the panel.
  const observedViolationsForce = typeof violationCountValue === 'number' && violationCountValue > 0;
  const declaredStatusValid =
    governanceViolation?.status === 'block' ||
    governanceViolation?.status === 'warn' ||
    governanceViolation?.status === 'pass' ||
    governanceViolation?.status === 'unknown';
  // Fail-closed: an unexpected `status` string with violation_count = 0 must
  // NOT fall through to 'pass'. A malformed status is itself a data-quality
  // signal that the panel should surface, not hide behind a clean state.
  const governanceViolationStatus: 'pass' | 'warn' | 'block' | 'unknown' = !governanceViolation
    ? 'unknown'
    : observedViolationsForce
      ? 'block'
      : declaredStatusValid
        ? (governanceViolation.status as 'pass' | 'warn' | 'block' | 'unknown')
        : 'unknown';
  const governanceViolationsBlock = governanceViolation
    ? {
        status: governanceViolationStatus,
        violation_count: violationCountValue,
        violations: filteredViolations,
        reason_codes: governanceViolation.reason_codes ?? [],
        failure_prevented: governanceViolation.failure_prevented ?? null,
        signal_improved: governanceViolation.signal_improved ?? null,
        data_source: governanceViolation.data_source ?? 'unknown',
        source_artifacts_used: governanceViolation.source_artifacts_used ?? [],
        warnings: [
          ...(governanceViolation.warnings ?? []),
          ...(malformedViolationCount > 0
            ? [
                `${malformedViolationCount} violation row(s) dropped from the rendered list due to missing required string field(s); they still count toward violation_count and the BLOCK status (fail-closed against data-shape drift).`,
              ]
            : []),
        ],
      }
    : {
        status: 'unknown' as const,
        violation_count: 'unknown' as const,
        violations: [] as GovernanceViolationEntry[],
        reason_codes: ['governance_violation_record_missing'],
        failure_prevented: null,
        signal_improved: null,
        data_source: 'unknown',
        source_artifacts_used: [],
        warnings: [
          `${ARTIFACT_PATHS.governanceViolation} unavailable; violation_count reported as unknown rather than 0.`,
        ],
      };

  // AEX-PQX-DASH-02 — core-loop compliance summary. Aggregates per-leg
  // present/partial/missing/unknown for the AI programming governed path.
  // BLOCK if AEX or PQX missing (unconditional — these legs prove admission
  // and execution and are required for any governed path); BLOCK if any
  // required leg missing AND repo_mutating === true; WARN on partial; UNKNOWN
  // if insufficient evidence.
  const compliance = aiProgrammingGovernedPath?.core_loop_compliance ?? {};
  // Fail-closed: any leg value that is not exactly one of the four known
  // LegState strings (case-sensitive) is normalized to 'unknown'. Casing
  // variants, typos, or unexpected enum values must not bypass the
  // missing/unknown checks downstream and accidentally promote a malformed
  // record to PASS or WARN.
  const normalizeLegState = (value: unknown): LegState =>
    value === 'present' || value === 'partial' || value === 'missing' || value === 'unknown'
      ? value
      : 'unknown';
  const legStates: Record<CoreLoopLeg, LegState> = {
    AEX: normalizeLegState(compliance.AEX),
    PQX: normalizeLegState(compliance.PQX),
    EVL: normalizeLegState(compliance.EVL),
    TPA: normalizeLegState(compliance.TPA),
    CDE: normalizeLegState(compliance.CDE),
    SEL: normalizeLegState(compliance.SEL),
  };
  const legArray: Array<{ leg: CoreLoopLeg; state: LegState }> = CORE_LOOP_LEGS.map(
    (leg) => ({ leg, state: legStates[leg] }),
  );
  const presentLegs = legArray.filter((l) => l.state === 'present').map((l) => l.leg);
  const partialLegs = legArray.filter((l) => l.state === 'partial').map((l) => l.leg);
  const missingLegs = legArray.filter((l) => l.state === 'missing').map((l) => l.leg);
  const unknownLegs = legArray.filter((l) => l.state === 'unknown').map((l) => l.leg);

  const computedComplianceScore = presentLegs.length;
  const declaredComplianceScore = aiProgrammingGovernedPath?.compliance_score;
  const complianceScore: number | 'unknown' = aiProgrammingGovernedPath
    ? typeof declaredComplianceScore === 'number'
      ? declaredComplianceScore
      : computedComplianceScore
    : 'unknown';

  // Fail-closed: repo_mutating must be a true boolean. Any non-boolean
  // token (e.g. the string "true", "yes", or undefined) collapses to
  // 'unknown' so the missing-leg block rule cannot be skipped by
  // data-shape drift.
  const rawRepoMutating: unknown = aiProgrammingGovernedPath?.repo_mutating;
  const repoMutating: boolean | 'unknown' =
    typeof rawRepoMutating === 'boolean' ? rawRepoMutating : 'unknown';

  const computedFirstMissingLeg = legArray.find((l) => l.state === 'missing')?.leg ?? null;
  const declaredFirstMissingLeg = aiProgrammingGovernedPath?.first_missing_leg;
  const firstMissingLeg: string | null = aiProgrammingGovernedPath
    ? typeof declaredFirstMissingLeg === 'string'
      ? declaredFirstMissingLeg
      : computedFirstMissingLeg
    : null;

  const computedWeakestLeg =
    legArray.find((l) => l.state === 'missing')?.leg ??
    legArray.find((l) => l.state === 'partial')?.leg ??
    legArray.find((l) => l.state === 'unknown')?.leg ??
    null;
  const declaredWeakestLeg = aiProgrammingGovernedPath?.weakest_leg;
  const weakestLeg: string | null = aiProgrammingGovernedPath
    ? typeof declaredWeakestLeg === 'string'
      ? declaredWeakestLeg
      : computedWeakestLeg
    : null;

  const requiredLegMissing = missingLegs.length > 0;
  const aexOrPqxMissing = legStates.AEX === 'missing' || legStates.PQX === 'missing';
  const allPresent = computedComplianceScore === CORE_LOOP_LEGS.length;
  const anyPartial = partialLegs.length > 0;
  const anyUnknown = unknownLegs.length > 0;
  // Fail-closed: derive core_loop_complete from normalized leg states rather
  // than trusting the artifact's declared boolean. A stale or inconsistent
  // record could otherwise mark a work item compliant while observed legs
  // still show missing — yielding contradictory compliant_work_items vs
  // blocked_work_items counts. Observed evidence wins.
  const declaredCoreLoopComplete = aiProgrammingGovernedPath?.core_loop_complete;
  const coreLoopComplete: boolean | 'unknown' = aiProgrammingGovernedPath
    ? allPresent
    : 'unknown';
  const coreLoopCompleteDeclaredMismatch =
    aiProgrammingGovernedPath !== null &&
    typeof declaredCoreLoopComplete === 'boolean' &&
    declaredCoreLoopComplete !== allPresent;

  let coreLoopStatus: 'pass' | 'warn' | 'block' | 'unknown';
  if (!aiProgrammingGovernedPath) {
    coreLoopStatus = 'unknown';
  } else if (aexOrPqxMissing) {
    coreLoopStatus = 'block';
  } else if (requiredLegMissing && repoMutating !== false) {
    // Fail-closed: BLOCK when a required leg is missing and repo_mutating
    // is true OR unknown. Treating 'unknown' as non-blocking would let
    // malformed runtime artifacts (e.g. repo_mutating: "true" as a string)
    // downgrade to WARN and under-report blocked work items.
    coreLoopStatus = 'block';
  } else if (allPresent) {
    coreLoopStatus = 'pass';
  } else if (anyPartial) {
    coreLoopStatus = 'warn';
  } else if (anyUnknown) {
    coreLoopStatus = 'unknown';
  } else {
    coreLoopStatus = 'warn';
  }

  // Work-item counts: derive from the per-work-item summary that
  // computeCoreLoopSummary() already produces from
  // ai_programming_work_items[]. Hard-coding to 1 would under-report scope
  // as soon as the artifact carries multiple work items (the seed already
  // ships 4). Falls back to the aggregate-only computation when no
  // per-work-item array is present.
  const perItemSummary = aiProgrammingCoreLoopSummary;
  const hasWorkItems = (perItemSummary.work_items?.length ?? 0) > 0;
  const totalWorkItems: number | 'unknown' = !aiProgrammingGovernedPath
    ? 'unknown'
    : hasWorkItems
      ? perItemSummary.work_items.length
      : 1;
  const compliantWorkItems: number | 'unknown' = !aiProgrammingGovernedPath
    ? 'unknown'
    : hasWorkItems
      ? perItemSummary.core_loop_complete_count
      : coreLoopComplete === true
        ? 1
        : 0;
  const blockedWorkItems: number | 'unknown' = !aiProgrammingGovernedPath
    ? 'unknown'
    : hasWorkItems
      ? perItemSummary.blocked_work_items.length
      : coreLoopStatus === 'block'
        ? 1
        : 0;

  // missing_by_leg: when per-work-item observations exist, use the count of
  // items with each leg missing (richer signal for blocked-scope consumers);
  // otherwise fall back to the aggregate single-row indicator.
  const missingByLeg: Record<CoreLoopLeg, number | 'unknown'> = !aiProgrammingGovernedPath
    ? { AEX: 'unknown', PQX: 'unknown', EVL: 'unknown', TPA: 'unknown', CDE: 'unknown', SEL: 'unknown' }
    : hasWorkItems
      ? {
          AEX: perItemSummary.missing_by_leg.AEX,
          PQX: perItemSummary.missing_by_leg.PQX,
          EVL: perItemSummary.missing_by_leg.EVL,
          TPA: perItemSummary.missing_by_leg.TPA,
          CDE: perItemSummary.missing_by_leg.CDE,
          SEL: perItemSummary.missing_by_leg.SEL,
        }
      : {
          AEX: legStates.AEX === 'missing' ? 1 : 0,
          PQX: legStates.PQX === 'missing' ? 1 : 0,
          EVL: legStates.EVL === 'missing' ? 1 : 0,
          TPA: legStates.TPA === 'missing' ? 1 : 0,
          CDE: legStates.CDE === 'missing' ? 1 : 0,
          SEL: legStates.SEL === 'missing' ? 1 : 0,
        };

  const coreLoopComplianceSummaryBlock = aiProgrammingGovernedPath
    ? {
        status: coreLoopStatus,
        core_loop_compliance: legStates,
        core_loop_complete: coreLoopComplete,
        compliance_score: complianceScore,
        total_legs: aiProgrammingGovernedPath.total_legs ?? CORE_LOOP_LEGS.length,
        first_missing_leg: firstMissingLeg,
        weakest_leg: weakestLeg,
        repo_mutating: repoMutating,
        missing_legs: aiProgrammingGovernedPath.missing_legs ?? missingLegs,
        partial_legs: aiProgrammingGovernedPath.partial_legs ?? partialLegs,
        unknown_legs: unknownLegs,
        violation_count: violationCountValue,
        total_work_items: totalWorkItems,
        compliant_work_items: compliantWorkItems,
        blocked_work_items: blockedWorkItems,
        weakest_leg_summary: weakestLeg,
        missing_by_leg: missingByLeg,
        next_recommended_input: aiProgrammingGovernedPath.next_recommended_input ?? null,
        reason_codes: aiProgrammingGovernedPath.reason_codes ?? [],
        failure_prevented: aiProgrammingGovernedPath.failure_prevented ?? null,
        signal_improved: aiProgrammingGovernedPath.signal_improved ?? null,
        data_source: aiProgrammingGovernedPath.data_source ?? 'unknown',
        source_artifacts_used: aiProgrammingGovernedPath.source_artifacts_used ?? [],
        warnings: [
          ...(aiProgrammingGovernedPath.warnings ?? []),
          ...(coreLoopCompleteDeclaredMismatch
            ? [
                `Declared core_loop_complete=${String(declaredCoreLoopComplete)} disagrees with observed leg states (allPresent=${String(allPresent)}); observed evidence wins.`,
              ]
            : []),
        ],
      }
    : {
        status: 'unknown' as const,
        core_loop_compliance: legStates,
        core_loop_complete: 'unknown' as const,
        compliance_score: 'unknown' as const,
        total_legs: CORE_LOOP_LEGS.length,
        first_missing_leg: null,
        weakest_leg: null,
        repo_mutating: 'unknown' as const,
        missing_legs: [] as string[],
        partial_legs: [] as string[],
        unknown_legs: [...CORE_LOOP_LEGS] as string[],
        violation_count: violationCountValue,
        total_work_items: 'unknown' as const,
        compliant_work_items: 'unknown' as const,
        blocked_work_items: 'unknown' as const,
        weakest_leg_summary: null,
        missing_by_leg: missingByLeg,
        next_recommended_input: null,
        reason_codes: ['ai_programming_governed_path_record_missing'],
        failure_prevented: null,
        signal_improved: null,
        data_source: 'unknown',
        source_artifacts_used: [],
        warnings: [
          `${ARTIFACT_PATHS.aiProgrammingGovernedPath} unavailable; core-loop compliance reported as unknown rather than PASS.`,
        ],
      };

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
    governance_violations: governanceViolationsBlock,
    core_loop_compliance_summary: coreLoopComplianceSummaryBlock,
    ai_programming_governed_path: aiProgrammingGovernedPathBlock,
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
        ...(governanceViolation?.source_artifacts_used ?? []),
        ...(aiProgrammingGovernedPath?.source_artifacts_used ?? []),
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
