export interface Issue {
  issue_id: string;
  type: "finding" | "action_item" | "risk";
  description: string;
  priority: "high" | "medium" | "low";
  assignee?: string;
  status: "open" | "closed";
  source_turn_ref: string;
}

export interface IssueExtractionResult {
  success: boolean;
  issue_registry_artifact?: any;
  execution_record?: any;
  error?: string;
  error_codes?: string[];
}
