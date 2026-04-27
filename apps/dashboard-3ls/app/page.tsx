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
  fallback_signal_count?: number | 'unknown';
  unknown_signal_count?: number | 'unknown';
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

interface SystemFlowNodeArtifact {
  system_id: string;
  upstream: string[];
  downstream: string[];
  artifacts_owned?: string[];
  primary_code_paths?: string[];
  purpose?: string;
}

interface SystemFlowArtifact {
  schema_version?: string;
  phase?: string;
  active_systems: SystemFlowNodeArtifact[];
  canonical_loop: string[];
  canonical_overlays: string[];
}

type SystemFlowState = 'ok' | 'missing' | 'invalid_schema';

interface SystemFlowResult {
  state: SystemFlowState;
  payload: SystemFlowArtifact | null;
  reason?: string;
  source_artifact?: string;
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

interface RankedSystemView {
  rank: number;
  system_id: string;
  classification: string;
  score: number;
  action: string;
  why_now: string;
  trust_gap_signals: string[];
  dependencies: { upstream: string[]; downstream: string[] };
  unlocks: string[];
  finish_definition: string;
  next_prompt: string;
  trust_state: string;
  unknown_justification?: string;
}

type PriorityArtifactState =
  | 'ok'
  | 'missing'
  | 'stale'
  | 'invalid_schema'
  | 'blocked_signal'
  | 'freeze_signal';

interface PriorityArtifactResult {
  state: PriorityArtifactState;
  payload: {
    schema_version?: string;
    phase?: string;
    top_5?: RankedSystemView[];
    ranked_systems?: RankedSystemView[];
    requested_candidate_set?: string[];
    requested_candidate_ranking?: Array<{
      requested_rank: number;
      global_rank?: number | null;
      system_id: string;
      classification: string;
      score?: number | null;
      recommended_action: string;
      why_now: string;
      prerequisite_systems: string[];
      trust_gap_signals: string[];
      finish_definition: string;
      risk_if_built_before_prerequisites: string;
      rank_explanation: string;
      prerequisite_explanation: string;
      safe_next_action: string;
      build_now_assessment: string;
      why_not_higher: string;
      why_not_lower: string;
      minimum_safe_prompt_scope: string;
      dependency_warning_level: string;
      evidence_summary: string;
      ambiguity_reason?: string;
    }>;
    ambiguous_requested_candidates?: Array<{ system_id: string; ambiguity_reason: string }>;
  } | null;
  generated_at?: string;
  reason?: string;
}

interface LeverageItem {
  title: string;
  failure_prevented: string;
  signal_improved: string;
  systems_affected: string[];
  severity: 'high' | 'medium' | 'low';
  effort: 'high' | 'medium' | 'low' | 'unknown';
  source: 'artifact' | 'derived' | 'fallback';
  // Preserve the declared confidence label exactly as it appears in the
  // source artifact (e.g. 'artifact_backed', 'derived_estimate',
  // 'unknown') so a provisional item is never displayed as fully
  // artifact-backed.
  confidence: string;
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
  const [priority, setPriority] = useState<PriorityArtifactResult | null>(null);
  const [systemFlow, setSystemFlow] = useState<SystemFlowResult | null>(null);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [overlayTrust, setOverlayTrust] = useState(true);
  const [overlayDataSource, setOverlayDataSource] = useState(true);
  const [overlayControlPath, setOverlayControlPath] = useState(true);
  const [filterBrokenOnly, setFilterBrokenOnly] = useState(false);
  const [filterFallbackOnly, setFilterFallbackOnly] = useState(false);
  const [filterCanonicalLoopOnly, setFilterCanonicalLoopOnly] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const [healthRes, intelligenceRes, systemsRes, rgeRes, priorityRes] = await Promise.all([
          fetch('/api/health'),
          fetch('/api/intelligence'),
          fetch('/api/systems'),
          fetch('/api/rge/analysis'),
          fetch('/api/priority'),
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

        // The priority endpoint is allowed to be missing/stale/invalid — the
        // panel itself handles those states. A non-200 response is treated as
        // a soft missing artifact, not a hard dashboard failure.
        const priorityData: PriorityArtifactResult = priorityRes.ok
          ? await priorityRes.json()
          : { state: 'missing', payload: null, reason: 'priority_endpoint_unavailable' };

        setHealth(healthData);
        setIntelligence(intelligenceData);
        setSystemsEnvelope(systemsData);
        setRge(rgeData);
        setPriority(priorityData);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    };

    fetchData();

    fetch('/api/system-flow')
      .then(async (res) => {
        if (!res.ok) {
          setSystemFlow({ state: 'missing', payload: null, reason: `http_${res.status}` });
          return;
        }
        const payload = (await res.json()) as SystemFlowResult;
        setSystemFlow(payload);
      })
      .catch(() => {
        setSystemFlow({ state: 'missing', payload: null, reason: 'fetch_failed' });
      });
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
    const fallbackCount: number | 'unknown' =
      apiRisk?.fallback_signal_count ?? sourceMix.stub_fallback;
    const unknownCount: number | 'unknown' =
      apiRisk?.unknown_signal_count ?? sourceMix.unknown;
    const fallbackCountForBoost = typeof fallbackCount === 'number' ? fallbackCount : 0;
    const unknownCountForBoost = typeof unknownCount === 'number' ? unknownCount : 0;
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
        failure_prevented: 'Untraceable enforcement signals',
        signal_improved: 'Proof-chain lineage completeness',
        systems_affected: ['LIN', 'CDE', 'SEL'],
        severity: 'high',
        effort: 'medium',
        source: 'derived',
        confidence: 'derived',
      });
    }

    if (fallbackCountForBoost > 0) {
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
        const repeatBoost = fallbackCountForBoost > 0 || unknownCountForBoost > 0 ? 1.15 : 1;
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
          item.source_artifacts_used.length > 0 &&
          Array.isArray(item.systems_affected) &&
          item.systems_affected.length > 0
      )
      .map((item) => {
        const itemDS = item.data_source ?? 'unknown';
        // Map the item's declared data_source to the local source label,
        // never assume 'artifact' just because the item exists.
        const source: 'artifact' | 'derived' | 'fallback' =
          itemDS === 'artifact_store' || itemDS === 'repo_registry'
            ? 'artifact'
            : itemDS === 'derived' || itemDS === 'derived_estimate'
            ? 'derived'
            : 'fallback';
        return {
          title: item.title,
          failure_prevented: item.failure_prevented,
          signal_improved: item.signal_improved,
          systems_affected: item.systems_affected,
          severity: item.severity,
          effort: (item.estimated_effort ?? 'unknown') as 'high' | 'medium' | 'low' | 'unknown',
          source,
          confidence: item.confidence ?? 'unknown',
          leverage_score: item.leverage_score,
          source_artifacts_used: item.source_artifacts_used,
        };
      })
      .sort((a, b) => b.leverage_score - a.leverage_score)
      .slice(0, 5);

    const leverageQueue = apiLeverage.length > 0
      ? apiLeverage
      : derivedLeverage.map((d) => ({ ...d, source_artifacts_used: [] as string[] }));

    const graphPayload = systemFlow?.state === 'ok' ? systemFlow.payload : null;
    const graphNodesRaw = graphPayload?.active_systems ?? [];
    const graphNodeIds = new Set(graphNodesRaw.map((n) => n.system_id));
    const healthById = new Map(systems.map((s) => [s.system_id, s]));
    const rankedById = new Map(
      (priority?.payload?.ranked_systems ?? []).map((row) => [row.system_id, row] as const)
    );

    const graphNodes = graphNodesRaw.map((node) => {
      const healthNode = healthById.get(node.system_id);
      const ds = (healthNode?.data_source ?? 'unknown') as DataSource;
      const sourceClass =
        ds === 'artifact_store' || ds === 'repo_registry'
          ? 'artifact'
          : ds === 'unknown' || ds === 'stub_fallback'
          ? 'fallback'
          : 'inferred';
      return {
        ...node,
        status: healthNode?.status ?? 'unknown',
        data_source: ds,
        sourceClass,
        trust_gap_signals: rankedById.get(node.system_id)?.trust_gap_signals ?? [],
      };
    });

    const graphEdges = graphNodesRaw.flatMap((node) =>
      (node.upstream ?? []).map((upstream) => {
        const sourceNode = healthById.get(upstream);
        const targetNode = healthById.get(node.system_id);
        const missingSource = !graphNodeIds.has(upstream);
        const sourceBacked =
          sourceNode &&
          ((sourceNode.data_source ?? 'unknown') === 'artifact_store' ||
            (sourceNode.data_source ?? 'unknown') === 'repo_registry');
        const targetBacked =
          targetNode &&
          ((targetNode.data_source ?? 'unknown') === 'artifact_store' ||
            (targetNode.data_source ?? 'unknown') === 'repo_registry');

        return {
          source: upstream,
          target: node.system_id,
          kind: missingSource ? 'broken' : sourceBacked && targetBacked ? 'artifact_backed' : 'inferred',
          canonical:
            (graphPayload?.canonical_loop ?? []).includes(upstream) &&
            (graphPayload?.canonical_loop ?? []).includes(node.system_id),
          overlay:
            (graphPayload?.canonical_overlays ?? []).includes(upstream) ||
            (graphPayload?.canonical_overlays ?? []).includes(node.system_id),
        };
      })
    );

    const brokenNodeIds = new Set(
      graphEdges.filter((e) => e.kind === 'broken').flatMap((e) => [e.source, e.target])
    );
    const visibleNodes = graphNodes.filter((node) => {
      if (filterBrokenOnly && !brokenNodeIds.has(node.system_id)) return false;
      if (filterFallbackOnly && node.sourceClass !== 'fallback') return false;
      if (filterCanonicalLoopOnly && !(graphPayload?.canonical_loop ?? []).includes(node.system_id))
        return false;
      return true;
    });
    const visibleNodeIds = new Set(visibleNodes.map((n) => n.system_id));
    const visibleEdges = graphEdges.filter(
      (edge) => visibleNodeIds.has(edge.target) || visibleNodeIds.has(edge.source)
    );

    const selected = selectedNode ? graphNodes.find((n) => n.system_id === selectedNode) ?? null : null;
    const selectedRanked = selected ? rankedById.get(selected.system_id) : null;
    const selectedUpstream = selected ? selected.upstream : [];
    const selectedDownstream = selected ? selected.downstream : [];

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
      graphState: systemFlow?.state ?? 'missing',
      graphReason: systemFlow?.reason ?? null,
      graphSourceArtifact: systemFlow?.source_artifact ?? null,
      graphNodes: visibleNodes,
      graphEdges: visibleEdges,
      graphCanonicalLoop: graphPayload?.canonical_loop ?? [],
      graphSelected: selected,
      graphSelectedRanked: selectedRanked,
      graphSelectedUpstream: selectedUpstream,
      graphSelectedDownstream: selectedDownstream,
    };
  }, [
    health,
    intelligence,
    systemsEnvelope,
    rge,
    systemFlow,
    priority,
    selectedNode,
    filterBrokenOnly,
    filterFallbackOnly,
    filterCanonicalLoopOnly,
  ]);

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

      <section className="bg-white border rounded p-4" data-testid="system-flow-graph-panel">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold">3LS SYSTEM FLOW (TRUST-AWARE)</h2>
          <div className="text-xs text-gray-500 font-mono">
            source: {computed.graphSourceArtifact ?? 'missing_artifact'}
          </div>
        </div>

        {computed.graphState !== 'ok' ? (
          <div className="border border-red-300 bg-red-50 rounded p-3 text-sm text-red-800" data-testid="system-flow-fail-closed">
            3LS System Flow unavailable ({computed.graphState}). Fail-closed: flow panel remains in degraded mode until a valid artifact is available.
            {computed.graphReason ? <span className="ml-1 font-mono">reason={computed.graphReason}</span> : null}
          </div>
        ) : (
          <>
            <div className="flex flex-wrap gap-2 mb-3 text-xs">
              <button className={`border rounded px-2 py-1 ${overlayTrust ? 'bg-blue-50 border-blue-300' : ''}`} onClick={() => setOverlayTrust((v) => !v)}>
                Trust overlay
              </button>
              <button className={`border rounded px-2 py-1 ${overlayDataSource ? 'bg-blue-50 border-blue-300' : ''}`} onClick={() => setOverlayDataSource((v) => !v)}>
                Data source overlay
              </button>
              <button className={`border rounded px-2 py-1 ${overlayControlPath ? 'bg-blue-50 border-blue-300' : ''}`} onClick={() => setOverlayControlPath((v) => !v)}>
                Control path overlay
              </button>
              <button className={`border rounded px-2 py-1 ${filterBrokenOnly ? 'bg-red-50 border-red-300' : ''}`} onClick={() => setFilterBrokenOnly((v) => !v)}>
                Show only broken systems
              </button>
              <button className={`border rounded px-2 py-1 ${filterFallbackOnly ? 'bg-amber-50 border-amber-300' : ''}`} onClick={() => setFilterFallbackOnly((v) => !v)}>
                Show only fallback systems
              </button>
              <button className={`border rounded px-2 py-1 ${filterCanonicalLoopOnly ? 'bg-indigo-50 border-indigo-300' : ''}`} onClick={() => setFilterCanonicalLoopOnly((v) => !v)}>
                Show only canonical loop
              </button>
            </div>

            {computed.graphNodes.length === 0 ? (
              <div className="mt-3 border border-amber-300 bg-amber-50 rounded p-3 text-sm text-amber-800" data-testid="system-flow-empty">
                Flow artifact loaded but contains zero active systems. Treat as degraded until upstream artifact generation restores node rows.
              </div>
            ) : null}


            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {computed.graphNodes.map((node) => {
                const trustClass =
                  node.status === 'healthy'
                    ? 'bg-green-50 border-green-300'
                    : node.status === 'warning'
                    ? 'bg-amber-50 border-amber-300'
                    : node.status === 'critical'
                    ? 'bg-red-50 border-red-300'
                    : 'bg-gray-50 border-gray-300';
                const controlPath =
                  computed.graphCanonicalLoop.includes(node.system_id) && overlayControlPath;
                return (
                  <button
                    type="button"
                    key={node.system_id}
                    data-testid={`flow-node-${node.system_id}`}
                    onClick={() => setSelectedNode(node.system_id)}
                    className={`text-left border rounded p-3 ${overlayTrust ? trustClass : ''} ${
                      controlPath ? 'ring-2 ring-indigo-300' : ''
                    }`}
                  >
                    <div className="font-mono font-semibold">{node.system_id}</div>
                    {overlayTrust ? <div className="text-xs">trust: {node.status}</div> : null}
                    {overlayDataSource ? (
                      <div className="text-xs">
                        source: {node.sourceClass} ({node.data_source})
                      </div>
                    ) : null}
                  </button>
                );
              })}
            </div>

            <div className="mt-3 border rounded p-3" data-testid="flow-edge-list">
              <div className="text-xs uppercase tracking-wide text-gray-500 mb-2">Edges</div>
              <ul className="space-y-1 text-xs font-mono">
                {computed.graphEdges.map((edge, idx) => (
                  <li
                    key={`${edge.source}-${edge.target}-${idx}`}
                    data-testid={edge.kind === 'broken' ? 'flow-edge-broken' : undefined}
                    className={
                      edge.kind === 'broken'
                        ? 'text-red-700'
                        : edge.kind === 'artifact_backed'
                        ? 'text-gray-800'
                        : 'text-gray-500'
                    }
                  >
                    {edge.source} → {edge.target} [{edge.kind === 'artifact_backed' ? 'solid' : edge.kind === 'inferred' ? 'dashed' : 'broken/red'}]
                  </li>
                ))}
              </ul>
            </div>

            <div className="mt-3 border rounded p-3 text-xs" data-testid="flow-legend">
              <div className="font-semibold mb-1">Legend</div>
              <div>Node colors: green=trusted, yellow=watch, red=critical, gray=unknown.</div>
              <div>Edge types: solid=artifact-backed, dashed=inferred, red=broken.</div>
            </div>

            {computed.graphSelected && (
              <div className="mt-3 border rounded p-3 text-sm" data-testid="flow-node-detail">
                <div className="font-semibold font-mono">{computed.graphSelected.system_id}</div>
                <div className="text-xs text-gray-600 mt-1">upstream dependencies: {computed.graphSelectedUpstream.join(', ') || 'none'}</div>
                <div className="text-xs text-gray-600">downstream systems: {computed.graphSelectedDownstream.join(', ') || 'none'}</div>
                <div className="text-xs text-gray-600">
                  trust_gap_signals:{' '}
                  {computed.graphSelectedRanked?.trust_gap_signals?.join(', ') || computed.graphSelected.trust_gap_signals.join(', ') || 'none'}
                </div>
                <div className="text-xs text-gray-600 break-all">
                  artifact refs:{' '}
                  {[...(computed.graphSelected.artifacts_owned ?? []), ...(computed.graphSelected.primary_code_paths ?? [])].join(', ') || 'none'}
                </div>
              </div>
            )}
          </>
        )}
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
          <div className="border rounded p-2">fallback count: {String(computed.fallbackCount)}</div>
          <div className="border rounded p-2">unknown count: {String(computed.unknownCount)}</div>
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

      <NextSystemsToFinishPanel result={priority} />

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

// ---------------------------------------------------------------------------
// D3L-01 — "Next Systems to Finish" panel.
//
// Strict visualization-only: renders whatever the TLS-04 priority artifact
// declares. NEVER reorders, scores, or classifies. Renders explicit states
// when the artifact is missing, stale, schema-invalid, or carries a
// freeze_signal / blocked_signal control_signal asserted by an upstream
// canonical owner.
// ---------------------------------------------------------------------------
function NextSystemsToFinishPanel({ result }: { result: PriorityArtifactResult | null }) {
  if (!result) {
    return (
      <section
        className="bg-white border rounded p-4"
        data-testid="next-systems-panel"
        data-state="loading"
      >
        <h2 className="font-semibold mb-3">NEXT SYSTEMS TO FINISH</h2>
        <p className="text-sm text-gray-500">Loading priority artifact…</p>
      </section>
    );
  }

  const stateMessages: Record<PriorityArtifactState, { tone: string; label: string; help: string }> = {
    ok: { tone: 'bg-green-50 border-green-300 text-green-800', label: 'ARTIFACT OK', help: '' },
    missing: {
      tone: 'bg-red-50 border-red-300 text-red-800',
      label: 'ARTIFACT MISSING',
      help: 'Run scripts/build_tls_dependency_priority.py to publish artifacts/system_dependency_priority_report.json.',
    },
    stale: {
      tone: 'bg-amber-50 border-amber-300 text-amber-800',
      label: 'ARTIFACT STALE',
      help: 'Re-run the TLS pipeline to refresh.',
    },
    invalid_schema: {
      tone: 'bg-red-50 border-red-300 text-red-800',
      label: 'ARTIFACT SCHEMA INVALID',
      help: 'Schema mismatch — pipeline must be re-validated before relying on this panel.',
    },
    blocked_signal: {
      tone: 'bg-red-50 border-red-300 text-red-800',
      label: 'CONTROL SIGNAL: BLOCKED_SIGNAL',
      help: 'Upstream control authority asserted blocked_signal on the priority recommendation.',
    },
    freeze_signal: {
      tone: 'bg-orange-50 border-orange-300 text-orange-800',
      label: 'CONTROL SIGNAL: FREEZE_SIGNAL',
      help: 'Upstream control authority asserted freeze_signal on the priority recommendation.',
    },
  };

  const banner = stateMessages[result.state];
  const top5 = result.payload?.top_5 ?? [];
  const requestedSet = result.payload?.requested_candidate_set ?? [];
  const requestedRanking = result.payload?.requested_candidate_ranking ?? [];
  const ambiguousRequested = result.payload?.ambiguous_requested_candidates ?? [];

  return (
    <section
      className="bg-white border rounded p-4"
      data-testid="next-systems-panel"
      data-state={result.state}
    >
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-semibold">NEXT SYSTEMS TO FINISH</h2>
        <span
          className={`border rounded px-2 py-0.5 text-xs font-mono ${banner.tone}`}
          data-testid="next-systems-state-badge"
        >
          {banner.label}
        </span>
      </div>

      {result.state !== 'ok' && (
        <div
          className={`border rounded p-3 mb-3 text-sm ${banner.tone}`}
          data-testid="next-systems-state-banner"
        >
          <p className="font-semibold">{banner.label}</p>
          {banner.help && <p className="text-xs mt-1">{banner.help}</p>}
          {result.reason && (
            <p className="text-xs mt-1 font-mono break-all">reason: {result.reason}</p>
          )}
        </div>
      )}

      {top5.length === 0 ? (
        <p className="text-sm text-gray-500" data-testid="next-systems-empty">
          No ranked systems available.
        </p>
      ) : (
        <ol className="space-y-3">
          {top5.map((row) => (
            <li
              key={`${row.rank}-${row.system_id}`}
              className="border rounded p-3"
              data-testid="next-system-row"
              data-system-id={row.system_id}
            >
              <div className="flex justify-between items-start gap-2">
                <div>
                  <h3 className="font-semibold">
                    #{row.rank} <span className="font-mono">{row.system_id}</span>{' '}
                    <span className="text-xs uppercase tracking-wide text-gray-500">
                      ({row.classification})
                    </span>
                  </h3>
                  <p className="text-xs text-gray-600">action: {row.action}</p>
                </div>
                <span className="text-xs font-mono">score {row.score}</span>
              </div>
              <p className="text-sm mt-2">why_now: {row.why_now}</p>
              <div className="mt-2 text-xs text-gray-700">
                trust_gap_signals:{' '}
                {row.trust_gap_signals.length === 0 ? (
                  <span className="text-gray-500">none</span>
                ) : (
                  row.trust_gap_signals.map((g) => (
                    <span
                      key={g}
                      className="inline-block border border-red-300 text-red-700 bg-red-50 rounded px-1.5 py-0.5 mr-1 mb-1 font-mono"
                    >
                      {g}
                    </span>
                  ))
                )}
              </div>
              <div className="mt-2 text-xs text-gray-700">
                dependencies: upstream=[{row.dependencies.upstream.join(', ') || '—'}], downstream=[
                {row.dependencies.downstream.join(', ') || '—'}]
              </div>
              <div className="mt-1 text-xs text-gray-700">
                unlocks: {row.unlocks.length === 0 ? '—' : row.unlocks.join(', ')}
              </div>
              <div className="mt-2 text-xs text-gray-600">
                <span className="font-semibold">finish: </span>
                {row.finish_definition}
              </div>
              <div className="mt-1 text-xs text-gray-500 font-mono break-all">
                next_prompt: {row.next_prompt}
              </div>
              {row.unknown_justification && (
                <p className="mt-2 text-xs text-amber-800 bg-amber-50 border border-amber-300 rounded px-2 py-1">
                  {row.unknown_justification}
                </p>
              )}
            </li>
          ))}
        </ol>
      )}

      <p className="text-xs text-gray-500 mt-3">
        Source: artifacts/system_dependency_priority_report.json (TLS-04). Dashboard does not compute ranking.
      </p>

      <div className="mt-5 border-t pt-4" data-testid="requested-candidate-ranking">
        <h3 className="font-semibold">Requested Candidate Ranking</h3>
        {requestedSet.length === 0 ? (
          <p className="text-sm text-gray-500 mt-2" data-testid="requested-candidate-empty">
            No requested candidate set provided. Run with --candidates H01,RFX,HOP,MET,METS.
          </p>
        ) : (
          <div className="mt-3 space-y-2">
            {ambiguousRequested.length > 0 && (
              <div className="border border-amber-300 bg-amber-50 rounded p-2 text-xs text-amber-900" data-testid="requested-candidate-ambiguity">
                Ambiguity warnings: {ambiguousRequested.map((row) => `${row.system_id} (${row.ambiguity_reason})`).join(', ')}
              </div>
            )}
            <ol className="space-y-2">
              {requestedRanking.map((row) => (
                <li key={`${row.requested_rank}-${row.system_id}`} className="border rounded p-2 text-sm" data-testid="requested-candidate-row">
                  <div className="flex justify-between">
                    <span className="font-semibold">
                      #{row.requested_rank} <span className="font-mono">{row.system_id}</span> ({row.classification})
                    </span>
                    <span className="text-xs font-mono">
                      global_rank: {row.global_rank ?? '—'} | score: {row.score ?? '—'}
                    </span>
                  </div>
                  <p className="text-xs mt-1">recommended_action: {row.recommended_action}</p>
                  <p className="text-xs">why_now: {row.why_now}</p>
                  <p className="text-xs">prerequisite_systems: {row.prerequisite_systems.join(', ') || '—'}</p>
                  <p className="text-xs">trust_gap_signals: {row.trust_gap_signals.join(', ') || 'none'}</p>
                  <p className="text-xs">finish_definition: {row.finish_definition}</p>
                  <p className="text-xs">build_now_signal: {row.risk_if_built_before_prerequisites}</p>
                  <details className="mt-2 border rounded p-2 bg-gray-50" data-testid="requested-candidate-details">
                    <summary className="text-xs font-semibold cursor-pointer">Explanation details</summary>
                    <div className="mt-2 space-y-1">
                      <p className="text-xs">rank_explanation: {row.rank_explanation}</p>
                      <p className="text-xs">prerequisites: {row.prerequisite_explanation}</p>
                      <p className="text-xs">safe_next_action: {row.safe_next_action}</p>
                      <p className="text-xs">build_now_assessment: {row.build_now_assessment}</p>
                      <p className="text-xs">minimum_safe_prompt_scope: {row.minimum_safe_prompt_scope}</p>
                      <p className="text-xs">evidence_summary: {row.evidence_summary}</p>
                    </div>
                  </details>
                  {row.ambiguity_reason && (
                    <p className="text-xs mt-1 text-amber-800">ambiguity_reason: {row.ambiguity_reason}</p>
                  )}
                </li>
              ))}
            </ol>
          </div>
        )}
      </div>
    </section>
  );
}
