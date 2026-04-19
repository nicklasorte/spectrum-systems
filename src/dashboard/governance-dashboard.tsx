"use client";

import React, { useEffect, useState } from "react";
import {
  AlertCircle,
  TrendingDown,
  TrendingUp,
  CheckCircle,
  AlertTriangle,
  RefreshCw,
} from "lucide-react";

/**
 * Governance Dashboard
 * Read-only view of SLI status, drift signals, exception backlog, policy health
 */

interface SLIStatus {
  sli_name: string;
  current_value: number;
  target_value: number;
  unit: string;
  status: "healthy" | "warning" | "critical";
  trend: "up" | "down" | "stable";
}

interface DriftSignal {
  artifact_id: string;
  drift_type: string;
  current_value: number;
  baseline_value: number;
  recommendations: string[];
}

interface ExceptionBacklog {
  total_active: number;
  overdue: number;
  unconverted: number;
  status: "healthy" | "warning" | "critical";
}

interface PolicyStatus {
  policy_name: string;
  status: string;
  rollout_percentage: number;
  incidents_since_deployment: number;
}

export default function GovernanceDashboard() {
  const [sliStatus, setSliStatus] = useState<SLIStatus[]>([]);
  const [driftSignals, setDriftSignals] = useState<DriftSignal[]>([]);
  const [exceptionBacklog, setExceptionBacklog] = useState<ExceptionBacklog | null>(
    null
  );
  const [policies, setPolicies] = useState<PolicyStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());

  useEffect(() => {
    fetchDashboardData();
    const interval = setInterval(fetchDashboardData, 30000);
    return () => clearInterval(interval);
  }, []);

  async function fetchDashboardData() {
    try {
      const [sliRes, driftRes, excRes, polRes] = await Promise.all([
        fetch("/api/governance/sli-status"),
        fetch("/api/governance/drift-signals"),
        fetch("/api/governance/exceptions/backlog"),
        fetch("/api/governance/policies"),
      ]);

      if (sliRes.ok) setSliStatus(await sliRes.json());
      if (driftRes.ok) setDriftSignals(await driftRes.json());
      if (excRes.ok) setExceptionBacklog(await excRes.json());
      if (polRes.ok) setPolicies(await polRes.json());

      setLastUpdated(new Date());
      setLoading(false);
    } catch (error) {
      console.error("Failed to fetch dashboard data:", error);
      setLoading(false);
    }
  }

  const getSLIStatusColor = (status: string) => {
    switch (status) {
      case "healthy":
        return "bg-green-50 border-green-300";
      case "warning":
        return "bg-yellow-50 border-yellow-300";
      case "critical":
        return "bg-red-50 border-red-300";
      default:
        return "bg-gray-50 border-gray-300";
    }
  };

  const getStatusBadge = (status: string) => {
    const colors: Record<string, string> = {
      healthy: "bg-green-100 text-green-800",
      warning: "bg-yellow-100 text-yellow-800",
      critical: "bg-red-100 text-red-800",
      active: "bg-blue-100 text-blue-800",
    };
    return colors[status] || "bg-gray-100 text-gray-800";
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <RefreshCw className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Governance Dashboard</h1>
          <div className="text-sm text-gray-600">
            Last updated: {lastUpdated.toLocaleTimeString()}
          </div>
        </div>

        {/* SLI Status Grid */}
        <section className="mb-8">
          <h2 className="text-2xl font-semibold text-gray-900 mb-4">SLI Status</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
            {sliStatus.map((sli) => (
              <div
                key={sli.sli_name}
                className={`border rounded-lg p-4 ${getSLIStatusColor(sli.status)}`}
              >
                <div className="flex justify-between items-start">
                  <div>
                    <h3 className="font-semibold text-gray-900">{sli.sli_name}</h3>
                    <p className="text-sm text-gray-600 mt-1">
                      {sli.current_value.toFixed(1)} / {sli.target_value} {sli.unit}
                    </p>
                  </div>
                  <div>
                    {sli.trend === "up" && <TrendingUp className="w-4 h-4 text-red-500" />}
                    {sli.trend === "down" && (
                      <TrendingDown className="w-4 h-4 text-green-500" />
                    )}
                    {sli.trend === "stable" && (
                      <CheckCircle className="w-4 h-4 text-blue-500" />
                    )}
                  </div>
                </div>
                <div className="mt-2">
                  <span
                    className={`text-xs font-semibold px-2 py-1 rounded ${getStatusBadge(
                      sli.status
                    )}`}
                  >
                    {sli.status.toUpperCase()}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Drift Signals */}
        <section className="mb-8">
          <h2 className="text-2xl font-semibold text-gray-900 mb-4">Active Drift Signals</h2>
          {driftSignals.length === 0 ? (
            <div className="bg-white rounded-lg border border-gray-200 p-6 text-center text-gray-600">
              No active drift signals
            </div>
          ) : (
            <div className="space-y-3">
              {driftSignals.map((signal) => (
                <div
                  key={signal.artifact_id}
                  className="bg-yellow-50 border border-yellow-300 rounded-lg p-4"
                >
                  <div className="flex items-start">
                    <AlertTriangle className="w-5 h-5 text-yellow-600 mt-1 mr-3 flex-shrink-0" />
                    <div className="flex-1">
                      <h3 className="font-semibold text-gray-900">{signal.drift_type}</h3>
                      <p className="text-sm text-gray-700 mt-1">
                        Value: {signal.current_value.toFixed(2)} (baseline:{" "}
                        {signal.baseline_value.toFixed(2)})
                      </p>
                      <div className="mt-2">
                        <p className="text-xs text-gray-600 font-semibold mb-1">
                          Recommendations:
                        </p>
                        <ul className="text-xs text-gray-600 list-disc list-inside">
                          {signal.recommendations.slice(0, 2).map((rec, i) => (
                            <li key={i}>{rec}</li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Exception Backlog */}
        {exceptionBacklog && (
          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 mb-4">Exception Backlog</h2>
            <div className={`rounded-lg border p-6 ${getStatusBadge(exceptionBacklog.status)}`}>
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <p className="text-sm font-semibold">Total Active</p>
                  <p className="text-2xl font-bold mt-1">{exceptionBacklog.total_active}</p>
                </div>
                <div>
                  <p className="text-sm font-semibold">Overdue</p>
                  <p className="text-2xl font-bold mt-1">{exceptionBacklog.overdue}</p>
                </div>
                <div>
                  <p className="text-sm font-semibold">Unconverted</p>
                  <p className="text-2xl font-bold mt-1">{exceptionBacklog.unconverted}</p>
                </div>
              </div>
              <div className="mt-4">
                <span
                  className={`text-sm font-semibold px-3 py-1 rounded ${getStatusBadge(
                    exceptionBacklog.status
                  )}`}
                >
                  Status: {exceptionBacklog.status.toUpperCase()}
                </span>
              </div>
            </div>
          </section>
        )}

        {/* Policy Rollout */}
        <section>
          <h2 className="text-2xl font-semibold text-gray-900 mb-4">Policy Rollout Status</h2>
          <div className="space-y-3">
            {policies.map((policy) => (
              <div key={policy.policy_name} className="bg-white border border-gray-200 rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="font-semibold text-gray-900">{policy.policy_name}</h3>
                  <span
                    className={`text-xs font-semibold px-2 py-1 rounded ${getStatusBadge(
                      policy.status
                    )}`}
                  >
                    {policy.status.toUpperCase()}
                  </span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2 mb-2">
                  <div
                    className="bg-blue-600 h-2 rounded-full"
                    style={{ width: `${policy.rollout_percentage}%` }}
                  ></div>
                </div>
                <div className="flex justify-between text-xs text-gray-600">
                  <span>Rollout: {policy.rollout_percentage}%</span>
                  <span>Incidents: {policy.incidents_since_deployment}</span>
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
