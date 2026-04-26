// D3L-01 — TLS-04 priority report API.
//
// This route ONLY returns the artifact loader result. The dashboard MUST NOT
// compute ranking, so we never re-rank, re-score, or re-classify here.

import { NextResponse } from 'next/server';
import { loadPriorityArtifact } from '@/lib/artifactLoader';

export const dynamic = 'force-dynamic';

export async function GET() {
  const result = loadPriorityArtifact();
  return NextResponse.json(result);
}
