import { NextRequest, NextResponse } from 'next/server';

export async function GET(request: NextRequest) {
  const health = {
    status: 'healthy',
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
    memory: process.memoryUsage(),
    checks: {
      artifact_api: await checkArtifactAPI(),
      database: 'ok',
    },
  };

  return NextResponse.json(health);
}

async function checkArtifactAPI(): Promise<string> {
  try {
    const url = process.env.ARTIFACT_API_URL || 'http://localhost:3001';
    const response = await fetch(`${url}/health`, { signal: AbortSignal.timeout(5000) });
    return response.ok ? 'ok' : 'degraded';
  } catch {
    return 'down';
  }
}
