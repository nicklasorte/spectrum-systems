// D3L-REGISTRY-01 — Registry contract API.
//
// Exposes the parsed registry contract so the dashboard UI can read the
// allowlist of registry-active node ids and reject unknown labels client-side.

import { NextResponse } from 'next/server';
import { loadRegistryContract } from '@/lib/registryContract';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET() {
  const contract = loadRegistryContract();
  return NextResponse.json(contract, { status: 200 });
}
