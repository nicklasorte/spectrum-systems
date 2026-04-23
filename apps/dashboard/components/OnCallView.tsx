'use client';

import React from 'react';

export interface Incident {
  id: string;
  title: string;
  system_id: string;
  severity: 'critical' | 'warning' | 'info';
  status: 'open' | 'acknowledged' | 'resolved';
  duration: string;
  root_cause: string;
  recommended_fix: string;
  impact_description: string;
  runbook_url?: string;
}

interface IncidentCardProps {
  incident: Incident;
}

function IncidentCard({ incident }: IncidentCardProps) {
  const severityColors = {
    critical: 'border-red-500 bg-red-50',
    warning: 'border-yellow-500 bg-yellow-50',
    info: 'border-blue-500 bg-blue-50',
  };

  const severityBadgeColors = {
    critical: 'bg-red-100 text-red-800',
    warning: 'bg-yellow-100 text-yellow-800',
    info: 'bg-blue-100 text-blue-800',
  };

  const statusBadgeColors = {
    open: 'bg-red-100 text-red-800',
    acknowledged: 'bg-yellow-100 text-yellow-800',
    resolved: 'bg-green-100 text-green-800',
  };

  return (
    <div className={`p-6 rounded-lg border-l-4 ${severityColors[incident.severity]}`}>
      <div className="flex justify-between items-start mb-4">
        <div className="flex-1">
          <h2 className="text-xl font-bold">{incident.title}</h2>
          <p className="text-sm text-gray-600">{incident.system_id}</p>
        </div>
        <div className="flex gap-2">
          <span
            className={`inline-block px-2 py-1 rounded text-xs font-semibold ${
              severityBadgeColors[incident.severity]
            }`}
          >
            {incident.severity.toUpperCase()}
          </span>
          <span
            className={`inline-block px-2 py-1 rounded text-xs font-semibold ${
              statusBadgeColors[incident.status]
            }`}
          >
            {incident.status.toUpperCase()}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4 mb-4">
        <div>
          <p className="text-sm text-gray-600">Duration</p>
          <p className="font-mono font-semibold">{incident.duration}</p>
        </div>
        <div>
          <p className="text-sm text-gray-600">Status</p>
          <p className="font-mono font-semibold capitalize">{incident.status}</p>
        </div>
        <div>
          <p className="text-sm text-gray-600">Impact</p>
          <p className="font-mono font-semibold">{incident.impact_description}</p>
        </div>
      </div>

      <div className="bg-white p-4 rounded border mb-4">
        <p className="text-sm">
          <strong>Root Cause:</strong> {incident.root_cause}
        </p>
        <p className="text-sm mt-2">
          <strong>Recommendation:</strong> {incident.recommended_fix}
        </p>
      </div>

      {incident.runbook_url && (
        <button className="w-full px-4 py-2 bg-blue-600 text-white rounded font-semibold hover:bg-blue-700">
          Open Runbook
        </button>
      )}
    </div>
  );
}

interface OnCallViewProps {
  incidents: Incident[];
  isLoading?: boolean;
}

export function OnCallView({ incidents, isLoading = false }: OnCallViewProps) {
  const sorted = [...incidents].sort((a, b) => {
    const severities = { critical: 3, warning: 2, info: 1 };
    return (
      (severities[b.severity as keyof typeof severities] ?? 0) -
      (severities[a.severity as keyof typeof severities] ?? 0)
    );
  });

  const criticalCount = sorted.filter((i) => i.severity === 'critical').length;
  const warningCount = sorted.filter((i) => i.severity === 'warning').length;

  return (
    <div className="bg-gray-50 p-8 min-h-screen">
      <div className="max-w-4xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold mb-2">On-Call Incident Dashboard</h1>
          <p className="text-gray-600 mb-4">Worst incidents first</p>

          <div className="flex gap-4 mb-6">
            <div className="bg-white p-4 rounded border border-red-200">
              <p className="text-sm text-gray-600">Critical Incidents</p>
              <p className="text-2xl font-bold text-red-600">{criticalCount}</p>
            </div>
            <div className="bg-white p-4 rounded border border-yellow-200">
              <p className="text-sm text-gray-600">Warnings</p>
              <p className="text-2xl font-bold text-yellow-600">{warningCount}</p>
            </div>
            <div className="bg-white p-4 rounded border border-gray-200">
              <p className="text-sm text-gray-600">Total Incidents</p>
              <p className="text-2xl font-bold text-gray-600">{sorted.length}</p>
            </div>
          </div>
        </div>

        {isLoading ? (
          <div className="bg-white p-8 rounded-lg border border-gray-200 text-center">
            <p className="text-gray-600">Loading incidents...</p>
          </div>
        ) : sorted.length === 0 ? (
          <div className="bg-green-50 p-8 rounded-lg border border-green-200 text-center">
            <p className="text-green-700 font-semibold">
              ✓ No active incidents
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {sorted.map((incident) => (
              <IncidentCard key={incident.id} incident={incident} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
