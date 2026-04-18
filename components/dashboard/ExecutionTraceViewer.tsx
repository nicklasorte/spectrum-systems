'use client';

import { useState } from 'react';
import { TraceDetail } from './types';

interface ExecutionTraceViewerProps {
  trace: TraceDetail;
}

export default function ExecutionTraceViewer({
  trace,
}: ExecutionTraceViewerProps) {
  const [showJson, setShowJson] = useState(false);

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
        Trace: {trace.trace_id}
      </h3>

      <div className="space-y-2">
        {trace.steps.map((step, index) => (
          <div
            key={index}
            className="flex items-start gap-3 p-3 bg-gray-50 dark:bg-gray-900 rounded border-l-4 border-l-gray-300 dark:border-l-gray-700"
          >
            <span className="text-lg font-semibold mt-0.5">
              {step.status === 'PASS' || step.status === 'ALLOW' ? '✓' : '✗'}
            </span>
            <div className="flex-1 min-w-0">
              <p className="font-mono text-sm text-gray-900 dark:text-gray-100 break-all">
                {step.artifact_id}
              </p>
              {step.error && (
                <p className="text-sm text-red-600 dark:text-red-400 mt-1">
                  Error: {step.error}
                </p>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="border-t border-gray-300 dark:border-gray-700 pt-4 mt-4">
        <h4 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-2">
          Control Decision
        </h4>
        <div className="bg-gray-50 dark:bg-gray-900 p-3 rounded border border-gray-200 dark:border-gray-800">
          <p className="font-mono text-sm text-gray-900 dark:text-gray-100">
            {trace.control_decision.decision}
          </p>
          <p className="text-sm text-gray-700 dark:text-gray-300 mt-1">
            {trace.control_decision.reason}
          </p>
        </div>
      </div>

      <div className="flex gap-2 pt-2">
        <button
          onClick={() => setShowJson(!showJson)}
          className="px-4 py-2 bg-gray-200 dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded hover:bg-gray-300 dark:hover:bg-gray-700 font-medium text-sm"
        >
          {showJson ? 'Hide' : 'View'} JSON
        </button>
        <button
          onClick={() => {}}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 font-medium text-sm disabled:opacity-50"
          disabled
          title="Replay functionality coming soon"
        >
          Replay
        </button>
      </div>

      {showJson && (
        <div className="bg-gray-900 text-gray-100 p-4 rounded font-mono text-xs overflow-auto max-h-96 border border-gray-800">
          <pre>{JSON.stringify(trace, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}
