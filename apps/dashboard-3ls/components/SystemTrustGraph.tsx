import React, { useMemo } from 'react';
import { SystemNode } from './SystemNode';
import { SystemEdge } from './SystemEdge';
import type { DebugMode, SystemGraphEdge, SystemGraphPayload } from '@/lib/systemGraph';
import { CONTROL_PATH_SYSTEMS, deriveDebugStatus } from '@/lib/systemGraph';

export type GraphLayoutKey = 'layered' | 'compact';
export type GraphViewMode = 'clean_structure' | 'failure_path' | 'selected_node' | 'full_registry';

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

const SUPPORT_LIKE_LAYERS: ReadonlySet<string> = new Set(['support']);
const CORE_LIKE_LAYERS: ReadonlySet<string> = new Set(['core']);

const BLOCKING_STATUSES: ReadonlySet<string> = new Set(['MISSING', 'STALE', 'FAILED', 'FALLBACK', 'BLOCKING']);

function buildSlotPositions(layout: GraphLayoutKey): Map<string, { x: number; y: number }> {
  const map = new Map<string, { x: number; y: number }>();
  const padX = 30;
  for (const row of LAYOUTS[layout]) {
    const usable = CANVAS_WIDTH - 2 * padX;
    const n = row.slots.length;
    const totalWidth = n * NODE_WIDTH;
    const gap = n > 1 ? (usable - totalWidth) / (n - 1) : 0;
    const startX = padX;
    row.slots.forEach((slot, idx) => {
      map.set(slot, { x: startX + idx * (NODE_WIDTH + gap), y: row.y });
    });
  }
  return map;
}

function buildOverflowPositions(layout: GraphLayoutKey, ids: string[]): Map<string, { x: number; y: number }> {
  const map = new Map<string, { x: number; y: number }>();
  const baseY = (LAYOUTS[layout].at(-1)?.y ?? 380) + NODE_HEIGHT + 30;
  ids.forEach((id, idx) => {
    map.set(id, { x: 30 + idx * (NODE_WIDTH + 20), y: baseY });
  });
  return map;
}

function rowHeight(): number {
  return NODE_HEIGHT + 30;
}

interface Props {
  graph: SystemGraphPayload;
  selectedSystem: string | null;
  selectedEdgeKey?: string | null;
  showAll: boolean;
  layout?: GraphLayoutKey;
  debugMode?: DebugMode;
  highlightedPath?: string[];
  graphMode?: GraphViewMode;
  onSelect: (systemId: string) => void;
  onSelectEdge?: (edge: SystemGraphEdge) => void;
}

const CORE_CHAIN = ['AEX', 'PQX', 'EVL', 'TPA', 'CDE', 'SEL'] as const;
const CORE_CHAIN_EDGE_KEYS = new Set(
  CORE_CHAIN.slice(0, -1).map((id, i) => `${id}->${CORE_CHAIN[i + 1]}`),
);

export function SystemTrustGraph({
  graph,
  selectedSystem,
  selectedEdgeKey = null,
  showAll,
  layout = 'layered',
  debugMode = 'normal',
  highlightedPath = [],
  graphMode = 'clean_structure',
  onSelect,
  onSelectEdge,
}: Props) {
  const slotPositions = useMemo(() => buildSlotPositions(layout), [layout]);

  const overflowIds = useMemo(() => graph.nodes.map((n) => n.system_id).filter((id) => !slotPositions.has(id)), [graph.nodes, slotPositions]);
  const overflowPositions = useMemo(() => buildOverflowPositions(layout, overflowIds), [layout, overflowIds]);

  const allPositions = useMemo(() => {
    const m = new Map<string, { x: number; y: number }>();
    slotPositions.forEach((v, k) => m.set(k, v));
    overflowPositions.forEach((v, k) => m.set(k, v));
    return m;
  }, [slotPositions, overflowPositions]);

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

  const canvasHeight = useMemo(() => {
    const lastRow = LAYOUTS[layout].at(-1);
    const baseHeight = (lastRow?.y ?? 380) + NODE_HEIGHT + 30;
    return overflowIds.length > 0 ? baseHeight + rowHeight() : baseHeight;
  }, [layout, overflowIds.length]);

  const isPrimaryEdge = (from: string, to: string, isFailurePath: boolean, edgeType: string) => {
    if (edgeType === 'dependency') return true;
    if (isFailurePath) return true;
    if (graph.focus_systems.includes(from) || graph.focus_systems.includes(to)) return true;
    return false;
  };

  const highlightedSet = useMemo(() => new Set(highlightedPath), [highlightedPath]);

  const isPathEdge = (from: string, to: string) => {
    if (highlightedPath.length < 2) return false;
    for (let i = 0; i < highlightedPath.length - 1; i += 1) {
      if (highlightedPath[i] === from && highlightedPath[i + 1] === to) return true;
    }
    return false;
  };

  const labelByRow: Array<{ y: number; label: string }> = LAYOUTS[layout].map((row) => ({ y: row.y, label: row.label }));
  const selectedContext = useMemo(() => {
    const out = new Set<string>();
    if (!selectedSystem) return out;
    out.add(selectedSystem);
    for (const edge of graph.edges) {
      if (edge.from === selectedSystem) out.add(edge.to);
      if (edge.to === selectedSystem) out.add(edge.from);
    }
    return out;
  }, [graph.edges, selectedSystem]);

  const isVisibleByMode = (from: string, to: string, edge: SystemGraphEdge) => {
    const coreEdge = CORE_CHAIN_EDGE_KEYS.has(`${from}->${to}`);
    if (graphMode === 'full_registry') return true;
    if (graphMode === 'clean_structure') return coreEdge;
    if (graphMode === 'failure_path') {
      return coreEdge || edge.is_failure_path || (graph.failure_path.includes(from) && graph.failure_path.includes(to));
    }
    if (graphMode === 'selected_node') {
      return coreEdge || (selectedContext.has(from) && selectedContext.has(to));
    }
    return coreEdge;
  };

  const isNodeVisibleByMode = (systemId: string) => {
    if (graphMode === 'full_registry') return true;
    if (graphMode === 'clean_structure') return CORE_CHAIN.includes(systemId as (typeof CORE_CHAIN)[number]);
    if (graphMode === 'failure_path') {
      return CORE_CHAIN.includes(systemId as (typeof CORE_CHAIN)[number]) || graph.failure_path.includes(systemId);
    }
    if (graphMode === 'selected_node') {
      return CORE_CHAIN.includes(systemId as (typeof CORE_CHAIN)[number]) || selectedContext.has(systemId);
    }
    return true;
  };

  // Mode-driven node opacity. Fail-closed: if mode data is missing, fall back to focus dimming.
  const nodeOpacityForMode = (systemId: string, baseOpacity: number) => {
    const node = graph.nodes.find((n) => n.system_id === systemId);
    if (!node) return baseOpacity;
    if (debugMode === 'blockers') {
      const status = node.debug_status ?? deriveDebugStatus(node);
      return BLOCKING_STATUSES.has(status) ? 1 : 0.2;
    }
    if (debugMode === 'control') {
      return CONTROL_PATH_SYSTEMS.includes(systemId) ? 1 : 0.25;
    }
    if (debugMode === 'lineage') {
      return node.source_artifact_refs.length > 0 ? 1 : 0.25;
    }
    if (debugMode === 'freshness') {
      const status = node.debug_status ?? deriveDebugStatus(node);
      return node.source_type === 'missing' || node.source_type === 'stub_fallback' || status === 'STALE'
        ? 1
        : 0.3;
    }
    return baseOpacity;
  };

  const edgeOpacityForMode = (edge: SystemGraphEdge, baseOpacity: number) => {
    if (debugMode === 'blockers') {
      return edge.is_failure_path || edge.is_broken ? 1 : 0.2;
    }
    if (debugMode === 'control') {
      const onPath = CONTROL_PATH_SYSTEMS.includes(edge.from) && CONTROL_PATH_SYSTEMS.includes(edge.to);
      return onPath ? 1 : 0.2;
    }
    if (debugMode === 'lineage') {
      const backed = edge.artifact_backed ?? (edge.source_type === 'artifact_store' || edge.source_type === 'repo_registry');
      return backed ? 1 : 0.3;
    }
    if (debugMode === 'freshness') {
      return edge.last_validated ? 0.4 : 1;
    }
    return baseOpacity;
  };

  return (
    <div
      className="border dark:border-slate-700 rounded-lg p-4 bg-white dark:bg-slate-900 dark:text-slate-100"
      data-testid="system-trust-graph"
      data-layout={layout}
      data-debug-mode={debugMode}
      data-graph-mode={graphMode}
    >
      <svg
        viewBox={`0 0 ${CANVAS_WIDTH} ${canvasHeight}`}
        className="w-full h-auto"
        role="img"
        aria-label="System trust graph"
        data-testid="system-trust-graph-svg"
      >
        <defs>
          <marker id="arrow-core" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M0,0 L10,5 L0,10 Z" fill="#1d4ed8" />
          </marker>
          <marker id="arrow-failure" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M0,0 L10,5 L0,10 Z" fill="#ea580c" />
          </marker>
          <marker id="arrow-broken" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M0,0 L10,5 L0,10 Z" fill="#dc2626" />
          </marker>
          <marker id="arrow-secondary" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
            <path d="M0,0 L10,5 L0,10 Z" fill="#9ca3af" />
          </marker>
        </defs>

        {LAYOUTS[layout].map((row) => {
          const padX = 18;
          const startX = 30 - padX;
          const width = CANVAS_WIDTH - 2 * (30 - padX);
          const y = row.y - 18;
          const height = NODE_HEIGHT + 36;
          return (
            <g key={`row-${row.key}`} data-testid={`graph-row-${row.key}`}>
              <rect
                x={startX}
                y={y}
                width={width}
                height={height}
                fill={row.groupColor}
                fillOpacity={0.45}
                stroke={row.dashed ? '#cbd5e1' : '#cbd5e1'}
                strokeDasharray={row.dashed ? '6 4' : undefined}
                strokeWidth={1}
                rx={10}
              />
              <text x={startX + 12} y={y + 14} fontSize={10} fill="#475569" fontWeight={600} textAnchor="start">
                {row.label.toUpperCase()}
              </text>
            </g>
          );
        })}

        {graph.edges.map((edge) => {
          const from = allPositions.get(edge.from);
          const to = allPositions.get(edge.to);
          if (!from || !to) return null;
          const modeVisible = isVisibleByMode(edge.from, edge.to, edge);
          if (!modeVisible) {
            return (
              <SystemEdge
                key={`${edge.from}-${edge.to}`}
                edge={edge}
                from={from}
                to={to}
                opacity={0}
                hidden
                nodeWidth={NODE_WIDTH}
                nodeHeight={NODE_HEIGHT}
              />
            );
          }
          const primary = isPrimaryEdge(edge.from, edge.to, edge.is_failure_path, edge.edge_type);
          if (!showAll && !primary && debugMode === 'normal') {
            return (
              <SystemEdge
                key={`${edge.from}-${edge.to}`}
                edge={edge}
                from={from}
                to={to}
                opacity={0}
                hidden
                nodeWidth={NODE_WIDTH}
                nodeHeight={NODE_HEIGHT}
              />
            );
          }
          const baseOpacity = showAll
            ? primary
              ? 1
              : 0.45
            : graph.focus_systems.includes(edge.from) || graph.focus_systems.includes(edge.to)
              ? 1
              : connectedToFocus.has(edge.from) || connectedToFocus.has(edge.to)
                ? 0.6
                : 0.2;
          const opacity = debugMode === 'normal' ? baseOpacity : edgeOpacityForMode(edge, baseOpacity);
          const highlighted = isPathEdge(edge.from, edge.to);
          return (
            <SystemEdge
              key={`${edge.from}-${edge.to}`}
              edge={edge}
              from={from}
              to={to}
              opacity={opacity}
              nodeWidth={NODE_WIDTH}
              nodeHeight={NODE_HEIGHT}
              highlighted={highlighted}
              onSelect={onSelectEdge}
            />
          );
        })}

        {graph.nodes.map((node) => {
          if (!isNodeVisibleByMode(node.system_id)) return null;
          const pos = allPositions.get(node.system_id);
          if (!pos) return null;
          const baseOpacity = showAll
            ? 1
            : graph.focus_systems.includes(node.system_id)
              ? 1
              : connectedToFocus.has(node.system_id)
                ? 0.65
                : 0.25;
          const modeOpacity = debugMode === 'normal' ? baseOpacity : nodeOpacityForMode(node.system_id, baseOpacity);
          const isOnHighlightedPath = highlightedSet.has(node.system_id);
          return (
            <SystemNode
              key={node.system_id}
              node={node}
              x={pos.x}
              y={pos.y}
              width={NODE_WIDTH}
              height={NODE_HEIGHT}
              opacity={isOnHighlightedPath ? 1 : modeOpacity}
              onSelect={onSelect}
              selected={selectedSystem === node.system_id}
              isOnHighlightedPath={isOnHighlightedPath}
              isHighlightRoot={highlightedPath.length > 0 && highlightedPath[0] === node.system_id}
            />
          );
        })}

        {labelByRow && null}
      </svg>

      <div className="hidden" data-testid="core-flow-systems">AEX PQX EVL TPA CDE SEL</div>
      <div className="hidden" data-testid="overlay-systems">REP LIN OBS SLO</div>
      <div className="hidden" data-testid="candidate-systems">H01 RFX HOP MET METS</div>
      {selectedEdgeKey && <div className="hidden" data-testid="selected-edge-key">{selectedEdgeKey}</div>}

      <p className="text-xs text-gray-500 mt-2">
        Slots are static for readability; nodes, edges, and trust state come from the artifact payload.
      </p>
    </div>
  );
}

export { LAYOUTS as GRAPH_LAYOUTS, CORE_LIKE_LAYERS, SUPPORT_LIKE_LAYERS };
