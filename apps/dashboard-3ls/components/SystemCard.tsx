import React from 'react';

interface SystemMetrics {
  system_id: string;
  system_name: string;
  system_type: string;
  health_score: number;
  status: 'healthy' | 'warning' | 'critical';
  incidents_week: number;
  contract_violations: Array<{rule: string, detail: string}>;
}

export function SystemCard({ 
  system, 
  onClick, 
  isSelected 
}: { 
  system: SystemMetrics;
  onClick: () => void;
  isSelected: boolean;
}) {
  const statusColors = {
    healthy: 'bg-green-50 border-green-300',
    warning: 'bg-yellow-50 border-yellow-300',
    critical: 'bg-red-50 border-red-300',
  };

  const statusBadgeColors = {
    healthy: 'bg-green-100 text-green-800',
    warning: 'bg-yellow-100 text-yellow-800',
    critical: 'bg-red-100 text-red-800',
  };

  return (
    <div
      onClick={onClick}
      className={`p-6 rounded-lg border-2 cursor-pointer transition ${
        isSelected 
          ? 'ring-2 ring-blue-500 ' + statusColors[system.status]
          : statusColors[system.status]
      }`}
    >
      <div className="flex justify-between items-start mb-4">
        <div>
          <h3 className="font-bold text-lg">{system.system_id}</h3>
          <p className="text-sm text-gray-600">{system.system_name}</p>
          <p className="text-xs text-gray-500">{system.system_type}</p>
        </div>
        <div className="text-right">
          <div className="text-3xl font-bold">{system.health_score}</div>
          <span className={`inline-block px-2 py-1 rounded text-xs font-semibold ${
            statusBadgeColors[system.status]
          }`}>
            {system.status.toUpperCase()}
          </span>
        </div>
      </div>

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
              <li key={v.rule} className="text-red-600">• {v.rule}</li>
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
