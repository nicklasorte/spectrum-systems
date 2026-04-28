'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { TrustGraphSection } from '@/components/TrustGraphSection';
import type { PriorityArtifactLoadResult } from '@/lib/artifactLoader';
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

type TabKey = 'overview' | 'graph' | 'decision' | 'prioritization' | 'sources' | 'diagnostics' | 'roadmap' | 'raw';

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

const TABS: Array<{ key: TabKey; label: string }> = [
  { key: 'overview', label: 'Overview' },
  { key: 'graph', label: 'Graph' },
  { key: 'decision', label: 'Decision Layer' },
  { key: 'prioritization', label: 'Prioritization' },
  { key: 'sources', label: 'Sources' },
  { key: 'diagnostics', label: 'Diagnostics' },
  { key: 'roadmap', label: 'Roadmap' },
  { key: 'raw', label: 'Raw Artifacts' },
];

function Panel({ title, children, testId }: { title: string; children: React.ReactNode; testId?: string }) {
  return (
    <section data-testid={testId ?? 'overview-section'} className="bg-white border rounded p-4 space-y-3">
      <h2 className="font-semibold text-sm uppercase tracking-wide">{title}</h2>
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
  const [intelligence, setIntelligence] = useState<unknown>(null);
  const [contract, setContract] = useState<RegistryGraphContract | null>(null);
  const [explain, setExplain] = useState<ExplainSystemStateResult | null>(null);
  const [decisionLayer, setDecisionLayer] = useState<DecisionLayerResponse | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const [healthRes, priorityRes, flowRes, graphRes, roadmapRes, intelligenceRes, contractRes, explainRes, decisionRes] = await Promise.all([
          fetch('/api/health'),
          fetch('/api/priority'),
          fetch('/api/system-flow'),
          fetch('/api/system-graph'),
          fetch('/api/tls-roadmap'),
          fetch('/api/intelligence'),
          fetch('/api/registry-contract'),
          fetch('/api/explain-state'),
          fetch('/api/decision-layer'),
        ]);

        const [healthData, priorityData, flowData, graphData, roadmapData, intelligenceData, contractData, explainData, decisionData] = await Promise.all([
          healthRes.json(),
          priorityRes.json(),
          flowRes.json(),
          graphRes.json(),
          roadmapRes.json(),
          intelligenceRes.json(),
          contractRes.json(),
          explainRes.json(),
          decisionRes.json(),
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
        <p className="text-xs text-gray-600">
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
            <ul className="text-sm space-y-1">
              <li>trust state: <strong>{trustPulse.trust_state}</strong></li>
              <li>artifact-backed %: <strong>{trustPulse.artifact_backed_pct}%</strong></li>
              <li>stub fallback %: <strong>{trustPulse.stub_fallback_pct}%</strong></li>
              <li>last recompute: <strong>{trustPulse.last_recompute}</strong></li>
              <li>warning count: <strong>{trustPulse.warning_count}</strong></li>
              <li>registry-active count: <strong data-testid="registry-active-count">{contract?.allowed_active_node_ids?.length ?? 0}</strong></li>
            </ul>
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
            {topThree.warning && <p data-testid="top3-warning" className="text-sm text-red-700">⚠ {topThree.warning}</p>}
            {topThree.recompute_command && (
              <p data-testid="top3-recompute-command" className="text-xs text-gray-700 break-all">
                regenerate: <code className="text-xs">{topThree.recompute_command}</code>
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
                  {card.registry_role && <p className="text-xs italic text-gray-600">role: {card.registry_role}</p>}
                  <p><strong>what_to_fix:</strong> {card.what_to_fix}</p>
                  <p><strong>why_now:</strong> {card.why_now}</p>
                  <p><strong>safe_prompt_scope:</strong> {card.safe_prompt_scope}</p>
                  <p><strong>prerequisite_systems:</strong> {card.prerequisite_systems.join(', ') || 'none'}</p>
                  <p><strong>do_not_touch / boundary warning:</strong> {card.boundary_warning}</p>
                  <p className="text-xs text-gray-600"><strong>supporting_artifact:</strong> {card.supporting_artifact}</p>
                  {card.next_bundle_text && (
                    <p className="text-xs text-gray-600"><strong>next bundle:</strong> {card.next_bundle_text}</p>
                  )}
                </article>
              ))}
            </div>
            <p className="text-xs text-gray-600">Dashboard does not compute ranking.</p>
          </Panel>

          <Panel title="D. Leverage Queue (compressed; full detail in Roadmap)">
            {queueResult.warning && <p data-testid="queue-warning" className="text-sm text-red-700">⚠ {queueResult.warning}</p>}
            {([
              ['Queue 1: immediate next bundle', queueResult.queues.queue_1_immediate_next_bundle],
              ['Queue 2: next hardening bundle', queueResult.queues.queue_2_next_hardening_bundle],
              ['Queue 3: next review/fix bundle', queueResult.queues.queue_3_next_review_fix_bundle],
              ['Queue 4: later work', queueResult.queues.queue_4_later_work],
            ] as Array<[string, typeof queueResult.queues.queue_1_immediate_next_bundle]>).map(([label, items]) => (
              <div key={label} className="border rounded p-3">
                <h3 className="font-medium text-sm">{label}</h3>
                {items.length === 0 && <p className="text-xs text-gray-500">empty</p>}
                {items.map((item) => (
                  <article key={item.bundle_id} data-testid="leverage-queue-item" className="text-sm mt-2">
                    <header className="flex flex-wrap gap-2 items-center">
                      <strong>{item.bundle_id}</strong>
                      <span className="text-xs text-gray-700">— {item.title}</span>
                      {item.linked_top3_system_id && (
                        <span className="text-xs px-1.5 py-0.5 rounded bg-blue-100 text-blue-800 border border-blue-300" data-testid="queue-top3-link">
                          ↔ Top 3: {item.linked_top3_system_id}
                        </span>
                      )}
                    </header>
                    <p className="text-xs">{item.why_it_matters}</p>
                    <p className="text-xs text-gray-600">deps: {item.dependency_count} · {item.next_safe_action}</p>
                  </article>
                ))}
              </div>
            ))}
          </Panel>

          {explain && explain.root_cause && (
            <Panel title="E. Explain System State (deterministic)" testId="explain-system-state">
              <p className="text-sm" data-testid="explain-trust-state">trust state: <strong>{explain.trust_state ?? 'unknown'}</strong></p>
              <p className="text-sm" data-testid="explain-root-cause">
                root cause: <strong>{explain.root_cause.system_id ?? 'Unknown'}</strong> ({explain.root_cause.taxonomy ?? 'unknown'})
              </p>
              <p className="text-xs text-gray-600">{explain.root_cause.explanation ?? 'no explanation available'}</p>
              <p className="text-sm" data-testid="explain-propagation">
                propagation: {(explain.propagation_path ?? []).length > 0 ? (explain.propagation_path ?? []).join(' → ') : 'none'}
              </p>
              <p className="text-sm" data-testid="explain-next-action">
                next safe action: <strong>{explain.next_safe_action ?? 'unknown'}</strong>
              </p>
              {(explain.missing_data ?? []).length > 0 && (
                <ul className="text-xs text-amber-700 list-disc ml-5" data-testid="explain-missing-data">
                  {(explain.missing_data ?? []).map((m) => <li key={m}>{m}</li>)}
                </ul>
              )}
              {(explain.notes ?? []).length > 0 && (
                <ul className="text-xs text-gray-600 list-disc ml-5" data-testid="explain-notes">
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
          <p className="text-xs text-gray-600">
            View-only projection over the registry. Adds no new systems. CDE is the sole control authority; SEL is the sole enforcement authority.
          </p>
          {(decisionLayer?.groups ?? []).length === 0 && <p className="text-sm text-amber-700">Decision layer unavailable: registry contract empty.</p>}
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3" data-testid="decision-groups">
            {(decisionLayer?.groups ?? []).map((group) => (
              <article key={group.layer} data-testid={`decision-group-${group.layer}`} className="border rounded p-3">
                <h3 className="font-semibold text-sm">{group.label}</h3>
                <p className="text-xs italic text-gray-600">{group.description}</p>
                <p className="text-sm mt-1"><strong>systems:</strong> {group.systems.join(', ') || 'none registered'}</p>
              </article>
            ))}
          </div>
        </section>
      )}

      {activeTab === 'prioritization' && (
        <section className="bg-white border rounded p-4" data-testid="prioritization-tab">
          <h2 className="font-semibold mb-2">Full Prioritization Artifact</h2>
          <pre className="text-xs overflow-auto max-h-[60vh]">{JSON.stringify(priority, null, 2)}</pre>
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

          <div data-testid="invariant-violations-panel" className="border rounded p-3 space-y-1">
            <h3 className="font-semibold text-sm">Invariant Violations</h3>
            {invariantFindings.length === 0 ? (
              <p className="text-xs text-gray-600">No invariant violations detected from current artifacts.</p>
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
