import React from 'react';
import type { SystemGraphNode } from '@/lib/systemGraph';

export function SystemInspector({ node, replayCommands }: { node: SystemGraphNode | null; replayCommands: string[] }) {
  if (!node) {
    return <div className="border rounded p-3 text-sm text-gray-600" data-testid="system-inspector">Select a node to investigate.</div>;
  }
  return (
    <div className="border rounded p-3 text-sm" data-testid="system-inspector">
      <h3 className="font-semibold">Investigate: {node.system_id}</h3>
      <p>upstream: {node.upstream.join(', ') || 'none'}</p>
      <p>downstream: {node.downstream.join(', ') || 'none'}</p>
      <p>trust gaps: {node.trust_gap_signals.join(', ') || 'none'}</p>
      <p>artifact refs: {node.source_artifact_refs.join(', ')}</p>
      <p>source mix: {node.source_type}</p>
      <p>minimum safe prompt scope: recommendation: single-system hardening for {node.system_id} trust-gap signals.</p>
      <p>replay command refs: {replayCommands.join(' | ')}</p>
    </div>
  );
}
