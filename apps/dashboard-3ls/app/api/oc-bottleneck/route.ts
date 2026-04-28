// D3L-DATA-REGISTRY-01 — OC bottleneck steering API.
//
// Returns the OC bottleneck card or a fail-closed unavailable / invalid /
// stale_proof / conflict_proof / ambiguous response. The dashboard never
// fabricates a bottleneck: when OC-ALL-01 artifacts are not present this
// route surfaces 'unavailable' so the operator knows the OC layer has
// not been wired in yet.

import { NextResponse } from 'next/server';
import { loadOcBottleneck } from '@/lib/ocBottleneck';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET() {
  return NextResponse.json(loadOcBottleneck(), { status: 200 });
}
