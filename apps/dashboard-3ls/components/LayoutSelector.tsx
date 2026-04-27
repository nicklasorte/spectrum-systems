import React from 'react';
import type { GraphLayoutKey } from './SystemTrustGraph';

const OPTIONS: Array<{ value: GraphLayoutKey; label: string }> = [
  { value: 'layered', label: 'Layered (overlay / core / support / extension)' },
  { value: 'compact', label: 'Compact (overlay / core / support+extension)' },
];

interface Props {
  value: GraphLayoutKey;
  onChange: (value: GraphLayoutKey) => void;
}

export function LayoutSelector({ value, onChange }: Props) {
  return (
    <label className="flex items-center gap-2 text-xs" data-testid="layout-selector">
      <span className="text-gray-600">Layout</span>
      <select
        className="border rounded px-2 py-1 text-xs bg-white"
        value={value}
        onChange={(event) => onChange(event.target.value as GraphLayoutKey)}
        data-testid="layout-selector-input"
      >
        {OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}
