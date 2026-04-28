// D3L-REGISTRY-01 — Explain System State API.
//
// Builds the deterministic explanation server-side so the same inputs
// produce the same output. Snapshot tests pin the contract.

import { NextResponse } from 'next/server';
import { loadPriorityArtifact } from '@/lib/artifactLoader';
import { buildSystemGraphPayload } from '@/lib/systemGraphBuilder';
import { loadRegistryContract } from '@/lib/registryContract';
import { explainSystemState } from '@/lib/explainSystemState';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET() {
  const graph = buildSystemGraphPayload();
  const priority = loadPriorityArtifact();
  const contract = loadRegistryContract();
  const result = explainSystemState({ graph, priority, contract });
  return NextResponse.json(result, { status: 200 });
}
