'use client';

import { useEffect, useState } from 'react';
import PipelineOverview from '@/components/dashboard/PipelineOverview';
import ExecutionTable from '@/components/dashboard/ExecutionTable';
import ExecutionTraceViewer from '@/components/dashboard/ExecutionTraceViewer';
import {
  Execution,
  PipelineMetrics,
  TraceDetail,
} from '@/components/dashboard/types';

export default function PipelinePage() {
  const [executions, setExecutions] = useState<Execution[]>([]);
  const [selectedTrace, setSelectedTrace] = useState<TraceDetail | null>(null);
  const [metrics, setMetrics] = useState<PipelineMetrics>({
    total_runs: 0,
    passed: 0,
    failed: 0,
    in_progress: 0,
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const response = await fetch('/api/executions?limit=20');
        const data = await response.json();
        setExecutions(data.executions);

        const computedMetrics: PipelineMetrics = {
          total_runs: data.executions.length,
          passed: data.executions.filter(
            (e: Execution) => e.status === 'PASS' || e.status === 'ALLOW'
          ).length,
          failed: data.executions.filter(
            (e: Execution) => e.status === 'FAIL' || e.status === 'BLOCK'
          ).length,
          in_progress: data.executions.filter(
            (e: Execution) => e.status === 'RUN' || e.status === 'PENDING'
          ).length,
        };
        setMetrics(computedMetrics);
      } catch (error) {
        console.error('Failed to fetch executions:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  const handleSelectTrace = async (trace_id: string) => {
    try {
      const response = await fetch(`/api/executions/${trace_id}`);
      const data = await response.json();
      setSelectedTrace(data);
    } catch (error) {
      console.error('Failed to fetch trace detail:', error);
    }
  };

  return (
    <main className="max-w-6xl mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-gray-100">
          Pipeline Status
        </h1>
        <p className="text-gray-600 dark:text-gray-400 mt-2">
          Monitor execution runs and control decisions
        </p>
      </div>

      {loading ? (
        <div className="text-center py-12">
          <p className="text-gray-600 dark:text-gray-400">Loading...</p>
        </div>
      ) : (
        <>
          <PipelineOverview metrics={metrics} />

          <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100 mb-4">
            Recent Runs
          </h2>
          <ExecutionTable
            executions={executions}
            onSelectTrace={handleSelectTrace}
          />

          {selectedTrace && (
            <div className="mt-8 pt-8 border-t border-gray-300 dark:border-gray-700">
              <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100 mb-4">
                Execution Trace
              </h2>
              <ExecutionTraceViewer trace={selectedTrace} />
            </div>
          )}
        </>
      )}
    </main>
  );
}
