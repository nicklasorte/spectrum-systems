import React from 'react';
import type { SystemGraphPayload } from '@/lib/systemGraph';

export function ExplainFreezePanel({ graph }: { graph: SystemGraphPayload }) {
  const show = graph.trust_posture === 'freeze_signal' || graph.graph_state === 'degraded_signal' || graph.trust_posture === 'blocked_signal';
  if (!show) return null;
  const cause = graph.failure_path[0] ?? 'evidence_insufficient';
  const nextAction = graph.focus_systems[0] ? `harden ${graph.focus_systems[0]} before advancing dependent systems.` : 'evidence is insufficient for a safe next action.';
  return (
    <div className="border rounded p-3 bg-orange-50" data-testid="explain-freeze-panel">
      <h3 className="font-semibold">Explain Freeze</h3>
      <p>Root cause: {cause === 'evidence_insufficient' ? 'evidence is insufficient.' : `${cause} has missing trust-gap signals.`}</p>
      <p>Propagation path: {graph.failure_path.join(' → ') || 'evidence is insufficient.'}</p>
      <p>Missing artifacts: {graph.missing_artifacts.join(', ') || 'none'}</p>
      <p>Dominant fallback areas: {Object.entries(graph.source_mix).filter(([,n]) => n>0 && (n as number) > 0).map(([k]) => k).join(', ')}</p>
      <p>Recommended next action: {nextAction}</p>
    </div>
  );
}
