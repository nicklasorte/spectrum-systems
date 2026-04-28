// D3L-MASTER-01 Phase 4 — maturity table API.
//
// Reads the registry contract + system_evidence_attachment +
// system_trust_gap_report, plus the priority freshness state, and
// returns a maturity report per active system. The dashboard never
// invents rows; if any input is missing the route returns fail-closed
// with explicit blocking_reasons.

import { NextResponse } from 'next/server';
import { loadArtifact, evaluatePriorityFreshnessGate } from '@/lib/artifactLoader';
import { loadD3LRegistryContract } from '@/lib/systemRegistry';
import { computeMaturityReport } from '@/lib/maturity';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

interface RawEvidenceAttachment {
  systems?: Array<{ system_id?: string; has_evidence?: boolean; evidence_count?: number }>;
}

interface RawTrustGap {
  systems?: Array<{ system_id?: string; trust_state?: string; failing_signals?: string[] }>;
}

export async function GET() {
  const contract = loadD3LRegistryContract();
  const evidenceArtifact = loadArtifact<RawEvidenceAttachment>('artifacts/tls/system_evidence_attachment.json');
  const trustArtifact = loadArtifact<RawTrustGap>('artifacts/tls/system_trust_gap_report.json');
  const gate = evaluatePriorityFreshnessGate();

  const evidence = (evidenceArtifact?.systems ?? [])
    .filter((row): row is { system_id: string; has_evidence?: boolean; evidence_count?: number } => typeof row.system_id === 'string')
    .map((row) => ({
      system_id: row.system_id,
      has_evidence: row.has_evidence === true,
      evidence_count: typeof row.evidence_count === 'number' ? row.evidence_count : 0,
    }));
  const trustGap = (trustArtifact?.systems ?? [])
    .filter((row): row is { system_id: string; trust_state?: string; failing_signals?: string[] } => typeof row.system_id === 'string')
    .map((row) => ({
      system_id: row.system_id,
      trust_state: typeof row.trust_state === 'string' ? row.trust_state : 'unknown_signal',
      failing_signals: Array.isArray(row.failing_signals) ? row.failing_signals : [],
    }));

  const report = computeMaturityReport({
    contract,
    evidence,
    trustGap,
    priorityFresh: gate.ok && gate.status === 'ok',
    priorityGeneratedAt: gate.generated_at,
  });

  return NextResponse.json({
    ...report,
    sources: {
      contract: 'artifacts/tls/d3l_registry_contract.json',
      evidence: 'artifacts/tls/system_evidence_attachment.json',
      trust_gap: 'artifacts/tls/system_trust_gap_report.json',
      priority_freshness_gate: gate.status,
    },
  });
}
