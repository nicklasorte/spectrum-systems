// Auto-generated TypeScript types from JSON schemas
// Single source of truth for all artifact types

export type UUID = string;
export type ISODatetime = string;
export type SHA256Prefixed = string;

export type ReasonCode =
  | "schema_violation"
  | "missing_artifact"
  | "policy_block"
  | "timeout"
  | "eval_failure"
  | "control_block";

export type ExecutionStatus = "queued" | "running" | "succeeded" | "failed" | "canceled";
export type EvalStatus = "pass" | "fail" | "indeterminate";
export type ControlDecision = "allow" | "block" | "freeze_pipeline";

export interface TraceContext {
  trace_id: UUID;
  parent_trace_id?: UUID;
  created_at: ISODatetime;
}

export interface TranscriptArtifact {
  artifact_kind: "transcript_artifact";
  artifact_id: UUID;
  created_at: ISODatetime;
  schema_ref: string;
  trace: TraceContext;
  content: string;
  metadata: {
    speaker_labels: string[];
    duration_minutes: number;
    language: string;
    source_file: string;
  };
  content_hash: SHA256Prefixed;
}

export interface ContextBundle {
  artifact_kind: "context_bundle";
  artifact_id: UUID;
  created_at: ISODatetime;
  schema_ref: string;
  trace: TraceContext;
  input_artifacts: UUID[];
  context: {
    transcript_id: UUID;
    task_description: string;
    instructions: string;
    prior_outputs?: Record<string, unknown>[];
  };
  content_hash: SHA256Prefixed;
}

export interface AgentExecutionTrace {
  artifact_kind: "agent_execution_trace";
  artifact_id: UUID;
  created_at: ISODatetime;
  schema_ref: string;
  trace: TraceContext;
  context_bundle_id: UUID;
  agent_name: string;
  steps: Array<{
    step_number: number;
    description: string;
    status: "running" | "succeeded" | "failed";
    output?: Record<string, unknown>;
    error?: string;
  }>;
  final_output: Record<string, unknown>;
  model_used: string;
  total_duration_ms: number;
  random_seed: number;
}

export interface EvalCase {
  artifact_kind: "eval_case";
  artifact_id: UUID;
  created_at: ISODatetime;
  schema_ref: string;
  trace: TraceContext;
  eval_type: string;
  target_artifact_kind: string;
  description: string;
  input_artifact_refs: UUID[];
  expected_output: Record<string, unknown>;
  success_criteria: string[];
}

export interface EvalResult {
  artifact_kind: "eval_result";
  artifact_id: UUID;
  created_at: ISODatetime;
  schema_ref: string;
  trace: TraceContext;
  eval_case_id: UUID;
  target_artifact_id: UUID;
  status: EvalStatus;
  score: number;
  details: Record<string, unknown>;
  error?: string;
}

export interface EvalSummary {
  artifact_kind: "eval_summary";
  artifact_id: UUID;
  created_at: ISODatetime;
  schema_ref: string;
  trace: TraceContext;
  target_artifact_id: UUID;
  eval_case_ids: UUID[];
  eval_result_ids: UUID[];
  overall_status: EvalStatus;
  pass_rate: number;
  metrics: Record<string, unknown>;
}

export interface ControlDecisionArtifact {
  artifact_kind: "control_decision";
  artifact_id: UUID;
  created_at: ISODatetime;
  schema_ref: string;
  trace: TraceContext;
  eval_summary_id: UUID;
  policy_applied: string;
  decision: ControlDecision;
  rationale: string;
  next_step: string;
  blocks_until?: ISODatetime;
}

export interface PQXExecutionRecord {
  artifact_kind: "pqx_execution_record";
  artifact_id: UUID;
  created_at: ISODatetime;
  schema_ref: string;
  trace: TraceContext;
  pqx_step: {
    name: string;
    version: string;
  };
  execution_status: ExecutionStatus;
  inputs: {
    artifact_ids: UUID[];
  };
  outputs: {
    artifact_ids: UUID[];
  };
  timing: {
    started_at: ISODatetime;
    ended_at?: ISODatetime;
  };
  failure?: {
    reason_codes: ReasonCode[];
    error_message: string;
  };
}

export interface FailureArtifact {
  artifact_kind: "failure_artifact";
  artifact_id: UUID;
  created_at: ISODatetime;
  schema_ref: string;
  trace: TraceContext;
  failed_step: string;
  reason_codes: ReasonCode[];
  error_message: string;
  input_artifact_id: UUID;
  recovery_suggested?: string;
}

export type AnyArtifact =
  | TranscriptArtifact
  | ContextBundle
  | AgentExecutionTrace
  | EvalCase
  | EvalResult
  | EvalSummary
  | ControlDecisionArtifact
  | PQXExecutionRecord
  | FailureArtifact;
