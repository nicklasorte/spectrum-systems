'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { TrustGraphSection } from '@/components/TrustGraphSection';
import type { PriorityArtifactLoadResult } from '@/lib/artifactLoader';
import { getRankingBlockDecision } from '@/lib/rankingGate';
import type { SystemGraphPayload } from '@/lib/systemGraph';
import {
  buildLeverageQueueFromRoadmap,
  extractTopThreeRecommendations,
  type RoadmapArtifact,
  type TopThreeResult,
} from '@/lib/dashboardSimplified';
import type { RegistryGraphContract } from '@/lib/registryContract';
import type { ExplainSystemStateResult } from '@/lib/explainSystemState';
import type { DecisionLayerGroup } from '@/lib/decisionLayer';
import { humanTrustState } from '@/lib/humanStateLabels';
import type { MaturityReport } from '@/lib/maturity';
import { MVP_BOXES } from '@/lib/mvpGraph';

type TabKey = 'overview' | 'graph' | 'mvp' | 'decision' | 'prioritization' | 'maturity' | 'sources' | 'diagnostics' | 'roadmap' | 'raw';

// D3L-DATA-REGISTRY-01 — operator complexity budget for the Overview tab.
const OVERVIEW_QUEUE_MAX = 3;

type HealthPayload = {
  warnings?: string[];
};

type SystemFlowArtifact = {
  active_systems: Array<{ system_id: string; upstream: string[]; downstream: string[] }>;
  canonical_loop: string[];
  canonical_overlays: string[];
};

type SystemFlowResult = {
  state: 'ok' | 'missing' | 'invalid_schema';
  payload: SystemFlowArtifact | null;
  reason?: string;
  source_artifact?: string;
};

type RoadmapResponse = {
  state: 'ok' | 'missing';
  payload: RoadmapArtifact | null;
  table_markdown: string | null;
  source_artifacts_used?: string[];
};

type DecisionLayerResponse = {
  groups: DecisionLayerGroup[];
  allowed_active_node_ids: string[];
};

type IntelligenceBlockEnvelope = {
  data_source?: string;
  source_artifacts_used?: string[];
  warnings?: string[];
};

type FeedbackTheme = {
  theme: string;
  feedback_item_ids?: string[];
  candidate_ids?: string[];
  failure_prevented?: string;
};

type FeedbackLoopBlock = IntelligenceBlockEnvelope & {
  feedback_items_count?: number | 'unknown';
  eval_candidates_count?: number | 'unknown';
  policy_candidate_signals_count?: number | 'unknown';
  unresolved_feedback_count?: number | 'unknown';
  expired_feedback_count?: number | 'unknown';
  top_feedback_themes?: FeedbackTheme[];
  next_recommended_improvement_inputs?: string[];
  loop_status?: string;
};

type FailureExplanationPacket = {
  packet_id?: string;
  title?: string;
  failure_prevented?: string;
  signal_improved?: string;
  affected_systems?: string[];
  what_failed?: string;
  why_it_matters?: string;
  evidence_artifacts?: string[];
  constrained_loop_leg?: string;
  current_status?: string;
  next_recommended_input?: string;
  owner_recommendation?: string;
  unknowns?: string[];
  debug_summary?: string;
  source_artifacts_used?: string[];
};

type FailureExplanationPacketsBlock = IntelligenceBlockEnvelope & {
  packets?: FailureExplanationPacket[];
};

type OverrideAuditBlock = IntelligenceBlockEnvelope & {
  override_count?: number | 'unknown';
  overrides?: Array<Record<string, unknown>>;
  next_recommended_input?: string | null;
  reason_codes?: string[];
};

type FallbackItem = {
  system_id?: string;
  current_data_source?: string;
  replacement_signal_needed?: string;
  failure_prevented?: string;
  signal_improved?: string;
  priority?: string;
  source_artifacts_used?: string[];
};

type FallbackReductionPlanBlock = IntelligenceBlockEnvelope & {
  total_fallback_count?: number | 'unknown';
  high_leverage_fallback_count?: number | 'unknown';
  fallback_items?: FallbackItem[];
};

type ReplayDimensionEntry = { dimension?: string; status?: string; source?: string };
type LineageEdgeEntry = { edge?: string; status?: string; source?: string };

type ReplayLineageHardeningBlock = IntelligenceBlockEnvelope & {
  replay_dimensions_checked?: ReplayDimensionEntry[];
  lineage_links_checked?: LineageEdgeEntry[];
  gaps_observed?: string[];
  hardening_recommendations?: Array<Record<string, unknown>>;
  affected_systems?: string[];
};

type CandidateClosureItem = {
  candidate_id?: string;
  candidate_type?: string;
  current_state?: string;
  age_days?: number | 'unknown';
  stale_after_days?: number | 'unknown';
  affected_systems?: string[];
  next_recommended_input?: string;
  source_artifacts_used?: string[];
};

type CandidateClosureBlock = IntelligenceBlockEnvelope & {
  candidate_items?: CandidateClosureItem[];
  candidate_item_count?: number | 'unknown';
  stale_candidate_signal_count?: number | 'unknown';
};

type DependencyEntry = {
  artifact_path?: string;
  api_fields?: string[];
  dashboard_panels?: string[];
  keep_fold_remove?: string;
  rationale?: string;
};

type MetArtifactDependencyIndexBlock = IntelligenceBlockEnvelope & {
  artifact_dependencies?: DependencyEntry[];
};

type BlockedTrendField = { field?: string; reason?: string; current_value?: string };

type TrendFrequencyHonestyGateBlock = IntelligenceBlockEnvelope & {
  comparable_case_count?: number | 'unknown';
  required_case_count_for_trend?: number;
  trend_state?: string;
  frequency_state?: string;
  cases_needed?: number | 'unknown';
  blocked_trend_fields?: BlockedTrendField[];
};

type HandoffItem = {
  handoff_signal_id?: string;
  source_eval_candidate_id?: string;
  target_owner_recommendation?: string;
  target_loop_leg?: string;
  materialization_observation?: string;
  next_recommended_input?: string;
  source_artifacts_used?: string[];
};

type EvlHandoffObservationsBlock = IntelligenceBlockEnvelope & {
  handoff_items?: HandoffItem[];
  handoff_item_count?: number | 'unknown';
};

type OverrideEvidenceIntakeBlock = IntelligenceBlockEnvelope & {
  override_evidence_count?: number | 'unknown';
  evidence_status?: string;
  next_recommended_input?: string | null;
  reason_codes?: string[];
};

type ExplanationEntry = {
  explanation_id?: string;
  related_failure_packet?: string;
  what_failed?: string;
  where_in_loop?: string;
  next_recommended_input?: string;
  debug_readiness?: string;
  source_evidence?: string[];
};

type DebugExplanationIndexBlock = IntelligenceBlockEnvelope & {
  debug_target_minutes?: number;
  explanation_entries?: ExplanationEntry[];
  explanation_entry_count?: number | 'unknown';
};

type ClassifiedPath = {
  path?: string;
  classification?: string;
  merge_policy?: string;
};

type MetGeneratedArtifactClassificationBlock = IntelligenceBlockEnvelope & {
  classified_paths?: ClassifiedPath[];
  classified_path_count?: number | 'unknown';
};


type OwnerReadObservationItem = {
  owner_read_observation_id?: string;
  source_candidate_id?: string;
  read_observation_state?: string;
  recommended_owner_system?: string;
  next_recommended_input?: string;
  source_artifacts_used?: string[];
};

type OwnerReadObservationsBlock = IntelligenceBlockEnvelope & {
  owner_read_items?: OwnerReadObservationItem[];
};

type MaterializationObservationItem = {
  materialization_observation_id?: string;
  source_candidate_id?: string;
  owner_system_recommendation?: string;
  materialization_observation?: string;
  next_recommended_input?: string;
  observed_owner_artifact_refs?: string[];
};

type MaterializationObservationMapperBlock = IntelligenceBlockEnvelope & {
  materialization_observations?: MaterializationObservationItem[];
};

type ComparableCaseQualificationGateBlock = IntelligenceBlockEnvelope & {
  qualification_rules?: Record<string, unknown> | null;
  qualified_case_groups?: Array<Record<string, unknown>>;
};

type TrendReadyCasePackBlock = IntelligenceBlockEnvelope & {
  case_packs?: Array<Record<string, unknown>>;
};

type FoldCandidateProofCheckBlock = IntelligenceBlockEnvelope & {
  fold_candidates?: Array<Record<string, unknown>>;
};

type OperatorDebuggabilityDrillBlock = IntelligenceBlockEnvelope & {
  target_minutes?: number;
  drill_items?: Array<Record<string, unknown>>;
};

// MET-FULL-ROADMAP — non-owning cockpit blocks. Each block is observation only;
// authority remains with CDE/SEL/GOV/REL.
type MetRegistryStatusBlock = {
  registry_id?: string;
  status?: string;
  authority?: string;
  forbidden?: string[];
  invariant?: string;
  failure_prevented?: string[];
  signal_improved?: string[];
  upstream_dependencies?: string[];
  downstream_consumers?: string[];
  data_source?: string;
  source_artifacts_used?: string[];
  warnings?: string[];
};

type MetCockpitBlock = IntelligenceBlockEnvelope & {
  trust_observation?: string;
  weakest_loop_leg?: string;
  top_next_input_count?: number;
  owner_handoff_queue_count?: number;
  stale_candidate_pressure_state?: number | string;
  trend_readiness_state?: string;
  debug_readiness_state?: string;
  artifact_integrity_state?: string;
  outcome_attribution_state?: string;
  confidence_calibration_state?: string;
  recurrence_state?: string;
  anti_gaming_state?: string;
  status?: string;
};

type SliceCandidateItem = {
  slice_candidate_id?: string;
  affected_systems?: string[];
  recommended_owner_system?: string;
  readiness_state?: string;
  next_recommended_input?: string | null;
  source_artifacts_used?: string[];
};

type TopNextInputsBlock = IntelligenceBlockEnvelope & {
  items?: SliceCandidateItem[];
  status?: string;
};

type OwnerHandoffItem = {
  owner_read_observation_id?: string;
  source_candidate_id?: string;
  recommended_owner_system?: string;
  read_observation_state?: string;
  next_recommended_input?: string | null;
  source_artifacts_used?: string[];
};

type OwnerHandoffBlock = IntelligenceBlockEnvelope & {
  items?: OwnerHandoffItem[];
  status?: string;
};

type GenericRowsBlock = IntelligenceBlockEnvelope & {
  status?: string;
  [key: string]: unknown;
};

type IntelligencePayload = {
  feedback_loop?: FeedbackLoopBlock;
  feedback_loop_status?: string;
  unresolved_feedback_count?: number | 'unknown';
  failure_explanation_packets?: FailureExplanationPacketsBlock;
  override_audit?: OverrideAuditBlock;
  fallback_reduction_plan?: FallbackReductionPlanBlock;
  replay_lineage_hardening?: ReplayLineageHardeningBlock;
  candidate_closure?: CandidateClosureBlock;
  met_artifact_dependency_index?: MetArtifactDependencyIndexBlock;
  trend_frequency_honesty_gate?: TrendFrequencyHonestyGateBlock;
  evl_handoff_observations?: EvlHandoffObservationsBlock;
  override_evidence_intake?: OverrideEvidenceIntakeBlock;
  debug_explanation_index?: DebugExplanationIndexBlock;
  met_generated_artifact_classification?: MetGeneratedArtifactClassificationBlock;
  owner_read_observations?: OwnerReadObservationsBlock;
  materialization_observation_mapper?: MaterializationObservationMapperBlock;
  comparable_case_qualification_gate?: ComparableCaseQualificationGateBlock;
  trend_ready_case_pack?: TrendReadyCasePackBlock;
  fold_candidate_proof_check?: FoldCandidateProofCheckBlock;
  operator_debuggability_drill?: OperatorDebuggabilityDrillBlock;
  met_registry_status?: MetRegistryStatusBlock;
  met_cockpit?: MetCockpitBlock;
  top_next_inputs?: TopNextInputsBlock;
  owner_handoff?: OwnerHandoffBlock;
  stale_candidate_pressure?: GenericRowsBlock;
  trend_readiness?: GenericRowsBlock;
  override_evidence?: GenericRowsBlock;
  fold_safety?: GenericRowsBlock;
  outcome_attribution?: GenericRowsBlock;
  failure_reduction_signal?: GenericRowsBlock;
  recommendation_accuracy?: GenericRowsBlock;
  calibration_drift?: GenericRowsBlock;
  signal_confidence?: GenericRowsBlock;
  cross_run_consistency?: GenericRowsBlock;
  divergence_detection?: GenericRowsBlock;
  error_budget_observation?: GenericRowsBlock;
  freeze_recommendation_signal?: GenericRowsBlock;
  next_best_slice?: GenericRowsBlock;
  pqx_candidate_action_bundle?: GenericRowsBlock;
  counterfactuals?: GenericRowsBlock;
  earlier_intervention_signal?: GenericRowsBlock;
  recurring_failures?: GenericRowsBlock;
  recurrence_severity_signal?: GenericRowsBlock;
  debug_readiness?: GenericRowsBlock;
  time_to_explain?: GenericRowsBlock;
  metric_gaming_detection?: GenericRowsBlock;
  misleading_signal_detection?: GenericRowsBlock;
  signal_integrity?: GenericRowsBlock;
};

// MET-19-33 — operator complexity budget for compact MET sections.
const MET_COMPACT_ITEM_MAX = 5;

type OcBottleneckResponse = {
  state: 'ok' | 'unavailable' | 'invalid_schema' | 'stale_proof' | 'conflict_proof' | 'ambiguous';
  card: {
    overall_status: 'pass' | 'block' | 'freeze' | 'unknown';
    category: string;
    reason_code: string;
    owning_system: string | null;
    next_safe_action: string;
    source_artifact_type: 'dashboard_truth_projection' | 'operational_closure_bundle';
    warnings: string[];
  } | null;
  reason: string;
  sources?: string[];
};

const TABS: Array<{ key: TabKey; label: string }> = [
  { key: 'overview', label: 'Overview' },
  { key: 'graph', label: 'Graph' },
  { key: 'mvp', label: 'MVP Graph' },
  { key: 'decision', label: 'Decision Layer' },
  { key: 'prioritization', label: 'Prioritization' },
  { key: 'maturity', label: 'Maturity' },
  { key: 'sources', label: 'Sources' },
  { key: 'diagnostics', label: 'Diagnostics' },
  { key: 'roadmap', label: 'Roadmap' },
  { key: 'raw', label: 'Raw Artifacts' },
];

function Panel({ title, children, testId }: { title: string; children: React.ReactNode; testId?: string }) {
  return (
    <section
      data-testid={testId ?? 'overview-section'}
      className="bg-white dark:bg-slate-900 text-slate-950 dark:text-slate-100 border border-slate-200 dark:border-slate-700 rounded p-4 space-y-3"
    >
      <h2 className="font-semibold text-sm uppercase tracking-wide text-slate-900 dark:text-slate-100">{title}</h2>
      {children}
    </section>
  );
}

export default function DashboardPage() {
  const [activeTab, setActiveTab] = useState<TabKey>('overview');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [priority, setPriority] = useState<PriorityArtifactLoadResult | null>(null);
  const [flow, setFlow] = useState<SystemFlowResult | null>(null);
  const [graph, setGraph] = useState<SystemGraphPayload | null>(null);
  const [health, setHealth] = useState<HealthPayload | null>(null);
  const [roadmap, setRoadmap] = useState<RoadmapResponse | null>(null);
  const [intelligence, setIntelligence] = useState<IntelligencePayload | null>(null);
  const [contract, setContract] = useState<RegistryGraphContract | null>(null);
  const [explain, setExplain] = useState<ExplainSystemStateResult | null>(null);
  const [decisionLayer, setDecisionLayer] = useState<DecisionLayerResponse | null>(null);
  const [ocBottleneck, setOcBottleneck] = useState<OcBottleneckResponse | null>(null);
  const [maturity, setMaturity] = useState<(MaturityReport & { sources?: Record<string, string | null> }) | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const [healthRes, priorityRes, flowRes, graphRes, roadmapRes, intelligenceRes, contractRes, explainRes, decisionRes, ocRes, maturityRes] = await Promise.all([
          fetch('/api/health'),
          fetch('/api/priority'),
          fetch('/api/system-flow'),
          fetch('/api/system-graph'),
          fetch('/api/tls-roadmap'),
          fetch('/api/intelligence'),
          fetch('/api/registry-contract'),
          fetch('/api/explain-state'),
          fetch('/api/decision-layer'),
          fetch('/api/oc-bottleneck'),
          fetch('/api/maturity'),
        ]);

        const [healthData, priorityData, flowData, graphData, roadmapData, intelligenceData, contractData, explainData, decisionData, ocData, maturityData] = await Promise.all([
          healthRes.json(),
          priorityRes.json(),
          flowRes.json(),
          graphRes.json(),
          roadmapRes.json(),
          intelligenceRes.json(),
          contractRes.json(),
          explainRes.json(),
          decisionRes.json(),
          ocRes.json(),
          maturityRes.json(),
        ]);

        setHealth(healthData);
        setPriority(priorityData);
        setFlow(flowData);
        setGraph(graphData);
        setRoadmap(roadmapData);
        setIntelligence(intelligenceData);
        setContract(contractData);
        setExplain(explainData);
        setDecisionLayer(decisionData);
        setOcBottleneck(ocData);
        setMaturity(maturityData);
        setError(null);
      } catch (e) {
        setError(e instanceof Error ? e.message : 'dashboard_load_failure');
      } finally {
        setLoading(false);
      }
    };

    load();
  }, []);

  const trustPulse = useMemo(() => {
    const mix = graph?.source_mix ?? { artifact_store: 0, repo_registry: 0, derived: 0, stub_fallback: 0, missing: 0 };
    const total = Object.values(mix).reduce((sum, n) => sum + n, 0);
    const artifactBacked = (mix.artifact_store ?? 0) + (mix.repo_registry ?? 0);
    const stubFallback = mix.stub_fallback ?? 0;
    return {
      trust_state: graph?.trust_posture ?? 'unknown',
      artifact_backed_pct: total > 0 ? Math.round((artifactBacked / total) * 100) : 0,
      stub_fallback_pct: total > 0 ? Math.round((stubFallback / total) * 100) : 0,
      last_recompute: graph?.generated_at ?? 'unknown',
      warning_count: (graph?.warnings?.length ?? 0) + (health?.warnings?.length ?? 0),
    };
  }, [graph, health]);

  const topThree: TopThreeResult = useMemo(
    () => extractTopThreeRecommendations(priority, contract),
    [priority, contract],
  );
  const freshnessGate = (priority as unknown as { freshness_gate?: { ok: boolean; status: string; blocking_reasons?: string[]; recompute_command?: string } } | null)?.freshness_gate;
  const rankingDecision = useMemo(() => getRankingBlockDecision(priority), [priority]);
  const rankingBlocked = rankingDecision.blocked;

  const queueResult = useMemo(
    () => buildLeverageQueueFromRoadmap(
      roadmap?.payload ?? null,
      topThree.registry_backed_system_ids,
    ),
    [roadmap, topThree.registry_backed_system_ids],
  );

  const flowEdges = useMemo(() => {
    if (flow?.state !== 'ok' || !flow.payload) return [] as string[];
    const canonical = new Set(flow.payload.canonical_loop);
    return flow.payload.active_systems
      .filter((node) => canonical.has(node.system_id))
      .flatMap((node) => node.downstream.map((target) => ({ from: node.system_id, to: target })))
      .filter((edge) => canonical.has(edge.to))
      .map((edge) => `${edge.from} → ${edge.to}`);
  }, [flow]);

  const flowWarnings = useMemo(() => {
    const warnings: string[] = [];
    if (!flow || flow.state !== 'ok' || !flow.payload) {
      warnings.push('Missing artifact: artifacts/tls/system_registry_dependency_graph.json');
      return warnings;
    }
    if (flowEdges.length === 0) {
      warnings.push('No canonical edges retrieved from artifact; cannot render flow links.');
    }
    return warnings;
  }, [flow, flowEdges.length]);

  // Invariant violations: derived from graph warnings + missing artifacts.
  const invariantFindings = useMemo(() => {
    const out: Array<{ invariant: string; violated_by: string; source_artifact: string; affected_system: string; expected: string }> = [];
    if (!graph) return out;
    for (const warn of graph.warnings ?? []) {
      if (warn.startsWith('registry_contract_rejected_nodes')) {
        const ids = warn.split(':')[1] ?? '';
        out.push({
          invariant: 'no-invented-systems',
          violated_by: warn,
          source_artifact: 'artifacts/tls/system_registry_dependency_graph.json',
          affected_system: ids,
          expected: 'graph payload contains only registry-active nodes; non-registry labels are filtered',
        });
      }
      if (warn.startsWith('graph_contract_violation')) {
        out.push({
          invariant: 'graph-contract',
          violated_by: warn,
          source_artifact: 'artifacts/tls/system_registry_dependency_graph.json',
          affected_system: warn.split(':')[2] ?? 'unknown',
          expected: 'all nodes/edges resolve to registry-active systems',
        });
      }
      if (warn.startsWith('missing_artifact')) {
        out.push({
          invariant: 'artifact-first',
          violated_by: warn,
          source_artifact: warn.split(':')[1] ?? 'unknown',
          affected_system: 'dashboard',
          expected: 'fail-closed when required artifact missing',
        });
      }
    }
    return out;
  }, [graph]);

  if (loading) {
    return <main className="p-6">Loading dashboard cockpit…</main>;
  }

  if (error) {
    return <main className="p-6 text-red-700">Dashboard failure: {error}</main>;
  }

  return (
    <main className="p-3 sm:p-6 space-y-4 max-w-full overflow-x-hidden">
      <header>
        <h1 className="text-xl sm:text-2xl font-bold">Dashboard 3LS — Registry-Aligned Operator Cockpit</h1>
        <p className="text-xs text-gray-600 dark:text-slate-300">
          Graph nodes are registry-backed only. Roadmap labels, batch IDs, and prompt labels never become nodes.
        </p>
      </header>

      <nav className="sticky top-0 z-10 bg-white pb-1 flex flex-wrap gap-2 overflow-x-auto" aria-label="Dashboard tabs">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => setActiveTab(tab.key)}
            data-testid={`tab-${tab.key}`}
            className={`px-3 py-1.5 rounded border text-xs sm:text-sm whitespace-nowrap ${activeTab === tab.key ? 'bg-gray-900 text-white' : 'bg-white'}`}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      {activeTab === 'overview' && (
        <div className="space-y-4" data-testid="overview-tab">
          <Panel title="A. Trust Pulse">
            {(() => {
              const human = humanTrustState(trustPulse.trust_state);
              return (
                <ul className="text-sm space-y-1">
                  <li>
                    Status: <strong data-testid="trust-pulse-label">{human.label}</strong>
                  </li>
                  <li className="text-xs text-gray-600 dark:text-slate-300">Reason: {human.description}</li>
                  <li>artifact-backed %: <strong>{trustPulse.artifact_backed_pct}%</strong></li>
                  <li>stub fallback %: <strong>{trustPulse.stub_fallback_pct}%</strong></li>
                  <li>last recompute: <strong>{trustPulse.last_recompute}</strong></li>
                  <li>warning count: <strong>{trustPulse.warning_count}</strong></li>
                  <li>registry-active count: <strong data-testid="registry-active-count">{contract?.allowed_active_node_ids?.length ?? 0}</strong></li>
                </ul>
              );
            })()}
          </Panel>

          <Panel title="A2. MET Cockpit (non-owning observations)" testId="met-cockpit-section">
            {(() => {
              const cockpit = intelligence?.met_cockpit;
              const registry = intelligence?.met_registry_status;
              const topNext = intelligence?.top_next_inputs?.items ?? [];
              const handoff = intelligence?.owner_handoff?.items ?? [];
              const integrityState = cockpit?.artifact_integrity_state ?? 'unknown';
              return (
                <div className="text-sm space-y-2" data-testid="met-cockpit-card">
                  <p className="text-xs text-gray-700 dark:text-slate-300">
                    Authority: <strong data-testid="met-authority">{registry?.authority ?? 'unknown'}</strong> · Registry: <strong data-testid="met-registry-status">{registry?.status ?? 'unknown'}</strong>
                  </p>
                  <ul className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 text-xs">
                    <li>weakest loop leg: <strong>{cockpit?.weakest_loop_leg ?? 'unknown'}</strong></li>
                    <li>stale candidate pressure: <strong>{String(cockpit?.stale_candidate_pressure_state ?? 'unknown')}</strong></li>
                    <li>owner handoff queue: <strong>{cockpit?.owner_handoff_queue_count ?? 0}</strong></li>
                    <li>trend readiness: <strong>{cockpit?.trend_readiness_state ?? 'unknown'}</strong></li>
                    <li>debug readiness: <strong>{cockpit?.debug_readiness_state ?? 'unknown'}</strong></li>
                    <li>artifact integrity: <strong>{integrityState}</strong></li>
                    <li>outcome attribution: <strong>{cockpit?.outcome_attribution_state ?? 'unknown'}</strong></li>
                    <li>confidence/calibration: <strong>{cockpit?.confidence_calibration_state ?? 'unknown'}</strong></li>
                    <li>recurrence state: <strong>{cockpit?.recurrence_state ?? 'unknown'}</strong></li>
                    <li>anti-gaming state: <strong>{cockpit?.anti_gaming_state ?? 'unknown'}</strong></li>
                  </ul>

                  <div data-testid="met-top-next-inputs-section">
                    <p className="text-xs font-semibold mt-2">Top 3 next inputs (candidate signals only):</p>
                    {topNext.length === 0 ? (
                      <p className="text-xs text-amber-700 dark:text-amber-300">Top next inputs unknown.</p>
                    ) : (
                      <ul className="list-disc ml-5 text-xs">
                        {topNext.slice(0, 3).map((item, idx) => (
                          <li key={`${item.slice_candidate_id}-${idx}`} data-testid="met-top-next-input-item">
                            <strong>{item.slice_candidate_id ?? 'unknown'}</strong>
                            {' '}— affects {(item.affected_systems ?? []).join(', ') || 'unknown'} · owner: {item.recommended_owner_system ?? 'unknown'} · readiness: {item.readiness_state ?? 'unknown'}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>

                  <div data-testid="met-owner-handoff-section">
                    <p className="text-xs font-semibold mt-2">Owner handoff queue (signals only):</p>
                    {handoff.length === 0 ? (
                      <p className="text-xs text-amber-700 dark:text-amber-300">Owner handoff queue empty or unknown.</p>
                    ) : (
                      <ul className="list-disc ml-5 text-xs">
                        {handoff.slice(0, 5).map((item, idx) => (
                          <li key={`${item.owner_read_observation_id}-${idx}`} data-testid="met-owner-handoff-item">
                            <strong>{item.source_candidate_id ?? 'unknown'}</strong>
                            {' '}— state {item.read_observation_state ?? 'unknown'} · owner {item.recommended_owner_system ?? 'unknown'}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>

                  <p className="text-xs text-gray-500 dark:text-slate-400">
                    sources: {(cockpit?.source_artifacts_used ?? []).slice(0, 3).join(', ') || 'unknown'}
                  </p>
                  <p className="text-xs text-gray-500 dark:text-slate-400">
                    MET is non-owning. CDE/SEL/GOV/REL retain authority.
                  </p>
                </div>
              );
            })()}
          </Panel>

          <Panel title="A3. MET Outcome / Calibration / Integrity" testId="met-outcome-attribution-section">
            {(() => {
              const outcomes = (intelligence?.outcome_attribution?.outcome_entries as Array<Record<string, unknown>> | undefined) ?? [];
              const calBuckets = (intelligence?.calibration_drift?.calibration_buckets as Array<Record<string, unknown>> | undefined) ?? [];
              const recurClusters = (intelligence?.recurring_failures?.clusters as Array<Record<string, unknown>> | undefined) ?? [];
              const integrityChecks = (intelligence?.signal_integrity?.integrity_checks as Array<Record<string, unknown>> | undefined) ?? [];
              return (
                <div className="text-xs space-y-2">
                  <div data-testid="met-outcome-attribution-list">
                    <p className="font-semibold">Outcome attribution (top {Math.min(outcomes.length, MET_COMPACT_ITEM_MAX)} of {outcomes.length}):</p>
                    {outcomes.length === 0 ? (
                      <p className="text-amber-700 dark:text-amber-300">Outcome attribution unknown.</p>
                    ) : (
                      <ul className="list-disc ml-5">
                        {outcomes.slice(0, MET_COMPACT_ITEM_MAX).map((entry, idx) => (
                          <li key={`outcome-${idx}`} data-testid="met-outcome-attribution-item">
                            <strong>{String(entry.change_or_candidate_id ?? 'unknown')}</strong> — status: {String(entry.status ?? 'unknown')}; delta: {String(entry.observed_delta ?? 'unknown')}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                  <div data-testid="met-calibration-drift-list">
                    <p className="font-semibold">Calibration drift:</p>
                    {calBuckets.length === 0 ? (
                      <p className="text-amber-700 dark:text-amber-300">Calibration drift unknown.</p>
                    ) : (
                      <ul className="list-disc ml-5">
                        {calBuckets.slice(0, MET_COMPACT_ITEM_MAX).map((bucket, idx) => (
                          <li key={`bucket-${idx}`}>
                            <strong>{String(bucket.bucket ?? 'unknown')}</strong> — drift: {String(bucket.drift_state ?? 'unknown')}; cases needed: {String(bucket.cases_needed ?? 'unknown')}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                  <div data-testid="met-recurring-failures-list">
                    <p className="font-semibold">Recurring failure clusters:</p>
                    {recurClusters.length === 0 ? (
                      <p className="text-amber-700 dark:text-amber-300">Recurring failures unknown.</p>
                    ) : (
                      <ul className="list-disc ml-5">
                        {recurClusters.slice(0, MET_COMPACT_ITEM_MAX).map((cluster, idx) => (
                          <li key={`cluster-${idx}`}>
                            <strong>{String(cluster.cluster_id ?? 'unknown')}</strong> — state: {String(cluster.recurrence_state ?? 'unknown')}; cases needed: {String(cluster.cases_needed ?? 'unknown')}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                  <div data-testid="met-signal-integrity-list">
                    <p className="font-semibold">Signal integrity (anti-gaming):</p>
                    {integrityChecks.length === 0 ? (
                      <p className="text-amber-700 dark:text-amber-300">Signal integrity unknown.</p>
                    ) : (
                      <ul className="list-disc ml-5">
                        {integrityChecks.slice(0, MET_COMPACT_ITEM_MAX).map((check, idx) => (
                          <li key={`integrity-${idx}`}>
                            <strong>{String(check.check_id ?? 'unknown')}</strong> — {String(check.state ?? 'unknown')}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                </div>
              );
            })()}
          </Panel>

          <Panel title="B. Simple 3LS Flowchart">
            <p className="text-sm">Core: {(flow?.payload?.canonical_loop ?? []).join(' → ') || 'unavailable'}</p>
            <p className="text-sm">Overlay: {(flow?.payload?.canonical_overlays ?? []).join(' / ') || 'unavailable'}</p>
            <ul data-testid="flow-edges" className="text-xs list-disc ml-5">
              {flowEdges.map((edge) => <li key={edge}>{edge}</li>)}
            </ul>
            {flowWarnings.map((w) => (
              <p key={w} className="text-xs text-red-700" data-testid="flow-warning">⚠ {w}</p>
            ))}
          </Panel>

          <Panel title="C. Top 3 Recommendations (TLS artifact only)">
            {rankingBlocked ? (
              <div data-testid="top3-fail-closed" className="border border-red-300 dark:border-red-700 bg-red-50 dark:bg-red-950 p-3 rounded text-sm">
                <p className="font-semibold text-red-700 dark:text-red-300">Top 3 hidden — freshness gate failed</p>
                <p className="text-xs text-red-700 dark:text-red-300">reason: <strong>{rankingDecision.reason}</strong></p>
                <p className="text-xs mt-1 break-all text-red-700 dark:text-red-300">regenerate: <code>{rankingDecision.recompute_command}</code></p>
              </div>
            ) : (
              <>
            {topThree.warning && <p data-testid="top3-warning" className="text-sm text-red-700 dark:text-red-300">⚠ {topThree.warning}</p>}
            {(rankingDecision.recompute_command ?? topThree.recompute_command) && (
              <p data-testid="top3-recompute-command" className="text-xs text-gray-700 dark:text-gray-300 break-all">
                regenerate: <code className="text-xs">{rankingDecision.recompute_command ?? topThree.recompute_command}</code>
              </p>
            )}
            <div className="space-y-2">
              {topThree.cards.map((card) => (
                <article
                  key={`${card.rank}-${card.system_id}`}
                  data-testid="top3-card"
                  data-registry-backed={card.is_registry_backed ? 'true' : 'false'}
                  className={`border rounded p-3 text-sm ${card.is_registry_backed ? 'border-blue-300' : 'border-amber-400 bg-amber-50'}`}
                >
                  <header className="flex items-center justify-between gap-2">
                    <strong className="text-base">#{card.rank} {card.system_id}</strong>
                    {card.is_registry_backed ? (
                      <span className="text-xs px-2 py-0.5 rounded bg-blue-100 text-blue-800 border border-blue-300">registry-backed</span>
                    ) : (
                      <span className="text-xs px-2 py-0.5 rounded bg-amber-100 text-amber-900 border border-amber-400" data-testid="top3-non-registry-warning">
                        text-only · not a registry system
                      </span>
                    )}
                  </header>
                  <p data-testid="top3-card-fix"><strong>Fix:</strong> {card.what_to_fix}</p>
                  <p data-testid="top3-card-why" className="text-sm"><strong>Why:</strong> {card.why_now}</p>
                  <p data-testid="top3-card-next" className="text-sm"><strong>Next:</strong> {card.safe_prompt_scope}</p>
                  <p data-testid="top3-card-boundary" className="text-xs text-gray-700"><strong>Boundary:</strong> {card.boundary_warning}</p>
                  <details className="text-xs text-gray-600 dark:text-slate-300 mt-1" data-testid="top3-card-details">
                    <summary>more</summary>
                    {card.registry_role && <p>role: {card.registry_role}</p>}
                    <p>prerequisite_systems: {card.prerequisite_systems.join(', ') || 'none'}</p>
                    <p>supporting_artifact: {card.supporting_artifact}</p>
                    {card.next_bundle_text && <p>next bundle: {card.next_bundle_text}</p>}
                  </details>
                </article>
              ))}
            </div>
            <p className="text-xs text-gray-600 dark:text-slate-300">Dashboard does not compute ranking. Full detail in the Prioritization tab.</p>
              </>
            )}
          </Panel>

          {/* D3L-MASTER-01 Phase 8 — Leverage Queue moved to Roadmap tab to keep Overview simple. */}
          {ocBottleneck && (
            <Panel title="D. Current Bottleneck (OC)" testId="overview-oc-bottleneck-section">
              {ocBottleneck.state === 'ok' && ocBottleneck.card ? (
                <div className="text-sm space-y-0.5" data-testid="overview-oc-bottleneck-card">
                  <p><strong>Overall status:</strong> {ocBottleneck.card.overall_status}</p>
                  <p><strong>Category:</strong> {ocBottleneck.card.category}</p>
                  <p><strong>Reason:</strong> {ocBottleneck.card.reason_code}</p>
                  <p><strong>Owning system:</strong> {ocBottleneck.card.owning_system ?? 'unknown'}</p>
                  <p><strong>Next safe action:</strong> {ocBottleneck.card.next_safe_action}</p>
                  {(ocBottleneck.card.warnings ?? []).length > 0 && (
                    <p className="text-xs text-amber-700 dark:text-amber-300">⚠ {(ocBottleneck.card.warnings ?? []).join('; ')}</p>
                  )}
                </div>
              ) : (
                <div className="text-sm space-y-1" data-testid="overview-oc-bottleneck-unavailable">
                  <p className="text-amber-700 dark:text-amber-300"><strong>Unavailable:</strong> {ocBottleneck.reason ?? ocBottleneck.state}</p>
                  <p className="text-xs break-all">regenerate: <code>python scripts/build_operator_complexity_report.py --fail-closed</code></p>
                </div>
              )}
            </Panel>
          )}

          {explain && explain.root_cause && (
            <Panel title="E. Explain System State (deterministic)" testId="explain-system-state">
              <p className="text-sm" data-testid="explain-trust-state">trust state: <strong>{humanTrustState(explain.trust_state).label}</strong> <span className="text-xs text-gray-500 dark:text-slate-400">({explain.trust_state ?? 'unknown'})</span></p>
              <p className="text-sm" data-testid="explain-root-cause">
                <strong>Root cause:</strong> {explain.root_cause.system_id ?? 'Unknown'}
                {!explain.root_cause.artifact_backed && <span className="text-xs text-amber-700"> (not artifact-backed)</span>}
              </p>
              <p className="text-sm" data-testid="explain-root-reason">
                <strong>Reason:</strong> {explain.root_cause.reason ?? 'no reason recorded'}
              </p>
              <p className="text-sm" data-testid="explain-taxonomy">
                <strong>Taxonomy:</strong> {explain.root_cause.taxonomy ?? 'unknown'}
              </p>
              {(explain.missing_signals ?? []).length > 0 && (
                <p className="text-xs" data-testid="explain-missing-signals">
                  <strong>Missing signals:</strong> {(explain.missing_signals ?? []).join(', ')}
                </p>
              )}
              {(explain.downstream_impact ?? []).length > 0 && (
                <p className="text-xs" data-testid="explain-downstream-impact">
                  <strong>Downstream impact:</strong> {(explain.downstream_impact ?? []).join(', ')}
                </p>
              )}
              <p className="text-sm" data-testid="explain-propagation">
                <strong>Propagation:</strong> {(explain.propagation_path ?? []).length > 0 ? (explain.propagation_path ?? []).join(' → ') : 'none'}
              </p>
              <p className="text-sm" data-testid="explain-next-action">
                <strong>Next safe action:</strong> {explain.next_safe_action ?? 'unknown'}
              </p>
              {(explain.missing_data ?? []).length > 0 && (
                <ul className="text-xs text-amber-700 list-disc ml-5" data-testid="explain-missing-data">
                  {(explain.missing_data ?? []).map((m) => <li key={m}>{m}</li>)}
                </ul>
              )}
              {(explain.notes ?? []).length > 0 && (
                <ul className="text-xs text-gray-600 dark:text-slate-300 list-disc ml-5" data-testid="explain-notes">
                  {(explain.notes ?? []).map((n) => <li key={n}>{n}</li>)}
                </ul>
              )}
            </Panel>
          )}
        </div>
      )}

      {activeTab === 'graph' && <TrustGraphSection />}

      {activeTab === 'decision' && (
        <section className="bg-white border rounded p-4 space-y-3" data-testid="decision-tab">
          <h2 className="font-semibold">Decision Layer (Signal → Evaluation → Policy → Control → Enforcement)</h2>
          <p className="text-xs text-gray-600 dark:text-slate-300">
            View-only projection over the registry. Adds no new systems. CDE is the sole control authority; SEL is the sole enforcement authority.
          </p>
          {(decisionLayer?.groups ?? []).length === 0 && <p className="text-sm text-amber-700">Decision layer unavailable: registry contract empty.</p>}
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3" data-testid="decision-groups">
            {(decisionLayer?.groups ?? []).map((group) => (
              <article key={group.layer} data-testid={`decision-group-${group.layer}`} className="border rounded p-3">
                <h3 className="font-semibold text-sm">{group.label}</h3>
                <p className="text-xs italic text-gray-600 dark:text-slate-300">{group.description}</p>
                <p className="text-sm mt-1"><strong>systems:</strong> {group.systems.join(', ') || 'none registered'}</p>
              </article>
            ))}
          </div>
        </section>
      )}

      {activeTab === 'prioritization' && (
        <section className="bg-white dark:bg-gray-800 dark:text-gray-100 border dark:border-gray-700 rounded p-4 space-y-3" data-testid="prioritization-tab">
          <h2 className="font-semibold mb-2">Prioritization (Top 10 + Full Active List)</h2>
          {(() => {
            if (rankingBlocked) {
              return (
                <div data-testid="prioritization-fail-closed" className="border border-red-300 dark:border-red-700 bg-red-50 dark:bg-red-950 p-3 rounded text-sm">
                  <p className="font-semibold text-red-700 dark:text-red-300">Prioritization hidden — freshness gate failed</p>
                  <p className="text-xs text-red-700 dark:text-red-300">reason: <strong>{rankingDecision.reason}</strong></p>
                  <p className="text-xs mt-1 break-all text-red-700 dark:text-red-300">regenerate: <code>{rankingDecision.recompute_command}</code></p>
                </div>
              );
            }
            const ranked: Array<{ rank?: number | null; system_id?: string; action?: string; why_now?: string; trust_state?: string }> = ((priority?.payload?.global_ranked_systems as unknown as Array<{ rank?: number | null; system_id?: string; action?: string; why_now?: string; trust_state?: string }> | undefined) ?? []);
            const universe = new Set(contract?.allowed_active_node_ids ?? []);
            const filtered = universe.size > 0 ? ranked.filter((r) => typeof r.system_id === 'string' && universe.has(r.system_id)) : ranked;
            const top10 = filtered.slice(0, 10);
            return (
              <div className="space-y-4">
                <div data-testid="prioritization-top10">
                  <h3 className="font-semibold text-sm">Top 10</h3>
                  <ol className="list-decimal pl-6 text-sm space-y-1">
                    {top10.map((row) => (
                      <li key={row.system_id} data-testid="prioritization-top10-row">
                        <strong>{row.system_id}</strong> — {row.action} <span className="text-xs text-gray-600 dark:text-slate-300 dark:text-gray-400">({row.trust_state})</span>
                      </li>
                    ))}
                  </ol>
                </div>
                <div data-testid="prioritization-full">
                  <h3 className="font-semibold text-sm">Full Active List ({filtered.length})</h3>
                  <ul className="text-xs columns-1 sm:columns-2 lg:columns-3">
                    {filtered.map((row, i) => (
                      <li key={`${row.system_id}-${i}`} data-testid="prioritization-full-row">
                        #{row.rank ?? i + 1} <strong>{row.system_id}</strong>
                      </li>
                    ))}
                  </ul>
                  <p className="text-xs text-gray-600 dark:text-slate-300 dark:text-gray-400 mt-1">Full detail (action, why-now, trust signals) available in the Raw Artifacts tab.</p>
                </div>
              </div>
            );
          })()}
        </section>
      )}

      {activeTab === 'maturity' && (
        <section className="bg-white dark:bg-gray-800 dark:text-gray-100 border dark:border-gray-700 rounded p-4 space-y-3" data-testid="maturity-tab">
          <h2 className="font-semibold mb-2">Maturity (Active Systems)</h2>
          {!maturity && <p className="text-xs text-gray-500 dark:text-slate-400">loading…</p>}
          {maturity && maturity.status === 'fail-closed' && (
            <p className="text-sm text-red-700 dark:text-red-300" data-testid="maturity-fail-closed">⚠ Maturity unavailable: {maturity.blocking_reasons.join(', ')}</p>
          )}
          {maturity && maturity.status === 'ok' && (
            <table className="w-full text-sm" data-testid="maturity-table">
              <thead>
                <tr className="text-left border-b dark:border-gray-600">
                  <th className="py-1">System</th>
                  <th className="py-1">Maturity</th>
                  <th className="py-1">Status</th>
                  <th className="py-1">Key Gap</th>
                </tr>
              </thead>
              <tbody>
                {maturity.rows.map((row) => (
                  <tr key={row.system_id} className="border-b last:border-0 dark:border-gray-700" data-testid="maturity-row">
                    <td className="py-1 font-mono">{row.system_id}</td>
                    <td className="py-1">{row.level} <span className="text-xs text-gray-600 dark:text-slate-300 dark:text-gray-400">{row.level_label}</span></td>
                    <td className="py-1">{row.status}</td>
                    <td className="py-1 text-xs">{row.key_gap}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      )}

      {activeTab === 'mvp' && (
        <section className="bg-white dark:bg-gray-800 dark:text-gray-100 border dark:border-gray-700 rounded p-4 space-y-3" data-testid="mvp-tab">
          <h2 className="font-semibold mb-1">MVP Graph (product capabilities, NOT registry systems)</h2>
          <p className="text-xs text-gray-600 dark:text-slate-300 dark:text-gray-300">MVP boxes never appear as 3LS graph nodes. Each box maps to registry-active systems.</p>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3" data-testid="mvp-boxes">
            {MVP_BOXES.map((box) => (
              <article key={box.id} data-testid="mvp-box" className="border dark:border-gray-600 rounded p-3 text-sm">
                <h3 className="font-semibold">{box.label}</h3>
                <p className="text-xs italic text-gray-600 dark:text-slate-300 dark:text-gray-300">{box.description}</p>
                <p className="text-xs"><strong>Maps to systems:</strong> {box.maps_to_systems.join(', ')}</p>
              </article>
            ))}
          </div>
        </section>
      )}

      {activeTab === 'sources' && (
        <section className="bg-white border rounded p-4" data-testid="sources-tab">
          <h2 className="font-semibold mb-2">Sources (artifact vs fallback)</h2>
          <pre className="text-xs overflow-auto max-h-[60vh]">
            {JSON.stringify({
              graph_source_mix: graph?.source_mix,
              priority_source_path: priority?.source_path,
              roadmap_sources: roadmap?.source_artifacts_used,
              registry_active_count: contract?.allowed_active_node_ids?.length,
            }, null, 2)}
          </pre>
        </section>
      )}

      {activeTab === 'diagnostics' && (
        <section className="bg-white border rounded p-4 space-y-3" data-testid="diagnostics-tab">
          <h2 className="font-semibold">Diagnostics (red-team + validation)</h2>
          <p className="text-sm">Critical hidden check: top 3 + queue + trust + flow visible from Overview.</p>
          <p className="text-sm">Dashboard-side computation check: ranking is read-only from artifact.</p>
          <p className="text-xs text-gray-600 dark:text-slate-300" data-testid="trust-pulse-raw">Trust pulse raw code: {humanTrustState(trustPulse.trust_state).raw || 'unknown'}</p>

          <Panel title="Learning Loop (proposed candidates only)" testId="learning-loop-section">
            <p className="text-sm">{intelligence?.feedback_loop ? 'Learning loop loaded.' : 'Learning loop unavailable.'}</p>
          </Panel>
          <Panel title="Failure Explanation (debug under 15 minutes)" testId="failure-explanation-section">
            <p className="text-sm">{(intelligence?.failure_explanation_packets?.packets ?? []).length > 0 ? 'Failure explanation packets loaded.' : 'No failure explanation packets available.'}</p>
          </Panel>
          <Panel title="Override / Unknowns (fail-closed)" testId="override-unknowns-section">
            <p className="text-sm">override count: <strong>{String(intelligence?.override_audit?.override_count ?? 'unknown')}</strong></p>
          </Panel>
          <Panel title="Fallback Reduction (high-leverage rows only)" testId="fallback-reduction-section">
            <p className="text-sm">high-leverage rows: <strong>{String(intelligence?.fallback_reduction_plan?.high_leverage_fallback_count ?? 'unknown')}</strong></p>
          </Panel>
          <Panel title="Replay + Lineage Hardening" testId="replay-lineage-hardening-section">
            <p className="text-sm">affected systems: <strong>{(intelligence?.replay_lineage_hardening?.affected_systems ?? []).join(', ') || 'unknown'}</strong></p>
          </Panel>
          <Panel title="Candidate Closure (proposed/open/stale only)" testId="candidate-closure-section">
            <p className="text-sm">tracked items: <strong>{String(intelligence?.candidate_closure?.candidate_item_count ?? 'unknown')}</strong></p>
          </Panel>

          <Panel title="Owner Read Observations" testId="owner-read-observations-section">
            {(() => {
              const items = intelligence?.owner_read_observations?.owner_read_items ?? [];
              if (items.length === 0) {
                return <p className="text-sm text-amber-700 dark:text-amber-300">Owner read observations unknown.</p>;
              }
              return (
                <ul className="list-disc ml-5 text-xs">
                  {items.slice(0, MET_COMPACT_ITEM_MAX).map((item, index) => (
                    <li key={`${item.owner_read_observation_id}-${index}`}>
                      <strong>{item.source_candidate_id ?? 'unknown'}</strong> — {item.read_observation_state ?? 'unknown'} ({item.recommended_owner_system ?? 'unknown'})
                    </li>
                  ))}
                </ul>
              );
            })()}
            <p className="text-xs text-gray-600 dark:text-slate-300">sources: {(intelligence?.owner_read_observations?.source_artifacts_used ?? []).slice(0, 3).join(', ') || 'unknown'}</p>
          </Panel>

          <Panel title="Materialization Observations" testId="materialization-observations-section">
            {(() => {
              const items = intelligence?.materialization_observation_mapper?.materialization_observations ?? [];
              if (items.length === 0) {
                return <p className="text-sm text-amber-700 dark:text-amber-300">Materialization observations unknown.</p>;
              }
              return (
                <ul className="list-disc ml-5 text-xs">
                  {items.slice(0, MET_COMPACT_ITEM_MAX).map((item, index) => (
                    <li key={`${item.materialization_observation_id}-${index}`}>
                      <strong>{item.source_candidate_id ?? 'unknown'}</strong> — {item.materialization_observation ?? 'unknown'}
                    </li>
                  ))}
                </ul>
              );
            })()}
            <p className="text-xs text-gray-600 dark:text-slate-300">sources: {(intelligence?.materialization_observation_mapper?.source_artifacts_used ?? []).slice(0, 3).join(', ') || 'unknown'}</p>
          </Panel>

          <Panel title="Comparable Case / Trend Readiness" testId="comparable-trend-readiness-section">
            <p className="text-sm">qualified groups: <strong>{String((intelligence?.comparable_case_qualification_gate?.qualified_case_groups ?? []).length || 'unknown')}</strong></p>
            <p className="text-sm">case packs: <strong>{String((intelligence?.trend_ready_case_pack?.case_packs ?? []).length || 'unknown')}</strong></p>
            <p className="text-xs text-gray-600 dark:text-slate-300">sources: {(intelligence?.trend_ready_case_pack?.source_artifacts_used ?? []).slice(0, 3).join(', ') || 'unknown'}</p>
          </Panel>

          <Panel title="Fold Safety" testId="fold-safety-section">
            {(() => {
              const items = intelligence?.fold_candidate_proof_check?.fold_candidates ?? [];
              if (items.length === 0) {
                return <p className="text-sm text-amber-700 dark:text-amber-300">Fold safety observations unknown.</p>;
              }
              return (
                <ul className="list-disc ml-5 text-xs">
                  {items.slice(0, MET_COMPACT_ITEM_MAX).map((item, index) => (
                    <li key={`${String(item.fold_candidate_id)}-${index}`}>
                      <strong>{String(item.fold_candidate_id ?? 'unknown')}</strong> — {String(item.fold_safety_observation ?? 'unknown')}
                    </li>
                  ))}
                </ul>
              );
            })()}
          </Panel>

          <Panel title="Operator Debuggability Drill" testId="operator-debuggability-drill-section">
            {(() => {
              const items = intelligence?.operator_debuggability_drill?.drill_items ?? [];
              if (items.length === 0) {
                return <p className="text-sm text-amber-700 dark:text-amber-300">Operator drill unknown.</p>;
              }
              return (
                <ul className="list-disc ml-5 text-xs">
                  {items.slice(0, MET_COMPACT_ITEM_MAX).map((item, index) => (
                    <li key={`${String(item.drill_id)}-${index}`}>
                      <strong>{String(item.drill_id ?? 'unknown')}</strong> — readiness {String(item.debug_readiness ?? 'unknown')}
                    </li>
                  ))}
                </ul>
              );
            })()}
            <p className="text-xs text-gray-600 dark:text-slate-300">target minutes: {String(intelligence?.operator_debuggability_drill?.target_minutes ?? 'unknown')}</p>
          </Panel>

          <Panel title="Debug Explanation Index" testId="debug-explanation-index-section">
            {(() => {
              const entries = intelligence?.debug_explanation_index?.explanation_entries ?? [];
              if (entries.length === 0) {
                return <p className="text-sm text-amber-700 dark:text-amber-300">Debug explanation index unavailable.</p>;
              }
              return (
                <ul className="list-disc ml-5 text-xs">
                  {entries.slice(0, MET_COMPACT_ITEM_MAX).map((entry, index) => (
                    <li key={`${entry.explanation_id}-${index}`}>
                      <strong>{entry.explanation_id}</strong> — {entry.what_failed}
                    </li>
                  ))}
                </ul>
              );
            })()}
          </Panel>
          <Panel title="Trend / Frequency Honesty (no fake trend)" testId="trend-frequency-honesty-section">
            <p className="text-sm">trend state: <strong>{intelligence?.trend_frequency_honesty_gate?.trend_state ?? 'unknown'}</strong></p>
          </Panel>
          <Panel title="EVL Handoff Observations (signal only)" testId="evl-handoff-observations-section">
            <p className="text-sm">handoff items: <strong>{String(intelligence?.evl_handoff_observations?.handoff_item_count ?? 'unknown')}</strong></p>
          </Panel>
          <Panel title="Artifact Integrity (override + classification)" testId="artifact-integrity-section">
            <p className="text-sm">classified paths: <strong>{String(intelligence?.met_generated_artifact_classification?.classified_path_count ?? 'unknown')}</strong></p>
          </Panel>

          {/* D3L-DATA-REGISTRY-01 Phase 7: Compact OC bottleneck card. Renders only
              when the OC artifact loads cleanly. Fail-closed states (unavailable,
              invalid_schema, stale_proof, conflict_proof, ambiguous) are surfaced
              by reason text, never as a fabricated bottleneck. */}
          <div className="border rounded p-3 space-y-1" data-testid="oc-bottleneck-panel">
            <h3 className="font-semibold text-sm">Current Bottleneck (OC)</h3>
            {!ocBottleneck && <p className="text-xs text-gray-500 dark:text-slate-400" data-testid="oc-bottleneck-loading">loading…</p>}
            {ocBottleneck && ocBottleneck.state === 'ok' && ocBottleneck.card && (
              <div className="text-sm space-y-0.5" data-testid="oc-bottleneck-card">
                <p><strong>overall status:</strong> {ocBottleneck.card.overall_status}</p>
                <p><strong>category:</strong> {ocBottleneck.card.category}</p>
                <p><strong>owning system:</strong> {ocBottleneck.card.owning_system ?? 'unknown'}</p>
                <p><strong>reason:</strong> {ocBottleneck.card.reason_code}</p>
                <p><strong>next safe action:</strong> {ocBottleneck.card.next_safe_action}</p>
                <p className="text-xs text-gray-500 dark:text-slate-400">source: {ocBottleneck.card.source_artifact_type}</p>
                {(ocBottleneck.card.warnings ?? []).length > 0 && (
                  <p className="text-xs text-amber-700">⚠ {(ocBottleneck.card.warnings ?? []).join('; ')}</p>
                )}
              </div>
            )}
            {ocBottleneck && ocBottleneck.state !== 'ok' && (
              <p className="text-xs text-amber-700" data-testid="oc-bottleneck-fail-closed">
                ⚠ OC bottleneck: <strong>{ocBottleneck.state}</strong> — {ocBottleneck.reason}
              </p>
            )}
            <p className="text-xs text-gray-500 dark:text-slate-400">Top 3 (priority) and OC bottleneck are distinct surfaces; mismatches are reported here without a tie-break.</p>
          </div>

          <div data-testid="invariant-violations-panel" className="border rounded p-3 space-y-1">
            <h3 className="font-semibold text-sm">Invariant Violations</h3>
            {invariantFindings.length === 0 ? (
              <p className="text-xs text-gray-600 dark:text-slate-300">No invariant violations detected from current artifacts.</p>
            ) : (
              <ul className="text-xs space-y-1">
                {invariantFindings.map((f, i) => (
                  <li key={`${f.invariant}-${i}`} data-testid="invariant-violation" className="border-l-4 border-red-400 pl-2">
                    <strong>{f.invariant}</strong>: {f.violated_by} (affected: {f.affected_system}; expected: {f.expected}; source: {f.source_artifact})
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div data-testid="replay-debug-panel" className="border rounded p-3 space-y-1">
            <h3 className="font-semibold text-sm">Replay Debug</h3>
            <p className="text-xs">graph generated_at: {graph?.generated_at ?? 'unknown'}</p>
            <p className="text-xs">priority generated_at: {priority?.generated_at ?? 'unknown'}</p>
            <p className="text-xs">priority source_path: {priority?.source_path ?? 'unknown'}</p>
            <p className="text-xs">replay_commands: {(graph?.replay_commands ?? []).join(' | ')}</p>
            <p className="text-xs">missing artifacts: {(graph?.missing_artifacts ?? []).join(', ') || 'none'}</p>
          </div>
        </section>
      )}

      {activeTab === 'roadmap' && (
        <section className="bg-white border rounded p-4 space-y-3" data-testid="roadmap-tab">
          <h2 className="font-semibold">Roadmap (TLS artifacts)</h2>
          <p className="text-sm">Next safe bundles: {(roadmap?.payload?.safe_bundles ?? []).slice(0, 3).map((b) => b.bundle_id).join(', ') || 'unavailable'}</p>
          <p className="text-sm">Red-team/fix pairing status: paired in sequence (FX → RT → FIX) from roadmap entries.</p>

          <div className="space-y-3" data-testid="roadmap-full-queues">
            <h3 className="font-semibold text-sm">Full Leverage Queue</h3>
            {([
              ['Queue 1: immediate next bundle', queueResult.queues.queue_1_immediate_next_bundle],
              ['Queue 2: next hardening bundle', queueResult.queues.queue_2_next_hardening_bundle],
              ['Queue 3: next review/fix bundle', queueResult.queues.queue_3_next_review_fix_bundle],
              ['Queue 4: later work', queueResult.queues.queue_4_later_work],
            ] as Array<[string, typeof queueResult.queues.queue_1_immediate_next_bundle]>).map(([label, items]) => (
              <div key={label} className="border rounded p-3">
                <h4 className="font-medium text-sm">{label}</h4>
                {items.length === 0 && <p className="text-xs text-gray-500 dark:text-slate-400">empty</p>}
                {items.map((item) => (
                  <article key={item.bundle_id} data-testid="roadmap-queue-item" className="text-sm mt-2">
                    <header className="flex flex-wrap gap-2 items-center">
                      <strong>{item.bundle_id}</strong>
                      <span className="text-xs text-gray-700">— {item.title}</span>
                      {item.linked_top3_system_id && (
                        <span className="text-xs px-1.5 py-0.5 rounded bg-blue-100 text-blue-800 border border-blue-300">
                          ↔ Top 3: {item.linked_top3_system_id}
                        </span>
                      )}
                    </header>
                    <p className="text-xs">{item.why_it_matters}</p>
                    <p className="text-xs text-gray-600 dark:text-slate-300">deps: {item.dependency_count} · steps: {item.steps.join(' → ')}</p>
                  </article>
                ))}
              </div>
            ))}
          </div>

          <h3 className="font-semibold text-sm pt-2">Roadmap Markdown Table</h3>
          <pre className="text-xs overflow-auto max-h-[60vh]">{roadmap?.table_markdown ?? 'tls_roadmap_table.md missing'}</pre>
        </section>
      )}

      {activeTab === 'raw' && (
        <section className="bg-white border rounded p-4" data-testid="raw-tab">
          <h2 className="font-semibold mb-2">Raw Artifacts</h2>
          <pre className="text-xs overflow-auto max-h-[60vh]">
            {JSON.stringify({ priority, flow, graph, roadmap, intelligence, contract, explain, decisionLayer }, null, 2)}
          </pre>
        </section>
      )}
    </main>
  );
}
