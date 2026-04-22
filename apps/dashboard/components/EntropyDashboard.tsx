'use client';

import { EntropySnapshot } from '@/lib/types';
import { MetricCard } from './MetricCard';
import { ControlDecisionBanner } from './ControlDecisionBanner';
import { TrendChart } from './TrendChart';
import { useState } from 'react';
import { QueryDrillDown } from './QueryDrillDown';

export function EntropyDashboard({ snapshot }: { snapshot: EntropySnapshot }) {
  const [selectedQuery, setSelectedQuery] = useState<string | null>(null);

  return (
    <div className="space-y-6">
      <ControlDecisionBanner decisions={snapshot.control_decisions} />

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <MetricCard
          title="Decision Divergence"
          value={`${(snapshot.metrics.decision_divergence.current * 100).toFixed(1)}%`}
          threshold={`${(snapshot.metrics.decision_divergence.threshold * 100).toFixed(1)}%`}
          trend={snapshot.metrics.decision_divergence.trend}
          status={
            snapshot.metrics.decision_divergence.current >
            snapshot.metrics.decision_divergence.threshold
              ? 'warning'
              : 'good'
          }
          onClick={() => setSelectedQuery('reason-codes')}
        />

        <MetricCard
          title="Exception Rate"
          value={`${(snapshot.metrics.exception_rate.current * 100).toFixed(2)}%`}
          threshold={`${(snapshot.metrics.exception_rate.threshold * 100).toFixed(2)}%`}
          trend={snapshot.metrics.exception_rate.trend}
          status={
            snapshot.metrics.exception_rate.current >
            snapshot.metrics.exception_rate.threshold
              ? 'warning'
              : 'good'
          }
          onClick={() => setSelectedQuery('rising-overrides')}
        />

        <MetricCard
          title="Trace Coverage"
          value={`${snapshot.metrics.trace_coverage.current.toFixed(2)}%`}
          threshold={`${(snapshot.metrics.trace_coverage.slo * 100).toFixed(2)}%`}
          status={snapshot.metrics.trace_coverage.met ? 'good' : 'critical'}
          onClick={() => setSelectedQuery('coverage')}
        />

        <MetricCard
          title="Calibration Drift"
          value={`${(snapshot.metrics.calibration_drift.current * 100).toFixed(2)}%`}
          threshold={`${(snapshot.metrics.calibration_drift.threshold * 100).toFixed(2)}%`}
          status={
            snapshot.metrics.calibration_drift.current >
            snapshot.metrics.calibration_drift.threshold
              ? 'warning'
              : 'good'
          }
          onClick={() => setSelectedQuery('judge-disagreement')}
        />

        <MetricCard
          title="Override Hotspots"
          value={`${snapshot.metrics.override_hotspots.count}`}
          threshold="0"
          status={snapshot.metrics.override_hotspots.count > 0 ? 'warning' : 'good'}
          onClick={() => setSelectedQuery('rising-overrides')}
        />

        <MetricCard
          title="Failure-to-Eval"
          value={`${(snapshot.metrics.failure_to_eval_rate.current * 100).toFixed(2)}%`}
          threshold={`${(snapshot.metrics.failure_to_eval_rate.threshold * 100).toFixed(2)}%`}
          status={
            snapshot.metrics.failure_to_eval_rate.current >
            snapshot.metrics.failure_to_eval_rate.threshold
              ? 'critical'
              : 'good'
          }
          onClick={() => setSelectedQuery('failure-patterns')}
        />
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <h2 className="text-lg font-semibold mb-4">7-Day Trend</h2>
        <TrendChart
          data={[
            { date: 'Day 1', divergence: 0.045, exceptions: 0.007 },
            { date: 'Day 2', divergence: 0.048, exceptions: 0.008 },
            { date: 'Day 3', divergence: 0.052, exceptions: 0.009 },
            { date: 'Day 4', divergence: 0.051, exceptions: 0.008 },
            { date: 'Day 5', divergence: 0.050, exceptions: 0.007 },
            { date: 'Day 6', divergence: 0.049, exceptions: 0.006 },
            { date: 'Day 7', divergence: 0.052, exceptions: 0.008 },
          ]}
        />
      </div>

      <div className="text-xs text-gray-500 pt-4">
        <p>Snapshot ID: {snapshot.snapshot_id}</p>
        <p>Generated: {new Date(snapshot.timestamp).toLocaleString()}</p>
      </div>

      {selectedQuery && (
        <QueryDrillDown
          queryId={selectedQuery}
          onClose={() => setSelectedQuery(null)}
        />
      )}
    </div>
  );
}
