import { NextRequest, NextResponse } from 'next/server';

export async function GET(request: NextRequest) {
  try {
    const artifactApiUrl = process.env.ARTIFACT_API_URL || 'http://localhost:3001';

    const response = await fetch(`${artifactApiUrl}/api/entropy/latest-snapshot`, {
      cache: 'no-store',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Artifact API returned ${response.status}`);
    }

    const data = await response.json();

    return NextResponse.json(data, {
      headers: {
        'Cache-Control': 'public, max-age=5, stale-while-revalidate=10',
      },
    });
  } catch (error) {
    console.error('Failed to fetch entropy snapshot:', error);
    return NextResponse.json(
      { error: 'Failed to fetch entropy snapshot' },
      { status: 500 }
    );
  }
}
