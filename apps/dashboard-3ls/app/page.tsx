'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { AUTHORITY_ROLES } from '@/lib/displayGroups';
import { dataSourceAllowsHealthy } from '@/lib/truthClassifier';
import type { DataSource } from '@/lib/types';

type TrustState = 'PASS' | 'WARN' | 'FREEZE' | 'BLOCK';
type StageState = 'present' | 'partial' | 'missing' | 'unknown';

interface HealthSystem {
  system_id: string;
  system_name: string;
  status: 'healthy' | 'warning' | 'critical' | 'unknown';
  incidents_week: number;
  contract_violations: Array<{ rule: string; detail: string }>;
  data_source?: DataSource;
  authority_role?: string | null;
}

interface HealthPayload {
  data_source?: DataSource;
  generated_at?: string;
  source_artifacts_used?: string[];
  warnings?: string[];
  systems?: HealthSystem[];
}

interface BottleneckBlock {
  dominant_bottleneck_system?: string;
  constrained_loop_leg?: string;
  supporting_evidence?: Array<{ kind: string; source: string; detail: string }>;
  warning_counts_by_system?: Record<string, number>;
  block_counts_by_system?: Record<string, number>;
  priority_rule?: string | null;
  confidence_rationale?: string | null;
  data_source?: DataSource;
  source_artifacts_used?: string[];
  warnings?: string[];
}

interface LeverageQueueItem {
  id?: string;
  title: string;
  failure_prevented: string;
  signal_improved: string;
  systems_affected: string[];
  severity: 'high' | 'medium' | 'low';
  frequency?: 'high' | 'medium' | 'low' | 'unknown';
  estimated_effort?: 'high' | 'medium' | 'low' | 'unknown';
  blocks_promotion?: boolean;
  affects_governance_legs?: boolean;
  repeat_failure?: boolean;
  reduces_fallback_or_unknown?: boolean;
  leverage_score: number;
  data_source: DataSource;
  source_artifacts_used: string[];
  confidence: string;
}

interface LeverageQueueBlock {
  items?: LeverageQueueItem[];
  formula?: string | null;
  data_source?: DataSource;
  source_artifacts_used?: string[];
  warnings?: string[];
}

interface FailureMode {
  id: string;
  title: string;
  severity: string;
  frequency?: string;
  systems_affected?: string[];
  trend?: string;
  evidence?: string[];
}

interface RiskSummaryBlock {
  fallback_signal_count?: number;
  unknown_signal_count?: number;
  missing_eval_count?: number | 'unknown';
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
  data_source?: DataSource;
  source_artifacts_used?: string[];
  warnings?: string[];
}

interface IntelligencePayload {
  data_source?: DataSource;
  source_artifacts_used?: string[];
  warnings?: string[];
  bottleneck?: BottleneckBlock;
  bottleneck_confidence?: 'artifact_backed' | 'derived_estimate' | 'unknown';
  leverage_queue?: LeverageQueueBlock;
  risk_summary?: RiskSummaryBlock;
  failure_modes?: FailureMode[];
  intelligence_summary?: {
    roadmap?: {
      dominant_bottleneck?: string;
      bottleneck_statement?: string;
      top_risks?: string[];
    };
    mg_kernel?: {
      status?: string;
      all_pass?: boolean;
    };
    provenance?: {
      authority_precheck_valid?: boolean;
      step_count_exactly_24?: boolean;
    };
    repo?: {
      operational_signals?: Array<{ title: string; status: string; detail: string }>;
    };
    system_state?: {
      authority_precheck?: string;
      domain_state?: Record<string, string>;
    };
  };
}

interface SystemsPayload {
  data_source?: DataSource;
  source_artifacts_used?: string[];
  warnings?: string[];
}

interface RGEPayload {
  data_source?: DataSource;
  rge_can_operate?: boolean;
  context_maturity_level?: number | 'unknown';
  mg_kernel_status?: string;
  active_drift_legs?: string[];
  warnings?: string[];
}

interface ProofStage {
  name: string;
  state: StageState;
  data_source: DataSource;
  reason_codes: string[];
}

interface LeverageItem {
  title: string;
  failure_prevented: string;
  signal_improved: string;
  systems_affected: string[];
  severity: 'high' | 'medium' | 'low';
  effort: 'high' | 'medium' | 'low' | 'unknown';
  source: 'artifact' | 'derived' | 'fallback';
  confidence: 'artifact-backed' | 'derived' | 'fallback';
  leverage_score: number;
  source_artifacts_used?: string[];
}

const SOURCE_ORDER: DataSource[] = [
  'artifact_store',
  'repo_registry',
  'derived',
  'derived_estimate',
  'stub_fallback',
  'unknown',
];

const LOOP_SEQUENCE = ['AEX', 'PQX', 'EVL', 'TPA', 'CDE', 'SEL'];
const LOOP_OVERLAYS = ['REP', 'LIN', 'OBS', 'SLO'];

const SOURCE_TONE: Record<DataSource, string> = {
  artifact_store: 'bg-blue-50 text-blue-700 border-blue-300',
  repo_registry: 'bg-indigo-50 text-indigo-700 border-indigo-300',
  derived: 'bg-purple-50 text-purple-700 border-purple-300',
  derived_estimate: 'bg-amber-50 text-amber-700 border-amber-300',
  stub_fallback: 'bg-orange-50 text-orange-700 border-orange-300',
  unknown: 'bg-gray-100 text-gray-600 border-gray-300',
};

const STATUS_TONE: Record<TrustState, string> = {
  PASS: 'bg-green-50 text-green-800 border-green-300',
  WARN: 'bg-amber-50 text-amber-800 border-amber-300',
  FREEZE: 'bg-orange-50 text-orange-800 border-orange-300',
  BLOCK: 'bg-red-50 text-red-800 border-red-300',
};

function SourceBadge({ ds }: { ds: DataSource }) {
  return (
    <span className={`inline-flex items-center border rounded px-2 py-0.5 text-xs font-mono ${SOURCE_TONE[ds]}`}>
      {ds}
    </span>
  );
}

function ProvisionalBadge({ ds }: { ds: DataSource }) {
  if (ds !== 'derived_estimate') return null;
  return (
    <span
      data-testid="provisional-badge"
      className="inline-flex items-center border rounded px-2 py-0.5 text-xs font-mono uppercase tracking-wide bg-amber-50 border-amber-300 text-amber-800"
    >
      provisional
    </span>
  );
}

function statusTone(status: string) {
  if (status === 'healthy' || status === 'present' || status === 'PASS') return 'text-green-700';
  if (status === 'warning' || status === 'partial' || status === 'WARN') return 'text-amber-700';
  if (status === 'critical' || status === 'missing' || status === 'BLOCK') return 'text-red-700';
  if (status === 'FREEZE') return 'text-orange-700';
  return 'text-gray-500';
}

function severityWeight(value: 'high' | 'medium' | 'low') {
  return value === 'high' ? 3 : value === 'medium' ? 2 : 1;
}

function effortWeight(value: 'high' | 'medium' | 'low' | 'unknown') {
  return value === 'high' ? 3 : value === 'medium' ? 2 : value === 'low' ? 1 : 2;
}

export default function Dashboard() {
  const [health, setHealth] = useState<HealthPayload | null>(null);
  const [intelligence, setIntelligence] = useState<IntelligencePayload | null>(null);
  const [systemsEnvelope, setSystemsEnvelope] = useState<SystemsPayload | null>(null);
  const [rge, setRge] = useState<RGEPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const [healthRes, intelligenceRes, systemsRes, rgeRes] = await Promise.all([
          fetch('/api/health'),
          fetch('/api/intelligence'),
          fetch('/api/systems'),
          fetch('/api/rge/analysis'),
        ]);

        if (!healthRes.ok || !intelligenceRes.ok || !systemsRes.ok || !rgeRes.ok) {
          throw new Error('Failed to fetch dashboard artifacts');
        }

        const [healthData, intelligenceData, systemsData, rgeData] = await Promise.all([
          healthRes.json(),
          intelligenceRes.json(),
          systemsRes.json(),
          rgeRes.json(),
        ]);

        setHealth(healthData);
        setIntelligence(intelligenceData);
        setSystemsEnvelope(systemsData);
        setRge(rgeData);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  const computed = useMemo(() => {
    const systems = health?.systems ?? [];
    const warnings = [...(health?.warnings ?? []), ...(intelligence?.warnings ?? []), ...(rge?.warnings ?? [])];
    const sourceMix = SOURCE_ORDER.reduce(
      (acc, source) => {
        acc[source] = systems.filter((s) => (s.data_source ?? 'unknown') === source).length;
        return acc;
      },
      {
        artifact_store: 0,
        repo_registry: 0,
        derived: 0,
        derived_estimate: 0,
        stub_fallback: 0,
        unknown: 0,
      } as Record<DataSource, number>
    );

    const artifactBackedCount = sourceMix.artifact_store + sourceMix.repo_registry;
    const artifactBackedPct = systems.length === 0 ? 0 : Math.round((artifactBackedCount / systems.length) * 100);

    const loopRows = [...LOOP_SEQUENCE, ...LOOP_OVERLAYS].map((id) => {
      const node = systems.find((s) => s.system_id === id);
      const data_source = (node?.data_source ?? 'unknown') as DataSource;
      const incomingStatus = node?.status ?? 'unknown';
      const normalizedStatus =
        incomingStatus === 'healthy' && !dataSourceAllowsHealthy(data_source)
          ? data_source === 'derived_estimate'
            ? 'warning'
            : 'unknown'
          : incomingStatus;
      return {
        system_id: id,
        authority_role: AUTHORITY_ROLES[id] ?? 'unknown',
        status: normalizedStatus,
        data_source,
        warning_count: (node?.incidents_week ?? 0) + (node?.contract_violations?.length ?? 0),
      };
    });

    const missingLoopSystems = loopRows.filter((row) => row.status === 'unknown').map((row) => row.system_id);

    const bottleneckArtifact = intelligence?.bottleneck;
    const bottleneckFromMet =
      bottleneckArtifact && bottleneckArtifact.dominant_bottleneck_system &&
      bottleneckArtifact.dominant_bottleneck_system !== 'unknown'
        ? bottleneckArtifact.dominant_bottleneck_system
        : null;
    const bottleneckFromGap = intelligence?.intelligence_summary?.roadmap?.dominant_bottleneck;
    const bottleneckFallback = loopRows
      .filter((row) => LOOP_SEQUENCE.includes(row.system_id))
      .sort((a, b) => b.warning_count - a.warning_count)[0]?.system_id;
    const bottleneck = bottleneckFromMet ?? bottleneckFromGap ?? bottleneckFallback ?? 'unknown';
    // Prefer the declared bottleneck_confidence over the artifact's storage
    // provenance: the analysis itself can be derived_estimate even when its
    // source artifact is artifact_store. Take the worse of the two so the UI
    // never overstates confidence.
    const declaredConfidence = intelligence?.bottleneck_confidence;
    const declaredConfidenceDS: DataSource | null =
      declaredConfidence === 'artifact_backed'
        ? 'artifact_store'
        : declaredConfidence === 'derived_estimate'
        ? 'derived_estimate'
        : declaredConfidence === 'unknown'
        ? 'unknown'
        : null;
    const artifactSourceDS: DataSource | null = bottleneckFromMet
      ? (bottleneckArtifact?.data_source ?? 'artifact_store')
      : bottleneckFromGap
      ? (intelligence?.data_source ?? 'unknown')
      : null;
    const candidateSources: DataSource[] = [];
    if (declaredConfidenceDS) candidateSources.push(declaredConfidenceDS);
    if (artifactSourceDS) candidateSources.push(artifactSourceDS);
    const bottleneckConfidence: DataSource =
      candidateSources.length === 0
        ? 'derived_estimate'
        : candidateSources.includes('unknown')
        ? 'unknown'
        : candidateSources.includes('stub_fallback')
        ? 'stub_fallback'
        : candidateSources.includes('derived_estimate')
        ? 'derived_estimate'
        : candidateSources.includes('derived')
        ? 'derived'
        : candidateSources[0];
    const bottleneckEvidence = bottleneckArtifact?.supporting_evidence ?? [];
    const bottleneckReason =
      bottleneckArtifact?.confidence_rationale ??
      intelligence?.intelligence_summary?.roadmap?.bottleneck_statement ??
      null;

    const evalMissing = !systems.find((s) => s.system_id === 'EVL') || systems.find((s) => s.system_id === 'EVL')?.status === 'unknown';
    const lineageMissing = !systems.find((s) => s.system_id === 'LIN') || systems.find((s) => s.system_id === 'LIN')?.status === 'unknown';

    const proofStages: ProofStage[] = [
      {
        name: 'Source',
        state:
          (systemsEnvelope?.source_artifacts_used?.length ?? 0) > 0
            ? 'present'
            : systemsEnvelope?.data_source === 'derived_estimate'
            ? 'partial'
            : systemsEnvelope?.data_source === 'unknown'
            ? 'unknown'
            : 'missing',
        data_source: (systemsEnvelope?.data_source ?? 'unknown') as DataSource,
        reason_codes: systemsEnvelope?.warnings?.length ? ['source_warnings_present'] : [],
      },
      {
        name: 'Output',
        state: systems.length > 0 ? 'present' : 'missing',
        data_source: (health?.data_source ?? 'unknown') as DataSource,
        reason_codes: systems.length > 0 ? [] : ['output_missing'],
      },
      {
        name: 'Eval',
        state: evalMissing ? 'missing' : 'present',
        data_source: (health?.systems?.find((s) => s.system_id === 'EVL')?.data_source ?? 'unknown') as DataSource,
        reason_codes: evalMissing ? ['eval_missing'] : [],
      },
      {
        name: 'Control',
        state: systems.find((s) => s.system_id === 'CDE') ? 'present' : 'missing',
        data_source: (health?.systems?.find((s) => s.system_id === 'CDE')?.data_source ?? 'unknown') as DataSource,
        reason_codes: systems.find((s) => s.system_id === 'CDE') ? [] : ['control_missing'],
      },
      {
        name: 'Enforcement',
        state: systems.find((s) => s.system_id === 'SEL') ? 'present' : 'missing',
        data_source: (health?.systems?.find((s) => s.system_id === 'SEL')?.data_source ?? 'unknown') as DataSource,
        reason_codes: systems.find((s) => s.system_id === 'SEL') ? [] : ['enforcement_missing'],
      },
      {
        name: 'Certification',
        state:
          intelligence?.intelligence_summary?.mg_kernel?.all_pass === true
            ? 'present'
            : intelligence?.intelligence_summary?.mg_kernel?.status
            ? 'partial'
            : 'unknown',
        data_source: (intelligence?.data_source ?? 'unknown') as DataSource,
        reason_codes:
          intelligence?.intelligence_summary?.mg_kernel?.all_pass === true
            ? []
            : ['certification_incomplete'],
      },
    ];

    const proofCoverage = Math.round(
      (proofStages.filter((s) => s.state === 'present').length / proofStages.length) * 100
    );

    const apiRisk = intelligence?.risk_summary;
    const derivedMissingEval = proofStages.filter((s) => s.name === 'Eval' && s.state === 'missing').length;
    const derivedMissingTrace = lineageMissing ? 1 : 0;
    const missingEvalCount: number | 'unknown' =
      apiRisk?.missing_eval_count ?? (apiRisk ? derivedMissingEval : 'unknown');
    const missingTraceCount: number | 'unknown' =
      apiRisk?.missing_trace_count ?? (apiRisk ? derivedMissingTrace : 'unknown');
    const fallbackCount = apiRisk?.fallback_signal_count ?? sourceMix.stub_fallback;
    const unknownCount = apiRisk?.unknown_signal_count ?? sourceMix.unknown;
    const overrideCount: number | 'unknown' = apiRisk?.override_count ?? 'unknown';

    const topFailureModeArtifacts = (intelligence?.failure_modes ?? []).map((fm) => ({
      label: `${fm.title} (severity: ${fm.severity})`,
      systems_affected: fm.systems_affected ?? [],
      severity: fm.severity,
    }));
    const topFailureModes =
      topFailureModeArtifacts.length > 0
        ? topFailureModeArtifacts.slice(0, 5).map((fm) => fm.label)
        : [
            ...(intelligence?.intelligence_summary?.roadmap?.top_risks ?? []),
            ...((intelligence?.intelligence_summary?.repo?.operational_signals ?? [])
              .filter((s) => s.status !== 'ok')
              .map((s) => `${s.title}: ${s.detail}`)),
          ].slice(0, 5);

    const noHealthySource = systems.some(
      (s) => s.status === 'healthy' && !dataSourceAllowsHealthy((s.data_source ?? 'unknown') as DataSource)
    );

    const trustReasons: string[] = [];
    if (evalMissing) trustReasons.push('eval_missing');
    if (lineageMissing) trustReasons.push('lineage_missing');
    if (sourceMix.stub_fallback > 0) trustReasons.push('stub_fallback_present');
    if (sourceMix.unknown > 0) trustReasons.push('unknown_source_present');
    if (noHealthySource) trustReasons.push('healthy_blocked_by_source');
    if (missingLoopSystems.length > 0) trustReasons.push('loop_systems_unknown');

    let trustState: TrustState = 'PASS';
    if (evalMissing || lineageMissing) trustState = 'BLOCK';
    else if (sourceMix.stub_fallback > 0 || sourceMix.unknown > 0 || missingLoopSystems.length > 0)
      trustState = 'FREEZE';
    else if (warnings.length > 0 || proofCoverage < 100) trustState = 'WARN';

    const recs: Omit<LeverageItem, 'leverage_score'>[] = [];

    if (evalMissing) {
      recs.push({
        title: 'Restore EVL artifact-backed evaluation feed',
        failure_prevented: 'Promotion without evaluation evidence',
        signal_improved: 'Proof-chain Eval stage coverage',
        systems_affected: ['EVL', 'TPA', 'CDE'],
        severity: 'high',
        effort: 'medium',
        source: 'derived',
        confidence: 'derived',
      });
    }

    if (lineageMissing) {
      recs.push({
        title: 'Wire LIN trace lineage artifact into dashboard loop',
        failure_prevented: 'Untraceable enforcement decisions',
        signal_improved: 'Proof-chain lineage completeness',
        systems_affected: ['LIN', 'CDE', 'SEL'],
        severity: 'high',
        effort: 'medium',
        source: 'derived',
        confidence: 'derived',
      });
    }

    if (fallbackCount > 0) {
      recs.push({
        title: 'Replace stub_fallback health rows with artifact snapshots',
        failure_prevented: 'False confidence from placeholder statuses',
        signal_improved: 'Trust posture and artifact-backed percentage',
        systems_affected: LOOP_SEQUENCE,
        severity: 'high',
        effort: 'high',
        source: 'artifact',
        confidence: health?.data_source === 'stub_fallback' ? 'fallback' : 'artifact-backed',
      });
    }

    if (bottleneck !== 'unknown') {
      recs.push({
        title: `Mitigate current bottleneck: ${bottleneck}`,
        failure_prevented: 'Queue growth and promotion delay',
        signal_improved: 'Loop throughput stability',
        systems_affected: [bottleneck],
        severity: 'medium',
        effort: 'low',
        source: bottleneckFromMet ?? bottleneckFromGap ? 'artifact' : 'derived',
        confidence: bottleneckFromMet ?? bottleneckFromGap ? 'artifact-backed' : 'derived',
      });
    }

    if (rge?.rge_can_operate === false) {
      recs.push({
        title: 'Clear RGE operate blockers before next promotion cycle',
        failure_prevented: 'Stalled proposal generation for CDE',
        signal_improved: 'Readiness continuity for governed loop',
        systems_affected: ['RGE', 'CDE'],
        severity: 'medium',
        effort: 'unknown',
        source: 'artifact',
        confidence: (rge.data_source ?? 'unknown') === 'artifact_store' ? 'artifact-backed' : 'derived',
      });
    }

    const derivedLeverage = recs
      .filter((r) => r.source !== 'fallback' || r.confidence !== 'fallback')
      .map((item) => {
        const base =
          (severityWeight(item.severity) * Math.max(1, item.systems_affected.length)) /
          effortWeight(item.effort);
        const blockingBoost =
          item.failure_prevented.toLowerCase().includes('promotion') ||
          item.systems_affected.some((id) => ['EVL', 'CDE', 'TPA'].includes(id))
            ? 1.4
            : 1;
        const repeatBoost = fallbackCount > 0 || unknownCount > 0 ? 1.15 : 1;
        const score = Number((base * blockingBoost * repeatBoost).toFixed(2));
        return { ...item, leverage_score: score };
      })
      .filter((item) => item.failure_prevented && item.signal_improved)
      .sort((a, b) => b.leverage_score - a.leverage_score)
      .slice(0, 5);

    const apiLeverage = (intelligence?.leverage_queue?.items ?? [])
      .filter(
        (item) =>
          item.title &&
          item.failure_prevented &&
          item.signal_improved &&
          Array.isArray(item.source_artifacts_used) &&
          item.source_artifacts_used.length > 0
      )
      .map((item) => ({
        title: item.title,
        failure_prevented: item.failure_prevented,
        signal_improved: item.signal_improved,
        systems_affected: item.systems_affected,
        severity: item.severity,
        effort: (item.estimated_effort ?? 'unknown') as 'high' | 'medium' | 'low' | 'unknown',
        source: 'artifact' as const,
        confidence: 'artifact-backed' as const,
        leverage_score: item.leverage_score,
        source_artifacts_used: item.source_artifacts_used,
      }))
      .sort((a, b) => b.leverage_score - a.leverage_score)
      .slice(0, 5);

    const leverageQueue = apiLeverage.length > 0
      ? apiLeverage
      : derivedLeverage.map((d) => ({ ...d, source_artifacts_used: [] as string[] }));

    return {
      systems,
      sourceMix,
      artifactBackedPct,
      trustState,
      trustReasons: trustReasons.slice(0, 3),
      loopRows,
      bottleneck,
      bottleneckConfidence,
      bottleneckEvidence,
      bottleneckReason,
      proofStages,
      proofCoverage,
      fallbackCount,
      unknownCount,
      missingEvalCount,
      missingTraceCount,
      overrideCount,
      topFailureModes,
      failureModesDetailed: intelligence?.failure_modes ?? [],
      leverageQueue,
      leverageSource: (apiLeverage.length > 0
        ? (intelligence?.leverage_queue?.data_source ?? 'artifact_store')
        : ('derived' as DataSource)) as DataSource,
      warnings,
    };
  }, [health, intelligence, systemsEnvelope, rge]);

  if (loading) return <div className="p-8">Loading dashboard artifacts...</div>;
  if (error) return <div className="p-8 text-red-600">Error: {error}</div>;

  const rgeSource = (rge?.data_source ?? 'unknown') as DataSource;
  const rgeCanOperate = rge?.rge_can_operate;
  const sourceAllowsGreen = dataSourceAllowsHealthy(rgeSource);

  return (
    <div className="p-8 bg-gray-50 min-h-screen space-y-6">
      <h1 className="text-3xl font-bold">3LS Trust + Leverage Dashboard</h1>

      {computed.warnings.length > 0 && (
        <div role="alert" className="bg-amber-50 border border-amber-300 rounded p-3">
          <p className="text-sm font-semibold text-amber-800">Source warnings</p>
          <ul className="mt-1 text-xs text-amber-700 list-disc list-inside">
            {computed.warnings.slice(0, 4).map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      <section className="bg-white border rounded p-4" data-testid="trust-posture-panel">
        <h2 className="font-semibold mb-3">TRUST POSTURE</h2>
        <div className="flex items-center gap-3 mb-3">
          <span className={`border rounded px-3 py-1 text-sm font-semibold ${STATUS_TONE[computed.trustState]}`}>
            {computed.trustState}
          </span>
          <span className="text-sm text-gray-600">Artifact-backed {computed.artifactBackedPct}%</span>
        </div>
        <div className="mb-3">
          <p className="text-xs uppercase tracking-wide text-gray-500 mb-1">Top reasons</p>
          <div className="flex flex-wrap gap-2">
            {computed.trustReasons.length > 0 ? (
              computed.trustReasons.map((reason) => (
                <span key={reason} className="text-xs border border-gray-300 rounded px-2 py-0.5 font-mono">
                  {reason}
                </span>
              ))
            ) : (
              <span className="text-xs text-gray-500">none</span>
            )}
          </div>
        </div>
        <div>
          <p className="text-xs uppercase tracking-wide text-gray-500 mb-1">Source mix</p>
          <div className="flex flex-wrap gap-2">
            {SOURCE_ORDER.map((source) => (
              <span key={source} className="text-xs border rounded px-2 py-0.5">
                {source}: {computed.sourceMix[source]}
              </span>
            ))}
          </div>
        </div>
      </section>

      <section className="bg-white border rounded p-4" data-testid="loop-bottleneck-panel">
        <h2 className="font-semibold mb-3">GOVERNED LOOP + BOTTLENECK</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {computed.loopRows.map((row) => {
            const isBottleneck = row.system_id === computed.bottleneck;
            return (
              <div
                key={row.system_id}
                className={`border rounded p-3 ${
                  isBottleneck ? 'border-red-400 bg-red-50 ring-2 ring-red-200' : ''
                }`}
                data-testid={`loop-node-${row.system_id}`}
                data-bottleneck={isBottleneck ? 'true' : undefined}
              >
                <div className="flex justify-between items-start">
                  <div>
                    <div className="font-mono font-semibold">
                      {row.system_id}
                      {isBottleneck && (
                        <span className="ml-2 text-xs uppercase tracking-wide bg-red-100 text-red-700 border border-red-300 rounded px-1.5 py-0.5">
                          bottleneck
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-gray-600" data-testid={`authority-${row.system_id}`}>
                      {row.authority_role}
                    </div>
                  </div>
                  <span className={`text-sm font-semibold ${statusTone(row.status)}`}>{row.status}</span>
                </div>
                <div className="mt-2 flex items-center gap-2">
                  <SourceBadge ds={row.data_source} />
                  <ProvisionalBadge ds={row.data_source} />
                  {row.data_source === 'unknown' && (
                    <span className="text-xs border border-gray-300 rounded px-2 py-0.5">unknown</span>
                  )}
                </div>
                <div className="mt-2 text-xs text-gray-600">warning_count: {row.warning_count}</div>
              </div>
            );
          })}
        </div>
        <div className="mt-3 text-sm" data-testid="bottleneck-summary">
          Current bottleneck: <span className="font-mono">{computed.bottleneck}</span>
          <span className="ml-2">
            <SourceBadge ds={computed.bottleneckConfidence} />
          </span>
        </div>
        {computed.bottleneckReason && (
          <p className="mt-1 text-xs text-gray-700" data-testid="bottleneck-reason">
            reason: {computed.bottleneckReason}
          </p>
        )}
        {computed.bottleneckEvidence.length > 0 && (
          <ul className="mt-2 text-xs text-gray-600 list-disc list-inside" data-testid="bottleneck-evidence">
            {computed.bottleneckEvidence.slice(0, 3).map((ev, idx) => (
              <li key={`${ev.kind}-${idx}`}>
                <span className="font-mono">{ev.kind}</span>: {ev.detail}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="bg-white border rounded p-4" data-testid="proof-chain-panel">
        <h2 className="font-semibold mb-3">PROOF CHAIN</h2>
        <div className="space-y-2">
          {computed.proofStages.map((stage) => (
            <div key={stage.name} className="border rounded p-2">
              <div className="flex items-center justify-between">
                <div className="font-medium">{stage.name}</div>
                <div className="flex items-center gap-2">
                  <span className={`text-sm font-semibold ${statusTone(stage.state)}`}>{stage.state}</span>
                  <SourceBadge ds={stage.data_source} />
                </div>
              </div>
              {stage.reason_codes.length > 0 && (
                <div className="text-xs text-gray-600 mt-1">reason_codes: {stage.reason_codes.join(', ')}</div>
              )}
            </div>
          ))}
        </div>
        <div className="mt-3 text-sm">Proof chain coverage: {computed.proofCoverage}%</div>
      </section>

      <section className="bg-white border rounded p-4" data-testid="fragility-risk-panel">
        <h2 className="font-semibold mb-3">FRAGILITY + RISK SNAPSHOT</h2>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
          <div className="border rounded p-2">fallback count: {computed.fallbackCount}</div>
          <div className="border rounded p-2">unknown count: {computed.unknownCount}</div>
          <div className="border rounded p-2">missing eval count: {String(computed.missingEvalCount)}</div>
          <div className="border rounded p-2">missing trace count: {String(computed.missingTraceCount)}</div>
          <div className="border rounded p-2">override count: {String(computed.overrideCount)}</div>
          <div className="border rounded p-2">trend: unknown (no historical artifacts)</div>
        </div>
        <div className="mt-3">
          <p className="text-xs uppercase tracking-wide text-gray-500 mb-1">Top failure modes</p>
          {computed.failureModesDetailed.length > 0 ? (
            <ul className="list-disc list-inside text-sm text-red-700 space-y-1" data-testid="risk-failure-modes">
              {computed.failureModesDetailed.slice(0, 5).map((fm) => (
                <li key={fm.id}>
                  <span className="font-medium">{fm.title}</span>{' '}
                  <span className="text-xs text-gray-600">
                    (severity: {fm.severity}; systems: {(fm.systems_affected ?? []).join(', ') || 'unknown'};
                    frequency: {fm.frequency ?? 'unknown'}; trend: {fm.trend ?? 'unknown'})
                  </span>
                </li>
              ))}
            </ul>
          ) : computed.topFailureModes.length === 0 ? (
            <div className="text-sm text-gray-500">unknown</div>
          ) : (
            <ul className="list-disc list-inside text-sm text-red-700 space-y-1">
              {computed.topFailureModes.map((risk, idx) => (
                <li key={`${risk}-${idx}`}>{risk}</li>
              ))}
            </ul>
          )}
        </div>
      </section>

      <section className="bg-white border rounded p-4" data-testid="leverage-queue-panel">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold">LEVERAGE QUEUE</h2>
          <SourceBadge ds={computed.leverageSource} />
        </div>
        {computed.leverageQueue.length === 0 ? (
          <div className="text-sm text-gray-500">No source-backed recommendations available.</div>
        ) : (
          <div className="space-y-3">
            {computed.leverageQueue.map((item, idx) => (
              <article key={idx} className="border rounded p-3" data-testid="leverage-item">
                <div className="flex justify-between items-start gap-2">
                  <h3 className="font-medium">{item.title}</h3>
                  <span className="text-xs font-mono">score {item.leverage_score}</span>
                </div>
                <p className="text-sm mt-1">failure_prevented: {item.failure_prevented}</p>
                <p className="text-sm">signal_improved: {item.signal_improved}</p>
                <p className="text-xs text-gray-600 mt-1">systems affected: {item.systems_affected.join(', ')}</p>
                <div className="mt-2 flex flex-wrap gap-2 text-xs">
                  <span className="border rounded px-2 py-0.5">severity: {item.severity}</span>
                  <span className="border rounded px-2 py-0.5">effort: {item.effort}</span>
                  <span className="border rounded px-2 py-0.5">source: {item.source}</span>
                  <span className="border rounded px-2 py-0.5">confidence: {item.confidence}</span>
                </div>
                {item.source_artifacts_used && item.source_artifacts_used.length > 0 && (
                  <p className="text-xs text-gray-500 mt-1 font-mono break-all">
                    source_artifacts_used: {item.source_artifacts_used.join(', ')}
                  </p>
                )}
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="bg-white border rounded p-4" data-testid="rge-readiness-panel">
        <h2 className="font-semibold mb-3">RGE READINESS</h2>
        <div className="space-y-2 text-sm">
          <div data-testid="rge-operational-status">
            rge_can_operate:{' '}
            {rgeCanOperate === undefined ? (
              <span className="text-gray-500">unknown</span>
            ) : rgeCanOperate && sourceAllowsGreen ? (
              <span className="text-green-700">CAN OPERATE</span>
            ) : rgeCanOperate ? (
              <span className="text-amber-700">CAN OPERATE (unverified)</span>
            ) : (
              <span className="text-red-700">BLOCKED</span>
            )}
          </div>
          <div className="flex items-center gap-2">
            data_source: <SourceBadge ds={rgeSource} /> <ProvisionalBadge ds={rgeSource} />
          </div>
          <div>context_maturity_level: {String(rge?.context_maturity_level ?? 'unknown')}</div>
          <div>mg_kernel_status: {String(rge?.mg_kernel_status ?? 'unknown')}</div>
          <div>active_drift_legs: {(rge?.active_drift_legs ?? []).join(', ') || 'none'}</div>
          <div className="text-xs text-gray-700 font-semibold">RGE proposes only. CDE decides. SEL enforces.</div>
        </div>
      </section>
    </div>
  );
}
