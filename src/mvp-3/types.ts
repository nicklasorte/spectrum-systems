/**
 * Type definitions for MVP-3: Transcript Eval Baseline
 */

export interface EvalCase {
  case_id: string;
  name: string;
  description: string;
  check: (transcript: any, contextBundle: any) => boolean;
}

export interface EvalResult {
  artifact_kind: "eval_result";
  artifact_id: string;
  created_at: string;
  schema_ref: string;
  trace: { trace_id: string; created_at: string };
  eval_case_id: string;
  target_artifact_id: string;
  status: "pass" | "fail";
  score: number;
  details?: Record<string, unknown>;
  error?: string;
}

export interface EvalSummary {
  artifact_kind: "eval_summary";
  artifact_id: string;
  created_at: string;
  schema_ref: string;
  trace: { trace_id: string; created_at: string };
  target_artifact_id: string;
  eval_case_ids: string[];
  overall_status: "pass" | "fail";
  pass_rate: number;
  metrics: { total_cases: number; passed: number; failed: number };
}

export interface ControlDecision {
  artifact_kind: "evaluation_control_decision";
  artifact_id: string;
  created_at: string;
  schema_ref: string;
  trace: { trace_id: string; created_at: string };
  decision: "allow" | "block";
  rationale: string;
  eval_summary_id: string;
}

export interface IngestionEvalGateResult {
  success: boolean;
  eval_results?: EvalResult[];
  eval_summary?: EvalSummary;
  control_decision?: ControlDecision;
  execution_record?: any;
  error?: string;
}
