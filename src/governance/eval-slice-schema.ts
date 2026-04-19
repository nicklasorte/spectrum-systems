import { v4 as uuidv4 } from "uuid";

/**
 * Slice-Based Eval Schema
 * Break evals into dimensional slices (issue type, priority, section, etc.)
 * Track per-slice pass rates for fine-grained observability
 */

export interface EvalSlice {
  slice_id: string;
  slice_name: string;
  dimensions: Record<string, string | string[]>;
  description: string;
  created_at: string;
}

export interface SliceEvalResult {
  artifact_kind: "slice_eval_result";
  artifact_id: string;
  eval_case_id: string;
  slice_id: string;
  status: "pass" | "fail" | "indeterminate";
  score: number;
  artifact_target_id: string;
  created_at: string;
  trace_id: string;
}

export interface SliceEvalSummary {
  artifact_kind: "slice_eval_summary";
  artifact_id: string;
  eval_case_name: string;
  all_slices: EvalSlice[];
  per_slice_results: {
    slice_id: string;
    total_cases: number;
    passed: number;
    failed: number;
    indeterminate: number;
    pass_rate: number;
    coverage_status: "good" | "thin" | "unmeasured";
  }[];
  overall_pass_rate: number;
  critical_slice_gaps: string[];
  created_at: string;
}

export const DEFAULT_EVAL_SLICES: EvalSlice[] = [
  {
    slice_id: uuidv4(),
    slice_name: "by_issue_type_finding",
    dimensions: { issue_type: "finding" },
    description: "Evals on issues classified as findings",
    created_at: new Date().toISOString(),
  },
  {
    slice_id: uuidv4(),
    slice_name: "by_issue_type_action",
    dimensions: { issue_type: "action_item" },
    description: "Evals on issues classified as action items",
    created_at: new Date().toISOString(),
  },
  {
    slice_id: uuidv4(),
    slice_name: "by_priority_high",
    dimensions: { priority: "high" },
    description: "Evals on high-priority issues",
    created_at: new Date().toISOString(),
  },
  {
    slice_id: uuidv4(),
    slice_name: "by_priority_medium",
    dimensions: { priority: "medium" },
    description: "Evals on medium-priority issues",
    created_at: new Date().toISOString(),
  },
  {
    slice_id: uuidv4(),
    slice_name: "by_section_findings",
    dimensions: { paper_section: "findings" },
    description: "Evals on findings section",
    created_at: new Date().toISOString(),
  },
  {
    slice_id: uuidv4(),
    slice_name: "by_section_recommendations",
    dimensions: { paper_section: "recommendations" },
    description: "Evals on recommendations section",
    created_at: new Date().toISOString(),
  },
];
