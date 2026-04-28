// D3L-01 — TLS-04 priority report API.
//
// This route ONLY returns the artifact loader result. The dashboard MUST NOT
// compute ranking, so we never re-rank, re-score, or re-classify here.
//
// D3L-MASTER-01 Phase 1: also returns the freshness gate so the dashboard
// can show the fail-closed banner with the exact recompute command when
// the artifact is missing / stale / non-registry-aligned.

import { NextResponse } from 'next/server';
import { evaluatePriorityFreshnessGate } from '@/lib/artifactLoader';

export const dynamic = 'force-dynamic';

export async function GET() {
  const gate = evaluatePriorityFreshnessGate();
  // Keep backward compatibility: top-level fields mirror the loader result
  // so existing consumers reading `state` / `payload` / `recompute_command`
  // continue to work, while the new `freshness_gate` block adds the
  // registry-universe check.
  const body = {
    ...gate.loader,
    freshness_gate: {
      status: gate.status,
      ok: gate.ok,
      ranking_universe_size: gate.ranking_universe_size,
      non_active_in_top_5: gate.non_active_in_top_5,
      non_active_in_global: gate.non_active_in_global,
      blocking_reasons: gate.blocking_reasons,
      recompute_command: gate.recompute_command,
      source_contract_artifact: gate.source_contract_artifact,
    },
  };
  return NextResponse.json(body);
}
