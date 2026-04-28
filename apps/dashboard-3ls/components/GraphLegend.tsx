import React from 'react';

const NODE_GROUPS: Array<{ key: string; label: string; fill: string; border: string }> = [
  { key: 'core', label: 'Core upstream (AEX, PQX, EVL)', fill: '#dbeafe', border: '#1d4ed8' },
  { key: 'control', label: 'Control / enforcement (TPA, CDE, SEL)', fill: '#fde68a', border: '#b45309' },
  { key: 'support', label: 'Support systems', fill: '#bbf7d0', border: '#15803d' },
  { key: 'overlay', label: 'Overlay / candidate', fill: '#ddd6fe', border: '#7c3aed' },
];

const EDGE_GROUPS: Array<{ key: string; label: string; stroke: string; dash?: string }> = [
  { key: 'core', label: 'Core flow (artifact-backed)', stroke: '#1d4ed8' },
  { key: 'failure', label: 'Failure path', stroke: '#ea580c' },
  { key: 'broken', label: 'Broken / missing', stroke: '#dc2626', dash: '4 4' },
  { key: 'secondary', label: 'Secondary / observed', stroke: '#9ca3af', dash: '5 4' },
];

const TRUST_BORDERS: Array<{ key: string; label: string; color: string }> = [
  { key: 'trusted_signal', label: 'trusted', color: '#16a34a' },
  { key: 'caution_signal', label: 'caution', color: '#ca8a04' },
  { key: 'freeze_signal', label: 'freeze', color: '#ea580c' },
  { key: 'blocked_signal', label: 'blocked', color: '#dc2626' },
  { key: 'unknown_signal', label: 'unknown', color: '#94a3b8' },
];

export function GraphLegend() {
  return (
    <div className="border dark:border-slate-700 rounded p-3 text-xs space-y-3 bg-white dark:bg-slate-900 dark:text-slate-100" data-testid="graph-legend">
      <h3 className="font-semibold text-sm">Graph Legend</h3>

      <div data-testid="legend-node-groups">
        <p className="font-medium mb-1">Node groups</p>
        <ul className="space-y-1">
          {NODE_GROUPS.map((group) => (
            <li key={group.key} className="flex items-center gap-2" data-testid={`legend-node-${group.key}`}>
              <span
                className="inline-block w-4 h-3 rounded"
                style={{ backgroundColor: group.fill, border: `1.5px solid ${group.border}` }}
                aria-hidden
              />
              <span>{group.label}</span>
            </li>
          ))}
        </ul>
      </div>

      <div data-testid="legend-edge-types">
        <p className="font-medium mb-1">Edge types</p>
        <ul className="space-y-1">
          {EDGE_GROUPS.map((group) => (
            <li key={group.key} className="flex items-center gap-2" data-testid={`legend-edge-${group.key}`}>
              <svg width="36" height="10" aria-hidden>
                <line x1="0" y1="5" x2="36" y2="5" stroke={group.stroke} strokeWidth="2" strokeDasharray={group.dash} />
              </svg>
              <span>{group.label}</span>
            </li>
          ))}
        </ul>
      </div>

      <div data-testid="legend-trust-borders">
        <p className="font-medium mb-1">Trust state (border)</p>
        <ul className="space-y-1">
          {TRUST_BORDERS.map((trust) => (
            <li key={trust.key} className="flex items-center gap-2" data-testid={`legend-trust-${trust.key}`}>
              <span
                className="inline-block w-4 h-3 rounded bg-white"
                style={{ border: `2px solid ${trust.color}` }}
                aria-hidden
              />
              <span>{trust.label}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
