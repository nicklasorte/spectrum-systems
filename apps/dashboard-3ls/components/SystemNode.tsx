import React from 'react';
import type { SystemGraphNode } from '@/lib/systemGraph';
import { humanTrustLabel } from '@/lib/humanStateLabels';

const TRUST_BORDER: Record<string, string> = {
  trusted_signal: '#16a34a',
  caution_signal: '#ca8a04',
  blocked_signal: '#dc2626',
  freeze_signal: '#ea580c',
  degraded_signal: '#ea580c',
  unknown_signal: '#94a3b8',
};

const LAYER_FILL: Record<string, { primary: string; secondary: string; text: string }> = {
  core: { primary: '#dbeafe', secondary: '#eff6ff', text: '#1e3a8a' },
  control: { primary: '#fde68a', secondary: '#fef3c7', text: '#78350f' },
  support: { primary: '#bbf7d0', secondary: '#dcfce7', text: '#14532d' },
  overlay: { primary: '#ddd6fe', secondary: '#ede9fe', text: '#4c1d95' },
  candidate: { primary: '#e9d5ff', secondary: '#faf5ff', text: '#581c87' },
  unknown: { primary: '#e5e7eb', secondary: '#f3f4f6', text: '#374151' },
};

const CONTROL_SYSTEMS: ReadonlySet<string> = new Set(['CDE', 'SEL', 'TPA']);

const SHORT_PURPOSE: Record<string, string> = {
  AEX: 'admission gate',
  PQX: 'execution',
  EVL: 'evaluation',
  TPA: 'trust pulse',
  CDE: 'control decision',
  SEL: 'enforcement',
  REP: 'replay overlay',
  LIN: 'lineage',
  OBS: 'observation',
  SLO: 'slo tracker',
  CTX: 'context',
  PRM: 'prompt registry',
  TLC: 'orchestration',
  RIL: 'input structure',
  FRE: 'failure routing',
  JDX: 'judgment',
  PRX: 'permissions',
  PRA: 'permissions',
  GOV: 'governance',
  MAP: 'map registry',
  HOP: 'handoff',
  H01: 'hardening slice',
  RFX: 'retry/fix',
  MET: 'metrics',
  METS: 'metric stream',
};

function colorGroup(node: SystemGraphNode): { primary: string; secondary: string; text: string } {
  if (CONTROL_SYSTEMS.has(node.system_id)) return LAYER_FILL.control;
  if (node.layer === 'core') return LAYER_FILL.core;
  if (node.layer === 'support') return LAYER_FILL.support;
  if (node.layer === 'overlay') return LAYER_FILL.overlay;
  if (node.layer === 'candidate') return LAYER_FILL.candidate;
  return LAYER_FILL.unknown;
}

function shortPurpose(node: SystemGraphNode): string {
  const cleanedRole = (node.role ?? '').replace(/_/g, ' ').slice(0, 18);
  return SHORT_PURPOSE[node.system_id] ?? (cleanedRole || 'unspecified');
}

interface Props {
  node: SystemGraphNode;
  x: number;
  y: number;
  width?: number;
  height?: number;
  opacity: number;
  onSelect: (systemId: string) => void;
  selected: boolean;
  isOnHighlightedPath?: boolean;
  isHighlightRoot?: boolean;
}

export function SystemNode({
  node,
  x,
  y,
  width = 120,
  height = 70,
  opacity,
  onSelect,
  selected,
  isOnHighlightedPath = false,
  isHighlightRoot = false,
}: Props) {
  const colors = colorGroup(node);
  const trustBorder = TRUST_BORDER[node.trust_state] ?? '#94a3b8';
  const purpose = shortPurpose(node);
  const outline = selected
    ? '#0f172a'
    : isHighlightRoot
      ? '#dc2626'
      : isOnHighlightedPath
        ? '#ea580c'
        : trustBorder;
  const outlineWidth = selected || isHighlightRoot ? 3 : isOnHighlightedPath ? 2.5 : 1.5;
  // D3L-DATA-REGISTRY-01 Phase 5: node card shows only acronym + one
  // short role + one status badge. src/weight/warning fields move to
  // the inspector so the default graph is not cluttered.
  const status = humanTrustLabel(node.trust_state);

  return (
    <g
      transform={`translate(${x}, ${y})`}
      opacity={opacity}
      onClick={() => onSelect(node.system_id)}
      style={{ cursor: 'pointer' }}
      data-testid={`trust-node-${node.system_id}`}
      data-selected={selected ? 'true' : 'false'}
      data-trust-state={node.trust_state}
      data-trust-label={status}
      data-debug-status={node.debug_status}
      data-highlight-path={isOnHighlightedPath ? 'true' : 'false'}
      data-highlight-root={isHighlightRoot ? 'true' : 'false'}
    >
      <rect
        width={width}
        height={height}
        rx={10}
        ry={10}
        fill={colors.secondary}
        stroke={outline}
        strokeWidth={outlineWidth}
      />
      <rect
        x={0}
        y={0}
        width={width}
        height={22}
        rx={10}
        ry={10}
        fill={colors.primary}
      />
      <rect x={0} y={12} width={width} height={10} fill={colors.primary} />
      <text x={10} y={16} fontSize={13} fontWeight={700} fill={colors.text}>
        {node.system_id}
      </text>
      <text x={10} y={40} fontSize={10} fill="#1f2937">
        {purpose}
      </text>
      <rect x={10} y={48} width={width - 20} height={16} rx={6} fill={trustBorder} fillOpacity={0.12} stroke={trustBorder} strokeWidth={0.75} />
      <text x={width / 2} y={59} fontSize={10} fill={trustBorder} fontWeight={700} textAnchor="middle">
        {status}
      </text>
    </g>
  );
}
