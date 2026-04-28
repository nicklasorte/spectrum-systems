'use client';

import React, { useEffect, useMemo, useState } from 'react';
import type { DebugMode, GraphMode, SystemGraphEdge, SystemGraphPayload } from '@/lib/systemGraph';
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
  const [graphMode, setGraphMode] = useState<GraphMode>('clean_structure');
  const [highlightedPath, setHighlightedPath] = useState<string[]>([]);
  const [lastRecompute, setLastRecompute] = useState<string | null>(null);
  const [recomputeStatus, setRecomputeStatus] = useState<string | null>(null);
  const [entries, setEntries] = useState<ActivityEntry[]>([]);
  const [priority, setPriority] = useState<PriorityArtifactLoadResult | null>(null);
  // D3L-DATA-REGISTRY-01 Phase 5: Fit / Scroll toggle. Default 'fit' makes
  // the SVG scale to container width (good on desktop, thumbnail on
  // mobile). 'scroll' renders a wide canvas inside an x-scroll container
  // so the operator can pan a usable, full-resolution graph on mobile.
  const [canvasMode, setCanvasMode] = useState<'fit' | 'scroll'>('fit');

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
      <section className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded p-4" data-testid="trust-graph-section">
        <p className="text-sm text-red-700" data-testid="graph-fail-closed-warning">
          ⚠ Trust graph artifact unavailable. Fail-closed: dashboard will not synthesize graph data.
        </p>
      </section>
    );
  }

  if (!displayGraph) {
    return (
      <section className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded p-4" data-testid="trust-graph-section">
        <p className="text-sm text-gray-500">Loading trust graph artifact…</p>
      </section>
    );
  }

  if (isFailClosed) {
    return (
      <section className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded p-4 space-y-2" data-testid="trust-graph-section">
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
    <section className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded p-4 space-y-3" data-testid="trust-graph-section">
      <header className="flex flex-wrap items-center justify-between gap-2 sticky top-0 z-10 bg-white/95 dark:bg-gray-950/95 pb-1">
        <h2 className="font-semibold">SYSTEM TRUST GRAPH</h2>
        <div className="flex flex-wrap items-center gap-3">
          <DebugModeSelector value={debugMode} onChange={setDebugMode} />
          <label className="text-xs text-slate-700 dark:text-slate-200" htmlFor="graph-mode-select">
            Mode:
            <select
              id="graph-mode-select"
              className="ml-1 border rounded px-1 py-0.5 text-xs bg-white dark:bg-slate-800 dark:border-slate-600"
              value={graphMode}
              onChange={(e) => setGraphMode(e.target.value as GraphMode)}
              data-testid="graph-mode-select"
            >
              <option value="clean_structure">Clean Structure</option>
              <option value="failure_path">Failure Path</option>
              <option value="selected_node">Selected Node</option>
              <option value="full_registry">Full Registry</option>
            </select>
          </label>
          <LayoutSelector value={layout} onChange={setLayout} />
          <button
            type="button"
            className="text-xs underline"
            onClick={() => setShowAll((s) => !s)}
            data-testid="focus-toggle"
          >
            {showAll ? 'Focus mode' : 'Show all'}
          </button>
          <button
            type="button"
            className="text-xs underline"
            onClick={() => setCanvasMode((m) => (m === 'fit' ? 'scroll' : 'fit'))}
            data-testid="canvas-mode-toggle"
            data-canvas-mode={canvasMode}
            aria-label="Toggle Fit / Scroll canvas mode"
          >
            {canvasMode === 'fit' ? 'Scroll canvas' : 'Fit canvas'}
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
          {graphMode === 'full_registry' && (
            <p className="text-xs text-amber-700 dark:text-amber-300" data-testid="full-registry-warning">
              ⚠ Full Registry mode is a dense diagnostic view with secondary and observed edges.
            </p>
          )}
          <ActivityLog entries={entries} />
        </aside>

        <div className="space-y-3 min-w-0" data-testid="graph-main-panel" data-canvas-mode={canvasMode}>
          <div
            className={canvasMode === 'scroll' ? 'overflow-x-auto -mx-2 px-2' : ''}
            data-testid="graph-canvas-wrapper"
          >
            <div
              style={canvasMode === 'scroll' ? { minWidth: '1100px' } : undefined}
              data-testid="graph-canvas-inner"
            >
              <SystemTrustGraph
                graph={displayGraph}
                selectedSystem={selected}
                selectedEdgeKey={selectedEdge ? `${selectedEdge.from}-${selectedEdge.to}` : null}
                showAll={showAll}
                layout={layout}
                debugMode={debugMode}
                graphMode={graphMode}
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
            </div>
          </div>
          <SystemInspector node={selectedNode} replayCommands={displayGraph.replay_commands} />
          <EdgeInspector edge={selectedEdge} />
          <RecommendationDebugPanel priority={priority} />
        </div>
      </div>
    </section>
  );
}
