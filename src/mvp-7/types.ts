export interface StructuredIssue {
  issue_id: string;
  type: string;
  description: string;
  spectrum_band: string;
  policy_section: string;
  paper_section_id: string;
  source_turn_ref: string;
}

export interface StructuredIssueSet {
  artifact_type: "structured_issue_set";
  schema_version: "1.0.0";
  artifact_id: string;
  created_at: string;
  schema_ref: string;
  trace: { trace_id: string; created_at: string };
  issues: StructuredIssue[];
  content_hash: string;
}

export interface IssueStructuringResult {
  success: boolean;
  structured_issue_set?: StructuredIssueSet;
  execution_record?: any;
  error?: string;
}
