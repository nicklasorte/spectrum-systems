'use client';

import React, { useEffect, useState } from 'react';
import { HealthChart } from '@/components/HealthChart';

interface SystemMetrics {
  system_id: string;
  system_name: string;
  system_type: string;
  health_score: number;
  status: 'healthy' | 'warning' | 'critical';
  incidents_week: number;
  contract_violations: Array<{ rule: string; detail: string }>;
}

interface TrendData {
  date: string;
  health_score: number;
}

export default function DetailPage() {
  const [systemId, setSystemId] = useState<string>('PQX');
  const [system, setSystem] = useState<SystemMetrics | null>(null);
  const [trends, setTrends] = useState<TrendData[]>([]);
  const [allSystems, setAllSystems] = useState<SystemMetrics[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchSystems();
  }, []);

  useEffect(() => {
    if (allSystems.length > 0) {
      fetchSystemDetail(systemId);
    }
  }, [systemId]);

  const fetchSystems = async () => {
    try {
      const response = await fetch('/api/health');
      const data = await response.json();
      setAllSystems(data.systems || []);
      if (data.systems && data.systems.length > 0) {
        setSystemId(data.systems[0].system_id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    }
  };

  const fetchSystemDetail = async (id: string) => {
    try {
      setLoading(true);
      const [healthRes, trendsRes] = await Promise.all([
        fetch('/api/health'),
        fetch(`/api/trends?system_id=${id}`),
      ]);

      if (healthRes.ok && trendsRes.ok) {
        const healthData = await healthRes.json();
        const trendData = await trendsRes.json();

        const systemData = healthData.systems.find((s: SystemMetrics) => s.system_id === id);
        setSystem(systemData);
        setTrends(trendData.data || []);
        setError(null);
      } else {
        throw new Error('Failed to fetch data');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const statusColors = {
    healthy: 'bg-green-100 text-green-800',
    warning: 'bg-yellow-100 text-yellow-800',
    critical: 'bg-red-100 text-red-800',
  };

  return (
    <div className="p-8 bg-gray-50 min-h-screen">
      <h1 className="text-4xl font-bold mb-8">System Detail</h1>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 mb-8">
        <div className="lg:col-span-1 bg-white rounded-lg p-4 border border-gray-200">
          <h3 className="font-semibold mb-3 text-gray-700">Select System</h3>
          <select
            value={systemId}
            onChange={(e) => setSystemId(e.target.value)}
            className="w-full p-2 border rounded text-sm"
          >
            {allSystems.map((sys) => (
              <option key={sys.system_id} value={sys.system_id}>
                {sys.system_id} - {sys.system_name}
              </option>
            ))}
          </select>
        </div>

        {system && (
          <>
            <div className="bg-white rounded-lg p-6 border border-gray-200">
              <p className="text-sm text-gray-600 mb-1">Health Score</p>
              <p className="text-3xl font-bold">{system.health_score}%</p>
            </div>
            <div className="bg-white rounded-lg p-6 border border-gray-200">
              <p className="text-sm text-gray-600 mb-1">Status</p>
              <span className={`inline-block px-3 py-1 rounded font-semibold text-sm ${
                statusColors[system.status]
              }`}>
                {system.status.toUpperCase()}
              </span>
            </div>
            <div className="bg-white rounded-lg p-6 border border-gray-200">
              <p className="text-sm text-gray-600 mb-1">Incidents (Week)</p>
              <p className="text-3xl font-bold">{system.incidents_week}</p>
            </div>
          </>
        )}
      </div>

      {error && (
        <div className="bg-yellow-50 border border-yellow-300 p-4 rounded mb-8">
          <p className="text-sm text-yellow-800">{error}</p>
        </div>
      )}

      {loading ? (
        <div className="text-center py-12">
          <p className="text-gray-600">Loading details...</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <HealthChart data={trends} title="7-Day Health Trend" />
          {system && system.contract_violations.length > 0 && (
            <div className="bg-red-50 rounded-lg p-6 border border-red-300">
              <h3 className="font-semibold text-red-800 mb-4">Contract Violations</h3>
              <ul className="space-y-3">
                {system.contract_violations.map((v) => (
                  <li key={v.rule} className="text-red-700">
                    <p className="font-semibold">{v.rule}</p>
                    <p className="text-sm">{v.detail}</p>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
