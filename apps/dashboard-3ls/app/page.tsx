'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { TrustGraphSection } from '@/components/TrustGraphSection';
import type { PriorityArtifactLoadResult } from '@/lib/artifactLoader';
import type { SystemGraphPayload } from '@/lib/systemGraph';
import {
  buildLeverageQueueFromRoadmap,
  extractTopThreeRecommendations,
  type QueueGroups,
  type RoadmapArtifact,
} from '@/lib/dashboardSimplified';

type TabKey = 'overview' | 'graph' | 'prioritization' | 'sources' | 'diagnostics' | 'roadmap' | 'raw';

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

const TABS: Array<{ key: TabKey; label: string }> = [
  { key: 'overview', label: 'Overview' },
  { key: 'graph', label: 'Graph' },
  { key: 'prioritization', label: 'Prioritization' },
  { key: 'sources', label: 'Sources' },
  { key: 'diagnostics', label: 'Diagnostics' },
  { key: 'roadmap', label: 'Roadmap' },
  { key: 'raw', label: 'Raw Artifacts' },
];

const SUPPORT_SYSTEMS = ['CTX', 'PRM', 'TLC', 'RIL', 'FRE', 'GOV', 'MAP'];
const CANDIDATE_SYSTEMS = ['H01', 'RFX', 'HOP', 'MET', 'METS'];

const initialQueues: QueueGroups = {
  queue_1_immediate_next_bundle: [],
  queue_2_next_hardening_bundle: [],
  queue_3_next_review_fix_bundle: [],
  queue_4_later_work: [],
};

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section data-testid="overview-section" className="bg-white border rounded p-4 space-y-3">
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

  useEffect(() => {
    const load = async () => {
      try {
        const [healthRes, priorityRes, flowRes, graphRes, roadmapRes, intelligenceRes] = await Promise.all([
          fetch('/api/health'),
          fetch('/api/priority'),
          fetch('/api/system-flow'),
          fetch('/api/system-graph'),
          fetch('/api/tls-roadmap'),
          fetch('/api/intelligence'),
        ]);

        const [healthData, priorityData, flowData, graphData, roadmapData, intelligenceData] = await Promise.all([
          healthRes.json(),
          priorityRes.json(),
          flowRes.json(),
          graphRes.json(),
          roadmapRes.json(),
          intelligenceRes.json(),
        ]);

        setHealth(healthData);
        setPriority(priorityData);
        setFlow(flowData);
        setGraph(graphData);
        setRoadmap(roadmapData);
        setIntelligence(intelligenceData);
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

  const topThree = useMemo(() => extractTopThreeRecommendations(priority), [priority]);
  const queueResult = useMemo(() => buildLeverageQueueFromRoadmap(roadmap?.payload ?? null), [roadmap]);

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

  if (loading) {
    return <main className="p-6">Loading dashboard cockpit…</main>;
  }

  if (error) {
    return <main className="p-6 text-red-700">Dashboard failure: {error}</main>;
  }

  return (
    <main className="p-6 space-y-4">
      <header>
        <h1 className="text-2xl font-bold">Dashboard 3LS — Simple Operator Cockpit</h1>
      </header>

      <nav className="flex flex-wrap gap-2" aria-label="Dashboard tabs">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => setActiveTab(tab.key)}
            data-testid={`tab-${tab.key}`}
            className={`px-3 py-1.5 rounded border text-sm ${activeTab === tab.key ? 'bg-gray-900 text-white' : 'bg-white'}`}
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
            </ul>
          </Panel>

          <Panel title="B. Simple 3LS Flowchart">
            <p className="text-sm">Core: {(flow?.payload?.canonical_loop ?? []).join(' → ') || 'unavailable'}</p>
            <p className="text-sm">Overlay: {(flow?.payload?.canonical_overlays ?? []).join(' / ') || 'unavailable'}</p>
            <p className="text-sm">Support: {SUPPORT_SYSTEMS.join(', ')}</p>
            <p className="text-sm">Candidates: {CANDIDATE_SYSTEMS.join(', ')}</p>
            <ul data-testid="flow-edges" className="text-xs list-disc ml-5">
              {flowEdges.map((edge) => <li key={edge}>{edge}</li>)}
            </ul>
            {flowWarnings.map((w) => (
              <p key={w} className="text-xs text-red-700" data-testid="flow-warning">⚠ {w}</p>
            ))}
          </Panel>

          <Panel title="C. Top 3 Recommendations (TLS artifact only)">
            {topThree.warning && <p data-testid="top3-warning" className="text-sm text-red-700">⚠ {topThree.warning}</p>}
            <div className="space-y-2">
              {topThree.cards.map((card) => (
                <article key={card.system_id} data-testid="top3-card" className="border rounded p-3 text-sm">
                  <p><strong>system_id:</strong> {card.system_id}</p>
                  <p><strong>what_to_fix:</strong> {card.what_to_fix}</p>
                  <p><strong>why_now:</strong> {card.why_now}</p>
                  <p><strong>safe_prompt_scope:</strong> {card.safe_prompt_scope}</p>
                  <p><strong>prerequisite_systems:</strong> {card.prerequisite_systems.join(', ') || 'none'}</p>
                  <p><strong>do_not_touch / boundary warning:</strong> {card.boundary_warning}</p>
                </article>
              ))}
            </div>
            <p className="text-xs text-gray-600">Dashboard does not compute ranking.</p>
          </Panel>

          <Panel title="D. Leverage Queue (TLS roadmap)">
            {queueResult.warning && <p data-testid="queue-warning" className="text-sm text-red-700">⚠ {queueResult.warning}</p>}
            {([
              ['Queue 1: immediate next bundle', queueResult.queues.queue_1_immediate_next_bundle],
              ['Queue 2: next hardening bundle', queueResult.queues.queue_2_next_hardening_bundle],
              ['Queue 3: next review/fix bundle', queueResult.queues.queue_3_next_review_fix_bundle],
              ['Queue 4: later work', queueResult.queues.queue_4_later_work],
            ] as Array<[string, typeof initialQueues.queue_1_immediate_next_bundle]>).map(([label, items]) => (
              <div key={label} className="border rounded p-3">
                <h3 className="font-medium text-sm">{label}</h3>
                {items.map((item) => (
                  <article key={item.bundle_id} data-testid="leverage-queue-item" className="text-sm mt-2">
                    <p><strong>title:</strong> {item.title}</p>
                    <p><strong>why it matters:</strong> {item.why_it_matters}</p>
                    <p><strong>dependency:</strong> {item.dependency}</p>
                    <p><strong>next safe action:</strong> {item.next_safe_action}</p>
                  </article>
                ))}
              </div>
            ))}
          </Panel>
        </div>
      )}

      {activeTab === 'graph' && <TrustGraphSection />}

      {activeTab === 'prioritization' && (
        <section className="bg-white border rounded p-4" data-testid="prioritization-tab">
          <h2 className="font-semibold mb-2">Full Prioritization Artifact</h2>
          <pre className="text-xs overflow-auto">{JSON.stringify(priority, null, 2)}</pre>
        </section>
      )}

      {activeTab === 'sources' && (
        <section className="bg-white border rounded p-4" data-testid="sources-tab">
          <h2 className="font-semibold mb-2">Sources (artifact vs fallback)</h2>
          <pre className="text-xs overflow-auto">{JSON.stringify({ graph_source_mix: graph?.source_mix, roadmap_sources: roadmap?.source_artifacts_used }, null, 2)}</pre>
        </section>
      )}

      {activeTab === 'diagnostics' && (
        <section className="bg-white border rounded p-4" data-testid="diagnostics-tab">
          <h2 className="font-semibold mb-2">Diagnostics (red-team + validation)</h2>
          <p className="text-sm">Critical hidden check: top 3 + queue + trust + flow visible from Overview.</p>
          <p className="text-sm">Dashboard-side computation check: ranking is read-only from artifact.</p>
        </section>
      )}

      {activeTab === 'roadmap' && (
        <section className="bg-white border rounded p-4 space-y-3" data-testid="roadmap-tab">
          <h2 className="font-semibold">Roadmap (TLS artifacts)</h2>
          <p className="text-sm">Next safe bundles: {(roadmap?.payload?.safe_bundles ?? []).slice(0, 3).map((b) => b.bundle_id).join(', ') || 'unavailable'}</p>
          <p className="text-sm">Red-team/fix pairing status: paired in sequence (FX → RT → FIX) from roadmap entries.</p>
          <pre className="text-xs overflow-auto max-h-96">{roadmap?.table_markdown ?? 'tls_roadmap_table.md missing'}</pre>
        </section>
      )}

      {activeTab === 'raw' && (
        <section className="bg-white border rounded p-4" data-testid="raw-tab">
          <h2 className="font-semibold mb-2">Raw Artifacts</h2>
          <pre className="text-xs overflow-auto">{JSON.stringify({ priority, flow, graph, roadmap, intelligence }, null, 2)}</pre>
        </section>
      )}
    </main>
  );
}
