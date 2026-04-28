import React from 'react';
import { DEBUG_MODES, type DebugMode } from '@/lib/systemGraph';

interface Props {
  value: DebugMode;
  onChange: (mode: DebugMode) => void;
}

export function DebugModeSelector({ value, onChange }: Props) {
  return (
    <label className="flex items-center gap-2 text-xs" data-testid="debug-mode-selector">
      <span className="text-slate-600 dark:text-slate-300">Graph mode</span>
      <select
        className="border rounded px-2 py-1 text-xs bg-white text-slate-900 border-slate-300 dark:bg-slate-900 dark:text-slate-100 dark:border-slate-600"
        value={value}
        onChange={(event) => onChange(event.target.value as DebugMode)}
        data-testid="debug-mode-selector-input"
      >
        {DEBUG_MODES.map((mode) => (
          <option key={mode.value} value={mode.value} title={mode.description}>
            {mode.label}
          </option>
        ))}
      </select>
      {value === 'full_registry' && (
        <span className="text-amber-700 dark:text-amber-300" data-testid="full-registry-warning">
          dense diagnostic view
        </span>
      )}
    </label>
  );
}
