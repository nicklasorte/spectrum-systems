import { NextRequest, NextResponse } from 'next/server';

export async function GET(request: NextRequest) {
  try {
    const days = request.nextUrl.searchParams.get('days') || '30';
    const limit = request.nextUrl.searchParams.get('limit') || '10';

    const artifactApiUrl = process.env.ARTIFACT_API_URL || 'http://localhost:3001';

    const response = await fetch(
      `${artifactApiUrl}/api/queries/reason-codes?days=${days}&limit=${limit}`,
      {
        cache: 'no-store',
        headers: { 'Content-Type': 'application/json' },
      }
    );

    if (!response.ok) {
      throw new Error(`Query failed: ${response.status}`);
    }

    const data = await response.json();

    return NextResponse.json(data, {
      headers: {
        'Cache-Control': 'public, max-age=30, stale-while-revalidate=60',
      },
    });
  } catch (error) {
    console.error('Reason code query failed:', error);
    return NextResponse.json(
      { error: 'Failed to fetch reason codes' },
      { status: 500 }
    );
  }
}
