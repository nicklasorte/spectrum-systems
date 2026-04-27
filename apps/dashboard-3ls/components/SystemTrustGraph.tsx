import React, { useMemo } from 'react';
import { SystemNode } from './SystemNode';
import { SystemEdge } from './SystemEdge';
import type { SystemGraphPayload } from '@/lib/systemGraph';

const SLOT_POSITIONS: Record<string, { x: number; y: number }> = {
  REP: { x: 30, y: 20 }, LIN: { x: 180, y: 20 }, OBS: { x: 330, y: 20 }, SLO: { x: 480, y: 20 },
  AEX: { x: 30, y: 140 }, PQX: { x: 180, y: 140 }, EVL: { x: 330, y: 140 }, TPA: { x: 480, y: 140 }, CDE: { x: 630, y: 140 }, SEL: { x: 780, y: 140 },
  CTX: { x: 30, y: 260 }, PRM: { x: 140, y: 260 }, TLC: { x: 250, y: 260 }, RIL: { x: 360, y: 260 }, FRE: { x: 470, y: 260 }, JDX: { x: 580, y: 260 }, PRA: { x: 690, y: 260 }, GOV: { x: 800, y: 260 }, MAP: { x: 910, y: 260 },
  H01: { x: 30, y: 380 }, RFX: { x: 180, y: 380 }, HOP: { x: 330, y: 380 }, MET: { x: 480, y: 380 }, METS: { x: 630, y: 380 },
};

interface Props {
  graph: SystemGraphPayload;
  selectedSystem: string | null;
  showAll: boolean;
  onSelect: (systemId: string) => void;
}

export function SystemTrustGraph({ graph, selectedSystem, showAll, onSelect }: Props) {
  const nodeById = useMemo(() => new Map(graph.nodes.map((node) => [node.system_id, node])), [graph.nodes]);

  const connectedToFocus = useMemo(() => {
    const set = new Set<string>();
    for (const edge of graph.edges) {
      if (graph.focus_systems.includes(edge.from) || graph.focus_systems.includes(edge.to)) {
        set.add(edge.from);
        set.add(edge.to);
      }
    }
    return set;
  }, [graph.edges, graph.focus_systems]);

  return (
    <div className="border rounded p-3" data-testid="system-trust-graph">
      <svg width="1040" height="470" role="img" aria-label="System trust graph">
        {graph.edges.map((edge) => {
          const from = SLOT_POSITIONS[edge.from] ?? { x: 920, y: 380 };
          const to = SLOT_POSITIONS[edge.to] ?? { x: 920, y: 420 };
          const opacity = showAll ? 1 : graph.focus_systems.includes(edge.from) || graph.focus_systems.includes(edge.to) ? 1 : connectedToFocus.has(edge.from) || connectedToFocus.has(edge.to) ? 0.6 : 0.2;
          return <SystemEdge key={`${edge.from}-${edge.to}`} edge={edge} from={from} to={to} opacity={opacity} />;
        })}
        {graph.nodes.map((node) => {
          const pos = SLOT_POSITIONS[node.system_id] ?? { x: 920, y: 420 };
          const opacity = showAll ? 1 : graph.focus_systems.includes(node.system_id) ? 1 : connectedToFocus.has(node.system_id) ? 0.65 : 0.25;
          return <SystemNode key={node.system_id} node={node} x={pos.x} y={pos.y} opacity={opacity} onSelect={onSelect} selected={selectedSystem === node.system_id} />;
        })}
      </svg>
      <p className="text-xs text-gray-500">Edges come from API payload artifacts; visual slots are static for readability only.</p>
      <div className="hidden" data-testid="core-flow-systems">AEX PQX EVL TPA CDE SEL</div>
      <div className="hidden" data-testid="overlay-systems">REP LIN OBS SLO</div>
      <div className="hidden" data-testid="candidate-systems">H01 RFX HOP MET METS</div>
    </div>
  );
}
