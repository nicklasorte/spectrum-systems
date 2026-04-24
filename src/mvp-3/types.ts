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
  artifact_type: "eval_result";
  schema_version: "1.0.0";
  eval_case_id: string;
  run_id: string;
  trace_id: string;
  result_status: "pass" | "fail" | "indeterminate";
  score: number;
  failure_modes: string[];
  provenance_refs: string[];
}

export interface EvalSummary {
  artifact_type: "eval_summary";
  schema_version: "1.0.0";
  artifact_id: string;
  created_at: string;
  trace: { trace_id: string; created_at: string };
  target_artifact_id: string;
  eval_case_ids: string[];
  overall_status: "pass" | "fail";
  pass_rate: number;
  metrics: { total_cases: number; passed: number; failed: number };
}

export interface ControlDecision {
  artifact_type: "evaluation_control_decision";
  schema_version: "1.2.0";
  decision_id: string;
  eval_run_id: string;
  system_status: "healthy" | "warning" | "exhausted" | "blocked";
  system_response: "allow" | "warn" | "freeze" | "block";
  triggered_signals: string[];
  threshold_snapshot: {
    reliability_threshold: number;
    drift_threshold: number;
    trust_threshold: number;
  };
  threshold_context: "active_runtime" | "comparative_analysis";
  trace_id: string;
  created_at: string;
  decision: "allow" | "deny" | "require_review";
  rationale_code: string;
  input_signal_reference: {
    signal_type: "eval_summary" | "failure_eval_case";
    source_artifact_id: string;
  };
  run_id: string;
}

export interface IngestionEvalGateResult {
  success: boolean;
  eval_results?: EvalResult[];
  eval_summary?: EvalSummary;
  control_decision?: ControlDecision;
  execution_record?: any;
  error?: string;
}
