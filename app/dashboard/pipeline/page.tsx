'use client';

import { useEffect, useState } from 'react';
import { fetchExecutions, fetchTraceDetail } from '@/lib/api';
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
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadExecutions = async () => {
      try {
        setLoading(true);
        const data = await fetchExecutions(20, 0);
        setExecutions(data.executions);
        setMetrics({
          total_runs: data.total,
          passed: data.metrics.passed,
          failed: data.metrics.failed,
          in_progress: data.metrics.in_progress,
        });
        setError(null);
      } catch (err) {
        console.error('Failed to load executions:', err);
        setError(
          err instanceof Error
            ? err.message
            : 'Failed to load execution data'
        );
      } finally {
        setLoading(false);
      }
    };

    loadExecutions();
  }, []);

  const handleSelectTrace = async (trace_id: string) => {
    try {
      const trace = await fetchTraceDetail(trace_id);
      setSelectedTrace(trace);
    } catch (err) {
      console.error('Failed to load trace:', err);
      setError(
        err instanceof Error
          ? err.message
          : 'Failed to load trace details'
      );
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

      {error && (
        <div className="mb-6 p-4 bg-red-50 dark:bg-red-900 border border-red-200 dark:border-red-700 rounded-lg">
          <p className="text-red-700 dark:text-red-100">{error}</p>
        </div>
      )}

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
          {executions.length === 0 ? (
            <div className="p-6 text-center text-gray-500 dark:text-gray-400 border rounded-lg">
              No executions yet. Start a pipeline run to see data here.
            </div>
          ) : (
            <ExecutionTable
              executions={executions}
              onSelectTrace={handleSelectTrace}
            />
          )}

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
