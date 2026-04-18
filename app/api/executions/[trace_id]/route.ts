import { NextRequest, NextResponse } from 'next/server';
import { createArtifactStore, MemoryStorageBackend } from '@/src/artifact-store';
import type { TraceDetail, TraceStep } from '@/components/dashboard/types';

// Initialize artifact store
const backend = new MemoryStorageBackend();
const artifactStore = createArtifactStore(backend);

interface RouteParams {
  params: {
    trace_id: string;
  };
}

export async function GET(
  request: NextRequest,
  { params }: RouteParams
) {
  const trace_id = params.trace_id;

  try {
    // Fetch the pqx_execution_record artifact
    const executionRecord = await artifactStore.retrieve(trace_id);

    if (!executionRecord) {
      return NextResponse.json(
        { error: `Execution not found: ${trace_id}` },
        { status: 404 }
      );
    }

    const payload = executionRecord.payload as any;
    const pqxStep = payload.pqx_step || {};
    const failure = payload.failure;

    // Build trace steps from execution record
    // In a full implementation, would fetch intermediate artifacts
    const steps: TraceStep[] = [];

    // Step 1: Context Bundle (if inputs exist)
    if (payload.inputs?.artifact_ids?.length > 0) {
      steps.push({
        artifact_id: payload.inputs.artifact_ids[0],
        status: 'PASS',
      });
    }

    // Step 2: Agent Execution (if execution started)
    if (payload.execution_status !== 'queued') {
      steps.push({
        artifact_id:
          payload.outputs?.artifact_ids?.[0] || `executing-${trace_id}`,
        status:
          payload.execution_status === 'succeeded' ||
          payload.execution_status === 'running'
            ? 'PASS'
            : 'FAIL',
        error: failure?.error_message,
      });
    }

    // Step 3: Eval Gate (if outputs exist)
    if (payload.outputs?.artifact_ids?.length > 0) {
      steps.push({
        artifact_id: `eval-${trace_id}`,
        status: 'PASS',
      });
    }

    // Determine control decision
    const controlDecision = {
      decision: (
        payload.execution_status === 'succeeded' ? 'ALLOW' : 'BLOCK'
      ) as 'ALLOW' | 'BLOCK',
      reason:
        payload.execution_status === 'succeeded'
          ? 'all_evals_pass → promote'
          : failure?.reason_codes?.[0] || 'execution_failed',
    };

    const traceDetail: TraceDetail = {
      trace_id,
      steps,
      control_decision: controlDecision,
    };

    return NextResponse.json(traceDetail);
  } catch (error) {
    console.error('Error fetching trace:', error);
    return NextResponse.json(
      { error: 'Failed to fetch trace details' },
      { status: 500 }
    );
  }
}
