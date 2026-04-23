'use client';

import React from 'react';
import { SystemMetrics } from './SystemCard';

interface MetricBoxProps {
  label: string;
  value: string | number;
  unit?: string;
  status?: 'healthy' | 'warning' | 'critical';
  isText?: boolean;
}

function MetricBox({
  label,
  value,
  unit = '',
  status = 'healthy',
  isText = false,
}: MetricBoxProps) {
  const statusColors = {
    healthy: 'bg-green-50 border-green-200',
    warning: 'bg-yellow-50 border-yellow-200',
    critical: 'bg-red-50 border-red-200',
  };

  return (
    <div className={`p-4 rounded border ${statusColors[status]}`}>
      <p className="text-sm text-gray-600">{label}</p>
      <p className="text-2xl font-bold mt-1">
        {isText ? value : `${value}${unit}`}
      </p>
    </div>
  );
}

interface SystemDetailProps {
  system?: SystemMetrics;
}

export function SystemDetail({ system }: SystemDetailProps) {
  if (!system) return null;

  return (
    <div className="bg-white rounded-lg p-6 border border-gray-200 mb-8">
      <h2 className="text-2xl font-bold mb-6">
        {system.system_id}: {system.system_name}
      </h2>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <MetricBox
          label="Health Score"
          value={system.health_score}
          unit="%"
          status={system.status}
        />
        <MetricBox
          label="Incidents (week)"
          value={system.incidents_week}
          status={system.incidents_week === 0 ? 'healthy' : 'warning'}
        />
        <MetricBox
          label="Contract Violations"
          value={system.contract_violations.length}
          status={
            system.contract_violations.length === 0 ? 'healthy' : 'critical'
          }
        />
        <MetricBox
          label="Type"
          value={system.system_type}
          isText={true}
        />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <MetricBox
          label="Execution Success"
          value={system.execution_success.toFixed(1)}
          unit="%"
        />
        <MetricBox
          label="Contract Adherence"
          value={system.contract_adherence.toFixed(1)}
          unit="%"
        />
        <MetricBox
          label="Avg Latency"
          value={system.avg_latency_ms.toFixed(0)}
          unit="ms"
        />
        <MetricBox label="Incident Count" value={system.incident_count} />
      </div>

      {system.contract_violations.length > 0 && (
        <div className="bg-red-50 p-4 rounded mb-6 border border-red-200">
          <h3 className="font-semibold mb-2 text-red-900">
            Contract Violations:
          </h3>
          <ul className="space-y-1 text-sm">
            {system.contract_violations.map((v) => (
              <li key={v.rule} className="text-red-700">
                • {v.rule}: {v.detail}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="bg-gray-50 p-4 rounded">
        <h3 className="font-semibold mb-2">System Type: {system.system_type}</h3>
        <p className="text-sm text-gray-600">
          {system.system_name} is responsible for{' '}
          {system.system_type === 'execution' && 'executing bounded operations'}
          {system.system_type === 'governance' && 'governance decisions'}
          {system.system_type === 'orchestration' && 'orchestrating workflows'}
          {system.system_type === 'data' && 'data management'}
          {system.system_type === 'planning' && 'planning and extraction'}
          {system.system_type === 'placeholder' && 'placeholder functionality'}
        </p>
      </div>
    </div>
  );
}
