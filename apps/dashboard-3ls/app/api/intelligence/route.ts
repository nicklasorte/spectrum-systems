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
    missing_eval_count?: number;
    missing_eval_dimensions?: string[];
    missing_trace_count?: number;
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
        data_source: bottleneck.data_source ?? 'artifact_store',
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

  // Leverage queue block — never recommend without source/failure_prevented/signal_improved.
  const filteredLeverage = (leverageQueue?.items ?? []).filter(
    (item) =>
      item.title &&
      item.failure_prevented &&
      item.signal_improved &&
      Array.isArray(item.source_artifacts_used) &&
      item.source_artifacts_used.length > 0
  );
  const leverageBlock = {
    items: filteredLeverage.sort((a, b) => b.leverage_score - a.leverage_score),
    formula: leverageQueue?.leverage_formula ?? null,
    data_source: leverageQueue?.data_source ?? (leverageQueue ? 'artifact_store' : 'unknown'),
    source_artifacts_used: leverageQueue?.source_artifacts_used ?? [],
    warnings: leverageQueue
      ? leverageQueue.warnings ?? []
      : [`${ARTIFACT_PATHS.leverageQueue} unavailable; leverage queue reported as empty.`],
  };

  const riskBlock = {
    fallback_signal_count: riskSummary?.payload?.fallback_signal_count ?? fallbackSignalCount,
    unknown_signal_count: riskSummary?.payload?.unknown_signal_count ?? unknownSignalCount,
    missing_eval_count: riskSummary?.payload?.missing_eval_count ?? 0,
    missing_trace_count: riskSummary?.payload?.missing_trace_count ?? 0,
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
    data_source: riskSummary?.data_source ?? (riskSummary ? 'artifact_store' : 'unknown'),
    source_artifacts_used: riskSummary?.source_artifacts_used ?? [],
    warnings: riskSummary
      ? riskSummary.warnings ?? []
      : [`${ARTIFACT_PATHS.riskSummary} unavailable; risk summary degraded to derived counts.`],
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
    source_artifacts_used: Array.from(
      new Set([
        ...(envelope.source_artifacts_used ?? []),
        ...(minimalLoop?.source_artifacts_used ?? []),
        ...(bottleneck?.source_artifacts_used ?? []),
        ...(leverageQueue?.source_artifacts_used ?? []),
        ...(riskSummary?.source_artifacts_used ?? []),
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
