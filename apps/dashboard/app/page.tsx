'use client';

import { useState, useEffect } from 'react';
import { EntropyDashboard } from '@/components/EntropyDashboard';
import { Header } from '@/components/Header';
import type { EntropySnapshot } from '@/lib/types';

export default function DashboardPage() {
  const [snapshot, setSnapshot] = useState<EntropySnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(30);

  useEffect(() => {
    const fetchSnapshot = async () => {
      try {
        const response = await fetch('/api/entropy/latest');
        if (!response.ok) throw new Error('Failed to fetch entropy snapshot');
        const data = await response.json();
        setSnapshot(data);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    };

    fetchSnapshot();

    const interval = setInterval(fetchSnapshot, autoRefresh * 1000);
    return () => clearInterval(interval);
  }, [autoRefresh]);

  return (
    <div className="min-h-screen bg-gray-50">
      <Header autoRefresh={autoRefresh} onRefreshChange={setAutoRefresh} />

      <main className="max-w-7xl mx-auto px-4 py-8">
        {loading && (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            <p className="mt-2 text-gray-600">Loading entropy posture...</p>
          </div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
            <p className="text-red-800 font-semibold">Error</p>
            <p className="text-red-700">{error}</p>
          </div>
        )}

        {snapshot && (
          <EntropyDashboard snapshot={snapshot} />
        )}
      </main>
    </div>
  );
}
