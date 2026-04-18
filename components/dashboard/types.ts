export type ExecutionStatus = 'PASS' | 'FAIL' | 'RUN' | 'PENDING' | 'BLOCK' | 'ALLOW';

export interface TraceStep {
  artifact_id: string;
  status: ExecutionStatus;
  error?: string;
}

export interface TraceDetail {
  trace_id: string;
  steps: TraceStep[];
  control_decision: {
    decision: 'ALLOW' | 'BLOCK';
    reason: string;
  };
}

export interface Execution {
  trace_id: string;
  phase: string;
  status: ExecutionStatus;
  created_at: string;
  control_decision: 'ALLOW' | 'BLOCK' | null;
}

export interface PipelineMetrics {
  total_runs: number;
  passed: number;
  failed: number;
  in_progress: number;
}
