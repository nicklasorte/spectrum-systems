'use client';

import React, { useEffect, useState } from 'react';

interface RoadmapRecord {
  record_id?: string;
  admitted_count: number;
  blocked_count: number;
  active_drift_legs: string[];
  step_count?: number;
  top_risks?: string[];
  data_source?: string;
  warnings?: string[];
}

interface AnalysisRecord {
  context_maturity_level: number | 'unknown';
  wave_status?: number | 'unknown';
  entropy_vectors: Record<string, string>;
  rge_can_operate?: boolean;
  rge_max_autonomy?: string;
  mg_kernel_status?: string;
  mg_kernel_run_id?: string;
  manual_residue_steps?: number | 'unknown';
  dashboard_truth_status?: string;
  registry_alignment_status?: string;
  active_drift_legs?: string[];
  data_source?: string;
  warnings?: string[];
}

interface ProposalResponse {
  data_source?: string;
  warnings?: string[];
  proposals: Proposal[];
}

interface Proposal {
  proposal_id: string;
  phase_id: string;
  phase_name: string;
  failure_prevented?: string;
  signal_improved?: string;
  status: string;
}

function StatusBadge({ value, good, warn }: { value: string; good?: string[]; warn?: string[] }) {
  const isGood = good?.includes(value);
  const isWarn = warn?.includes(value);
  const cls = isGood
    ? 'bg-green-100 text-green-800 border-green-300'
    : isWarn
    ? 'bg-yellow-100 text-yellow-800 border-yellow-300'
    : 'bg-gray-100 text-gray-700 border-gray-300';
  return (
    <span className={`inline-block border rounded px-2 py-0.5 text-xs font-mono ${cls}`}>
      {value}
    </span>
  );
}

function InfoRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between py-1 border-b border-gray-100 last:border-0">
      <span className="text-sm text-gray-500">{label}</span>
      <span className="text-sm font-medium">{value}</span>
    </div>
  );
}

export default function RGEPage() {
  const [roadmap, setRoadmap] = useState<RoadmapRecord | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisRecord | null>(null);
  const [proposalResponse, setProposalResponse] = useState<ProposalResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const [roadmapRes, analysisRes, proposalsRes] = await Promise.all([
          fetch('/api/rge/roadmap'),
          fetch('/api/rge/analysis'),
          fetch('/api/rge/proposals'),
        ]);

        if (!roadmapRes.ok || !analysisRes.ok || !proposalsRes.ok) {
          throw new Error('Failed to fetch RGE data');
        }

        const [roadmapData, analysisData, proposalsData] = await Promise.all([
          roadmapRes.json(),
          analysisRes.json(),
          proposalsRes.json(),
        ]);

        setRoadmap(roadmapData);
        setAnalysis(analysisData);
        setProposalResponse(proposalsData);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  const handleProposeToCandidate = async (proposalId: string) => {
    try {
      const res = await fetch('/api/rge/proposals', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          proposal_id: proposalId,
          decision: 'propose',
          reason: 'Submitted to CDE via dashboard',
        }),
      });

      if (!res.ok) throw new Error('Failed to submit proposal');
      const refreshRes = await fetch('/api/rge/proposals');
      const refreshed = await refreshRes.json();
      setProposalResponse(refreshed);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit proposal');
    }
  };

  if (loading) return <div className="p-8">Loading RGE data...</div>;
  if (error) return <div className="p-8 text-red-600">Error: {error}</div>;

  const maturityLevel = analysis?.context_maturity_level ?? 'unknown';
  const waveStatus = analysis?.wave_status ?? 'unknown';
  const driftLegs = analysis?.active_drift_legs ?? roadmap?.active_drift_legs ?? [];
  const rgeCanOperate = analysis?.rge_can_operate;
  const rgeMaxAutonomy = analysis?.rge_max_autonomy ?? 'unknown';
  const mgKernelStatus = analysis?.mg_kernel_status ?? 'unknown';
  const manualResidue = analysis?.manual_residue_steps ?? 'unknown';
  const dashboardTruth = analysis?.dashboard_truth_status ?? 'unknown';
  const registryAlignment = analysis?.registry_alignment_status ?? 'unknown';

  // Collect all warnings across all three sources
  const allWarnings = [
    ...(analysis?.warnings ?? []),
    ...(roadmap?.warnings ?? []),
    ...(proposalResponse?.warnings ?? []),
  ].filter((w, i, arr) => arr.indexOf(w) === i);

  const proposals = proposalResponse?.proposals ?? [];
  const analysisDataSource = analysis?.data_source ?? 'unknown';
  const isFallback = analysisDataSource === 'stub_fallback';

  return (
    <div className="min-h-screen bg-white p-8">
      <h1 className="text-3xl font-bold mb-2">RGE: Roadmap Generation Engine</h1>
      <p className="text-sm text-gray-500 mb-6">
        Data source:{' '}
        <span className={`font-mono ${isFallback ? 'text-red-600' : 'text-green-700'}`}>
          {analysisDataSource}
        </span>
      </p>

      {allWarnings.length > 0 && (
        <div
          role="alert"
          className="bg-amber-50 border border-amber-400 rounded p-4 mb-6 space-y-1"
        >
          <div className="text-sm font-semibold text-amber-800 mb-1">
            Inference warnings — values marked unknown are unavailable from artifacts:
          </div>
          {allWarnings.map((w, i) => (
            <div key={i} className="text-xs text-amber-700 font-mono">
              {w}
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <div className="border border-gray-300 p-4 rounded">
          <div className="text-xs text-gray-500 mb-1">Operational</div>
          <div className="text-lg font-semibold">
            {rgeCanOperate === undefined ? (
              <span className="text-gray-400">unknown</span>
            ) : rgeCanOperate ? (
              <span className="text-green-700">CAN OPERATE</span>
            ) : (
              <span className="text-red-600">BLOCKED</span>
            )}
          </div>
        </div>
        <div className="border border-gray-300 p-4 rounded">
          <div className="text-xs text-gray-500 mb-1">Trust Mode</div>
          <div className="text-lg font-semibold">
            {String(rgeMaxAutonomy).replace(/_/g, '-').toUpperCase()}
          </div>
        </div>
        <div className="border border-gray-300 p-4 rounded">
          <div className="text-xs text-gray-500 mb-1">Context Maturity</div>
          <div className="text-lg font-semibold">
            {maturityLevel === 'unknown' ? (
              <span className="text-gray-400">unknown</span>
            ) : (
              `${maturityLevel}/10`
            )}
          </div>
        </div>
        <div className="border border-gray-300 p-4 rounded">
          <div className="text-xs text-gray-500 mb-1">Wave Status</div>
          <div className="text-lg font-semibold">
            {waveStatus === 'unknown' ? (
              <span className="text-gray-400">unknown</span>
            ) : (
              `Wave ${waveStatus}`
            )}
          </div>
        </div>
      </div>

      <div className="border border-gray-200 rounded p-4 mb-8">
        <h2 className="text-lg font-semibold mb-3">Governance Signals</h2>
        <InfoRow
          label="MG-KERNEL status"
          value={
            <StatusBadge
              value={String(mgKernelStatus)}
              good={['pass']}
              warn={['fail', 'unknown']}
            />
          }
        />
        <InfoRow
          label="Manual residue steps"
          value={
            manualResidue === 'unknown' ? (
              <span className="text-gray-400 text-xs">unknown</span>
            ) : (
              <span className={manualResidue > 0 ? 'text-amber-700' : 'text-green-700'}>
                {String(manualResidue)}
              </span>
            )
          }
        />
        <InfoRow
          label="Dashboard truth"
          value={
            <StatusBadge
              value={String(dashboardTruth)}
              good={['verified']}
              warn={['unverified', 'unknown']}
            />
          }
        />
        <InfoRow
          label="Registry alignment"
          value={
            <StatusBadge
              value={String(registryAlignment)}
              good={['aligned']}
              warn={['misaligned', 'unknown']}
            />
          }
        />
      </div>

      {driftLegs.length > 0 && (
        <div className="bg-yellow-50 border border-yellow-300 p-4 rounded mb-8">
          <div className="text-sm font-semibold">Active Drift Legs</div>
          <div className="mt-2 flex gap-2">
            {driftLegs.map((leg) => (
              <span key={leg} className="inline-block bg-yellow-200 px-3 py-1 rounded text-sm">
                {leg}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="mb-8">
        <h2 className="text-2xl font-bold mb-4">Entropy Vectors</h2>
        {Object.keys(analysis?.entropy_vectors ?? {}).length === 0 ? (
          <div className="text-sm text-gray-400">Entropy vectors unavailable (no artifact source).</div>
        ) : (
          <div className="grid grid-cols-2 gap-4">
            {Object.entries(analysis?.entropy_vectors ?? {}).map(([vector, status]) => (
              <div
                key={vector}
                className={`p-3 rounded border ${
                  status === 'clean'
                    ? 'bg-green-50 border-green-300'
                    : status === 'warn'
                    ? 'bg-yellow-50 border-yellow-300'
                    : 'bg-red-50 border-red-300'
                }`}
              >
                <div className="font-semibold text-sm">{vector.replace(/_/g, ' ')}</div>
                <div className="text-xs mt-1 capitalize">{status}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {roadmap?.top_risks && roadmap.top_risks.length > 0 && (
        <div className="mb-8">
          <h2 className="text-xl font-bold mb-3">Top Roadmap Risks</h2>
          <ul className="space-y-2">
            {roadmap.top_risks.map((risk, i) => (
              <li key={i} className="text-sm text-red-700 bg-red-50 border border-red-200 rounded p-2">
                {risk}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="mb-8">
        <h2 className="text-2xl font-bold mb-4">Proposals Awaiting CDE</h2>
        {proposals.length === 0 ? (
          <div className="text-gray-500">No pending proposals</div>
        ) : (
          <div className="space-y-4">
            {proposals.map((proposal) => (
              <div key={proposal.proposal_id} className="border border-gray-300 p-4 rounded">
                <div className="font-semibold">{proposal.phase_name}</div>
                {proposal.failure_prevented && (
                  <div className="text-xs text-gray-500 mt-1">
                    Failure prevented: {proposal.failure_prevented}
                  </div>
                )}
                <div className="text-sm text-gray-600 mt-2">
                  ID: {proposal.phase_id} | Status: {proposal.status}
                </div>
                <button
                  onClick={() => handleProposeToCandidate(proposal.proposal_id)}
                  className="mt-3 bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
                >
                  Propose to CDE
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="text-xs text-gray-500 border-t border-gray-100 pt-4">
        Dashboard shows artifact-backed data when available; fallback data is labeled. All
        proposals must be submitted to CDE for decision.
      </div>
    </div>
  );
}
