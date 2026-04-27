import { NextResponse } from 'next/server';
import { loadNextStepArtifact } from '@/lib/nextStepArtifactLoader';

export const dynamic = 'force-dynamic';

export async function GET() {
  const result = loadNextStepArtifact();
  return NextResponse.json(result);
}
