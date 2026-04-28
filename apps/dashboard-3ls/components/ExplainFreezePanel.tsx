import React, { useMemo, useState } from 'react';
import type { SystemGraphPayload } from '@/lib/systemGraph';

interface Props {
  graph: SystemGraphPayload;
  onPathChange?: (path: string[]) => void;
  forceVisible?: boolean;
}

export function ExplainFreezePanel({ graph, onPathChange, forceVisible }: Props) {
  const [active, setActive] = useState(false);
  const showPanel =
    forceVisible ||
    graph.trust_posture === 'freeze_signal' ||
    graph.graph_state === 'degraded_signal' ||
    graph.trust_posture === 'blocked_signal';
  if (!showPanel) return null;

  const path = useMemo(() => graph.failure_path ?? [], [graph.failure_path]);
  const hasPath = path.length > 0;
  const rootCause = path[0] ?? null;
  const directBlockers = useMemo(() => {
    if (!rootCause) return [] as string[];
    const node = graph.nodes.find((n) => n.system_id === rootCause);
    return node?.upstream_blockers ?? [];
  }, [graph.nodes, rootCause]);
  const downstreamAffected = useMemo(() => {
    if (path.length === 0) return [] as string[];
    return path.slice(1);
  }, [path]);

  const toggle = () => {
    const next = !active;
    setActive(next);
    onPathChange?.(next ? path : []);
  };

  const label = graph.trust_posture === 'freeze_signal' ? 'Explain Freeze' : 'Explain Block';

  return (
    <div className="border rounded p-3 bg-orange-50 space-y-2" data-testid="explain-freeze-panel">
      <header className="flex items-center justify-between gap-2">
        <h3 className="font-semibold">{label}</h3>
        <button
          type="button"
          onClick={toggle}
          className={`text-xs px-2 py-0.5 rounded border ${active ? 'bg-orange-600 text-white border-orange-700' : 'bg-white border-orange-300 text-orange-800'}`}
          data-testid="explain-freeze-toggle"
          aria-pressed={active}
        >
          {active ? 'hide path' : 'highlight path'}
        </button>
      </header>
      <p>
        Root cause node: <strong data-testid="explain-freeze-root">{rootCause ?? 'evidence_insufficient'}</strong>
      </p>
      <p data-testid="explain-freeze-path-text">
        Propagation path: {hasPath ? path.join(' → ') : 'evidence is insufficient.'}
      </p>
      <p data-testid="explain-freeze-direct-blockers">
        Direct blockers: {directBlockers.length > 0 ? directBlockers.join(', ') : 'none recorded'}
      </p>
      <p data-testid="explain-freeze-downstream-affected">
        Downstream affected: {downstreamAffected.length > 0 ? downstreamAffected.join(', ') : 'none recorded'}
      </p>
      <p>Missing artifacts: {graph.missing_artifacts.join(', ') || 'none'}</p>
    </div>
  );
}
