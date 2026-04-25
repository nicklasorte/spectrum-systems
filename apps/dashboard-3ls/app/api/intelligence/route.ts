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
  bottleneckRecord: 'artifacts/dashboard_metrics/bottleneck_record.json',
  leverageQueueRecord: 'artifacts/dashboard_metrics/leverage_queue_record.json',
  riskSummaryRecord: 'artifacts/dashboard_metrics/risk_summary_record.json',
};

type LeverageItem = {
  id?: string;
  title: string;
  failure_prevented: string;
  signal_improved: string;
  systems_affected: string[];
  severity: string;
  frequency?: string;
  estimated_effort: string;
  leverage_score: number;
  data_source: string;
  confidence: string;
};

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
  const failureModes = loadArtifact<{ failure_modes?: unknown[] }>(ARTIFACT_PATHS.failureModes);
  const nearMisses = loadArtifact<{ near_misses?: unknown[] }>(ARTIFACT_PATHS.nearMisses);

  const bottleneckRecord = loadArtifact<{
    dominant_bottleneck_system?: string;
    constrained_loop_leg?: string;
    bottleneck_reason?: string;
    bottleneck_confidence?: string;
    evidence?: string[];
    warning_count_by_system?: Record<string, number>;
    warnings?: string[];
  }>(ARTIFACT_PATHS.bottleneckRecord);

  const leverageQueueRecord = loadArtifact<{
    items?: LeverageItem[];
    warnings?: string[];
  }>(ARTIFACT_PATHS.leverageQueueRecord);

  const riskSummaryRecord = loadArtifact<{
    fallback_signal_count?: number;
    unknown_signal_count?: number;
    missing_eval_count?: number;
    missing_trace_count?: number;
    override_count?: number | string;
    proof_chain_coverage?: {
      total: number;
      present: number;
      partial: number;
      missing: number;
      percent_present_or_partial: number;
      percent_fully_present: number;
    };
    top_risks?: string[];
    warnings?: string[];
  }>(ARTIFACT_PATHS.riskSummaryRecord);

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
    { path: ARTIFACT_PATHS.bottleneckRecord, loaded: bottleneckRecord !== null },
    { path: ARTIFACT_PATHS.leverageQueueRecord, loaded: leverageQueueRecord !== null },
    { path: ARTIFACT_PATHS.riskSummaryRecord, loaded: riskSummaryRecord !== null },
  ];

  const envelope = buildSourceEnvelope({
    slots: allSlots,
    isComputed: true,
    warnings: [
      ...(minimalLoop?.warnings ?? []),
      ...(evalSummary?.warnings ?? []),
      ...(bottleneckRecord?.warnings ?? []),
      ...(leverageQueueRecord?.warnings ?? []),
      ...(riskSummaryRecord?.warnings ?? []),
      'Dashboard seed artifacts are minimal and partial; unknown coverage remains visible by design.',
    ],
  });

  const proofChain = minimalLoop?.proof_chain ?? [];
  const proofPresent = proofChain.filter((s) => s.status === 'present').length;
  const proofPartial = proofChain.filter((s) => s.status === 'partial').length;
  const proofTotal = proofChain.length;
  const artifactBackedSignalCount = allSlots.filter((s) => s.loaded && s.path.includes('dashboard_seed')).length;
  const fallbackSignalCount = allSlots.filter((s) => !s.loaded).length;
  const unknownSignalCount = Math.max(0, proofTotal - proofPresent - proofPartial);

  const bottleneck = bottleneckRecord
    ? {
        system: bottleneckRecord.dominant_bottleneck_system ?? 'unknown',
        loop_leg: bottleneckRecord.constrained_loop_leg ?? 'unknown',
        reason: bottleneckRecord.bottleneck_reason ?? 'unknown',
        confidence: bottleneckRecord.bottleneck_confidence ?? 'derived_estimate',
        evidence: bottleneckRecord.evidence ?? [],
        warning_count_by_system: bottleneckRecord.warning_count_by_system ?? {},
        data_source: 'artifact_store' as const,
        source_artifacts_used: [ARTIFACT_PATHS.bottleneckRecord],
        warnings: bottleneckRecord.warnings ?? [],
      }
    : {
        system: 'unknown',
        loop_leg: 'unknown',
        reason: 'bottleneck_record artifact not loaded',
        confidence: 'unknown',
        evidence: [],
        warning_count_by_system: {},
        data_source: 'unknown' as const,
        source_artifacts_used: [] as string[],
        warnings: ['bottleneck_record not found; bottleneck state unknown'],
      };

  const leverageQueue = {
    items: leverageQueueRecord?.items ?? [],
    data_source: leverageQueueRecord ? ('artifact_store' as const) : ('unknown' as const),
    source_artifacts_used: leverageQueueRecord ? [ARTIFACT_PATHS.leverageQueueRecord] : ([] as string[]),
    warnings: [
      ...(leverageQueueRecord?.warnings ?? []),
      ...(leverageQueueRecord ? [] : ['leverage_queue_record not found; leverage queue empty']),
    ],
  };

  const riskSummary = riskSummaryRecord
    ? {
        fallback_signal_count: riskSummaryRecord.fallback_signal_count ?? 'unknown',
        unknown_signal_count: riskSummaryRecord.unknown_signal_count ?? 'unknown',
        missing_eval_count: riskSummaryRecord.missing_eval_count ?? 'unknown',
        missing_trace_count: riskSummaryRecord.missing_trace_count ?? 'unknown',
        override_count: riskSummaryRecord.override_count ?? 'unknown',
        proof_chain_coverage: riskSummaryRecord.proof_chain_coverage ?? null,
        top_risks: riskSummaryRecord.top_risks ?? [],
        data_source: 'artifact_store' as const,
        source_artifacts_used: [ARTIFACT_PATHS.riskSummaryRecord],
        warnings: riskSummaryRecord.warnings ?? [],
      }
    : {
        fallback_signal_count: 'unknown',
        unknown_signal_count: 'unknown',
        missing_eval_count: 'unknown',
        missing_trace_count: 'unknown',
        override_count: 'unknown',
        proof_chain_coverage: null,
        top_risks: [] as string[],
        data_source: 'unknown' as const,
        source_artifacts_used: [] as string[],
        warnings: ['risk_summary_record not found; risk summary unavailable'],
      };

  return NextResponse.json({
    ...envelope,
    seed_artifacts_present: minimalLoop !== null,
    proof_chain_coverage: {
      total: proofTotal,
      present: proofPresent,
      partial: proofPartial,
      missing_or_unknown: unknownSignalCount,
      percent_present_or_partial: proofTotal > 0 ? Math.round(((proofPresent + proofPartial) / proofTotal) * 100) : 0,
    },
    artifact_backed_signal_count: artifactBackedSignalCount,
    fallback_signal_count: fallbackSignalCount,
    unknown_signal_count: unknownSignalCount,
    failure_modes: failureModes?.failure_modes ?? [],
    near_misses: nearMisses?.near_misses ?? [],
    minimal_loop_status: minimalLoop?.minimal_loop_status ?? 'unknown',
    source_artifacts_used: Array.from(new Set([...(envelope.source_artifacts_used ?? []), ...(minimalLoop?.source_artifacts_used ?? [])])),
    bottleneck,
    bottleneck_confidence: bottleneck.confidence,
    leverage_queue: leverageQueue,
    risk_summary: riskSummary,
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
