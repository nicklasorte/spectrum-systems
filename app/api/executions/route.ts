import { NextRequest, NextResponse } from 'next/server';
import { createArtifactStore, MemoryStorageBackend } from '@/src/artifact-store';
import type { Execution, PipelineMetrics } from '@/components/dashboard/types';

// Initialize artifact store (TODO: use persistent backend in production)
const backend = new MemoryStorageBackend();
const artifactStore = createArtifactStore(backend);

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const limit = parseInt(searchParams.get('limit') ?? '20', 10);
  const offset = parseInt(searchParams.get('offset') ?? '0', 10);

  try {
    // Query pqx_execution_record artifacts from store
    // These represent pipeline step executions
    const executionRecords = await artifactStore.query({
      artifactKind: 'pqx_execution_record',
      limit: limit + 10, // Fetch extra to filter/sort
      offset,
    });

    // Transform stored artifacts into dashboard Execution format
    const executions: Execution[] = executionRecords
      .map((record) => {
        const payload = record.payload as any;
        const pqxStep = payload.pqx_step || {};
        const timing = payload.timing || {};
        const failure = payload.failure;

        // Determine status
        let status: 'PASS' | 'FAIL' | 'RUN' | 'PENDING' | 'BLOCK' | 'ALLOW' = 'RUN';
        if (payload.execution_status === 'succeeded') {
          status = 'PASS';
        } else if (payload.execution_status === 'failed') {
          status = 'FAIL';
        } else if (payload.execution_status === 'queued') {
          status = 'PENDING';
        }

        // Extract phase from step name (e.g., "MVP-1: Transcript Ingestion" → "Transcript Ingestion")
        const phase = pqxStep.name
          ? pqxStep.name.split(': ')[1] || pqxStep.name
          : 'Unknown';

        // Calculate duration
        const startTime = timing.started_at
          ? new Date(timing.started_at).getTime()
          : 0;
        const endTime = timing.ended_at
          ? new Date(timing.ended_at).getTime()
          : Date.now();
        const durationMs = endTime - startTime;

        // Determine control decision from status
        const controlDecision =
          status === 'PASS' ? ('ALLOW' as const) : status === 'FAIL' ? ('BLOCK' as const) : null;

        return {
          trace_id: record.artifactId,
          phase,
          status,
          created_at: record.createdAt,
          control_decision: controlDecision,
        };
      })
      .slice(0, limit); // Apply limit after transformation

    // Query all records to compute metrics
    const allRecords = await artifactStore.query({
      artifactKind: 'pqx_execution_record',
      limit: 1000, // Get all for metrics
    });

    const metrics: PipelineMetrics = {
      total_runs: allRecords.length,
      passed: allRecords.filter(
        (r) => (r.payload as any).execution_status === 'succeeded'
      ).length,
      failed: allRecords.filter(
        (r) => (r.payload as any).execution_status === 'failed'
      ).length,
      in_progress: allRecords.filter(
        (r) =>
          (r.payload as any).execution_status === 'queued' ||
          (r.payload as any).execution_status === 'running'
      ).length,
    };

    return NextResponse.json({
      executions,
      metrics,
      total: allRecords.length,
    });
  } catch (error) {
    console.error('Error fetching executions:', error);
    return NextResponse.json(
      { error: 'Failed to fetch executions' },
      { status: 500 }
    );
  }
}
