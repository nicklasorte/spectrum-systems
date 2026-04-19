"use client";

import React, { useEffect, useState } from "react";
import { BarChart, LineChart, AlertTriangle, TrendingUp } from "lucide-react";

/**
 * Pipeline Observability Dashboard
 * Shows: bottlenecks, costs, failure rates, trace completeness
 */

interface BottleneckMetric {
  mvp_name: string;
  avg_latency: number;
  stddev_latency: number;
  run_count: number;
}

interface CostTrend {
  date: string;
  avg_cost: number;
  max_cost: number;
}

export default function ObservabilityDashboard() {
  const [bottlenecks, setBottlenecks] = useState<BottleneckMetric[]>([]);
  const [costTrend, setCostTrend] = useState<CostTrend[]>([]);
  const [failureRate, setFailureRate] = useState<number>(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchMetrics();
    const interval = setInterval(fetchMetrics, 60000);
    return () => clearInterval(interval);
  }, []);

  async function fetchMetrics() {
    try {
      const [bottlenecksRes, costRes, failureRes] = await Promise.all([
        fetch("/api/observability/bottlenecks"),
        fetch("/api/observability/cost-trend"),
        fetch("/api/observability/failure-rate"),
      ]);

      if (bottlenecksRes.ok) setBottlenecks(await bottlenecksRes.json());
      if (costRes.ok) setCostTrend(await costRes.json());
      if (failureRes.ok) setFailureRate(await failureRes.json());

      setLoading(false);
    } catch (error) {
      console.error("Failed to fetch metrics:", error);
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-7xl mx-auto">
        <h1 className="text-3xl font-bold text-gray-900 mb-8">Pipeline Observability</h1>

        {failureRate > 0.1 && (
          <div className="bg-red-50 border border-red-300 rounded-lg p-4 mb-8">
            <div className="flex items-center">
              <AlertTriangle className="w-5 h-5 text-red-600 mr-3" />
              <div>
                <h3 className="font-semibold text-red-900">
                  High Failure Rate: {(failureRate * 100).toFixed(1)}%
                </h3>
                <p className="text-sm text-red-700 mt-1">
                  More than 10% of pipeline runs are failing. Investigate bottlenecks below.
                </p>
              </div>
            </div>
          </div>
        )}

        <section className="mb-8">
          <h2 className="text-2xl font-semibold text-gray-900 mb-4">Slowest MVPs (Bottlenecks)</h2>
          <div className="grid gap-4">
            {bottlenecks.map((b) => (
              <div key={b.mvp_name} className="bg-white border border-gray-200 rounded-lg p-4">
                <div className="flex justify-between items-start">
                  <div>
                    <h3 className="font-semibold text-gray-900">{b.mvp_name}</h3>
                    <p className="text-sm text-gray-600 mt-1">
                      Avg: {b.avg_latency.toFixed(0)}ms (σ {b.stddev_latency.toFixed(0)}ms)
                    </p>
                  </div>
                  <span className="text-xs bg-yellow-100 text-yellow-800 px-2 py-1 rounded">
                    {b.run_count} runs
                  </span>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="mb-8">
          <h2 className="text-2xl font-semibold text-gray-900 mb-4">Cost Trend (30 days)</h2>
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <div className="space-y-2">
              {costTrend.map((c) => (
                <div key={c.date} className="flex justify-between items-center">
                  <span className="text-sm text-gray-600">{c.date}</span>
                  <div className="flex items-center gap-4">
                    <div className="w-32 h-6 bg-blue-50 border border-blue-200 rounded">
                      <div
                        className="h-full bg-blue-500 rounded"
                        style={{ width: `${(c.avg_cost / 500) * 100}%` }}
                      ></div>
                    </div>
                    <span className="text-sm text-gray-900">
                      Avg: {c.avg_cost.toFixed(0)}¢ / Max: {c.max_cost.toFixed(0)}¢
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
