'use client';

import React, { useEffect, useState } from 'react';

interface RoadmapRecord {
  record_id: string;
  admitted_count: number;
  blocked_count: number;
  active_drift_legs: string[];
}

interface AnalysisRecord {
  context_maturity_level: number;
  entropy_vectors: Record<string, string>;
}

interface Proposal {
  proposal_id: string;
  phase_id: string;
  phase_name: string;
  status: string;
}

export default function RGEPage() {
  const [roadmap, setRoadmap] = useState<RoadmapRecord | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisRecord | null>(null);
  const [proposals, setProposals] = useState<Proposal[]>([]);
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
        setProposals(proposalsData);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  const handleApproveProposal = async (proposalId: string) => {
    try {
      const res = await fetch('/api/rge/proposals', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          proposal_id: proposalId,
          decision: 'approve',
          reason: 'CDE approved via dashboard',
        }),
      });

      if (!res.ok) throw new Error('Failed to record approval');
      const updatedRes = await fetch('/api/rge/proposals');
      const updatedProposals = await updatedRes.json();
      setProposals(updatedProposals);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to approve');
    }
  };

  if (loading) return <div className="p-8">Loading RGE data...</div>;
  if (error) return <div className="p-8 text-red-600">Error: {error}</div>;

  const maturityLevel = analysis?.context_maturity_level || 0;
  const admittedCount = roadmap?.admitted_count || 0;
  const blockedCount = roadmap?.blocked_count || 0;
  const driftLegs = roadmap?.active_drift_legs || [];

  return (
    <div className="min-h-screen bg-white p-8">
      <h1 className="text-3xl font-bold mb-8">RGE: Roadmap Generation Engine</h1>

      <div className="grid grid-cols-4 gap-4 mb-8">
        <div className="border border-gray-300 p-4 rounded">
          <div className="text-sm text-gray-600">Trust Mode</div>
          <div className="text-lg font-semibold">WARN-GATED</div>
        </div>
        <div className="border border-gray-300 p-4 rounded">
          <div className="text-sm text-gray-600">Context Maturity</div>
          <div className="text-lg font-semibold">{maturityLevel}/10</div>
        </div>
        <div className="border border-gray-300 p-4 rounded">
          <div className="text-sm text-gray-600">Admitted Phases</div>
          <div className="text-lg font-semibold text-green-600">{admittedCount}</div>
        </div>
        <div className="border border-gray-300 p-4 rounded">
          <div className="text-sm text-gray-600">Blocked Phases</div>
          <div className="text-lg font-semibold text-red-600">{blockedCount}</div>
        </div>
      </div>

      {driftLegs.length > 0 && (
        <div className="bg-yellow-50 border border-yellow-300 p-4 rounded mb-8">
          <div className="text-sm font-semibold">Active Drift Legs</div>
          <div className="mt-2 flex gap-2">
            {driftLegs.map((leg) => (
              <span
                key={leg}
                className="inline-block bg-yellow-200 px-3 py-1 rounded text-sm"
              >
                {leg}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="mb-8">
        <h2 className="text-2xl font-bold mb-4">Entropy Vectors</h2>
        <div className="grid grid-cols-2 gap-4">
          {Object.entries(analysis?.entropy_vectors || {}).map(([vector, status]) => (
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
      </div>

      <div className="mb-8">
        <h2 className="text-2xl font-bold mb-4">Proposals Awaiting CDE</h2>
        {proposals.length === 0 ? (
          <div className="text-gray-500">No pending proposals</div>
        ) : (
          <div className="space-y-4">
            {proposals.map((proposal) => (
              <div
                key={proposal.proposal_id}
                className="border border-gray-300 p-4 rounded"
              >
                <div className="font-semibold">{proposal.phase_name}</div>
                <div className="text-sm text-gray-600 mt-2">
                  ID: {proposal.phase_id} | Status: {proposal.status}
                </div>
                <button
                  onClick={() => handleApproveProposal(proposal.proposal_id)}
                  className="mt-3 bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
                >
                  Propose to CDE
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="text-xs text-gray-500">
        Dashboard shows real data from RGE backend APIs. All proposals must be approved by CDE.
      </div>
    </div>
  );
}
