'use client';

import React, { useEffect, useState } from 'react';
import { OnCallView } from '@/components/OnCallView';

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

export default function OnCallPage() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchIncidents();
    const interval = setInterval(fetchIncidents, 30000);
    return () => clearInterval(interval);
  }, []);

  const fetchIncidents = async () => {
    try {
      const response = await fetch('/api/incidents');
      if (!response.ok) throw new Error('Failed to fetch incidents');
      const data = await response.json();
      setIncidents(data.incidents || []);
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
          <h1 className="text-4xl font-bold mb-2">On-Call Dashboard</h1>
          <p className="text-gray-600">Active incidents and system alerts sorted by severity</p>
        </div>
        <button
          onClick={fetchIncidents}
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
          <p className="text-gray-600">Loading incidents...</p>
        </div>
      ) : (
        <OnCallView incidents={incidents} />
      )}
    </div>
  );
}
