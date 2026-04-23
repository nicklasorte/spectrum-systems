'use client';

import React, { useState, useEffect } from 'react';
import { SystemCard, SystemMetrics } from './SystemCard';
import { SystemDetail } from './SystemDetail';

interface DashboardViewProps {
  systems: SystemMetrics[];
  isLoading?: boolean;
  lastRefresh?: string;
}

export function DashboardView({
  systems,
  isLoading = false,
  lastRefresh,
}: DashboardViewProps) {
  const [selectedSystemId, setSelectedSystemId] = useState<string | null>(null);
  const [filteredSystems, setFilteredSystems] = useState<SystemMetrics[]>(
    systems
  );
  const [filter, setFilter] = useState<string>('all');

  const selectedSystem = systems.find((s) => s.system_id === selectedSystemId);

  useEffect(() => {
    let filtered = systems;

    if (filter === 'critical') {
      filtered = systems.filter((s) => s.status === 'critical');
    } else if (filter === 'warning') {
      filtered = systems.filter((s) => s.status === 'warning' || s.status === 'critical');
    } else if (filter === 'violations') {
      filtered = systems.filter((s) => s.contract_violations.length > 0);
    }

    setFilteredSystems(filtered);
  }, [systems, filter]);

  const statusCounts = {
    healthy: systems.filter((s) => s.status === 'healthy').length,
    warning: systems.filter((s) => s.status === 'warning').length,
    critical: systems.filter((s) => s.status === 'critical').length,
  };

  const avgHealth =
    systems.reduce((sum, s) => sum + s.health_score, 0) / systems.length || 0;

  return (
    <div className="bg-gray-50 min-h-screen p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold mb-2">3-Letter Systems Dashboard</h1>
          <p className="text-gray-600">
            Real-time observability for spectrum-systems governance runtime
          </p>
          {lastRefresh && (
            <p className="text-sm text-gray-500 mt-2">
              Last updated: {new Date(lastRefresh).toLocaleString()}
            </p>
          )}
        </div>

        {/* Status Summary */}
        <div className="grid grid-cols-4 gap-4 mb-8">
          <div className="bg-white p-6 rounded-lg border border-gray-200">
            <p className="text-sm text-gray-600">Avg Health Score</p>
            <p className="text-3xl font-bold text-blue-600">{avgHealth.toFixed(0)}%</p>
          </div>
          <div className="bg-white p-6 rounded-lg border border-green-200">
            <p className="text-sm text-gray-600">Healthy Systems</p>
            <p className="text-3xl font-bold text-green-600">
              {statusCounts.healthy}
            </p>
          </div>
          <div className="bg-white p-6 rounded-lg border border-yellow-200">
            <p className="text-sm text-gray-600">Warning Status</p>
            <p className="text-3xl font-bold text-yellow-600">
              {statusCounts.warning}
            </p>
          </div>
          <div className="bg-white p-6 rounded-lg border border-red-200">
            <p className="text-sm text-gray-600">Critical Systems</p>
            <p className="text-3xl font-bold text-red-600">
              {statusCounts.critical}
            </p>
          </div>
        </div>

        {/* Filters */}
        <div className="mb-8 flex gap-4">
          <button
            onClick={() => setFilter('all')}
            className={`px-4 py-2 rounded ${
              filter === 'all'
                ? 'bg-blue-600 text-white'
                : 'bg-white text-gray-700 border border-gray-300'
            }`}
          >
            All ({systems.length})
          </button>
          <button
            onClick={() => setFilter('critical')}
            className={`px-4 py-2 rounded ${
              filter === 'critical'
                ? 'bg-red-600 text-white'
                : 'bg-white text-gray-700 border border-gray-300'
            }`}
          >
            Critical ({statusCounts.critical})
          </button>
          <button
            onClick={() => setFilter('warning')}
            className={`px-4 py-2 rounded ${
              filter === 'warning'
                ? 'bg-yellow-600 text-white'
                : 'bg-white text-gray-700 border border-gray-300'
            }`}
          >
            Warning+ ({statusCounts.warning + statusCounts.critical})
          </button>
          <button
            onClick={() => setFilter('violations')}
            className={`px-4 py-2 rounded ${
              filter === 'violations'
                ? 'bg-purple-600 text-white'
                : 'bg-white text-gray-700 border border-gray-300'
            }`}
          >
            Violations
          </button>
        </div>

        {/* Main Layout */}
        <div className="grid grid-cols-3 gap-8">
          {/* System Cards */}
          <div className="col-span-2">
            {isLoading ? (
              <div className="bg-white p-8 rounded-lg border border-gray-200 text-center">
                <p className="text-gray-600">Loading systems...</p>
              </div>
            ) : filteredSystems.length === 0 ? (
              <div className="bg-white p-8 rounded-lg border border-gray-200 text-center">
                <p className="text-gray-600">No systems found</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-4">
                {filteredSystems.map((system) => (
                  <SystemCard
                    key={system.system_id}
                    system={system}
                    onClick={() => setSelectedSystemId(system.system_id)}
                    isSelected={selectedSystemId === system.system_id}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Detail Panel */}
          <div className="col-span-1">
            {selectedSystem ? (
              <SystemDetail system={selectedSystem} />
            ) : (
              <div className="bg-white p-8 rounded-lg border border-gray-200 text-center">
                <p className="text-gray-600">Select a system to view details</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
