'use client';

import React, { useEffect, useState } from 'react';
import { ComplianceView } from '@/components/ComplianceView';

interface SystemCompliance {
  system_id: string;
  compliant: boolean;
  violations: Array<{ rule: string; detail: string }>;
}

interface ComplianceResponse {
  status: string;
  total_systems: number;
  compliant: number;
  violations: number;
  by_system: SystemCompliance[];
  refreshed_at: string;
}

export default function CompliancePage() {
  const [systems, setSystems] = useState<SystemCompliance[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshedAt, setRefreshedAt] = useState<string>('');

  useEffect(() => {
    fetchCompliance();
  }, []);

  const fetchCompliance = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/compliance');
      if (!response.ok) throw new Error('Failed to fetch compliance data');
      const data: ComplianceResponse = await response.json();
      setSystems(data.by_system || []);
      setRefreshedAt(data.refreshed_at);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-8 bg-gray-50 min-h-screen">
      <div className="flex justify-between items-start mb-8">
        <div>
          <h1 className="text-4xl font-bold mb-2">Contract Compliance</h1>
          <p className="text-gray-600">System contract adherence and compliance status</p>
        </div>
        <div className="text-right">
          <button
            onClick={fetchCompliance}
            className="px-4 py-2 bg-blue-600 text-white rounded font-semibold hover:bg-blue-700"
          >
            Refresh
          </button>
          {refreshedAt && (
            <p className="text-sm text-gray-500 mt-2">
              Updated: {new Date(refreshedAt).toLocaleTimeString()}
            </p>
          )}
        </div>
      </div>

      {error && (
        <div className="bg-yellow-50 border border-yellow-300 p-4 rounded mb-8">
          <p className="text-sm text-yellow-800">{error}</p>
        </div>
      )}

      {loading ? (
        <div className="text-center py-12">
          <p className="text-gray-600">Loading compliance data...</p>
        </div>
      ) : (
        <ComplianceView systems={systems} />
      )}
    </div>
  );
}
