import React from 'react';
import type { SystemGraphNode } from '@/lib/systemGraph';

const TRUST_FILL: Record<string, string> = {
  trusted_signal: '#dcfce7',
  caution_signal: '#fef9c3',
  blocked_signal: '#fee2e2',
  freeze_signal: '#ffedd5',
  degraded_signal: '#ffedd5',
  unknown_signal: '#e5e7eb',
};

interface Props {
  node: SystemGraphNode;
  x: number;
  y: number;
  opacity: number;
  onSelect: (systemId: string) => void;
  selected: boolean;
}

export function SystemNode({ node, x, y, opacity, onSelect, selected }: Props) {
  return (
    <g
      transform={`translate(${x}, ${y})`}
      opacity={opacity}
      onClick={() => onSelect(node.system_id)}
      style={{ cursor: 'pointer' }}
      data-testid={`trust-node-${node.system_id}`}
      data-selected={selected ? 'true' : 'false'}
    >
      <rect
        width={110}
        height={56}
        rx={8}
        fill={TRUST_FILL[node.trust_state] ?? '#e5e7eb'}
        stroke={selected ? '#111827' : '#9ca3af'}
        strokeWidth={selected ? 2 : 1}
      />
      <text x={8} y={18} fontSize={12} fontWeight={700}>{node.system_id}</text>
      <text x={8} y={31} fontSize={9}>{node.role.slice(0, 18)}</text>
      <text x={8} y={44} fontSize={9}>{node.source_type === 'artifact_store' ? 'artifact' : node.source_type}</text>
      <text x={88} y={44} fontSize={9}>w:{node.warning_count}</text>
    </g>
  );
}
