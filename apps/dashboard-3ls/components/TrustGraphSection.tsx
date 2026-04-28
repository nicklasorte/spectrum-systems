'use client';

import React, { useEffect, useMemo, useState } from 'react';
import type { DebugMode, SystemGraphEdge, SystemGraphPayload } from '@/lib/systemGraph';
import type { PriorityArtifactLoadResult } from '@/lib/artifactLoader';
import { RecomputeGraphButton } from './RecomputeGraphButton';
import { SystemTrustGraph, type GraphLayoutKey } from './SystemTrustGraph';
import { SystemInspector } from './SystemInspector';
import { EdgeInspector } from './EdgeInspector';
import { ExplainFreezePanel } from './ExplainFreezePanel';
import { ActivityLog, type ActivityEntry } from './ActivityLog';
import { GraphLegend } from './GraphLegend';
import { LayoutSelector } from './LayoutSelector';
import { DebugModeSelector } from './DebugModeSelector';
import { SystemTrustStatusCard } from './SystemTrustStatusCard';
import { RecommendationDebugPanel } from './RecommendationDebugPanel';
import { DiffSinceLastRecompute } from './DiffSinceLastRecompute';

export function TrustGraphSection() {
  const [graph, setGraph] = useState<SystemGraphPayload | null>(null);
  const [lastKnownGraph, setLastKnownGraph] = useState<SystemGraphPayload | null>(null);
  const [previousGraph, setPreviousGraph] = useState<SystemGraphPayload | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<SystemGraphEdge | null>(null);
  const [showAll, setShowAll] = useState(false);
  const [layout, setLayout] = useState<GraphLayoutKey>('layered');
  const [debugMode, setDebugMode] = useState<DebugMode>('normal');
  const [highlightedPath, setHighlightedPath] = useState<string[]>([]);
  const [lastRecompute, setLastRecompute] = useState<string | null>(null);
  const [recomputeStatus, setRecomputeStatus] = useState<string | null>(null);
  const [entries, setEntries] = useState<ActivityEntry[]>([]);
  const [priority, setPriority] = useState<PriorityArtifactLoadResult | null>(null);

  const loadGraph = async () => {
    const res = await fetch('/api/system-graph');
    const payload = (await res.json()) as SystemGraphPayload;
    setGraph((prev) => {
      if (prev) setPreviousGraph(prev);
      return payload;
    });
    setLastKnownGraph(payload);
    setLoadFailed(false);
    setEntries((prev) => [{ timestamp: new Date().toISOString(), message: 'graph_loaded' }, ...prev].slice(0, 10));
  };

  const loadPriority = async () => {
    try {
      const res = await fetch('/api/priority');
      const payload = (await res.json()) as PriorityArtifactLoadResult;
      setPriority(payload);
    } catch {
      setPriority({ state: 'missing', payload: null, reason: 'fetch_failed' });
    }
  };

  useEffect(() => {
    loadGraph().catch(() => {
      setLoadFailed(true);
      setEntries((prev) => [{ timestamp: new Date().toISOString(), message: 'graph_load_failed' }, ...prev].slice(0, 10));
    });
    loadPriority();
  }, []);

  const displayGraph = graph ?? lastKnownGraph;
  const selectedNode = useMemo(
    () => displayGraph?.nodes.find((n) => n.system_id === selected) ?? null,
    [displayGraph, selected],
  );

  const isStale = useMemo(() => {
    if (!displayGraph || !lastRecompute) return false;
    const recomputeTime = Date.parse(lastRecompute);
    const generatedTime = Date.parse(displayGraph.generated_at);
    return Number.isFinite(recomputeTime) && Number.isFinite(generatedTime) && recomputeTime > generatedTime;
  }, [displayGraph, lastRecompute]);

  const isFailClosed = !displayGraph || displayGraph.nodes.length === 0;

  if (loadFailed && !displayGraph) {
    return (
      <section className="bg-white border rounded p-4" data-testid="trust-graph-section">
        <p className="text-sm text-red-700" data-testid="graph-fail-closed-warning">
          ⚠ Trust graph artifact unavailable. Fail-closed: dashboard will not synthesize graph data.
        </p>
      </section>
    );
  }

  if (!displayGraph) {
    return (
      <section className="bg-white border rounded p-4" data-testid="trust-graph-section">
        <p className="text-sm text-gray-500">Loading trust graph artifact…</p>
      </section>
    );
  }

  if (isFailClosed) {
    return (
      <section className="bg-white border rounded p-4 space-y-2" data-testid="trust-graph-section">
        <h2 className="font-semibold">SYSTEM TRUST GRAPH</h2>
        <p className="text-sm text-red-700" data-testid="graph-fail-closed-warning">
          ⚠ Graph artifact contains no nodes. Fail-closed: refusing to render synthetic graph data.
        </p>
        {displayGraph.warnings.length > 0 && (
          <p className="text-xs text-amber-700">warnings: {displayGraph.warnings.join(', ')}</p>
        )}
        <RecomputeGraphButton
          onResult={async (result) => {
            const timestamp = new Date().toISOString();
            setLastRecompute(timestamp);
            setRecomputeStatus(result.status);
            setEntries((prev) => [{ timestamp, message: `recompute:${result.status}` }, ...prev].slice(0, 10));
            if (result.status === 'recompute_success_signal') {
              await loadGraph();
            }
          }}
        />
      </section>
    );
  }

  return (
    <section className="bg-white border rounded p-4 space-y-3" data-testid="trust-graph-section">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-semibold">SYSTEM TRUST GRAPH</h2>
        <div className="flex flex-wrap items-center gap-3">
          <DebugModeSelector value={debugMode} onChange={setDebugMode} />
          <LayoutSelector value={layout} onChange={setLayout} />
          <button
            type="button"
            className="text-xs underline"
            onClick={() => setShowAll((s) => !s)}
            data-testid="focus-toggle"
          >
            {showAll ? 'Focus mode' : 'Show all'}
          </button>
          <RecomputeGraphButton
            onResult={async (result) => {
              const timestamp = new Date().toISOString();
              setLastRecompute(timestamp);
              setRecomputeStatus(result.status);
              setEntries((prev) => [{ timestamp, message: `recompute:${result.status}` }, ...prev].slice(0, 10));
              if (result.status === 'recompute_success_signal') {
                await loadGraph();
                await loadPriority();
              }
            }}
          />
        </div>
      </header>

      <div className="grid gap-4 lg:grid-cols-[260px_minmax(0,1fr)]" data-testid="graph-tab-layout">
        <aside className="space-y-3" data-testid="graph-left-rail">
          <SystemTrustStatusCard graph={displayGraph} lastRecompute={lastRecompute} isStale={isStale} />
          <ExplainFreezePanel graph={displayGraph} onPathChange={setHighlightedPath} />
          <DiffSinceLastRecompute current={displayGraph} previous={previousGraph} recomputeStatus={recomputeStatus} />
          <GraphLegend />
          <ActivityLog entries={entries} />
        </aside>

        <div className="space-y-3 min-w-0" data-testid="graph-main-panel">
          <SystemTrustGraph
            graph={displayGraph}
            selectedSystem={selected}
            selectedEdgeKey={selectedEdge ? `${selectedEdge.from}-${selectedEdge.to}` : null}
            showAll={showAll}
            layout={layout}
            debugMode={debugMode}
            highlightedPath={highlightedPath}
            onSelect={(id) => {
              setSelected(id);
              setEntries((prev) => [
                { timestamp: new Date().toISOString(), message: `node_selected:${id}` },
                ...prev,
              ].slice(0, 10));
            }}
            onSelectEdge={(edge) => {
              setSelectedEdge(edge);
              setEntries((prev) => [
                { timestamp: new Date().toISOString(), message: `edge_selected:${edge.from}->${edge.to}` },
                ...prev,
              ].slice(0, 10));
            }}
          />
          <SystemInspector node={selectedNode} replayCommands={displayGraph.replay_commands} />
          <EdgeInspector edge={selectedEdge} />
          <RecommendationDebugPanel priority={priority} />
        </div>
      </div>
    </section>
  );
}
