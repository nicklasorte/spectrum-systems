import React from 'react';
import { DEBUG_MODES, type DebugMode } from '@/lib/systemGraph';

interface Props {
  value: DebugMode;
  onChange: (mode: DebugMode) => void;
}

export function DebugModeSelector({ value, onChange }: Props) {
  return (
    <label className="flex items-center gap-2 text-xs" data-testid="debug-mode-selector">
      <span className="text-gray-600">Debug mode</span>
      <select
        className="border rounded px-2 py-1 text-xs bg-white"
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
    </label>
  );
}
