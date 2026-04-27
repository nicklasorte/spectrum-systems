import React from 'react';
import type { SystemGraphPayload } from '@/lib/systemGraph';

export function TrustPulseBar({ graph, lastRecompute, onRecomputeClick }: { graph: SystemGraphPayload; lastRecompute: string | null; onRecomputeClick: React.ReactNode }) {
  const total = graph.nodes.length || 1;
  const artifactPct = Math.round(((graph.source_mix.artifact_store + graph.source_mix.repo_registry) / total) * 100);
  const fallbackPct = Math.round(((graph.source_mix.stub_fallback + graph.source_mix.missing) / total) * 100);

  return (
    <div className="border rounded p-3 bg-slate-50" data-testid="trust-pulse-bar">
      <div className="flex flex-wrap items-center gap-4 text-sm">
        <span>System Trust: <strong>{graph.trust_posture}</strong></span>
        <span>Last recompute: {lastRecompute ?? graph.generated_at}</span>
        <span>Artifact-backed: {artifactPct}%</span>
        <span>Stub fallback: {fallbackPct}%</span>
        {onRecomputeClick}
      </div>
      {graph.warnings.length > 0 && (
        <p className="text-xs text-amber-700 mt-2">warnings: {graph.warnings.join(', ')}</p>
      )}
    </div>
  );
}
