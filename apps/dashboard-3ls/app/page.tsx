'use client';

import React, { useEffect, useState } from 'react';
import { SystemCard } from '@/components/SystemCard';
import { SystemDetail } from '@/components/SystemDetail';

interface SystemMetrics {
  system_id: string;
  system_name: string;
  system_type: string;
  health_score: number;
  status: 'healthy' | 'warning' | 'critical';
  incidents_week: number;
  contract_violations: Array<{rule: string, detail: string}>;
}

export default function Dashboard() {
  const [systems, setSystems] = useState<SystemMetrics[]>([]);
  const [selectedSystem, setSelectedSystem] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchSystems();
  }, []);

  const fetchSystems = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/health');
      if (!response.ok) throw new Error('Failed to fetch health data');
      const data = await response.json();
      setSystems(data.systems || []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const selectedSystemData = systems.find(s => s.system_id === selectedSystem);

  return (
    <div className="p-8 bg-gray-50 min-h-screen">
      <div className="flex justify-between items-start mb-8">
        <div>
          <h1 className="text-4xl font-bold mb-2">3-Letter Systems Dashboard</h1>
          <p className="text-gray-600">Real-time health monitoring of 28+ governance systems</p>
        </div>
        <button
          onClick={fetchSystems}
          className="px-4 py-2 bg-blue-600 text-white rounded font-semibold hover:bg-blue-700"
        >
          Refresh
        </button>
      </div>

      {error && (
        <div className="bg-yellow-50 border border-yellow-300 p-4 rounded mb-8">
          <p className="text-sm text-yellow-800">{error}</p>
        </div>
      )}

      {loading ? (
        <div className="text-center py-12">
          <p className="text-gray-600">Loading systems...</p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
            {systems.map((system) => (
              <SystemCard
                key={system.system_id}
                system={system}
                onClick={() => setSelectedSystem(system.system_id)}
                isSelected={selectedSystem === system.system_id}
              />
            ))}
          </div>

          {selectedSystemData && (
            <SystemDetail system={selectedSystemData} />
          )}
        </>
      )}
    </div>
  );
}
