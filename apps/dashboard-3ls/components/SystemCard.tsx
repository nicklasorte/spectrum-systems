import React from 'react';
import type { DataSource } from '@/lib/types';

export type SystemCardStatus = 'healthy' | 'warning' | 'critical' | 'unknown';

interface SystemMetrics {
  system_id: string;
  system_name: string;
  system_type: string;
  health_score: number;
  status: SystemCardStatus;
  incidents_week: number;
  contract_violations: Array<{ rule: string; detail: string }>;
  data_source?: DataSource;
  authority_role?: string | null;
  display_group?: string | null;
}

const STATUS_COLORS: Record<SystemCardStatus, string> = {
  healthy: 'bg-green-50 border-green-300',
  warning: 'bg-yellow-50 border-yellow-300',
  critical: 'bg-red-50 border-red-300',
  unknown: 'bg-gray-50 border-gray-300',
};

const STATUS_BADGE_COLORS: Record<SystemCardStatus, string> = {
  healthy: 'bg-green-100 text-green-800',
  warning: 'bg-yellow-100 text-yellow-800',
  critical: 'bg-red-100 text-red-800',
  unknown: 'bg-gray-200 text-gray-700',
};

const SOURCE_BADGE_STYLES: Record<DataSource, string> = {
  artifact_store: 'bg-blue-50 text-blue-700 border-blue-200',
  repo_registry: 'bg-indigo-50 text-indigo-700 border-indigo-200',
  derived: 'bg-purple-50 text-purple-700 border-purple-200',
  derived_estimate: 'bg-amber-50 text-amber-800 border-amber-300',
  stub_fallback: 'bg-orange-50 text-orange-800 border-orange-300',
  unknown: 'bg-gray-100 text-gray-600 border-gray-300',
};

const SOURCE_LABEL: Record<DataSource, string> = {
  artifact_store: 'artifact',
  repo_registry: 'registry',
  derived: 'derived',
  derived_estimate: 'derived estimate',
  stub_fallback: 'stub',
  unknown: 'unknown',
};

export function SystemCard({
  system,
  onClick,
  isSelected,
}: {
  system: SystemMetrics;
  onClick: () => void;
  isSelected: boolean;
}) {
  const ds = system.data_source;

  return (
    <div
      onClick={onClick}
      className={`p-6 rounded-lg border-2 cursor-pointer transition ${
        isSelected
          ? 'ring-2 ring-blue-500 ' + STATUS_COLORS[system.status]
          : STATUS_COLORS[system.status]
      }`}
    >
      <div className="flex justify-between items-start mb-4">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-bold text-lg">{system.system_id}</h3>
            {system.authority_role && (
              <span
                className="text-xs uppercase tracking-wide text-gray-500"
                title={`Authority: ${system.system_id} ${system.authority_role}`}
              >
                {system.authority_role}
              </span>
            )}
          </div>
          <p className="text-sm text-gray-600">{system.system_name}</p>
          <p className="text-xs text-gray-500">{system.system_type}</p>
        </div>
        <div className="text-right">
          <div className="text-3xl font-bold">{system.health_score}</div>
          <span
            className={`inline-block px-2 py-1 rounded text-xs font-semibold ${
              STATUS_BADGE_COLORS[system.status]
            }`}
          >
            {system.status.toUpperCase()}
          </span>
        </div>
      </div>

      {ds && (
        <div className="mb-3">
          <span
            className={`inline-block border rounded px-2 py-0.5 text-[10px] font-mono uppercase tracking-wide ${SOURCE_BADGE_STYLES[ds]}`}
            data-testid="source-badge"
          >
            {SOURCE_LABEL[ds]}
          </span>
        </div>
      )}

      <div className="space-y-2 text-sm border-t pt-3">
        <div className="flex justify-between">
          <span>Incidents (week):</span>
          <span className="font-mono">{system.incidents_week}</span>
        </div>
        <div className="flex justify-between">
          <span>Contract violations:</span>
          <span className="font-mono">{system.contract_violations.length}</span>
        </div>
      </div>

      {system.contract_violations.length > 0 && (
        <div className="mt-3 pt-3 border-t">
          <p className="text-xs font-semibold mb-1">Violations:</p>
          <ul className="text-xs space-y-1">
            {system.contract_violations.slice(0, 2).map((v) => (
              <li key={v.rule} className="text-red-600">
                • {v.rule}
              </li>
            ))}
            {system.contract_violations.length > 2 && (
              <li className="text-gray-500">+{system.contract_violations.length - 2} more</li>
            )}
          </ul>
        </div>
      )}
    </div>
  );
}
