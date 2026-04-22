import { NextRequest, NextResponse } from 'next/server';
import { ArtifactStoreClient } from '@/lib/artifact-client';

const client = new ArtifactStoreClient(
  process.env.ARTIFACT_API_URL || 'http://localhost:3001'
);

const QUERY_MAP: { [key: string]: string } = {
  'reason-codes': 'top_reason_codes_by_blocks',
  'rising-overrides': 'policies_with_rising_override_rates',
  'cost-increase': 'routes_increasing_cost',
  'context-contradiction': 'context_source_contradiction_correlation',
  'judge-disagreement': 'judge_human_disagreement_drift',
  'failure-patterns': 'top_failure_patterns_by_context_class',
  'incident-drill': 'incident_drill_replay',
  'reviewer-bias': 'reviewer_bias_matrix',
};

export async function GET(
  request: NextRequest,
  { params }: { params: { queryId: string } }
) {
  try {
    const queryId = params.queryId;
    const queryName = QUERY_MAP[queryId];

    if (!queryName) {
      return NextResponse.json(
        { error: `Unknown query: ${queryId}` },
        { status: 400 }
      );
    }

    const searchParams = Object.fromEntries(request.nextUrl.searchParams);
    const result = await client.executeQuery(queryName, searchParams);

    return NextResponse.json(result, {
      headers: {
        'Cache-Control': 'public, max-age=30, stale-while-revalidate=60',
      },
    });
  } catch (error) {
    console.error('Query execution failed:', error);
    return NextResponse.json(
      { error: 'Query execution failed', data: [] },
      { status: 503 }
    );
  }
}
