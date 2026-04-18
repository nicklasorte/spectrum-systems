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
  artifact_kind: "structured_issue_set";
  artifact_id: string;
  issues: StructuredIssue[];
  content_hash: string;
}

export interface IssueStructuringResult {
  success: boolean;
  structured_issue_set?: StructuredIssueSet;
  execution_record?: any;
  error?: string;
}
