import { NextRequest, NextResponse } from 'next/server';
import { TraceDetail } from '@/components/dashboard/types';

// TODO: Integrate with artifact store
// Steps to implement:
// 1. Query artifact store for pqx_execution_record with trace_id from path param
// 2. Fetch referenced artifacts:
//    - context_bundle: contains input context and request metadata
//    - agent_trace: contains step-by-step execution trace
//    - eval_results: contains evaluation results for each step
//    - control_decision: contains final control decision and reasoning
// 3. Reconstruct steps array from agent_trace artifact:
//    - Extract artifact_id and status for each execution step
//    - Map eval status (success/failure) to ExecutionStatus enum
// 4. Extract control decision from control_decision artifact:
//    - decision: ALLOW or BLOCK
//    - reason: explanation of decision
//
// Example response structure:
// {
//   "trace_id": "trace-abc123def456",
//   "steps": [
//     {
//       "artifact_id": "artifact-step-1-abc",
//       "status": "PASS",
//       "error": null
//     },
//     {
//       "artifact_id": "artifact-step-2-def",
//       "status": "FAIL",
//       "error": "Constraint violation: unauthorized_access_attempt"
//     },
//     {
//       "artifact_id": "artifact-step-3-ghi",
//       "status": "PASS",
//       "error": null
//     }
//   ],
//   "control_decision": {
//     "decision": "BLOCK",
//     "reason": "Step 2 failed constraint validation; blocking execution"
//   }
// }

const MOCK_TRACES: Record<string, TraceDetail> = {
  'trace-abc123def456': {
    trace_id: 'trace-abc123def456',
    steps: [
      {
        artifact_id: 'artifact-ril-a1b2c3d4',
        status: 'PASS',
      },
      {
        artifact_id: 'artifact-cde-e5f6g7h8',
        status: 'PASS',
      },
      {
        artifact_id: 'artifact-tlc-i9j0k1l2',
        status: 'PASS',
      },
    ],
    control_decision: {
      decision: 'ALLOW',
      reason: 'All validation checks passed; execution permitted',
    },
  },
  'trace-xyz789uvw012': {
    trace_id: 'trace-xyz789uvw012',
    steps: [
      {
        artifact_id: 'artifact-ril-m3n4o5p6',
        status: 'PASS',
      },
      {
        artifact_id: 'artifact-cde-q7r8s9t0',
        status: 'FAIL',
        error: 'Authorization check failed: insufficient permissions',
      },
    ],
    control_decision: {
      decision: 'BLOCK',
      reason: 'Authorization constraint violated at CDE phase',
    },
  },
};

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

  const trace = MOCK_TRACES[trace_id];
  if (!trace) {
    return NextResponse.json(
      { error: 'Trace not found' },
      { status: 404 }
    );
  }

  return NextResponse.json(trace);
}
