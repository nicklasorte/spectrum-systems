import React, { useMemo } from 'react';
import { SystemNode } from './SystemNode';
import { SystemEdge } from './SystemEdge';
import type { DebugMode, SystemGraphEdge, SystemGraphPayload } from '@/lib/systemGraph';

export type GraphLayoutKey = 'layered' | 'compact';

const NODE_WIDTH = 120;
const NODE_HEIGHT = 70;
const CANVAS_WIDTH = 1100;

interface RowDef {
  key: string;
  label: string;
  dashed: boolean;
  y: number;
  slots: string[];
  groupColor: string;
}

const LAYOUTS: Record<GraphLayoutKey, RowDef[]> = {
  layered: [
    { key: 'overlay', label: 'Overlay candidates', dashed: true, y: 20, slots: ['REP', 'LIN', 'OBS', 'SLO'], groupColor: '#ede9fe' },
    { key: 'core', label: 'Core trust loop', dashed: false, y: 150, slots: ['AEX', 'PQX', 'EVL', 'TPA', 'CDE', 'SEL'], groupColor: '#eff6ff' },
    { key: 'support', label: 'Support systems', dashed: true, y: 280, slots: ['CTX', 'PRM', 'TLC', 'RIL', 'FRE', 'JDX', 'PRX'], groupColor: '#ecfdf5' },
    { key: 'extension', label: 'Extensions', dashed: true, y: 410, slots: ['HOP', 'H01', 'RFX', 'MET'], groupColor: '#faf5ff' },
  ],
  compact: [
    { key: 'overlay', label: 'Overlay candidates', dashed: true, y: 20, slots: ['REP', 'LIN', 'OBS', 'SLO'], groupColor: '#ede9fe' },
    { key: 'core', label: 'Core trust loop', dashed: false, y: 130, slots: ['AEX', 'PQX', 'EVL', 'TPA', 'CDE', 'SEL'], groupColor: '#eff6ff' },
    { key: 'support', label: 'Support + extension', dashed: true, y: 240, slots: ['CTX', 'PRM', 'TLC', 'RIL', 'FRE', 'JDX', 'PRX', 'HOP', 'H01', 'RFX', 'MET'], groupColor: '#ecfdf5' },
  ],
};

const CORE_CHAIN: ReadonlyArray<[string, string]> = [['AEX', 'PQX'], ['PQX', 'EVL'], ['EVL', 'TPA'], ['TPA', 'CDE'], ['CDE', 'SEL']];

function buildSlotPositions(layout: GraphLayoutKey): Map<string, { x: number; y: number }> {
  const map = new Map<string, { x: number; y: number }>();
  const padX = 30;
  for (const row of LAYOUTS[layout]) {
    const usable = CANVAS_WIDTH - 2 * padX;
    const n = row.slots.length;
    const totalWidth = n * NODE_WIDTH;
    const gap = n > 1 ? (usable - totalWidth) / (n - 1) : 0;
    row.slots.forEach((slot, idx) => map.set(slot, { x: padX + idx * (NODE_WIDTH + gap), y: row.y }));
  }
  return map;
}

function buildOverflowPositions(layout: GraphLayoutKey, ids: string[]): Map<string, { x: number; y: number }> {
  const map = new Map<string, { x: number; y: number }>();
  const baseY = (LAYOUTS[layout].at(-1)?.y ?? 380) + NODE_HEIGHT + 30;
  ids.forEach((id, idx) => map.set(id, { x: 30 + idx * (NODE_WIDTH + 20), y: baseY }));
  return map;
}

interface Props {
  graph: SystemGraphPayload;
  selectedSystem: string | null;
  selectedEdgeKey?: string | null;
  showAll: boolean;
  layout?: GraphLayoutKey;
  debugMode?: DebugMode;
  highlightedPath?: string[];
  onSelect: (systemId: string) => void;
  onSelectEdge?: (edge: SystemGraphEdge) => void;
}

export function SystemTrustGraph({ graph, selectedSystem, selectedEdgeKey = null, showAll, layout = 'layered', debugMode = 'clean_structure', highlightedPath = [], onSelect, onSelectEdge }: Props) {
  const slotPositions = useMemo(() => buildSlotPositions(layout), [layout]);
  const overflowIds = useMemo(() => graph.nodes.map((n) => n.system_id).filter((id) => !slotPositions.has(id)), [graph.nodes, slotPositions]);
  const overflowPositions = useMemo(() => buildOverflowPositions(layout, overflowIds), [layout, overflowIds]);

  const allPositions = useMemo(() => {
    const m = new Map<string, { x: number; y: number }>();
    slotPositions.forEach((v, k) => m.set(k, v));
    overflowPositions.forEach((v, k) => m.set(k, v));
    return m;
  }, [slotPositions, overflowPositions]);

  const canvasHeight = useMemo(() => {
    const baseHeight = (LAYOUTS[layout].at(-1)?.y ?? 380) + NODE_HEIGHT + 30;
    return overflowIds.length > 0 ? baseHeight + NODE_HEIGHT + 30 : baseHeight;
  }, [layout, overflowIds.length]);

  const coreEdgeKeys = useMemo(() => new Set(CORE_CHAIN.map(([from, to]) => `${from}-${to}`)), []);
  const highlightedSet = useMemo(() => new Set(highlightedPath), [highlightedPath]);
  const selectedNeighborhood = useMemo(() => {
    if (!selectedSystem) return new Set<string>();
    const set = new Set<string>();
    for (const edge of graph.edges) if (edge.from === selectedSystem || edge.to === selectedSystem) set.add(`${edge.from}-${edge.to}`);
    return set;
  }, [graph.edges, selectedSystem]);

  const isPathEdge = (from: string, to: string) => {
    for (let i = 0; i < highlightedPath.length - 1; i += 1) if (highlightedPath[i] === from && highlightedPath[i + 1] === to) return true;
    return false;
  };

  return (
    <div className="border rounded-lg p-4 bg-white border-slate-200 text-slate-900 dark:bg-slate-900 dark:border-slate-700 dark:text-slate-100" data-testid="system-trust-graph" data-layout={layout} data-debug-mode={debugMode}>
      <svg viewBox={`0 0 ${CANVAS_WIDTH} ${canvasHeight}`} className="w-full h-auto" role="img" aria-label="System trust graph" data-testid="system-trust-graph-svg">
        <defs>
          <marker id="arrow-core" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 Z" fill="#1d4ed8" /></marker>
          <marker id="arrow-failure" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 Z" fill="#ea580c" /></marker>
          <marker id="arrow-broken" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 Z" fill="#dc2626" /></marker>
          <marker id="arrow-secondary" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 Z" fill="#9ca3af" /></marker>
        </defs>

        {LAYOUTS[layout].map((row) => (
          <g key={`row-${row.key}`} data-testid={`graph-row-${row.key}`}>
            <rect x={12} y={row.y - 18} width={CANVAS_WIDTH - 24} height={NODE_HEIGHT + 36} fill={row.groupColor} fillOpacity={0.45} stroke="#cbd5e1" strokeDasharray={row.dashed ? '6 4' : undefined} strokeWidth={1} rx={10} />
            <text x={24} y={row.y - 4} fontSize={10} fill="#475569" fontWeight={600}>{row.label.toUpperCase()}</text>
          </g>
        ))}

        {graph.edges.map((edge) => {
          const from = allPositions.get(edge.from);
          const to = allPositions.get(edge.to);
          if (!from || !to) return null;
          const edgeKey = `${edge.from}-${edge.to}`;
          const isCoreEdge = coreEdgeKeys.has(edgeKey);
          const isFailureEdge = edge.is_failure_path || isPathEdge(edge.from, edge.to);
          const isSelectedEdge = selectedNeighborhood.has(edgeKey);
          let visible = debugMode === 'full_registry';
          if (debugMode === 'clean_structure') visible = isCoreEdge;
          if (debugMode === 'failure_path') visible = isCoreEdge || isFailureEdge;
          if (debugMode === 'selected_node') visible = isCoreEdge || isSelectedEdge;
          if (showAll) visible = true;
          const opacity = visible ? (debugMode === 'full_registry' && !isCoreEdge ? 0.65 : 1) : 0;
          return <SystemEdge key={edgeKey} edge={edge} from={from} to={to} opacity={opacity} hidden={opacity === 0} nodeWidth={NODE_WIDTH} nodeHeight={NODE_HEIGHT} highlighted={isFailureEdge} onSelect={onSelectEdge} />;
        })}

        {graph.nodes.map((node) => {
          const pos = allPositions.get(node.system_id);
          if (!pos) return null;
          const baseOpacity = showAll || graph.focus_systems.includes(node.system_id) || highlightedSet.has(node.system_id) ? 1 : 0.3;
          const opacity = debugMode === 'selected_node' && selectedSystem && selectedSystem !== node.system_id ? Math.min(baseOpacity, 0.35) : baseOpacity;
          const isOnHighlightedPath = highlightedSet.has(node.system_id);
          return <SystemNode key={node.system_id} node={node} x={pos.x} y={pos.y} width={NODE_WIDTH} height={NODE_HEIGHT} opacity={isOnHighlightedPath ? 1 : opacity} onSelect={onSelect} selected={selectedSystem === node.system_id} isOnHighlightedPath={isOnHighlightedPath} isHighlightRoot={highlightedPath[0] === node.system_id} />;
        })}
      </svg>
    </div>
  );
}
