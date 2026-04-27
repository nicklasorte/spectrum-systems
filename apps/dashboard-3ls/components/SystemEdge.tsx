import React from 'react';
import type { SystemGraphEdge } from '@/lib/systemGraph';

interface Props {
  edge: SystemGraphEdge;
  from: { x: number; y: number };
  to: { x: number; y: number };
  opacity: number;
}

export function SystemEdge({ edge, from, to, opacity }: Props) {
  const stroke = edge.is_broken ? '#dc2626' : edge.is_failure_path ? '#ea580c' : '#6b7280';
  const dasharray = edge.is_broken ? '4 4' : edge.source_type === 'artifact_store' ? undefined : edge.edge_type === 'candidate' ? '2 5' : '6 4';
  return (
    <line
      x1={from.x + 110}
      y1={from.y + 28}
      x2={to.x}
      y2={to.y + 28}
      stroke={stroke}
      strokeWidth={2}
      strokeDasharray={dasharray}
      opacity={opacity}
      data-testid={`trust-edge-${edge.from}-${edge.to}`}
    />
  );
}
