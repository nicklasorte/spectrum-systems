import { NextRequest, NextResponse } from 'next/server';
import { ArtifactStoreClient } from '@/lib/artifact-client';

const client = new ArtifactStoreClient(
  process.env.ARTIFACT_API_URL || 'http://localhost:3001'
);

export async function GET(request: NextRequest) {
  try {
    const snapshot = await client.getEntropySnapshot();

    return NextResponse.json(snapshot, {
      headers: {
        'Cache-Control': 'public, max-age=5, stale-while-revalidate=10',
      },
    });
  } catch (error) {
    console.error('Failed to fetch entropy snapshot:', error);
    return NextResponse.json(
      {
        error: 'Failed to fetch entropy snapshot',
        fallback: true,
        timestamp: new Date().toISOString(),
      },
      { status: 503 }
    );
  }
}
