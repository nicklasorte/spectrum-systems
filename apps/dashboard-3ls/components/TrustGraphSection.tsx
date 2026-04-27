'use client';

import React, { useEffect, useMemo, useState } from 'react';
import type { SystemGraphPayload } from '@/lib/systemGraph';
import { TrustPulseBar } from './TrustPulseBar';
import { RecomputeGraphButton } from './RecomputeGraphButton';
import { SystemTrustGraph } from './SystemTrustGraph';
import { SystemInspector } from './SystemInspector';
import { ExplainFreezePanel } from './ExplainFreezePanel';
import { ActivityLog, type ActivityEntry } from './ActivityLog';

export function TrustGraphSection() {
  const [graph, setGraph] = useState<SystemGraphPayload | null>(null);
  const [lastKnownGraph, setLastKnownGraph] = useState<SystemGraphPayload | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);
  const [lastRecompute, setLastRecompute] = useState<string | null>(null);
  const [entries, setEntries] = useState<ActivityEntry[]>([]);

  const loadGraph = async () => {
    const res = await fetch('/api/system-graph');
    const payload = (await res.json()) as SystemGraphPayload;
    setGraph(payload);
    setLastKnownGraph(payload);
    setEntries((prev) => [{ timestamp: new Date().toISOString(), message: 'graph_loaded' }, ...prev].slice(0, 10));
  };

  useEffect(() => {
    loadGraph().catch(() => {
      setEntries((prev) => [{ timestamp: new Date().toISOString(), message: 'graph_load_failed' }, ...prev].slice(0, 10));
    });
  }, []);

  const displayGraph = graph ?? lastKnownGraph;
  const selectedNode = useMemo(() => displayGraph?.nodes.find((n) => n.system_id === selected) ?? null, [displayGraph, selected]);

  if (!displayGraph) {
    return <section className="bg-white border rounded p-4"><p className="text-sm text-gray-500">Loading trust graph artifact…</p></section>;
  }

  return (
    <section className="bg-white border rounded p-4 space-y-3" data-testid="trust-graph-section">
      <div className="flex justify-between items-center">
        <h2 className="font-semibold">SYSTEM TRUST GRAPH</h2>
        <button type="button" className="text-xs underline" onClick={() => setShowAll((s) => !s)} data-testid="focus-toggle">{showAll ? 'Focus mode' : 'Show all'}</button>
      </div>
      <TrustPulseBar
        graph={displayGraph}
        lastRecompute={lastRecompute}
        onRecomputeClick={
          <RecomputeGraphButton
            onResult={async (result) => {
              const timestamp = new Date().toISOString();
              setLastRecompute(timestamp);
              setEntries((prev) => [{ timestamp, message: `recompute:${result.status}` }, ...prev].slice(0, 10));
              if (result.status === 'recompute_success_signal') {
                await loadGraph();
              }
            }}
          />
        }
      />
      <SystemTrustGraph graph={displayGraph} selectedSystem={selected} showAll={showAll} onSelect={(id) => {
        setSelected(id);
        setEntries((prev) => [{ timestamp: new Date().toISOString(), message: `node_selected:${id}` }, ...prev].slice(0, 10));
      }} />
      <SystemInspector node={selectedNode} replayCommands={displayGraph.replay_commands} />
      <ExplainFreezePanel graph={displayGraph} />
      <ActivityLog entries={entries} />
    </section>
  );
}
