'use client';

import React from 'react';

interface Incident {
  id: string;
  system_id: string;
  title: string;
  severity: 'critical' | 'warning' | 'info';
  duration: string;
  status: 'open' | 'investigating' | 'resolved';
  root_cause: string;
  recommended_fix: string;
  runbook_url: string;
}

const severityColors = {
  critical: 'bg-red-50 border-red-300',
  warning: 'bg-yellow-50 border-yellow-300',
  info: 'bg-blue-50 border-blue-300',
};

const severityBadgeColors = {
  critical: 'bg-red-100 text-red-800',
  warning: 'bg-yellow-100 text-yellow-800',
  info: 'bg-blue-100 text-blue-800',
};

const statusColors = {
  open: 'text-red-600',
  investigating: 'text-yellow-600',
  resolved: 'text-green-600',
};

export function OnCallView({ incidents }: { incidents: Incident[] }) {
  if (!incidents || incidents.length === 0) {
    return (
      <div className="bg-green-50 border border-green-300 p-6 rounded-lg text-center">
        <p className="text-green-800 font-semibold">✓ All systems operational</p>
        <p className="text-sm text-green-600 mt-1">No active incidents</p>
      </div>
    );
  }

  const sorted = [...incidents].sort((a, b) => {
    const severityOrder = { critical: 0, warning: 1, info: 2 };
    return severityOrder[a.severity] - severityOrder[b.severity];
  });

  return (
    <div className="space-y-4">
      {sorted.map((incident) => (
        <div
          key={incident.id}
          className={`p-6 rounded-lg border-2 ${severityColors[incident.severity]}`}
        >
          <div className="flex justify-between items-start mb-4">
            <div>
              <h3 className="font-semibold text-lg">{incident.title}</h3>
              <p className="text-sm text-gray-600">{incident.system_id}</p>
            </div>
            <div className="space-y-1 text-right">
              <span className={`inline-block px-3 py-1 rounded text-xs font-semibold ${
                severityBadgeColors[incident.severity]
              }`}>
                {incident.severity.toUpperCase()}
              </span>
              <p className={`text-sm font-semibold ${statusColors[incident.status]}`}>
                {incident.status.toUpperCase()}
              </p>
            </div>
          </div>

          <div className="bg-white bg-opacity-50 p-3 rounded mb-4 text-sm space-y-2">
            <div>
              <span className="font-semibold text-gray-700">Duration: </span>
              <span className="text-gray-600">{incident.duration}</span>
            </div>
            <div>
              <span className="font-semibold text-gray-700">Root Cause: </span>
              <span className="text-gray-600">{incident.root_cause}</span>
            </div>
            <div>
              <span className="font-semibold text-gray-700">Recommendation: </span>
              <span className="text-gray-600">{incident.recommended_fix}</span>
            </div>
          </div>

          <a
            href={incident.runbook_url}
            className="inline-block px-3 py-1 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 font-semibold"
          >
            Open Runbook
          </a>
        </div>
      ))}
    </div>
  );
}
