import React, { useState, useEffect } from 'react';

export default function EntropyDashboard() {
  const [snapshot, setSnapshot] = useState(null);
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(30);

  useEffect(() => {
    const fetchSnapshot = async () => {
      try {
        const response = await fetch('/api/entropy/latest-snapshot');
        const data = await response.json();
        setSnapshot(data);
        setLoading(false);
      } catch (error) {
        console.error('Failed to fetch entropy snapshot:', error);
        setLoading(false);
      }
    };

    fetchSnapshot();
    const interval = setInterval(fetchSnapshot, autoRefresh * 1000);
    return () => clearInterval(interval);
  }, [autoRefresh]);

  if (loading) return <div className="p-4">Loading entropy posture...</div>;
  if (!snapshot) return <div className="p-4">No data available</div>;

  const getHealthColor = (decision) => {
    if (decision.includes('block')) return 'bg-red-100 border-red-500';
    if (decision.includes('escalate')) return 'bg-yellow-100 border-yellow-500';
    return 'bg-green-100 border-green-500';
  };

  return (
    <div className="p-6 bg-gray-50 min-h-screen">
      <div className="max-w-6xl mx-auto">
        <h1 className="text-3xl font-bold mb-6">System Entropy Posture</h1>

        {/* Control Decisions */}
        <div className={`p-4 rounded-lg border-2 mb-6 ${getHealthColor(snapshot.control_decisions)}`}>
          <h2 className="text-xl font-semibold mb-2">Control Decisions</h2>
          <div className="flex gap-2 flex-wrap">
            {snapshot.control_decisions.map((decision) => (
              <span key={decision} className="px-3 py-1 bg-white rounded-full font-mono text-sm">
                {decision.toUpperCase()}
              </span>
            ))}
          </div>
          <p className="mt-3 text-sm">{snapshot.recommendation}</p>
        </div>

        {/* Key Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
          {/* Decision Divergence */}
          <div className="bg-white p-4 rounded-lg border border-gray-200">
            <h3 className="font-semibold mb-2">Decision Divergence</h3>
            <div className="text-3xl font-bold mb-1">{(snapshot.metrics.decision_divergence.current * 100).toFixed(1)}%</div>
            <div className="text-xs text-gray-600">Threshold: {(snapshot.metrics.decision_divergence.threshold * 100).toFixed(1)}%</div>
            <div className="text-xs mt-1 font-mono">{snapshot.metrics.decision_divergence.trend}</div>
          </div>

          {/* Exception Rate */}
          <div className="bg-white p-4 rounded-lg border border-gray-200">
            <h3 className="font-semibold mb-2">Exception Rate</h3>
            <div className="text-3xl font-bold mb-1">{(snapshot.metrics.exception_rate.current * 100).toFixed(2)}%</div>
            <div className="text-xs text-gray-600">Threshold: {(snapshot.metrics.exception_rate.threshold * 100).toFixed(2)}%</div>
          </div>

          {/* Trace Coverage */}
          <div className="bg-white p-4 rounded-lg border border-gray-200">
            <h3 className="font-semibold mb-2">Trace Coverage</h3>
            <div className="text-3xl font-bold mb-1">{snapshot.metrics.trace_coverage.current.toFixed(2)}%</div>
            <div className="text-xs text-gray-600">SLO: {(snapshot.metrics.trace_coverage.slo * 100).toFixed(2)}%</div>
            <div className={`text-xs mt-1 font-mono ${snapshot.metrics.trace_coverage.met ? 'text-green-600' : 'text-red-600'}`}>
              {snapshot.metrics.trace_coverage.met ? '✓ MET' : '✗ MISS'}
            </div>
          </div>

          {/* Calibration Drift */}
          <div className="bg-white p-4 rounded-lg border border-gray-200">
            <h3 className="font-semibold mb-2">Calibration Drift</h3>
            <div className="text-3xl font-bold mb-1">{(snapshot.metrics.calibration_drift.current * 100).toFixed(2)}%</div>
            <div className="text-xs text-gray-600">Threshold: {(snapshot.metrics.calibration_drift.threshold * 100).toFixed(2)}%</div>
          </div>

          {/* Override Hotspots */}
          <div className="bg-white p-4 rounded-lg border border-gray-200">
            <h3 className="font-semibold mb-2">Override Hotspots</h3>
            <div className="text-3xl font-bold mb-1">{snapshot.metrics.override_hotspots.count}</div>
            <div className="text-xs text-gray-600">High-risk gates</div>
            <div className="text-xs mt-1 font-mono">{snapshot.metrics.override_hotspots.action}</div>
          </div>

          {/* Failure-to-Eval Rate */}
          <div className="bg-white p-4 rounded-lg border border-gray-200">
            <h3 className="font-semibold mb-2">Failure-to-Eval Rate</h3>
            <div className="text-3xl font-bold mb-1">{(snapshot.metrics.failure_to_eval_rate.current * 100).toFixed(2)}%</div>
            <div className="text-xs text-gray-600">Threshold: {(snapshot.metrics.failure_to_eval_rate.threshold * 100).toFixed(2)}%</div>
          </div>
        </div>

        {/* Auto-Refresh Control */}
        <div className="bg-white p-4 rounded-lg border border-gray-200">
          <label className="flex items-center gap-2">
            <span className="text-sm font-medium">Auto-refresh every</span>
            <input
              type="number"
              min="10"
              max="300"
              value={autoRefresh}
              onChange={(e) => setAutoRefresh(parseInt(e.target.value))}
              className="w-16 px-2 py-1 border border-gray-300 rounded text-sm"
            />
            <span className="text-sm text-gray-600">seconds</span>
          </label>
        </div>

        {/* Metadata */}
        <div className="mt-6 text-xs text-gray-500">
          <p>Snapshot ID: {snapshot.snapshot_id}</p>
          <p>Generated: {new Date(snapshot.timestamp).toLocaleString()}</p>
          <p>Week ending: {snapshot.week_ending}</p>
        </div>
      </div>
    </div>
  );
}
