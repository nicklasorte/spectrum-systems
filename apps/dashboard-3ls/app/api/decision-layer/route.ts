// D3L-REGISTRY-01 — Decision Layer API.
//
// Returns the registry-filtered Signal → Evaluation → Policy → Control →
// Enforcement projection used by the Decision Layer view.

import { NextResponse } from 'next/server';
import { loadRegistryContract } from '@/lib/registryContract';
import { filterDecisionLayersByRegistry } from '@/lib/decisionLayer';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET() {
  const contract = loadRegistryContract();
  const groups = filterDecisionLayersByRegistry(contract.allowed_active_node_ids);
  return NextResponse.json({ groups, allowed_active_node_ids: contract.allowed_active_node_ids }, { status: 200 });
}
