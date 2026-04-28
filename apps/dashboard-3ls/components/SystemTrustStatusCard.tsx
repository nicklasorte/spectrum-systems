import React from 'react';
import type { SystemGraphPayload } from '@/lib/systemGraph';

interface Props {
  graph: SystemGraphPayload;
  lastRecompute: string | null;
  isStale: boolean;
}

export function SystemTrustStatusCard({ graph, lastRecompute, isStale }: Props) {
  const total = graph.nodes.length || 1;
  const artifactPct = Math.round(((graph.source_mix.artifact_store + graph.source_mix.repo_registry) / total) * 100);
  const fallbackPct = Math.round(((graph.source_mix.stub_fallback + graph.source_mix.missing) / total) * 100);
  const displayedRecompute = lastRecompute ?? graph.generated_at ?? 'unknown';

  return (
    <div className="border rounded p-3 text-sm space-y-1" data-testid="system-trust-status-card">
      <h3 className="font-semibold text-sm">System Trust Status</h3>
      <p>
        Posture: <strong data-testid="trust-status-posture">{graph.trust_posture}</strong>
      </p>
      <p>
        Graph state: <strong>{graph.graph_state}</strong>
      </p>
      <p data-testid="trust-status-artifact-pct">Artifact-backed: <strong>{artifactPct}%</strong></p>
      <p data-testid="trust-status-fallback-pct">Stub fallback: <strong>{fallbackPct}%</strong></p>
      <p data-testid="trust-status-last-recompute">Last recompute: {displayedRecompute}</p>
      <p>Focus systems: {graph.focus_systems.join(', ') || 'none'}</p>
      {isStale && (
        <p
          className="text-xs text-amber-700 dark:text-amber-300 border border-amber-300 bg-amber-50 rounded px-2 py-1"
          data-testid="stale-warning"
        >
          ⚠ Displayed graph is older than the artifact payload — recompute to refresh.
        </p>
      )}
      {graph.warnings.length > 0 && (
        <p className="text-xs text-amber-700 dark:text-amber-300" data-testid="trust-status-warnings">
          warnings: {graph.warnings.join(', ')}
        </p>
      )}
    </div>
  );
}
