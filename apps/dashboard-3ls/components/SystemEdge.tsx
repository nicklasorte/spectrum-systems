import React from 'react';
import type { SystemGraphEdge } from '@/lib/systemGraph';

interface Props {
  edge: SystemGraphEdge;
  from: { x: number; y: number };
  to: { x: number; y: number };
  opacity: number;
  hidden?: boolean;
  nodeWidth?: number;
  nodeHeight?: number;
}

function endpoints(from: { x: number; y: number }, to: { x: number; y: number }, nodeWidth: number, nodeHeight: number) {
  const fromCenter = { x: from.x + nodeWidth / 2, y: from.y + nodeHeight / 2 };
  const toCenter = { x: to.x + nodeWidth / 2, y: to.y + nodeHeight / 2 };

  let x1 = fromCenter.x;
  let y1 = fromCenter.y;
  let x2 = toCenter.x;
  let y2 = toCenter.y;

  const sameRow = Math.abs(from.y - to.y) < 1;
  if (sameRow) {
    if (toCenter.x > fromCenter.x) {
      x1 = from.x + nodeWidth;
      x2 = to.x;
    } else {
      x1 = from.x;
      x2 = to.x + nodeWidth;
    }
  } else if (to.y > from.y) {
    y1 = from.y + nodeHeight;
    y2 = to.y;
  } else {
    y1 = from.y;
    y2 = to.y + nodeHeight;
  }

  return { x1, y1, x2, y2 };
}

export function SystemEdge({ edge, from, to, opacity, hidden, nodeWidth = 120, nodeHeight = 70 }: Props) {
  if (hidden) {
    return (
      <line
        x1={0}
        y1={0}
        x2={0}
        y2={0}
        stroke="transparent"
        opacity={0}
        data-testid={`trust-edge-${edge.from}-${edge.to}`}
        data-edge-hidden="true"
      />
    );
  }

  const isCore = edge.edge_type === 'dependency' && !edge.is_broken && !edge.is_failure_path;
  const isFailure = edge.is_failure_path && !edge.is_broken;
  const isBroken = edge.is_broken;

  let stroke = '#9ca3af';
  let dasharray: string | undefined = '4 4';
  let strokeWidth = 1.4;
  let marker = 'url(#arrow-secondary)';

  if (isBroken) {
    stroke = '#dc2626';
    dasharray = '4 4';
    strokeWidth = 2;
    marker = 'url(#arrow-broken)';
  } else if (isFailure) {
    stroke = '#ea580c';
    dasharray = undefined;
    strokeWidth = 2;
    marker = 'url(#arrow-failure)';
  } else if (isCore) {
    stroke = '#1d4ed8';
    dasharray = undefined;
    strokeWidth = 2.2;
    marker = 'url(#arrow-core)';
  } else if (edge.edge_type === 'overlay') {
    stroke = '#7c3aed';
    dasharray = '5 4';
  } else if (edge.edge_type === 'support') {
    stroke = '#15803d';
    dasharray = '5 4';
  } else if (edge.edge_type === 'candidate') {
    stroke = '#9333ea';
    dasharray = '2 5';
  }

  const { x1, y1, x2, y2 } = endpoints(from, to, nodeWidth, nodeHeight);

  return (
    <line
      x1={x1}
      y1={y1}
      x2={x2}
      y2={y2}
      stroke={stroke}
      strokeWidth={strokeWidth}
      strokeDasharray={dasharray}
      markerEnd={marker}
      opacity={opacity}
      data-testid={`trust-edge-${edge.from}-${edge.to}`}
      data-edge-style={isBroken ? 'broken' : isFailure ? 'failure' : isCore ? 'core' : 'secondary'}
    />
  );
}
