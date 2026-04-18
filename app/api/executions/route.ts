import { NextRequest, NextResponse } from 'next/server';
import { Execution } from '@/components/dashboard/types';

// TODO: Integrate with artifact store
// Steps to implement:
// 1. Query artifact store for pqx_execution_record artifacts
// 2. Filter by created_at DESC to get recent executions
// 3. Apply pagination with limit and offset
// 4. Extract these fields from artifact payload:
//    - trace_id: from artifact metadata or payload
//    - phase: execution phase (e.g., "RIL", "CDE", "TLC", "PQX", "FRE", "SEL")
//    - status: from execution result (PASS, FAIL, RUN, PENDING, BLOCK, ALLOW)
//    - created_at: ISO timestamp of execution
//    - control_decision: extracted from control_decision artifact (ALLOW or BLOCK)
//
// Example response structure:
// {
//   "executions": [
//     {
//       "trace_id": "trace-abc123def456",
//       "phase": "PQX",
//       "status": "PASS",
//       "created_at": "2026-04-18T10:30:00Z",
//       "control_decision": "ALLOW"
//     },
//     {
//       "trace_id": "trace-xyz789uvw012",
//       "phase": "CDE",
//       "status": "FAIL",
//       "created_at": "2026-04-18T10:25:00Z",
//       "control_decision": "BLOCK"
//     }
//   ]
// }

const MOCK_EXECUTIONS: Execution[] = [
  {
    trace_id: 'trace-abc123def456',
    phase: 'PQX',
    status: 'PASS',
    created_at: '2026-04-18T10:30:00Z',
    control_decision: 'ALLOW',
  },
  {
    trace_id: 'trace-xyz789uvw012',
    phase: 'CDE',
    status: 'FAIL',
    created_at: '2026-04-18T10:25:00Z',
    control_decision: 'BLOCK',
  },
  {
    trace_id: 'trace-ghi345jkl678',
    phase: 'TLC',
    status: 'RUN',
    created_at: '2026-04-18T10:20:00Z',
    control_decision: null,
  },
  {
    trace_id: 'trace-mno567pqr890',
    phase: 'FRE',
    status: 'PASS',
    created_at: '2026-04-18T10:15:00Z',
    control_decision: 'ALLOW',
  },
  {
    trace_id: 'trace-stu901vwx234',
    phase: 'RIL',
    status: 'PENDING',
    created_at: '2026-04-18T10:10:00Z',
    control_decision: null,
  },
];

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const limit = parseInt(searchParams.get('limit') ?? '20', 10);
  const offset = parseInt(searchParams.get('offset') ?? '0', 10);

  // Apply pagination to mock data
  const paginatedExecutions = MOCK_EXECUTIONS.slice(
    offset,
    offset + limit
  );

  return NextResponse.json({
    executions: paginatedExecutions,
  });
}
